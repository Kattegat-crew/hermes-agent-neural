---
name: adversarial-review-gate
description: Use when committing code — AGY reviewer adversarial.
version: 1.0.0
author: Ragnar — NeuralCrew Labs
license: MIT
metadata:
  hermes:
    tags: [code-review, adversarial, gate, agy, calidad, pre-commit]
    related_skills: [requesting-code-review, doubt-driven-development, test-driven-development, orca-fleet-delegate]
---

# Adversarial Review Gate

Ningún agente verifica su propio trabajo. Todo diff de código pasa por un reviewer
hostil e independiente (AGY, contexto limpio) antes de convertirse en commit.

## When to Use

- Antes de cualquier `git commit` / PR en un repo con código.
- Cuando el Admin pide "revisa", "verifica", "ship it" o "¿está bien?" sobre código propio.
- Después de cada tarea en un flujo SDD o de subagentes.
- NO para cambios solo de docs/config sin lógica, ni para renombres mecánicos.

## Regla dura

Antes de `git commit` en cualquier repo con código: **`review-gate`**. Sin excepción.
Si no existe el script, se hace la revisión manual equivalente (AGY con `--json-schema`,
ver abajo) y se registra en el ledger.

## Comando canónico

```bash
/opt/data/fleet/review-gate --repo /opt/<repo> --staged \
  --test-cmd "pytest -q tests/unit" --require-tests
# exit 0 = pasa · exit 2 = bloquea · exit 4 = error de uso
# añadir --json para consumo por máquina
```

Modos: `--staged` (default), `--work`, `--range main..HEAD`. `--force` ignora el cache.

## Pipeline (barato → caro, respétalo)

1. diff + hash sha256 → **idempotencia**: mismo diff = mismo receipt, no se re-paga LLM.
2. si el diff no toca código → skip.
3. escaneo estático de líneas añadidas (secretos, `shell=True`, `os.system`, `eval`, `pickle`,
   SQL por interpolación, `verify=False`, `chmod 777`, `innerHTML`).
4. `--test-cmd` si se pasa: si falla, bloquea **sin gastar tokens**.
5. AGY `--mode plan --json-schema` → `structured_output` validado.
6. receipt en `/opt/data/state/reviews/<repo-slug>/<review_id>.json` + `ledger.jsonl`.

## Loop de corrección (máx 2 ciclos)

BLOQUEA → corriges exactamente lo reportado → releer el diff real → re-gate.
Al 3.º fallo: **escalar a Plon** con los hallazgos restantes. No grindear un 4.º ciclo.

Clasifica cada hallazgo antes de aplicarlo (precedencia de `doubt-driven-development`):
1. **contract misread** — el prompt no dio contexto suficiente: mejora el CONTRATO y re-clasifica.
2. **válido y accionable** — corrige.
3. **trade-off válido** — documéntalo explícitamente, no lo escondas.
4. **ruido** — anótalo y sigue; nunca deferencia ciega al reviewer.

Nunca le pases al reviewer tu conclusión de que está bien: solo ARTIFACT + CONTRACT.

## Review de cierre de sesión (todo el trabajo, fuera del gate por-commit)

El gate por-commit cubre cada diff; el cierre de una sesión de código añade una
segunda pasada sobre TODO lo producido (código, crons, hilos de Discord, Sheet).
El brief y el flujo de resolución viven en `sdlc-review` → modo ad-hoc; aquí lo
operativo:

1. Brief para agy: cada afirmación del implementer va como CLAIM a falsificar
   (nunca como hecho), la lista completa de archivos/commits/crones a auditar,
   y formato de salida obligatorio: `VEREDICTO: APPROVE|REQUEST_CHANGES|ESCALATE`
   + críticos/menores + comandos ejecutados.
2. El reviewer NO edita nada: revisa, el implementer corrige.
3. `REQUEST_CHANGES` bloquea el cierre: cada crítico se resuelve con evidencia
   (comando + salida) antes de pushear y declarar la sesión cerrada.

Pitfalls de la invocación manual de agy:
- Un run largo `-p` lanzado como hijo del árbol del gateway muere con `exit -15`
  si el gateway se reinicia a mitad del review. Lanzarlo desacoplado (terminal
  `background=true`/`setsid`, HOME aislado `/opt/data/fleet/agy-home`) y SIEMPRE
  redirigir la salida a archivo: el veredicto debe sobrevivir aunque muera el
  proceso que lo disparó.
- No recortar los `--add-dir`: si el reviewer no puede leer una fuente (repo,
  esquema real de la API, config de crons, AGENTS.md del repo), audita solo lo
  que ve y los hallazgos salen sesgados a favor del implementer. El valor del
  review frío está justamente en leer el CONTRATO que el implementer asumió.

## Aprendizaje: que el error no vuelva

- Cada hallazgo queda en `/opt/data/state/reviews/ledger.jsonl` con fingerprint.
- Un fingerprint **repetido ≥2 veces** se convierte en check estático dentro de `review-gate`
  (entrada nueva en `STATIC`) **y** en regla en `<repo>/.agents/rules/50-review-lessons.md`.
  Ahí deja de depender de que un LLM lo recuerde: pasa a ser mecánico.
- Las reglas estables se destilan a esta skill (memoria procedimental), no a `MEMORY.md`.

## Pitfalls verificados

- **HOME aislado obligatorio** para AGY: dos instancias con el mismo `HOME` se matan.
  `review-gate` usa `/opt/data/fleet/agy-home-review` + `flock`, no clones por invocación.
- **`--json-schema` es la pieza clave**: sin él el veredicto es prosa y el gate no es parseable.
  Debe ir con `--output-format json` y leerse de `structured_output`.
- **Latencia real**: 108–260 s por revisión en `gemini-3.8-flash-high --effort high`
  (~100k tokens). No lo lances para cambios triviales ni en bucle por cada guardado.
- **`severity: low` no bloquea** — se enruta a advertencias; solo critical/high/medium bloquean.
- **Escalado por blast radius**: rutas de auth/pago/migración/DB/deploy o diff > 400 líneas
  suben a `claude-opus-5-5-high`. Nunca subir de modelo sin OK de Plon por costo/cuota.
- **Degradación explícita**: si AGY no responde, el receipt queda `degraded`, no `pass`.
  Un gate que aprueba en silencio es peor que no tenerlo.
- La deny rule de terminal (`*rm *-r* /opt*`) bloquea `rm -rf` y `git rm -r` sobre rutas /opt:
  usar `git rm --cached --ignore-unmatch` y nunca `rm -rf` en scripts de limpieza.

## Verificación de que el gate es real

Un gate solo cuenta si se probó en rojo y en verde:
1. diff con bug conocido → exit 2 con el hallazgo nombrado.
2. diff corregido → exit 0 y receipt con `decision=pass`.
3. mismo diff otra vez → `pass-cached` en <1 s.

Si alguna de las tres no se cumple, el gate no está funcionando.

## Errores que el reviewer ya me encontró (no repetirlos)

Nacieron del dogfooding del propio `review-gate` (6 hallazgos reales en 555 líneas).
Cada uno es ahora una regla dura, no una anécdota:

1. **Todo camino de error de un gate es fail-closed.** Devolver 0 en estado `degraded`
   era un bypass: basta con tumbar al reviewer para commitear cualquier cosa. El fail-open
   debe ser un flag explícito (`--allow-degraded`) y quedar marcado en el receipt.
2. **El cache nunca acredita más de lo que el receipt probó.** Un `pass` obtenido sin tests
   no puede satisfacer un run que exige tests. El hit de cache se valida contra los
   requisitos del run actual, no solo contra el hash del diff.
3. **Nunca concatenar entrada del usuario en un comando git.** `--range` con `--output=...`
   inyecta flags. Validar contra una regex de refs/rangos, rechazar lo que empiece con `-`,
   y terminar con `--`.
4. **El repo sin commit inicial debe funcionar** (`git rev-parse HEAD` falla con 128):
   usar el árbol vacío `4b825dc642cb6eb9a060e54bf8d69288fbee4904` como base.
5. **Lockfiles se abren en `'a'`, nunca en `'w'`** (truncar el lock de otro proceso) y con
   `chmod` explícito + fallback por uid si no hay permiso.
6. **Un componente nuevo sin tests no está terminado.** El reviewer bloquea por eso, y tiene razón.
7. **Todo scanner se escanea a sí mismo.** Las tablas de patrones son código-como-dato:
   excluirlas (`PATTERN_DEF_RE`) y ofrecer supresión en línea (`review-gate:ignore`).
