# SPEC — HERMES-DSML-GUARD (fix de fuga DSML de DeepSeek en la ruta de respuesta final)

**Repo:** /opt/hermes-agent · **Worktree:** fleet/codex-dsml-guard (desde origin/main 70a846f7e6)
**Modo:** SDD estricto · **Marcador de código:** `HERMES-DSML-GUARD` · **Sin push, sin atribución IA.**

## Problema (evidencia medida)
DeepSeek V4 (proxy NaN Builders) a veces emite su DSL interno de tool-calls como TEXTO en
`content` en vez de `tool_calls`. Desde el 14-oct: 56 fugas (admin 25, isa 13, nancy 6,
jacqueline 3, oscar 3, golden-game 3, gerardo 2, ivan 1), **todas con tool_calls vacío**
→ cero herramientas ejecutadas y el usuario ve basura (un cliente la vio el 24-oct 22:51).
El proxy es nginx→api.nan.builders: NO se arregla server-side (reescribir SSE = frágil;
non-streaming no es opción, el proxy da 408). El fix va en el cliente, en el punto único
de salida del texto asistente.

## Punto de inserción (verificado en vivo)
- `agent/turn_final_response.py` (18 KB) — `finish_text_response()`: chocke point único del
  texto final de turno. Importa `recover_empty_response` de `agent/turn_empty_response.py`
  (línea ~132) — reutilizar ese mecanismo existente para la capa de re-emisión.
- `agent/conversation_loop.py` línea 47 importa `finish_text_response` — NO tocar su contrato.
- Gateway: `gateway/run.py` línea ~1344 ya documenta un caso de replay del turno final.

## Cambio requerido: guard de 3 capas

### Capa 1 — RECUPERAR (parse → tool_call real)
En `turn_final_response.py`, ANTES de devolver el texto: detectar bloques DSML en `content`
y convertirlos a `tool_calls` estructurados re-ejecutables (la herramienta corre).
Variantes de marcador a normalizar (todas):
- `<｜｜DSML｜｜...` (doble barra fullwidth U+FF5C — la variante medida en producción)
- `<｜DSML｜...` (barra simple fullwidth)
- `<||DSML||...` (ASCII doble)
- `toolcalls` mal escrito (envoltura corrupta, vllm #51914)
- Bloque SIN cierre (dominante en producción: el leak llega truncado) → cortar desde el
  primer marcador hasta el fin del texto; un parser de bloque balanceado NO matchea.

### Capa 2 — RE-EMITIR (si no parsea)
Si hay marcador pero el bloque no se reconstruye con seguridad → enrutar a
`recover_empty_response` (mecanismo existente, con presupuesto de reintentos).

### Capa 3 — CORTAFUEGOS (strip garantizado)
Todo residuo DSML se elimina de `content` antes de salir al usuario + contador/log interno
con el marcador HERMES-DSML-GUARD para métrica. El cliente NUNCA ve el markup.

### Guardias anti-llamada fantasma (OBLIGATORIOS, vllm #51914)
Una llamada reconstruida SOLO se ejecuta si cumple TODAS:
1. Bloque estructuralmente cerrado o reconstruible sin ambigüedad.
2. La herramienta invocada está DECLARADA en el toolset del turno (nombre exacto).
3. Los argumentos requeridos de su schema están presentes y son JSON válido.
Si falla cualquier guardia → capa 2 (re-emisión), nunca ejecución inventada.

## TDD (orden inquebrantable)
1. Primero tests en `tests/agent/test_dsml_guard.py` (RED): cada variante de marcador,
   bloque truncado, bloque cerrado, guardias fantasma (cada uno), no-op byte a byte para
   texto limpio (regresión cero), integración con recover_empty_response.
2. Observar fallo → implementar → GREEN.
3. Suite: `.venv/bin/python -m pytest tests/agent/ -q` (env uv ya montado en el repo).
   NO romper tests existentes de la ruta (test_empty_response_fallback_refund.py,
   test_setup_beat_card_round.py, tests/gateway/test_replay_entry_fields.py).

## Fuera de alcance (NO tocar)
- proxy 8742, gateway/run.py salvo comentarios de tests existentes, prompt caching,
  turn_empty_response.py salvo integración de re-emisión, cualquier perfil/config.

## Commits (Conventional, sin Co-Authored-By)
1. `test(agent): add DSML leak recovery guard tests (RED)`
2. `fix(agent): recover, re-emit and strip leaked DSML tool-call blocks (HERMES-DSML-GUARD)`

## Rollback
`git revert` de los 2 commits en el worktree; el guard es aditivo (sin reescritura de
funciones existentes), revert limpio garantizado.

## Cierre de entrega
Terminar con marcador EXISTO: `STOP_FOR_RAGNAR_REVIEW FASE_1_2` + resumen de tests
(pass/fail exactos) + `git log --oneline` + `git status` limpio en el worktree.
