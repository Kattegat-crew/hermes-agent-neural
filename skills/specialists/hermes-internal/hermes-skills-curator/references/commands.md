# Comandos del curator de Hermes

Matriz completa de subcomandos de `hermes curator` y el formato de salida. Se ejecuta dentro del contenedor: `docker exec hermes-agent hermes curator <subcomando>`.

## Subcomandos

| Comando | Qué hace |
|---|---|
| `status` | Estado del curator: ENABLED, runs, último resumen, curator-managed (agent-created / bundled), unmanaged (pre-marker / foreground) |
| `usage` | Telemetría de uso de TODAS las skills (built-in, hub, agent) con procedencia — pesado |
| `run` | Disparar una revisión YA (auto=prune/stale/archive + llm=consolidación si está activa) |
| `pause` / `resume` | Pausar/reanudar el curator |
| `pin` / `unpin` | Bloquear/liberar una skill de transiciones automáticas |
| `list-unmanaged` | Listar skills elegibles sin marca de procedencia — MUY pesado, cuelga >60s |
| `adopt` | Entregar una skill unmanaged al curator (declaración de procedencia) |
| `restore` | Restaurar una skill archivada |
| `list-archived` | Listar skills archivadas |
| `archive` | Archivar manualmente una skill (mueve a `.archive/`, excluida del prompt) |
| `prune` | Archivar en lote skills curator-managed idle ≥ N días (default 90) |
| `backup` | Snapshot tar.gz de `~/.hermes/skills/` (el curator lo hace solo antes de cada run real) |
| `rollback` | Restaurar `~/.hermes/skills/` desde snapshot, o una mutación por id de ledger |
| `ledger` | Auditoría por mutación de skills (actor: curator/agent/user) |
| `purge` | Borrar skills archivadas > `curator.archive_ttl_days` (SOLO explícito; se registra en ledger) |

## Formato de `status` (referencia de lectura rápida)

```
curator: ENABLED
  runs:           17
  last run:       1d ago
  last summary:   auto: no changes; llm: skipped (consolidation off)
  last report:    /opt/data/logs/curator/<fecha>
  interval:       every 7d
  stale after:    30d unused
  archive after:  90d unused
  consolidate:    off (prune-only; LLM merge pass opt-in)

curator-managed skills: 34 total  (agent-created=0  bundled=34)
  active     34
  stale      0
  archived   0

unmanaged (no provenance marker): 356 total
  pre-dates marker    350
  foreground-created  6
  never auto-staled or archived — `hermes curator adopt <name>` hands one over

least actively used (top 5):
  <name>  activity= 0  use= 0  view= 0  patches= 0  last_activity=never
```

## Razones típicas de `auto: no changes`

Un `curator run` que no cambia nada casi siempre significa que la pila **curator-managed** es pequeña (bundled + adoptadas) y no hay skills inactivas. Las skills propias de la agencia quedan fuera en `unmanaged` — el curator NO las barre por diseño. Para gestionarlas hay que `adopt`, y para que un run las revise solo se añaden a la pila gestionada una vez adoptadas.

## Notas de rendimiento

- `status` y `usage`: correr en background (`docker exec hermes-agent hermes curator status > /tmp/cu.txt 2>&1` con `background=true`) y leer el archivo — en foreground cuelgan >60s.
- `list-unmanaged`: el más lento de todos; si se necesita el listado completo, redirigir `usage` a un archivo en background.
