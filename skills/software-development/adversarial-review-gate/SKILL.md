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

- `agy` instalado y con OAuth vivo (`agy models` responde). La ruta se puede fijar con
  `REVIEW_GATE_AGY_BIN`.
- Un `HOME` aislado con el token copiado en `.gemini/antigravity-cli/`. Por defecto
  `REVIEW_GATE_AGY_HOME`; dos instancias con el mismo `HOME` se matan entre sí y el gate lo
  serializa con `flock`.
- `git` en el repo objetivo. El gate se niega a correr fuera de un repositorio.

## How to Run

```bash
python3 skills/software-development/adversarial-review-gate/scripts/review_gate.py \
  --repo /opt/mi-repo --staged --test-cmd "pytest -q tests/unit" --require-tests
```

Salida: `0` pasa · `2` bloquea o degrada · `4` error de uso. Añadir `--json` para consumo por máquina.

## Quick Reference

| Flag | Efecto |
|---|---|
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
5. **Reviewer AGY** en `--mode plan` (no edita) con `--json-schema` y `--output-format json`: el
   veredicto llega como `structured_output` validado, no como prosa. Recibe el diff como DATO y el
   contrato; nunca la conclusión del autor.
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
