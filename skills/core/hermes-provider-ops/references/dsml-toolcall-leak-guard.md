# Fuga de tool-call DSL como texto plano (DeepSeek V4 / familia DSML)

Fallo de proveedor verificado en producción (25-oct-2026): el modelo emite su DSL interno
de invocación de herramientas (bloques `｜｜DSML｜｜ invoke ...`) como texto plano en
`content` en vez de `tool_calls` — el turno muere sin ejecutar nada y el usuario ve
markup crudo. Causa raíz: el proveedor/servidor debía convertir el DSL nativo a
`tool_calls` y su parser falla. Documentado también en vllm (#51914, llamadas fantasma).

## Marcadores observados (4 variantes + truncado)
- `｜｜DSML｜｜`, `｜DSML｜`, `||DSML||`, `<toolcalls>`; cierre con la barra ANTES de las
  barras: `</｜｜DSML｜｜ ...>`.
- Bloque truncado sin cierre (el más común en producción): el parámetro corre hasta EOS.
- Detección = marcador + forma de invocación (`invoke|calls`): la prosa que menciona el
  marcador NO dispara; texto limpio pasa byte a byte.

## Guard de 3 capas (implementado en /opt/hermes-agent, worktree DSML-GUARD)
1. **Intake** (`agent/turn_response_intake.py`, en `normalize_model_response` tras la
   coerción de contenido, ANTES del dispatch `run_tool_round if tool_calls else
   finish_text_response`): si la llamada es reconstruible (herramienta declarada en
   `valid_tool_names`, argumentos JSON parseables — guardias anti-fantasma), inyectar
   `tool_calls` reales (SimpleNamespace id/type/function{name, arguments JSON}) → la
   herramienta corre EN EL MISMO TURNO a 0 tokens extra y `validate_tool_calls` la
   valida como cualquier llamada del proveedor.
2. **Re-prompt acotado** (`agent/turn_final_response.py`, máx 2): nudge user con la
   llamada reconstruida exacta (o genérico) vía assistant efímero; verdict continue.
3. **Cortafuegos**: presupuesto agotado → strip del markup antes de mostrar; el usuario
   NUNCA ve el DSL. Contadores `_dsml_guard_recovered/retries/strips` + log
   `HERMES-DSML-GUARD` con modelo/proveedor.

Reglas clave: nunca ejecutar una llamada fantasma reconstruida sin guardias anti-fantasma
(nombre declarado + argumentos capturados); limpiar SIEMPRE el contenido aunque se
recupere la llamada; implementación en `agent/dsml_guard.py` (puro, con
`apply_dsml_guard` y `recover_leaked_tool_calls`), tests en
`tests/agent/test_dsml_guard.py`.

Estado 25-oct: 15/15 tests GREEN en worktree `fleet/codex-implementa-hermes-dsml-g-20261025-114510`; pendiente revisión fría + despliegue a perfiles (no asumir desplegado).
