---
name: email-report-cron-aggregator
description: "Use when aggregating daily email reports via cron to chat."
tags: [gmail, cron, informe, agregacion, whatsapp, parser, oauth, kassiuss]
version: "1.0.0"
author: Ragnar
license: MIT
metadata:
  hermes:
    tags: [gmail, cron, informe, agregacion, no_agent, whatsapp]
    category: devops
    related_skills: [cron-runtime-verification, cron-watchdog-scripts, whatsapp-bridge-operations, cron-delivery-routing, vps-ops]
---

# Patrón: Informe diario agregado desde correos → Cron incremental → WhatsApp

## When to Use

Cuando un cliente recibe cada día N correos con tablas (informes de venta, caja,
producción…) y hay que agregarlos en un informe consolidado entregado por chat
cada mañana. Caso origen: **Venta Diaria Golden Game** (7 informes KASSIUSS →
perfil helmer, PROD). Aplica a cualquier tabla HTML en correo Gmail que se quiera
consolidar a diario.

## Arquitectura general (las 5 piezas)

1. **Fuentes** — N buzones Gmail (credenciales OAuth en `/opt/data/secrets/*.json`).
   Cada buzón puede mandar un subconjunto de sedes.
2. **Parser de tabla HTML** — extrae el cuerpo del correo (usa el HTML payload de
   Gmail) y parsea la tabla; cada zona tiene una fila de totales que suele
   coincidir con un patrón (`^\d{0,4}\s*Maquinas` o similar).
3. **Agregador** — une las sedes de todos los buzones, calcula el consolidado
   (suma por columna) y formatea en es-CO (punto separador de miles).
4. **Motor de disparo** — script determinista con ventana horaria y dedup por
   (fecha, sede): envía la base a la hora ancla, luego cada tick envía lo que
   falta apenas llegue. stdout vacío = silencioso.
5. **Cron no_agent** — en el perfil del cliente (no en default), entrega por
   `deliver: whatsapp:<chat_id>` o `deliver: origin`.

## Formato de informe (recomendado)

```
📊 *TITULO* — <Dia DD-Mon-YYYY> · n/N sedes
• SEDE — Ingresos $x · Pagos $y · Venta $z
...
*CONSOLIDADO*
Ingreso total: $A
Pagos totales: $B
Venta total:   $C
```

## Motor de disparo (logica v2) — la parte delicada

### Ventana y ancla (minuto-consciente)

Constantes: `HORA_BASE = 710` (hhmm = 07:10), `VENTANA_INI = 5`, `VENTANA_FIN = 13`.

```python
hhmm = now.hour * 100 + now.minute
if hhmm < VENTANA_INI * 100 + 45 or hhmm > VENTANA_FIN * 100 + 30:
    sys.exit(0)  # fuera de ventana, silencioso
if hhmm < HORA_BASE:
    sys.exit(0)  # antes del ancla, no enviar aun
```

**PITFALL CRÍTICO:** NO usar `now.hour < HORA_BASE` con `HORA_BASE` en formato
hora simple (7 o 10). Un ancla 07:10 no es la hora 7 ni sirve la hora 10; si
comparas solo `hour` con `HORA_BASE=10`, bloquea todo hasta las 10:00 AM.
Siempre comparar `hhmm` (hora*100+minuto) contra un `HORA_BASE` en formato hhmm.

### Envío base + faltantes (dedup)

- **Primer tick a las 07:10** — envía la BASE: todas las sedes disponibles + su
  consolidado + lista de PENDIENTES (las que faltan).
- **Ticks siguientes (cada 5 min)** — si llegó una sede que no se había enviado,
  envía ESE faltante (con sus totales) + consolidado actualizado. Una sola vez.
- **Dedup** por `(fecha, sede)` en un archivo de estado JSON junto al script
  (`kassiuss_state.json`). Cuando las N sedes están enviadas → stdout vacío.
- **Cron no_agent entrega stdout verbatim:** stdout vacío = silencioso. Esta es
  la clave para que el tick no spammee: el script solo imprime cuando hay algo
  nuevo que enviar.

### Fecha objetivo y filtro Gmail (por recepcion)

- El informe de un día `dd` se **recibe** la mañana de `dd+1` (asunto con la fecha
  del día anterior al que llega).
- El filtro `after:/before:` de Gmail es por **recepción**, NO por fecha del asunto.
  Usar rango holgado: `dd-1 .. dd+2`, y luego matchear el subject por sufijo.
  Si filtraste por la fecha del asunto (ej. solo `dd`), no encontrará nada.
- `fecha_objetivo() = hoy - 1` (asumiendo informe diario que se recibe al día
  siguiente). Verificar con el cliente antes de asumir.

## Parser Gmail (con token de servicio)

```python
def token(path):
    cred = json.load(open(path))
    # refresh con google.oauth2.credentials.Credentials; scopes vienen como STRING
    # -> envolver en lista. Ver skill google-oauth-reauth-ops.
    ...
def api(url, tok):
    # GET con Authorization; retry en 403/429 con sleep
    ...
```

Listar correos: `GET gmail/v1/users/me/messages?q=<query>` → `id` →
`GET .../messages/<id>?format=full` → `payload.parts` (o `payload.body`) que
tienen `mimeType: text/html`, decodificar base64url y parsear la tabla.

**Evitar rate limit:** para N correos, no descargar todos de una vez. Filtrar en
la query por `from:` y rango de fechas, y `maxResults` acotado (50). Entre mensajes,
un pequeño sleep.

## Instalación en PROD (perfil del cliente, no default)

1. Subir el script al dir de scripts del perfil: `scp kassiuss.py prod:/opt/data/
   profiles/<cliente>/scripts/`
2. `chown 10000:10000` + chmod 755. Verificar sintaxis con setpriv como hermes.
3. Crear el cron APUNTANDO AL PERFIL: `hermes -p <cliente> cron create ...`
   (el flag `-p` es el que garantiza que el job cae en el perfil correcto).
4. `--no-agent`, `--script <nombre.py>` (relativo a `~/.hermes/scripts/` del
   perfil), `--deliver whatsapp:<chat_id>`.
5. Probar el script instalado como hermes (setpriv reuid 10000) ANTES de
   confiar el cron; si el gateway del perfil figura stopped, el scheduler
   multiplexor del default igualmente tickea los jobs (verificar cron TRM
   existente del mismo perfil: si disparó, tu job también).

## Entrega WhatsApp (si el perfil tiene platforms.whatsapp.enabled: false)

No es un problema: el ruteo real es por el **bridge compartido** del PROD
(`platforms.whatsapp.bridge_script: /opt/data/scripts/whatsapp-bridge/bridge.js`,
`enabled: true`) + `gateway.profile_routes` (chat_id → profile). El perfil del
cliente entrega igual con `deliver: origin` (chat ligado al perfil) o con
`deliver: whatsapp:<chat_id>` explícito. Ver skill whatsapp-bridge-operations.

## Verificacion (antes de confiar el cron)

1. En seco sobre un día completo (asunto de ayer): debe imprimir n/N con consolidado.
2. Threshold horario: mockear la hora y confirmar que antes del ancla es silencioso.
3. Instalado como hermes en PROD: exit 0.
4. Cron creado con `-p <perfil>`: verificar el id y `deliver` en jobs.json.

## Herramientas del caso (ejemplo real)

- `gtable.py` — parser de tablas HTML KASSIUSS (busca tabla, matchea fila totales).
- `gsearch.py` / `gfetch.py` — helpers Gmail.
- `kassiuss_diaria.py` — agregador + motor v2 completo (script de referencia).

## Pitfalls

- Descargas masivas de correos → rate limit Gmail (429). Filtrar por fecha y from.
- `after/before` de Gmail es por recepción, no por fecha del asunto.
- Ancla horaria: comparar hhmm, jamás solo hour.
- El cron no_agent entrega stdout; si quieres silencio, devuelve stdout vacío.
- El script corre como uid 10000 (hermes); nunca dejar archivos root-owned.
- Formato moneda es-CO: punto como separador de miles (no coma).
- Confirmar la semantica de cada columna con el cliente (ej. Venta = Neto/A
  Consignar, no Bruto) antes de definir el informe.
