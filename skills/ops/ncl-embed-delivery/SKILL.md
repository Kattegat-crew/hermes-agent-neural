---
name: ncl-embed-delivery
description: "Cron a Discord: embed canónico ncl-embed/1."
version: 1.0.0
author: Ragnar (NeuralCrew Labs)
license: proprietary
metadata:
  hermes:
    tags: [discord, embed, cron, delivery, formato]
    related_skills: [discord-server-ops, hermes-agent]
---

# Entregas de cron a Discord con embed canónico

## When to Use

- Vas a crear o modificar un cron cuyo destino es un canal o hilo de Discord.
- Un cron existente entrega texto plano y debe pasar al formato embed.
- Necesitas publicar un informe puntual con el formato aprobado por el Admin.

Toda entrega de cron a un canal o hilo de Discord de NeuralCrew Labs se publica como **embed**
con `ncl_embed.py`, no como texto plano. El adapter de Discord de Hermes manda `content` plano a
propósito (`plugins/platforms/discord/adapter.py:5681`: «embeds can be invisible/detached on
web/mobile»), así que el embed se publica por REST del bot, no por el gateway.

## Helper

`/opt/hermes-agent-data/scripts/ncl_embed.py` — contrato `ncl-embed/1`.
Tests: `/opt/hermes-agent-data/scripts/tests/test_ncl_embed.py`.

## Paleta y formato canónico

| estado | color | emoji |
|---|---|---|
| ok | 3066993 | 🛡️ |
| warn | 16776960 | ⚠️ |
| error | 15158332 | 🚨 |
| info | 3447003 | ℹ️ |
| neutral | 9807270 | 🗂️ |

- **Título**: `<emoji> <Job> — <fecha o alcance>`. Si el título ya empieza con emoji, no se duplica.
- **Fields**: `nombre=valor`, inline por defecto, máx 25 (el helper recorta y añade «➕ Más»).
- **Footer**: `NeuralCrew Labs · <módulo>`.
- **Timestamp**: ISO UTC automático; no lo pases salvo que simules un informe histórico.
- **description**: contexto en 1-2 líneas; no metas volcados de log.

## CLI

```bash
python3 /opt/hermes-agent-data/scripts/ncl_embed.py \
  --channel 1564308156044279938 \
  --title "Informe de ventas — 14 nov" --status ok \
  --desc "Resumen del día" \
  --field "Pedidos=12" --field "Ingreso=USD 1.240" \
  --footer "NeuralCrew Labs · Amazon AU"
```

- `--dry-run` imprime el payload y no toca la red.
- `--spec-file spec.json` o `--spec-file -` para un spec emitido por otro script.
- `--quiet` no imprime nada si el envío sale bien.

## Migrar un job `--no-agent`

Antes el script imprimía el mensaje y Hermes lo entregaba como texto:

```python
print(f"Informe {fecha}: {n} pedidos")
```

Ahora el script publica el embed y deja el stdout para diagnóstico:

```python
from ncl_embed import post_embed, embed_from_spec
embed = embed_from_spec({
    "title": f"Informe de ventas — {fecha}",
    "status": "ok" if fallos == 0 else "warn",
    "fields_raw": [f"Pedidos={n}", f"Fallos={fallos}"],
    "footer": "NeuralCrew Labs · Amazon AU",
})
post_embed("1567216974113542184", embed)
print(f"diagnóstico: {n} pedidos, {fallos} fallos")  # ya no es la entrega
```

## Reglas duras

- **Un solo helper.** Prohibido crear webhooks nuevos por job o improvisar `curl` a la API.
- **Token.** `resolve_token()` busca entorno → fuente de secretos del perfil → `.env` legado. No
  hardcodear tokens en scripts ni en crons.
- **Verificar.** Tras publicar, releer el mensaje y confirmar `embeds[0].fields`. Un HTTP 200 no
  prueba que quedó bien armado.
- **Telegram/WhatsApp no aplican.** Ahí se mantiene texto con emojis y negritas.
- **Nunca** poner tracebacks, tokens ni rutas de secretos en un field: el embed es público para el guild.

## Pitfalls

- `content` vacío + embed: si el consumidor lista mensajes por texto, el mensaje sale en blanco.
  Cuando el destinatario humano necesita verlo en notificaciones, añade `content` con una línea
  corta (`post_embed(..., content="Backup DEV SUCCESS")`).
- El bot necesita `Send Messages` + `Embed Links` en el canal destino. Un 403 casi siempre es eso.
- Hilos archivados: la REST acepta publicar en un hilo archivado y lo desarchiva; el canal padre
  no. Verifica el `channel_id` del hilo, no el del foro.
- Mensajes de webhook (como el backup) no los puede editar el bot: para corregir hay que republicar.
