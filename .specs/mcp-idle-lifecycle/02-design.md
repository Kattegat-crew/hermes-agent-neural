# Technical Design: MCP idle lifecycle policy

## 1. Component model

```
scripts/mcp_idle_policy.py          CLI + lógica pura (apply_policy, collect_targets)
utils._roundtrip_load               lectura round-trip del proyecto (quotes/indent/Unicode)
utils.atomic_roundtrip_yaml_save    escritura atómica con merge (comentarios preservados)
config.yaml del perfil              documento mutado (no se reordena ni se re-comenta)
```

Sin cambios en `tools/`, `agent/` ni `gateway/`: el reciclado ya existe y se activa leyendo
`idle_timeout_seconds` al arrancar el gateway.

## 2. Contrato con el núcleo (no negociable)

`_get_lifecycle_seconds` (`tools/mcp_tool_common.py:158-174`) resuelve en este orden:

1. `mcp_servers.<name>.idle_timeout_seconds` (top-level) — **gana**.
2. `mcp_servers.<name>.lifecycle.idle_timeout_seconds` — solo si la anterior falta.
3. Valor ausente, negativo o no numérico → se ignora (`None`).

Además, `_stdio_recycle_deadlines` (`tools/mcp_tool_health.py:25-26,40-46`) trata como HTTP toda
entrada con `url` y devuelve `[]`: **`url` no admite reciclado por inactividad**. El script replica
ambas reglas; cualquier divergencia es un bug, no una decisión de diseño.

Por eso `apply_policy` escribe el valor en top-level y, si ya existía la copia `lifecycle`, la
sincroniza: no se crea `lifecycle` desde cero y nunca queda un valor viejo ganando por precedencia.

## 3. API pública (CLI)

```
python3 scripts/mcp_idle_policy.py --config PATH [--idle-seconds 200]
                                   [--servers a,b] [--dry-run | --check] [--json]
```

| Flag | Semántica |
|---|---|
| `--config` | ruta obligatoria al `config.yaml` del perfil |
| `--idle-seconds` | entero ≥ 0, default 200; `0` desactiva el reciclado |
| `--servers` | lista separada por comas; default = todos los stdio |
| `--dry-run` | reporta sin escribir |
| `--check` | exit 3 si el valor efectivo difiere; nunca escribe |
| `--json` | salida machine-readable (para vigías) |

`--dry-run` y `--check` viven en un `add_mutually_exclusive_group()`: combinarlos es error de uso.

Exit codes: `0` ok · `2` config inválido/ilegible o uso incorrecto · `3` cambios pendientes
(`--check`) · `4` escritura fallida.

## 4. Funciones puras

```python
def collect_targets(data: Any, only: Sequence[str] | None = None) -> list[str]   # solo stdio
def http_servers(data: Any) -> list[str]                                          # informativos
def current_idle(server_cfg: dict) -> float | None                                # precedencia núcleo
def apply_policy(data: Any, idle_seconds: int,
                 only: Sequence[str] | None = None) -> list[Change]              # Change(server, before, after)
```

`current_idle` devuelve `float | None` y **no lanza** ante valores inválidos: un `abc` en un servidor
no debe tumbar el reporte de los otros 17 (el núcleo también lo ignora). `apply_policy` muta el
documento en memoria y devuelve los cambios, lo que permite testear sin disco.

## 5. Flujo

1. `utils._roundtrip_load(path)` → `CommentedMap` (misma config de indentado/quoting que el writer).
2. `collect_targets` valida `mcp_servers` (si falta, exit 2).
3. `apply_policy` → lista de cambios; `http_servers` → omitidos.
4. `--dry-run` / `--check`: reportar y salir sin escribir.
5. Sin cambios → salir `0` **sin reescribir** (idempotencia byte a byte, mtime intacto).
6. Con cambios → `utils.atomic_roundtrip_yaml_save(path, document)`.
7. Fallo de escritura → exit 4 con el mensaje del error en stderr.

## 6. Trade-offs y límites conocidos

- **Por qué no `yaml.safe_dump`**: destruye comentarios; prohibido por el check del repo.
- **Por qué no `atomic_config_write`**: exige que todos los mapping paths existentes estén presentes
  en `data`; pasar el documento completo al round-trip es equivalente y más simple.
- **Sin lock inter-proceso**: read-modify-write con reemplazo atómico, pero sin cerrojo. El script es
  de operaciones puntuales: **no debe ejecutarse mientras el gateway esté escribiendo config**
  (p. ej. cambios de config desde el dashboard). Un lost update es posible si ambos coinciden.
- **Semántica de reciclado**: el `rpc_lock` del núcleo impide reciclar un servidor con una llamada en
  curso, así que el valor escrito nunca corta una RPC viva.

## 7. Observabilidad

- Salida humana: cabecera con `stdio: N` y tabla `servidor  antes -> después`.
- `--json`: `{"config", "idle_seconds", "targets", "changed", "unchanged", "skipped_http", "applied"}`.
- Sin logs a disco; el script es de operaciones puntuales.
