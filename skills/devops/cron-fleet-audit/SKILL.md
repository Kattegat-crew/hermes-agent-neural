---
name: cron-fleet-audit
description: "Use when auditing, consolidating or cleaning a fleet of cron jobs, schedulers and notification channels (Hermes jobs.json, host crontabs, Discord forums). Inventories every trigger, classifies it by real trigger type, and proposes deletions with evidence."
---

# Auditoría y consolidación de flota de crons

## Cuándo usarla
Cuando hay demasiadas notificaciones, crons repetidos, canales ruidosos o informes que dicen lo mismo. También para auditar el trabajo de otro agente antes de darlo por hecho.

## 1. Inventario real (nunca de memoria)

```bash
python3 -c "import json;d=json.load(open('/opt/hermes-agent-data/cron/jobs.json'));print(len(d['jobs']))"
for f in /opt/hermes-agent-data/profiles/*/cron/jobs.json; do echo $f; done
crontab -l | grep -vc '^\s*#'; ls /etc/cron.d/
ssh prod 'crontab -l | grep -vc "^\s*#"; ls /etc/cron.d/'
```

**Pitfall:** en PROD los jobs pueden vivir en otra ruta (`/opt/hermes/data/cron/jobs.json`) repartidos en 13 perfiles. No asumas `/opt/hermes-agent-data`.

## 2. Medir el coste, no estimarlo

```python
# tokens por cron en 7 días (started_at es epoch float, no ISO)
sqlite3 /opt/hermes-agent-data/state.db "select id,title,input_tokens,output_tokens from sessions where source='cron'"
# agrupa por prefijo cron_<jobid>_
```

Ruido real en Discord:
```python
GET /guilds/{g}/threads/active
GET /guilds/{g}/webhooks
GET /channels/{id}/messages?after=<snowflake>
```

## 3. Clasificar por disparador (la decisión clave)

| Tipo | Mecanismo correcto |
|---|---|
| **Tiempo** (informes, saludos, recordatorios por hora) | Cron. La hora ES el disparador. |
| **Evento interno conocido** (buzones, handoffs, publicación) | **Webhook nativo.** El evento ocurre al depositar el dato. |
| **Fuente externa sin push** (SP-API, banco, conciliación) | Cron con frecuencia ajustada. Polling inevitable. |
| **Salida determinista** (informes de plantilla, recordatorios fijos, pico y placa, latidos) | **Script puro + job `no_agent`**, 0 tokens. Nunca un LLM para texto que es siempre igual salvo 3 números. |
| **Estado del sistema** (disco, RAM, gateways) | Cron con umbral + `deliver_only` (0 tokens), despertar el agente solo en transición. |

Hermes trae servidor de webhooks en `:8644` (`/health`) con rutas en `config.yaml` (`hermes webhook list`). Úsalo antes de proponer un buzón con polling.

### Patrón emisor → gate → publicador (para informes multi-host)

1. **Emisor** (en cada host): script puro, escribe JSON con `schema`, `host`, `jornada` — escritura atómica + symlink de "último".
2. **Receptor/gate**: valida esquema y frescura (`mtime_edad_s`); rechaza lo viejo con `valido:false`. Un bloque ausente se publica como `degradado explícito`, nunca como mudo.
3. **Publicador**: ensambla y publica en destino fijo (`destino.json` de una línea). Con destino configurado y fallo → **exit 2** + aviso a un hilo de fallos dedicado (no mezclar con watchdogs); sin destino configurado → exit 0 (arranque, no fallo).

Conversión típica: un cron LLM de ~2.300 tokens/día queda en 0 tokens de ejecución; el coste pasa a ser solo el mantenimiento del script.

## 4. Reglas que casi siempre salen de la auditoría

1. **Silencio por defecto:** un cron sin novedad no escribe nada. Prohibido el "todo OK" diario.
2. **Una alerta es una transición**, no un estado.
3. **Ningún webhook usa `thread_name` dinámico** — genera un hilo huérfano por publicación. Siempre `thread_id` fijo.
4. **Un destino = un webhook.**
5. **Un informe, un emisor.**

## 5. Auditar el trabajo de otro agente (obligatorio antes de aprobar)

Snapshot **antes** (`jobs.json` de todos los perfiles) vs **después**. Nunca contra el reporte del ejecutor:

```python
borrados = [k for k in antes if k not in despues]
criticos = [k for k in borrados if antes[k]['enabled'] and deliver(antes[k]) in ('whatsapp','origin')]
# criticos debe ser 0
```

Verifica también: backup con timestamp, manifiesto con `sha256` del script ejecutado, y que los jobs clave sigan `enabled`.

## 6. Pitfalls comprobados

- **Permisos:** `DELETE /channels/{id}` o `PATCH archived` sin `MANAGE_THREADS` da **403 Missing Permissions** y parece que "no pasó nada". Comprueba con `/users/@me` + `/guilds/{g}/roles` **antes**. El token del entorno puede ser de otro bot: cada perfil tiene el suyo.
- **Hilos de foro:** `POST /channels/{forum_id}/threads` exige `message`; en canal de texto no.
- **No borres un hilo que alimenta un webhook vivo:** archívalo (`archived=true`). Borrarlo hace que la publicación se pierda sin error.
- **Host vs contenedor:** un script que falla por SSH al host puede funcionar dentro del contenedor (intérprete, red de gateways). Prueba en el **mismo contexto** en que corre el cron antes de declarar un fallo.
- **`deliver` es la frontera de seguridad:** todo job con `deliver` `whatsapp:*` u `origin` le habla a una persona. Fuera de cualquier limpieza sin aprobación explícita.

## 7. Coordinación multiagente, fase a fase

- Una fase no avanza hasta que **ambos** la cierren con evidencia verificable (conteos, `404`, `archived=true`, hashes), no con "hecho".
- Cada uno menciona al otro con su **ID real de Discord** al cerrar. Sin mención, la fase no está reportada.
- El que cierra segundo arranca la fase siguiente y dice qué le toca al otro.
- Cada mitad la audita el otro contra el snapshot previo.
