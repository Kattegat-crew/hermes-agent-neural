# Monitoreo de bots y puntuación de output — criterios

Ejecutado por el job `hermes-maintenance-night` (03:30, monitor_script). El script emite una firma de estado; solo cuando cambia (release nuevo, errores nuevos, disco/restart) el agente corre y analiza.

## Qué revisa el script (`/opt/data/scripts/hermes-ops-monitor.py`)

| Señal | Fuente | Gatiila de cambio |
|---|---|---|
| Versión local | `hermes --version` | — |
| Release remoto + commits nuevos | GitHub API `NousResearch/hermes-agent` (releases/latest + commits) | tag nuevo o commits nuevos desde el último scan |
| Gateway up/down | `/opt/data/logs/gateways/default/current` + `ps` | caída o restart |
| Errores del día | grep de patrones de error en logs del gateway (Whatsapp, polling, etc.) | firma de errores nueva |
| Disco / RAM | `df /` · `/proc/meminfo` | umbral disco >85% / swap o memoria crítica |
| Señales de comportamiento | restarts, "Poll error", timeouts, sesiones truncadas | aparición nueva |

Regla del monitor: salida **byte-estable** cuando no hay novedades → el scheduler suprime el run (cero ruido). No incluir timestamps en la firma.

## Puntuación del output de los bots (cuando el agente corre)

Asignar **score 0–100** por bot activo (perfiles en `/opt/data/profiles/`, sesiones del gateway, logs) con estos componentes:

1. **Fiabilidad (30)** — tasa de errores de herramienta: llamadas fallidas / llamadas totales visibles en logs del día. ≥10% errores → descontar fuerte; 0% → máximo.
2. **Coherencia (25)** — respuestas completas, sin truncamientos, sin repetir bucles ("I'll try", loops de reintento), sin alucinaciones evidentes.
3. **Adherencia a tono/reglas (20)** — español por defecto, sin fillers ("¡Claro!", "Entendido"), sin inventar datos; ver SOUL del perfil.
4. **Capacidad de cierre (15)** — entrega resultados verificados, no descripciones de intención.
5. **Salud del flujo (10)** — restarts, timeouts, sesiones colgadas en las últimas 24h.

Salida del informe (cuando hay novedad): tabla por bot con score + 1 línea de evidencia (qué se puntuó y por qué). Riesgos | Likelihood | Mitigation para cada anomalía.

## Rutas de logs

- Gateway: `/opt/data/logs/gateways/default/current` (s6, rotado) + `@4000...u` antiguos.
- Serve (host): `/root/hermes-agent-legacy-docker/data/logs/{agent,errors,gui}.log` — leer via nsenter (skill `vps-host-access`).
- Sesiones: gateway write_sessions_json → revisar dir de sesiones si aplica.
- Cron outputs: `/opt/data/cron/output/`.

## Decisiones human-only (escalar, no ejecutar)

- Actualizar la versión de Hermes cuando hay release nueva (requiere ventana de mantenimiento + backup + restart) — recomendar, no ejecutar sin OK.
- Credenciales nuevas (API keys, tokens) → `brain/tasks/pending.md`.
