## 2.c Ticket Kanban como canal de handoff durable (estado vivo verificado 21-oct-2026)

Cuando el handoff cruza agentes, debe sobrevivir reinicios, necesitar revisión humana o requerir trazabilidad, el canal canónico NO es el chat ni el buzón: es la **tarjeta Kanban** (`kanban.db`). Referencia completa en `references/kanban-ticket-handoff.md`.

Resumen operativo:
- Crear con `kanban_create(title, assignee=<perfil real>, body=<spec>, skills=[...], parents=[...], workspace_kind/workspace_path)`.
- El `assignee` debe existir en `/opt/hermes-agent-data/profiles/`; si no, el spawn falla y tras `failure_limit` la tarjeta se auto-bloquea.
- El hijo recibe `summary` + `metadata` del padre **verbatim** → el padre cierra con rutas absolutas, hashes, tests y costos.
- Cerrar siempre con `kanban_complete(...)` o `kanban_block(kind=..., reason=...)`; salir sin llamarlos es violación de protocolo.
- Latencia medida en DEV: creada→reclamada 38 s; padre `done`→hijo arranca 28 s.
- Límite duro: cada worker es un proceso OS completo → 2-3 concurrentes realistas en DEV (4 cores / 7.9 GB), aunque el default derivado de memoria permita 8.

### Pipeline de fases con reviewer-gate (verificado 02-nov-2026)

Para reparaciones grandes multi-fase, encadenar tarjetas con `parents=[<fase anterior>]`: el hijo queda en `todo` con `gated: true` y NO se promueve a `ready` hasta que el padre llegue a `done` (verificado en `kanban_list`: `gated_by`).

- Revisión externa por fase: el implementador cierra con `kanban_request_review(reviewer='<perfil>')`, NUNCA con `kanban_complete`. El reviewer devuelve cambios con `kanban_request_changes(reason=...)` o aprueba cerrando.
- Si el reviewer no cierra en `done`, el hijo queda bloqueado indefinidamente — la revisión ES el gate, no un adorno: declararlo explícito en el body de cada tarjeta ("bloqueada hasta aprobación real del reviewer").
- Asignar las 4 tarjetas de una vez con `idempotency_key` por fase (evita duplicados en re-runs), `tenant` para aislar el pipeline y `max_runtime_seconds`/`goal_mode` para acotar cada worker.
- Ventanas de observación largas (ej. 24 h): la tarjeta NO debe dormir. Crear un cron one-shot (`cronjob_manage schedule='in 24h'`, `deliver='local'`) cuyo prompt despierte la tarjeta con `kanban_unblock`, persistir el `job_id` en la tarjeta, y entonces usar `kanban_schedule(reason='SCHEDULED_UNTIL=<UTC>; wake_job=<id>')` para liberar el worker. Recordar: `kanban_schedule` NO crea timer, solo aparca; sin cron previo la tarjeta nunca despierta.

### Reanimar tarjeta `ready` que el dispatcher no reclama (verificado 02-nov-2026)

Síntoma real: la tarjeta está `ready`/`todo`, `hermes kanban dispatch --max 1 --json` corre limpio pero `spawned: []` y `worker_pid` queda `None` indefinidamente.

1. **Inspección viva read-only** (sin tocar la DB): `sqlite3.connect('file:/opt/hermes-agent-data/kanban.db?mode=ro', uri=True)` sobre tablas `tasks` (status, worker_pid, last_spawn_error, last_heartbeat_at) y `task_comments`. Esto da el estado real cuando el resumen en chat es vago.
2. **Inyectar decisiones de usuario en el contexto del worker**: el worker NO ve el chat. Toda autorización o corrección de mitad de vuelo (ej. "autorizo subir a la carpeta Drive con anyoneWithLink") se registra como `hermes kanban comment <id> --author ragnar '<texto con fuente, fecha y alcance exacto>'` + `hermes kanban unblock <id> --reason '...'`. `kanban context <id>` lo muestra — el worker lo lee al reclamar.
3. **Spawn manual del worker** (la vía que sí funcionó): proceso background `hermes --cli --accept-hooks chat -q 'work kanban task <id>. <instrucción breve de reanudar y no detenerse por lo ya autorizado>'`. El worker reclama la tarjeta por su lock normal y ejecuta; es idempotente con el dispatcher (el lock evita doble reclamo).
4. Reportar al usuario el enlace del entregable pero **no** declarar "completo" hasta el readback de la tarjeta (`done` + evidencia); mientras, etiquetar como "lanzada, verificación pendiente".
