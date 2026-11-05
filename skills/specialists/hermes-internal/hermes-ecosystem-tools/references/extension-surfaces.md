# Superficies de extensión de Hermes

Contrato vigente: `hermes.middleware.v1` / `hermes.observer.v1`. Docs: `/docs/developer-guide/middleware`, `/docs/developer-guide/plugins`, `/docs/user-guide/features/hooks`, `/docs/developer-guide/plugins/catalog-submission`.

## Middleware — `ctx.register_middleware(kind, fn)`

| kind | payload | retorno | para qué |
|---|---|---|---|
| `llm_request` | `request`, `original_request` | `{"request": {...}}` (payload completo, no parches) | reescribir kwargs del proveedor antes de la llamada |
| `tool_request` | `tool_name`, `args`, `original_args` | `{"args": {...}}` | reescribir args **antes** de guardrails y aprobaciones |
| `llm_execution` | `request`, `original_request`, `next_call` | respuesta del proveedor | envolver la llamada real al proveedor |
| `tool_execution` | payload + `next_call` | resultado del tool | envolver la ejecución del tool |

Reglas que cuestan bugs: `next_call` es de un solo uso (llamarlo dos veces lanza); si el middleware lanza antes de `next_call` Hermes lo registra y sigue con la cadena; si lanza después, se preserva el resultado downstream y no se reintenta; un middleware que lanza se loguea y se salta.

## Stream: qué se puede y qué no

- `on_stream_start`, `on_stream_delta`, `on_stream_end`, `on_interim_message` son **observers**: los docs dicen explícitamente que los valores de retorno se ignoran, y se despachan fuera del camino del token por una cola acotada con un worker por callback.
- `transform_llm_output` corre antes de `post_llm_call` y de la entrega final: llega tarde para un canal con streaming, donde los deltas ya viajaron.
- `transform_tool_result` / `transform_terminal_output` sí reescriben, pero su ámbito es el resultado de un tool, no la salida del modelo.
- **Consecuencia:** reescribir el stream en vuelo (redactar, enmascarar, censurar) obliga a envolver `llm_execution` y transformar el propio generador, con ventana de lookahead para no cortar patrones partidos entre deltas. Un observer no sirve. Si algún día el core expone un hook de transformación de stream, el plugin debe detectarlo y usarlo, con el wrap como fallback.

## Otros hooks con retorno útil

`pre_tool_call` (`block` / `approve` / `modify`, fail-closed si expira), `pre_llm_call` (contexto inyectado o `block`), `pre_gateway_dispatch` (`skip` / `rewrite` / `allow` en el ingreso), `pre_verify` (gate de código editado), `transform_api_error_classification` (run-all-then-pick-first).

## Admisión al catálogo (`plugin-catalog/<name>.yaml`)

- Un archivo por PR contra `NousResearch/hermes-agent`; `sha` de 40 caracteres exactos; `version` entre comillas; `requires_hermes` como piso SemVer (`">=0.21.5"`), nunca fecha CalVer.
- Validar local antes del PR: `hermes plugins validate /ruta/al/plugin --install-deps` (mismo check que CI). En aislamiento: `hermes plugins doctor`.
- Prohibido y motivo de rechazo: auto-actualizador dentro del plugin, override de core/`sys.modules`/privates, leer credenciales de archivos o de otro login (solo `agent.secret_scope.get_secret` o `credentialed_provider_request`), saltarse aprobaciones o arrancar hijos con YOLO.
- `capabilities` declaradas deben coincidir exactamente con lo que se registra en el commit pinneado; el desajuste es fallo de validación.
- Desktop plugins: solo SDK — sin prototype patching, `eval`, ni observers sobre el markup del core.
- El SHA es el modelo de confianza: cada bump es PR nuevo revisado.

## Cuando la costura no existe

Los docs invitan a abrir issue pidiendo el hook en vez de parchear el core: "we would rather add a proper seam than list a patch". Un plugin concreto que lo va a usar es exactamente el consumidor que justifica el hook — argumento útil al proponer.
