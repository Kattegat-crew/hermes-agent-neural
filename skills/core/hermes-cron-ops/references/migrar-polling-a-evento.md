# Migrar un cron de polling a disparo por evento (webhook)

Procedimiento verificado en la migración real `buzon-from-bob` + `leads-alertas` (23-oct-2026).

## Paso 0 — decidir si aplica

Convierte solo si la causa del job es **un hecho externo**. Si la causa es el reloj (informe de las 08:00, ventana de publicación, cobro mensual), el cron es la herramienta correcta y migrarlo es un error.

Señal de que aplica: el job corre N veces y en la mayoría no encuentra nada. Medirlo con `cron/executions.db` (`completed` vs contenido real en `cron/output/<job>/`), no por intuición.

## Paso 1 — el receptor

Ruta en `platforms.webhook.extra.routes` de `config.yaml`. Requisitos duros:

- **Un secreto por ruta** (no el global). Guardarlo en `/opt/data/secrets/webhook-<ruta>.json` con 600.
- **Ingress privado**: `http://<ip-tailscale>:8644/webhooks/<ruta>`. El puerto escucha en 0.0.0.0 sin firewall de host; el SG del cloud es lo único que bloquea internet — no abrirlo sin TLS delante.
- `deliver_only: true` si el evento solo formatea y publica (coste LLM cero). Sin él, cada evento despierta un agente.
- `toolsets:` mínimo por ruta cuando sí despierta agente.
- **No** poner `events:` si el productor no marca el tipo con fiabilidad: un filtro mal puesto devuelve 200 `ignored` y el fallo es invisible.

## Paso 2 — verificar el receptor sin efectos secundarios

```bash
curl -o /dev/null -w '%{http_code}\n' -X POST http://localhost:8644/webhooks/<ruta> \
  -H 'X-Hub-Signature-256: sha256=deadbeef' -d '{}'
# 401 = ruta viva + HMAC aplicado | 404 = ruta no cargada (¿gateway sin reiniciar?)
```

## Paso 3 — el productor (aquí están las trampas)

1. **Cobertura de caminos**: un módulo con varios comandos que escriben en sitios distintos necesita un emisor por camino. En `agent_exchange.py` se migró `send()` y se dejó fuera `notify()` y `reply()`: el cron no se podía degradar porque seguía siendo el único que veía dos de los tres caminos. Enumerar TODOS los puntos de escritura antes de tocar el cron.
2. **Flags que nadie pone**: un `if env != "1": return` no se activa nunca cuando no existe cron, timer ni `.env` que exporte la variable. Verificar quién invoca el productor (`crontab -l`, `systemctl list-timers`, grep en los scripts) antes de diseñar el flag. Si la invocación es manual, invertir el default (`env.get("X","1") == "0"`).
3. **Permisos del secreto**: si el productor corre como uid 10000 y el secreto quedó `root:root 600`, la lectura falla y el POST se pierde en silencio (best-effort). `chown` al dueño real del ejecutor.
4. **Best-effort obligatorio**: timeout ≤3 s, excepción capturada, el artefacto queda intacto en su cola. Nunca revertir el depósito por un HTTP caído.

## Paso 4 — degradar el cron, no borrarlo

Reducir la frecuencia (no apagar) durante 14 días como red de seguridad para los eventos perdidos con el gateway caído. Solo borrar si tras la ventana no hubo ni un rescate.

## Paso 5 — probar cobertura, no solo transporte

Un E2E que valida firma/latencia/dedupe **no** prueba que todo lo que veía el cron siga generando evento. Comparar hora por hora:

- lo que el cron vio (`cron/output/<job>/AAAA-MM-DD_HH-*.md`, `silent (empty output)` = 0)
- los eventos del receptor (`grep route=<ruta> logs/agent.log`)

Con piso en la hora de activación (antes, el gap es histórico) y descartando sintéticos de QA. Script de referencia: `scripts/leads_coverage_check.py` en el perfil default de DEV. Sin GAP 0 medido, no se degrada.

## Pitfall de medición

Un worker puede cambiar la agenda del cron que se quería proteger mientras una tarjeta está en `running`: bloquear la tarjeta no detiene el proceso. Tras bloquear, re-leer `jobs.json` y revertir si la agenda ya cambió.

## Alternativa nativa y verificación post-migración (24-oct-2026)

- **Feature nativa a evaluar antes del próximo webhook a mano:** Hermes v0.22.5 trae workflows MCP disparados por eventos (experimental): un servidor MCP compatible notifica y el gateway lanza la corrida, sin cron sondeando. Mientras siga experimental, el patrón webhook + cron de respaldo de esta referencia es el canónico; para la próxima conversión (leads → radar DIAN → watchdog_ap, ese orden) comparar primero contra la doc oficial estable.
- **Pendientes abiertos de la migración 23-oct:** bajar `leads-alertas` de `0 7-22` a catch-up diario (su E2E t_12e8058a está done); registrar `/opt/data/secrets/webhook-*.json` en Vaultwarden (quedó pendiente, `bw status` unauthenticated); 14 días de observación antes de apagar redes de seguridad.
- **Verificación en vivo del estado de tarjetas/crons:** estado Kanban en `/opt/data/kanban.db` tabla `tasks` (campos `id`, `title`, `status` — NO existe tabla `cards`); abrir con `sqlite3 'file:...?mode=ro' uri=True`. Agenda vigente de un job: `schedule.kind` (`cron`+`expr` / `interval`+`minutes`) en `/opt/data/cron/jobs.json`. NO buscar DBs con glob recursivo sobre `/opt/hermes-agent-data` (tiempos fuera >60 s): apuntar directo a las rutas conocidas.
