---
name: discord-cron-embeds
description: Format cron reports as Discord embeds with color bars.
version: 1.0.0
author: Ragnar (NeuralCrew Labs)
license: internal
metadata:
  hermes:
    tags: [discord, cron, reporting, embeds, formatting]
    related_skills: [hermes-agent, hermes-scheduled-jobs]
---

# Discord cron embeds (barra de color + semáforo)

## When to Use

- Un cron o script debe entregar su reporte en Discord y se pide el formato con barra de color lateral (tipo watchdog), no texto plano.
- Hay que unificar varios reportes diarios en un solo mensaje visual.
- Un reporte existente necesita semáforo (verde/amarillo/rojo) por umbral.
- No aplica para mensajes conversacionales ni para logs crudos de operación.

## Regla que manda el diseño

El stdout de un cron `no-agent` se entrega como **texto plano**: no puede llevar barra de color. La barra lateral es un **embed** de Discord. Por tanto: o el script postea el embed por su cuenta, o el mensaje llega sin color.

## Token (canónico, verificado)

- Vaultwarden: `vw get "Discord NCA - bot+webhook - prod"` → campo `DISCORD_BOT_TOKEN` (bot id 1493385610797252758, admin del guild NeuralCrew Labs).
- `vw` solo corre como root (lee `/root/.bw-bot.env`). Desde el contenedor usar `ssh dev`.
- Materializar una vez en archivo 600 para que los scripts del cron lo lean sin root:
  ```
  printf "%s\n" "$TOK" > /opt/hermes-agent-data/secrets/discord-nca-bot.token
  chmod 600 ...; chown hermes:hermes ...
  ```
- Nunca imprimir el token en el chat ni en logs. Verificar con `${#TOK}` (longitud), no con echo.

## Envío (sin webhooks)

```python
POST https://discord.com/api/v10/channels/{channel_id}/messages
Authorization: Bot <token>
{'embeds': [embed]}
```

## Pitfall verificado (no repetir)

- **No se puede crear un webhook dentro de un hilo**: `POST /channels/{hilo}/webhooks` devuelve `404 Unknown Channel` aunque `GET /channels/{hilo}` dé 200 con el mismo token. Usar la API del bot directamente.
- Los webhooks existentes en `vps-monitor.env` apuntan a otros canales; no reutilizarlos.
- Si el embed depende de Composio, un fallo de esa API deja el reporte sin entregar. La API de Discord con token propio solo falla si Discord falla.

## Formato (probado)

Embed único, `description` con markdown de Discord:

```
**COSECHADAS HOY** 🟨🟨🟨🟨🟨🟨🟨⬜⬜⬜ **79/114** · 69% · 44 no cosechables

📅 **MES EN CURSO (2026-11)**
**Golden Game · Facebook** · 12.821 vistas (21)

📈 **HISTÓRICO**
...

🎯 **LEADS**
Leads: ...
```

Reglas:
- Barra de 10 bloques: `🟩🟨🟥⬜`, siempre seguida del número exacto (`79/114 · 69%`).
- **Semáforo invertido según la métrica**: cobertura/progreso → lleno = bueno (verde ≥80, amarillo 50-79, rojo <50). Recursos (CPU/RAM/disco) → lleno = malo (rojo ≥85, amarillo 70-84, verde <70). Mezclar las escalas pinta un disco al 92% en verde.
- Color del embed = el del semáforo principal (`0x2ECC71` / `0xF1C40F` / `0xE74C3C`).
- Sección vacía: decir `Sin piezas publicadas aún`, no dejar el bloque en blanco ni inventar.
- Nunca mezclar dominios en un embed: cada watchdog/reporte tiene el suyo (socials ≠ VPS).
- Límites Discord: `description` 4096 chars, título 256, hasta 10 embeds y 25 fields.

## Entrega one-shot a Discord desde una sesión (sin token propio)

Cuando hay que publicar UN mensaje puntual a un canal/hilo y no hay token de bot verificado, no postear a mano: crear un cron de una sola ejecución con `cronjob_manage`:

- `action: create`, `repeat: 1`, `no_agent: true`, `script: <archivo que imprime el mensaje a stdout>`, `deliver: "discord:<guild_id>:<channel_id>"`.
- `no_agent` entrega el stdout verbatim; stdout vacío no envía nada (patrón watchdog). El script imprime el mensaje y nada más.
- Verificar la entrega leyendo la BD, no confiando en el 200 de creación: `sqlite3 /opt/hermes-agent-data/cron/executions.db "SELECT delivery_outcome, error FROM executions WHERE job_id='<id>'"` → debe decir `delivered`. El texto corrido queda en `/opt/hermes-agent-data/cron/output/<job_id>/<timestamp>.md`.
- Si el canal es un hilo, usar el ID del hilo en `deliver` (los hilos aceptan mensajes como canales).

## Flujo de trabajo

1. Función pura `construir_embed(rows, ...) -> dict` (sin red) + pruebas de semáforo, secciones y datos.
2. `--dry-run` que imprime el JSON del embed.
3. `--send --channel <id>` que postea.
4. Enviar UNA muestra real al canal antes de cablear el cron.
5. Recién entonces conectar el cron.

Referencia viva: `planning/calendario-oct2026/social_report_embed.py` (tests en `tests/test_social_report_embed.py`).
