---
name: hermes-cron-ops
description: >-
  Creación, diagnóstico y verificación en vivo de tareas cron en Hermes. Manejo de namespaces (host vs contenedor), watchers, entregas a Discord y auditoría de jobs programados.
tags: [cron, scheduler, hermes, discord, nsenter, watchdog, vigia, devops]
version: 2.0.0
author: NeuralCrew / Hermes Fleet
---

# Operaciones y Verificación de Cron en Hermes

Habilidad canónica para gestionar, depurar y auditar todas las tareas programadas (cron jobs) de la flota de agentes Hermes, garantizando entregas fiables a Discord y consistencia en los entornos de ejecución.

---

## Cuándo usar esta Skill (Triggers y Síntomas)

Usa esta skill inmediatamente cuando se presente cualquiera de estas situaciones:
- Peticiones del usuario: *"por qué falló la tarea de la noche"*, *"el cron no mandó el reporte a Discord"*, *"crea un cron para vigía"*, o *"audita las tareas programadas"*.
- Diagnóstico de jobs que aparecen como activos pero no producen salida o fallan con errores de permisos (`Errno 13`) o archivos no encontrados (`ENOENT`).
- Configuración de alertas automáticas, watchdogs y entrega de reportes recurrentes.

---

## Arquitectura de Ejecución: La Trampa de los Dos Tickers

Un job en Hermes puede ser reclamado por uno de dos planificadores con vistas de sistema de archivos completamente distintas:

| Ticker / Planificador | Usuario | Resolución de `/opt/data` |
|---|---|---|
| **Gateway (`gateway-default`, s6)** | `uid 10000` (namespace contenedor) | El árbol compartido real del contenedor (`/opt/data`). |
| **Root ticker (Hermes Desktop / Host)** | `root` (namespace del host) | Directorio del host; el árbol real vive en `/root/hermes-agent-legacy-docker/data` o montaje persistente. |

**Consecuencia**: Un script que hardcodea `/opt/data/...` funciona si lo reclama el gateway, pero muere con `FileNotFoundError` si lo reclama el host.

### Regla para Wrappers de Cron
Todo script wrapper de cron debe auto-detectar su entorno antes de ejecutar:

```bash
IN_CONTAINER=0
[ -f /.dockerenv ] && IN_CONTAINER=1

run_cmd() {
  if [ "$IN_CONTAINER" = "1" ]; then
    bash -c "$1"
  else
    docker exec -u 10000 hermes-agent bash -c "$1"
  fi
}
```

---

## Verificación en Vivo bajo Namespaces (`nsenter`)

Para diagnosticar exactamente lo que ve el contenedor del gateway sin suposiciones:

```bash
# 1. Obtener el PID del proceso gateway
G_PID=$(pgrep -f "hermes.*gateway" | head -1)

# 2. Entrar al namespace de montaje y usuario (uid 10000)
nsenter -t $G_PID -m -S 10000 -u -- python3 -c "import os; print(os.listdir('/opt/data'))"

# 3. Comprobar permisos de escritura reales
nsenter -t $G_PID -m -S 10000 -u -- touch /opt/data/cron/output/test_write.tmp && rm -f /opt/data/cron/output/test_write.tmp
```

Si el comando falla con permisos, reparar desde el host:
```bash
chown -R 10000:10000 /opt/data/cron/output/
```

---

## Herramientas y Scripts Incluidos en esta Skill

Esta skill contiene herramientas operativas listas en su subcarpeta `scripts/`:

1. **Auditoría de flota de cron**:
   ```bash
   python3 /opt/hermes-agent/skills/core/hermes-cron-ops/scripts/cron_fleet_audit.py
   ```
2. **Watchdog de ejecución y fallback**:
   ```bash
   python3 /opt/hermes-agent/skills/core/hermes-cron-ops/scripts/fallback_watchdog.py
   ```
3. **Verificación de webhook de Discord**:
   ```bash
   python3 /opt/hermes-agent/skills/core/hermes-cron-ops/scripts/discord_verify_webhook.py --url "$DISCORD_WEBHOOK_URL"
   ```

---

## Gotchas y Errores Críticos Detectados en Producción

1. **Archivos creados por root**: Si ejecutas pruebas manuales como `root` que escriben en `/opt/data`, dejas trampas de sólo lectura para `uid 10000`. Siempre haz `chown -R 10000:10000` en los archivos creados.
2. **Serialización de terminal background**: Al lanzar procesos en segundo plano con `terminal(background=True, notify=True)`, el valor `notify` debe ser booleano estricto. Si se serializa como cadena `"True"`, el runtime arroja error.
3. **Salida limpia para eventos accionables**: Los cron jobs no deben imprimir basura en stdout si no hay error; solo emitir salida cuando requieran acción para no saturar los canales de alerta.
