---
name: adversarial-review-gate
description: Use when committing code — AGY adversarial review gate.
version: 1.0.0
author: Jonathan Parra (Plon), Hermes Agent
license: Apache-2.0
platforms: [linux, macos]
category: software-development
metadata:
  hermes:
    tags: [code-review, adversarial, gate, agy, pre-commit, calidad]
    related_skills: [requesting-code-review, doubt-driven-development, test-driven-development]
---

# Adversarial Review Gate Skill

Un agente no verifica su propio trabajo. Esta skill pone un segundo modelo, sin el contexto ni el
sesgo del autor, a buscar cómo romper el diff antes de que se convierta en commit. No garantiza
código correcto: garantiza que alguien distinto miró y no encontró un agujero.

## When to Use

- Antes de cualquier commit o PR en un repo con código.
- Después de cada tarea de un flujo SDD o de un subagente.
- Cuando el usuario pide "revisa", "verifica" o "¿está bien?" sobre código propio.
- NO para diffs que solo tocan documentación, config sin lógica o renombres mecánicos.

## Prerequisites

Para `agy`: el binario con OAuth vivo (`agy models` responde) y un `HOME` aislado con el token
en `.gemini/antigravity-cli/` (`REVIEW_GATE_AGY_HOME`). Dos instancias con el mismo `HOME` se
matan entre sí, y el gate lo serializa con `flock`.

Para `codex`: vive en el host y se invoca por `ssh` como root (`REVIEW_GATE_CODEX_SSH`,
`REVIEW_GATE_CODEX_PATH`). Siempre con `-s read-only`.

Para `opencode`: el binario local (`REVIEW_GATE_OPENCODE_BIN`). No tiene salida estructurada
nativa, así que su veredicto se parsea del stream de eventos.

`git` en el repo objetivo: el gate se niega a correr fuera de un repositorio.

## How to Run

```bash
# motor por defecto (agy) con tests obligatorios
python3 skills/software-development/adversarial-review-gate/scripts/review_gate.py \
  --repo /opt/mi-repo --staged --test-cmd "pytest -q tests/unit" --require-tests

# elegir motor y modelo
--engine codex --model gpt-6-astra
--engine opencode --model opencode/deepseek-v4.1-flash-free
--engine agy --model claude-opus-5-5-high

# elegir por riesgo y coste (diff normal -> codex; rutas sensibles -> agy opus)
--engine auto

# cadena de reserva si el primero falla o agota cuota
--engine agy --fallback "codex:gpt-6-astra,opencode:opencode/glm-5.3-flash-free"

# catálogo real de motores y modelos
python3 .../review_gate.py --list-engines
```

Salida: `0` pasa · `2` bloquea o degrada · `4` error de uso. Añadir `--json` para consumo por máquina.

## Quick Reference

| Flag | Efecto |
|---|---|
| `--engine agy\|codex\|opencode\|auto` | motor del reviewer (default: `agy`) |
| `--model M` / `--provider P` | modelo del motor; `--provider` solo para opencode |
| `--fallback "motor:modelo,..."` | cadena de reserva |
| `--stop-on critical,high,medium` | qué severidades bloquean; el resto pasa a advertencias |
| `--budget-seconds N` | 0 = sin límite; si se agota, bloquea sin llamar al reviewer |
| `--list-engines` | catálogo vivo de motores y modelos |
| `--staged` (default) / `--work` / `--range A..B` | qué diff se revisa |
| `--test-cmd "..."` | ejecuta la suite; si falla, bloquea sin gastar tokens |
| `--require-tests` | bloquea si no hay evidencia de tests verdes |
| `--force` | ignora el cache de receipts |
| `--allow-degraded` | fail-open explícito si el reviewer no responde (queda registrado) |
| `--no-escalate` | no subir a `claude-opus-5-5-high` en diffs de alto riesgo |
| `--json` | salida estructurada |

Variables: `REVIEW_GATE_STATE`, `REVIEW_GATE_AGY_HOME`, `REVIEW_GATE_AGY_BIN`, `REVIEW_GATE_MODEL`,
`REVIEW_GATE_MODEL_HIGH`, `REVIEW_GATE_SCHEMA`, `REVIEW_GATE_LOCK`.

## Procedure

1. **Diff y hash.** Se calcula el sha256 de `base + diff`. El mismo diff reutiliza su receipt: no se
   vuelve a pagar una revisión. El cache solo se acepta si acredita los requisitos del run actual
   (un `pass` sin tests no satisface `--require-tests`).
2. **Filtro de superficie.** Si el diff no toca código (`.md`, imágenes, `.gitignore`, `LICENSE`),
   el gate sale `0` sin gastar un token.
3. **Escaneo estático** de las líneas añadidas: secretos, `shell=True`, `os.system`, `eval`/`exec`,
   `pickle`, SQL por interpolación, `verify=False`, `chmod 777`, `innerHTML`, `except: pass`.
   Las tablas de patrones se excluyen a sí mismas y cada línea admite supresión con
   `# review-gate:ignore`.
4. **Tests primero.** Con `--test-cmd` el fallo corta aquí, antes del reviewer.
5. **Reviewer** en el motor elegido. Todos reciben el diff como DATO y el contrato, nunca la
   conclusión del autor. Cada adaptador traduce su salida al mismo contrato:
   `agy` (`--json-schema` → `structured_output`), `codex` (`--output-schema` estricto → fichero
   con `-o`), `opencode` (stream de eventos → texto → JSON). Un veredicto con forma inválida se
   normaliza o se descarta; nunca revienta el gate.
6. **Veredicto y receipt.** `critical`/`high`/`medium` bloquean; `low` va a advertencias. El receipt
   queda en `REVIEW_GATE_STATE/<repo-slug>/<review_id>.json` y el hallazgo en `ledger.jsonl` con
   fingerprint.
7. **Loop de corrección.** Corrección → re-gate. Máximo 2 ciclos; al tercero se escala al humano
   con los hallazgos restantes en vez de grindear.
8. **Promoción del aprendizaje.** Un fingerprint repetido dos veces se convierte en entrada de
   `STATIC` dentro del script (check mecánico) y en regla del repo. Ahí deja de depender de que un
   modelo lo recuerde.

## Pitfalls

- **Todo camino de error de un gate es fail-closed.** Devolver `0` cuando el reviewer no responde es
  un bypass: basta con tumbar al reviewer para commitear cualquier cosa. El fail-open exige
  `--allow-degraded` explícito y queda marcado en el receipt.
- **Un cache no acredita más de lo que el receipt probó.** El hit se valida contra los requisitos del
  run actual, no solo contra el hash del diff.
- **Nunca concatenar entrada del usuario en un comando git.** `--range=--output=/ruta` inyecta flags;
  se valida contra una regex de refs y se cierra con `--`.
- **Un repo sin commits iniciales existe.** `git rev-parse HEAD` falla con 128: usar el árbol vacío
  `4b825dc642cb6eb9a060e54bf8d69288fbee4904`.
- **Lockfiles se abren en `'a'`, nunca en `'w'`**: truncar el lock de otro proceso rompe la
  serialización. `chmod` explícito y fallback por uid si no hay permiso.
- **Todo scanner se escanea a sí mismo.** Las tablas de patrones son código-como-dato: excluirlas o
  el gate se reporta a sí mismo como vulnerable.
- **Una advertencia no puede suprimir la revisión.** Si los hallazgos de severidad `low` se
  acumulan en la misma lista que los bloqueantes, la condición "no hay bloqueantes → revisar" se
  vuelve falsa y el reviewer nunca corre: un `print` de depuración bastaría para saltarse el gate.
  Separa advertencias de bloqueantes antes de decidir si se revisa.
- **El cache no puede acreditar lo que no verificó.** El hash debe incluir los flags que cambian la
  verificación (`--skip-static`, modelo, reglas del repo) y el comando de tests ejecutado; si no, un
  pase obtenido saltándose el estático se reutiliza después.
- **Un receipt corrupto es un cache miss, no un fallo.** Leer estado ajeno con `json.loads` sin
  proteger deja el diff bloqueado para siempre; escribir con `tempfile` + `os.replace` evita crear
  ese receipt a medias.
- **El esquema portable es el más estricto.** `codex` rechaza el `--output-schema` si alguna clave
  de `properties` falta en `required`. El esquema del gate los exige todos y los adaptadores
  toleran valores vacíos al leer.
- **`codex` corre como root en el host: siempre `-s read-only`.** Copiar el patrón de `fleet-run`
  (`--dangerously-bypass-approvals-and-sandbox`) convertiría al reviewer en un root sin sandbox
  leyendo diffs ajenos.
- **`opencode` no tiene esquema**: puede devolver `blocking` como lista de frases sueltas. Hay que
  normalizarlo (severidad inferida del texto) o el gate muere con `AttributeError`.
- **`opencode` trocea el texto en eventos arbitrarios**: unirlos con `\n` parte claves JSON. Se
  concatenan sin separador y se reintenta con `\n` como respaldo.
- **`opencode` no tiene `-C`**: hay que lanzarlo con `cwd` en el repo o choca contra
  `external_directory` y auto-rechaza la lectura.
- **Los fail-open se esconden en las politicas, no en el codigo.** Si un flag como
  `--stop-on` re-clasifica severidades, todo lo que NO es heuristica (un rechazo del
  reviewer, un test en rojo, un presupuesto agotado) tiene que quedar fuera de ese
  filtro. Revisa cada vez: ¿que camino termina en exit 0 sin haber probado nada?
- **Un veredicto incompleto nunca es una aprobacion.** `{}`, `{"passed": true}` sin
  `blocking`, o `blocking: [null]` se normalizan a rechazo o se descartan; jamas a
  `passed=true`. Es el bug mas facil de escribir y el mas caro.
- **El aislamiento se acredita, no se supone.** Que exista un archivo de config no
  prueba nada: hay que leer la politica efectiva (`permission.edit == deny`), rechazar
  repos que traigan su propia config (se fusiona y puede reabrir permisos) y verificar
  despues que el arbol de trabajo no cambio.
- **Un lock con `flock` bloqueante se come el presupuesto.** Espera acotada con
  `LOCK_NB` + deadline, y libera siempre en un `finally` idempotente (cerrar el handle
  antes del `finally` provoca `ValueError` en el `unlock`).
- **Un motor sin esquema nativo puede devolver `blocking` como lista de frases.**
  Normaliza antes de recorrerla o el gate muere con `AttributeError` en el peor momento.
- **`--json-schema` es la pieza que hace el gate parseable.** Sin schema, `agy -p` devuelve prosa y el
  veredicto no se puede evaluar.
- **Latencia real**: 108–260 s y ~100k tokens por revisión con `gemini-3.8-flash-high --effort high`.
  No lanzarlo por cada guardado ni sobre cambios triviales.
- **La cuota de AGY se agota** y devuelve 429. El gate queda `degraded` (exit 2), no `pass`.

## Verification

```bash
python3 -m pytest tests/skills/test_adversarial_review_gate_skill.py -q
```

Y la prueba de que el gate es real, en rojo y en verde:

1. diff con un bug conocido → exit `2` con el hallazgo nombrado.
2. diff corregido → exit `0` y receipt con `decision=pass`.
3. el mismo diff otra vez → `pass-cached` en menos de un segundo.

Si alguna de las tres falla, el gate no está funcionando y no debe usarse como excusa.
