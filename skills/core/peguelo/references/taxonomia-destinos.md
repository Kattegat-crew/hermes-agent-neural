# Taxonomía de destinos y regla de promoción 1-2-3

Una lección sin destino es un diario. Cada hallazgo va a **una** de cinco cajas, y solo una.

## Las 5 cajas

| Destino | Qué va aquí | Herramienta | Ejemplo |
|---|---|---|---|
| **skill** | Procedimiento repetible, con pasos y verificación | `skill_manage(patch)` | «Antes de `patch`, releer el archivo: el buffer viejo deja el diff obsoleto» |
| **memoria** | Hecho permanente del entorno o del usuario (no procedimiento) | `memory(add)` máx 1/sesión | «El perfil default usa un state.db de 1.5 GB; read_file no lo abre» |
| **brain** | Contexto de proyecto/cliente que caduca | `mem_save` o `/opt/data/brain/` | «Golden Game: la hoja Bre-B se llama X y no incluye los pagos del 01-oct» |
| **guard** | Error que una máquina puede impedir mejor que la disciplina | propuesta de hook/validación | «Bloquear `write_file` si no hubo `read_file` del mismo path en la sesión» |
| **nada** | Caso único sin recurrencia | descarte explícito | «Se me olvidó un acento en un nombre» |

## Árbol de decisión

1. ¿Puede una máquina detectarlo y bloquearlo con una regla determinista? → **guard**.
2. ¿Es un «cómo hacer X» que se repite? → **skill**.
3. ¿Es un hecho estable que cambia cómo trabajo siempre? → **memoria**.
4. ¿Es contexto de un cliente/campaña con fecha? → **brain**.
5. ¿Ocurrió una vez y no tiene consecuencia? → **nada** (y lo dices).

Regla dura: **nada** es una respuesta legítima y frecuente. La memoria contaminada cuesta más que la memoria incompleta.

## Regla 1-2-3

| Apariciones | Acción |
|---|---|
| 1 | Solo ledger. No se toca nada. |
| 2 | Parche de la skill/regla concreta (bajo riesgo, aplicable en la sesión). |
| 3+ | Escalar a **guard**: proponer el hook/validación que lo bloquee en código. Requiere OK humano. |

La recurrencia se cuenta con `scripts/peguelo_ledger.py count --rule "…"`, no de memoria. Dos sesiones seguidas con el mismo FAIL ya son dos apariciones.

## Esquema del ledger (JSONL, append-only)

`/opt/data/brain/ops/session-retros/ledger.jsonl`

```json
{"ts":"2026-11-04T20:05:00-05:00","lesson_id":"9f2c1a7b3d","rule":"Leer el archivo antes de escribirlo","destination":"skill","target":"hermes-runtime-ops","session":"20261104_193740_d95f6b","evidence":"#12 write_file sin read_file previo","recurrence":2,"promotion":"PARCHE: 2 repeticiones -> proponer parche de la skill/regla concreta"}
```

- `lesson_id` = sha1 de la regla normalizada (minúsculas, sin puntuación, espacios colapsados). Dos redacciones casi iguales caen en el mismo id solo si el texto normalizado coincide; si no, unifica la regla al escribirla.
- `evidence` siempre con `#idx` o métrica. Sin evidencia, el registro no vale.
- `target` obligatorio para `skill` y `guard`; vacío para `nada`.

## Retención y privacidad

- El ledger crece poco (≤ 5 entradas por sesión). Si supera ~2.000 líneas, archivar por año (`ledger-2026.jsonl`) sin borrar.
- Nunca escribir secretos, tokens, teléfonos, correos de terceros ni datos de clientes. El script redacta el dossier; el ledger lo escribes tú.
- Los informes viven en `/opt/data/brain/ops/session-retros/` y son internos. No se publican ni se mandan a clientes.

## Anti-patrones

- Guardar la misma lección con destino distinto cada vez (rompe la recurrencia).
- Convertir en guard algo que aún no se repitió tres veces (sobre-ingeniería).
- Escribir 5 memorias al cerrar: la memoria se llena y se vuelve ruido.
- Parchear una skill que no se usó en la sesión (el contexto del parche se pierde).
