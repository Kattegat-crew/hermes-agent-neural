## 2.c Ticket Kanban como canal de handoff durable (estado vivo verificado 21-oct-2026)

Cuando el handoff cruza agentes, debe sobrevivir reinicios, necesitar revisión humana o requerir trazabilidad, el canal canónico NO es el chat ni el buzón: es la **tarjeta Kanban** (`kanban.db`). Referencia completa en `references/kanban-ticket-handoff.md`.

Resumen operativo:
- Crear con `kanban_create(title, assignee=<perfil real>, body=<spec>, skills=[...], parents=[...], workspace_kind/workspace_path)`.
- El `assignee` debe existir en `/opt/hermes-agent-data/profiles/`; si no, el spawn falla y tras `failure_limit` la tarjeta se auto-bloquea.
- El hijo recibe `summary` + `metadata` del padre **verbatim** → el padre cierra con rutas absolutas, hashes, tests y costos.
- Cerrar siempre con `kanban_complete(...)` o `kanban_block(kind=..., reason=...)`; salir sin llamarlos es violación de protocolo.
- Latencia medida en DEV: creada→reclamada 38 s; padre `done`→hijo arranca 28 s.
- Límite duro: cada worker es un proceso OS completo → 2-3 concurrentes realistas en DEV (4 cores / 7.9 GB), aunque el default derivado de memoria permita 8.
