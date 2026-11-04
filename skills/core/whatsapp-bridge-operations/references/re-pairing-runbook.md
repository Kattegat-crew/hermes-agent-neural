# Re-emparejamiento del bridge WhatsApp (logout 401 / device_removed)

Caso real: 27/08/2026 — `stream:error 401 conflict device_removed` en bridge.log → WhatsApp desvinculó el dispositivo server-side sin que nadie tocara el teléfono. Causa raíz: 2 instancias peleando por la misma sesión (contenedor + host).

## 0. Diagnóstico (VERIFICADO)
- `curl -m 3 127.0.0.1:3000/health` sin respuesta = bridge abajo.
- `grep device_removed /opt/data/whatsapp/bridge.log` = WhatsApp sacó el dispositivo. NO lo causa enviar mensajes (envíos previos sin incidente lo confirman).
- Timestamps del log son epoch ms (pino). Convertir a Bogotá:
  `datetime.fromtimestamp(ts/1000, timezone(timedelta(hours=-5)))`
- **Detectar instancia duplicada (causa raíz):** hostnames en bridge.log — `de051af38d62` = contenedor, `vmi*` = proceso en el HOST. Si hay dos, pedir a Chucho `pgrep -af bridge.js` en el host y matar el duplicado ANTES de re-emparejar (si no, WhatsApp vuelve a castigar).

## 1. Backup sesión vieja (VERIFICADO)
```bash
mv /opt/data/whatsapp/session /opt/data/whatsapp/session.bak-logout-$(date +%Y%m%d)
```

## 2. Emparejamiento por código (NO QR)
- QR bloqueado desde Colombia. Script: `node /opt/data/scripts/whatsapp-bridge/pair-code.js 573166910728` → imprime `{"event":"pairing_code","code":"XXXXXXXX"}`.
- Parches ya aplicados al script: browser profile Ubuntu/Chrome estándar + espera de socket listo antes de `requestPairingCode` (sin eso sale "Connection Closed").
- El código vive ~60 s. Generarlo SOLO con el teléfono ya en WhatsApp → Ajustes → Dispositivos vinculados → Vincular con el número de teléfono. Coordinar con el usuario: él avisa "listo", tú generas y pasas el código.

## 3. Cooldown (VERIFICADO — pasó de verdad)
- Intentos seguidos → enfriamiento 5-15 min: "Connection Closed" silencioso y en el teléfono "intente más tarde".
- UN intento limpio por ventana. Bucles de códigos empeoran el enfriamiento (10 intentos seguidos fallaron todos; tras esperar 5 min, el código se generó limpio).

## 4. Verificar registro (VERIFICADO END-TO-END 28/08)

```bash
python3 -c "import json; c=json.load(open('/opt/data/whatsapp/session/creds.json')); print(c.get('registered'), bool(c.get('account')))"
```
Tras el QR exitoso del 28/08 quedó `registered: False, account: True` y el bridge conectó igual — no confiar solo en `registered`; el test real es `/health` → `connected`.

## 2bis. Alternativa QR (pair-qr.js, verificada 28/08)

QR está bloqueado desde Colombia SOLO para generar código en la app del teléfono; el ESCANEO de QR por la app SÍ funciona. `node /opt/data/scripts/whatsapp-bridge/pair-qr.js` escribe un QR PNG rotativo en `/opt/data/workspace/whatsapp-qr.png` (~50s por código; relanzar en bucle si expira). Requiere symlink `node_modules/qrcode` → `/opt/hermes/node_modules/qrcode` (ya creado). Log: `/tmp/qr-pair.log` dentro del contenedor.

## 6. Pitfalls nuevos (28/08, operación real)

- **pair-code.js bug de versión (CORREGIDO)**: `fetchLatestBaileysVersion()` devuelve `{version:[...], isLatest}` — pasar el objeto crudo a `makeWASocket` truena `config.version.join is not a function` y el script cuelga EN SILENCIO (cero output, exit 0 aparente). Fix aplicado: desempaquetar `Array.isArray(_v) ? _v : _v.version`. bridge.js no lo necesita (usa `createVersionResolver`).
- **Sesión creada root-owned**: correr el pairing via `docker exec` crea `/opt/data/whatsapp/session/` como root → el bridge (UID 10000) crashea en loop con `EACCES creds.json`. Fix OBLIGATORIO antes de reiniciar el gateway: `docker exec -u root hermes-agent chown -R hermes:hermes /opt/data/whatsapp/session`.
- **Gateway parked**: si el gateway estaba vivo cuando la sesión murió, el bridge queda estacionado y NO reintenta solo → tras el pairing exitoso reiniciar el gateway: `s6-svc -r /run/service/gateway-default` (mata turnos en curso — hacerlo en punto muerto).
