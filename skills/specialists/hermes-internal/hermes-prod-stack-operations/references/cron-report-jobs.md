# Cron jobs de reporte diario — diseño corregido (24/08/2026)

## Síntoma original

Jobs `context-report-morning` (0 8 * * *) y `context-report-evening` (0 20 * * *) entregaban informes larguísimos (~94 líneas), con datos que no se actualizaban (las mismas "tareas completadas" día tras día) e información irrelevante (83M tokens, top herramientas, desglose por plataforma).

## Causa raíz

Los prompts apuntaban a rutas del HOST que no existen dentro del contenedor:
- `/root/hermes-agent-legacy-docker/data/scripts/context-monitor.sh` → real: `/opt/data/scripts/context-monitor.sh`
- `/root/hermes-agent-legacy-docker/data/brain/tasks/pending.md` → real: `/opt/data/brain/tasks/pending.md`

El agente del cron no podía leer las fuentes → rellenaba con lo que encontraba (datos viejos reciclados) → "no se actualizan".

## Regla para prompts de cron

Usar SIEMPRE rutas reales del contenedor (`/opt/data/...`). Nunca rutas del host (`/root/hermes-agent-legacy-docker/...`).

## Fuentes reales verificadas (comandos que funcionan)

- Clima Bogotá (Celsius): `curl -s "wttr.in/Bogota?m&format=%C+%t+%f"` → ej. `Fog +10°C +9°C`
- Calendario de hoy: `python3 /opt/data/skills/productivity/google-workspace/scripts/google_api.py calendar list --start <hoy>T00:00:00-05:00 --end <hoy>T23:59:59-05:00` (OAuth ya autenticado; `[]` = sin eventos)
- Actividad real del día: `python3 /opt/data/scripts/daily_session_report.py` (lee state.db; excluye fuentes cron/tui; mínimo 4 mensajes; emite "Sin sesiones de trabajo" si no hubo)
- Tareas pendientes: leer `/opt/data/brain/tasks/pending.md`
- `hermes insights --days 1`: funciona vía `/opt/hermes/.venv/bin/hermes` pero siempre reporta costo "Unknown" (sin datos de pricing) — no usarlo como fuente de costo.

## Formato mínimo accionable (aprobado por el Admin 24/08/2026)

Matutino (máx 10 líneas):
```
🌅 MATUTINO — [fecha]
🌤 Clima Bogotá: [condición] [temp]
📅 Calendario: [evento — hora] · [evento — hora] (o "Sin eventos")
📌 Hoy: [1-3 prioridades de pending.md]
⚠️ Alertas: [solo si algo roto; omitir si nada]
```

Vespertino (máx 12 líneas):
```
🌆 CIERRE DEL DÍA — [fecha]
✅ Hoy: [1-2 líneas: sesiones reales del día según daily_session_report.py]
📌 Pendientes: [1-3 de pending.md]
⚠️ Alertas: [solo si algo roto; omitir si nada]
```

Reglas:
- **NO** incluir métricas de tokens/sesiones/costos — el Admin no las usa.
- **NO** repetir tareas de días anteriores — solo lo de HOY.
- Si no hay nada nuevo/roto → responder EXACTAMENTE `[SILENT]` (el scheduler suprime la entrega).
- El job `guardar-diario-memoria` (23:00) es silencioso y hace el doble guardado (Engram + memoria nativa) con el mismo `daily_session_report.py` como fuente — no tocar; los informes informan, ese job guarda.

## Preferencia del Admin (embedir en futuros jobs)

"Los informes están muy largos, no se actualizan, hay información innecesaria" → mínimo accionable, silencio inteligente, solo alertas reales. El matutino incluye clima + calendario por petición explícita.
