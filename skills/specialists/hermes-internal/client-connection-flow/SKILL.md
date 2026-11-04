---
name: client-connection-flow
description: "Use when a new client needs Google accounts connected."
tags: [clientes, onboarding, oauth, activepieces, conexiones, google, mcp, secrets]
version: "1.0"
author: Ragnar
created: 2026-08-28
category: devops
metadata:
  hermes:
    tags: [clientes, onboarding, oauth, activepieces, conexiones, google]
    related_skills: [oauth-connection-gateway, activepieces-connection-api, google-workspace]
---

# Client Connection Flow — alta y conexión de clientes (Google → AP → agente)

## When to Use

- "Agregar un cliente nuevo", "conectar su correo/cuentas", onboarding a ActivePieces.
- Reconectar cuentas de cliente existente (usar `?force=1` solo si Jonathan aprueba).

## Reglas duras

1. **NUNCA conectar a ciegas**: primero REGISTRAR el tenant (Fase 0), luego invitar.
2. **externalId es clave única en AP** — reconectar sobre el mismo nombre SOBRESCRIBE. La conexión debe estar `pending` en el mapa antes de invitar.
3. **Slugs reservados** (neuralcrew, jonathan, chucho, perfiles de bots) nunca para clientes. Segundo correo del cliente = `-gmail2`, jamás reusar el nombre del primero.
4. Los scripts corren como usuario `hermes` (NO docker exec root — root no tiene claves SSH a prod).

## El proceso (SOP completo: /opt/data/plans/SOP-CONEXION-CLIENTES-GOOGLE.md)

1. **Alta tenant** (con OK de Jonathan):
   ```bash
   python3 /opt/data/scripts/provision_client.py --slug <slug> --empresa "<nombre>" \
       --email <correo-cliente> --owner <perfil-agente> --services gmail,drive,calendar
   ```
   → chequea colisiones (mapa + DB AP), crea entries `pending`, genera link de invitación + borrador de correo, sync prod.
2. **Invitación** (Fase 1): enviar correo con el link `https://connect.neuralcrewlabs.com/?connection=<slug>-gmail` usando el script oficial:
   ```bash
   python3 /opt/data/scripts/send_client_invite.py --slug <slug> --email <correo> --nombre <nombre> --empresa <empresa>
   ```
   → envía desde `captain@neuralcrewlabs.com` con formato Chucho (3 tarjetas, firma Founder). Ver `oauth-connection-gateway` para el estándar de formato. Solo enviar con OK de Jonathan.
3. **Cliente conecta** (Fase 2): clic → Google → callback crea la conexión DENTRO de AP. No intervenir.
4. **Verificación (Fase 3) — AUTOMÁTICA desde 28/08**: el cron `sync-connections-map` (cada 30 min) ejecuta `verify_pending()`, que verifica toda conexión `pending` del mapa (`verify_connection.py`): descifra AP, refresca contra Google, **compara cuenta real vs registrada** (🚨 ALERTA si mismatch = cliente usó otra cuenta), materializa `secrets/<conn>.json`, marca `active` + sync a las 3 copias. Timeline: cliente autoriza → ≤30 min el agente ya opera. Manual solo si Jonathan pide activación inmediata:
   ```bash
   python3 /opt/data/scripts/verify_connection.py <slug>-gmail
   ```
5. **Asignación agente** (Fase 4): owner en el mapa gobierna quién la usa (`ap_call.py` valida). Si el cliente tiene perfil Hermes propio: MCP Engram `--project neuralcrew-<slug>`, copiar bloque providers al config, `chown -R 10000:10000`, ruta de canal en `gateway.profile_routes`.
6. **Cierre** (Fase 5): correo de confirmación al cliente + reporte a Jonathan.

## Verificación

- Mapa actualizado con `status: active` + `cuenta_verificada` (el correo REAL que autorizó el cliente).
- AP DB: `SELECT "externalId", status FROM app_connection WHERE "externalId" LIKE '<slug>-%';` → ACTIVE.
- Gate G1: `curl https://connect.neuralcrewlabs.com/go?connection=<slug>-gmail` sobre conexión activa debe devolver el error anti-sobrescritura (sin `&force=1`).

## Cablear el MCP bridge (Fase 4.5 — la última milla)

Las conexiones quedan `active` en AP, pero el bot del cliente **NO puede usarlas** hasta que tenga un MCP server que exponga las tools (Gmail/Drive/Calendar). Sin esto, la conexión existe pero es inerte.

### MCP server `ncl_google_mcp.py`

- **Script:** `/opt/data/scripts/ncl_google_mcp.py` (stdio MCP, stdlib puro, sin dependencias)
- **Tools:** `gmail_list`, `gmail_send`, `drive_search`, `drive_read_text`, `calendar_list_events`
- **Ownership enforcement:** detecta `HERMES_HOME` → basename = perfil → valida que `{perfil}-{svc}` sea owner en el mapa → rechaza si no. Misma lógica que `ap_call.py`.
- **Credenciales:** lee `/opt/data/secrets/{conexion}.json` (materializadas por `verify_connection.py` al marcar `active`). OAuth refresh automático.

### Deploy en prod

1. **Secrets:** `verify_connection.py` ahora escribe `/opt/data/secrets/{slug}-{svc}.json` (chmod 600, account/refresh/client_id/secret) al marcar `active`. Para conexiones existentes: re-ejecutar `verify_connection.py <slug>-<svc>` sin `--no-write`.
2. **Sync a prod:** `sync_connections_map.py` propaga mapa + secrets a las 3 ubicaciones:
   - `/opt/connect-neuralcrew/connections-map.json` (gate)
   - `/opt/hermes/data/connections-map.json` (agente prod)
   - `/opt/hermes/data/secrets/` (credenciales del MCP)
3. **Config del perfil** (en `profiles/{slug}/config.yaml` de prod):
   ```yaml
   mcp_servers:
     engram:
       command: engram mcp
       args: [--project, neuralcrew-{slug}]
     ncl_google:
       command: python3
       args: [/opt/data/scripts/ncl_google_mcp.py, --profile, {slug}]
       env:
         NCL_MAP: /opt/data/connections-map.json
         NCL_SECRETS: /opt/data/secrets
   ```
4. **Restart:** en prod multiplexado, `s6-svc -r /run/service/gateway-default` (todos los perfiles). En prod con gateways perfiles: reiniciar el específico (`gateway-{slug}`).

### Verificación post-deploy

```bash
# MCP list (debe mostrar ncl_google como enabled):
hermes -p {slug} mcp list

# Test funcional — SIEMPRE en lenguaje natural (como hablaría el cliente):
hermes -p {slug} chat "búscame la lista de nóminas"
```

NUNCA probar con "usa drive_search para..." — eso enmascara el fallo real: que el bot no sepa que tiene las cuentas.

### Auto-descubrimiento (Fase 4.6 — el agente "ya sabe" que tiene las cuentas)

Caso real (Rosita/Nancy, 28/08): conexiones `active` + MCP cableado, pero la clienta tuvo que decirle al bot "busca con el mcp de active pieces" — y el bot mencionó ActivePieces al cliente. Causa: las tools MCP quedan tras el catálogo deferred (progressive disclosure) y el SOUL no afirmaba el acceso en lenguaje natural. Cablear el puente NO basta.

**Solución en 3 capas (cero menciones de infra al cliente):**

1. **SOUL.md** — bloque `## Tus Cuentas Conectadas (Google de X)` en lenguaje natural: "tienes acceso directo y real a su correo, sus archivos y su agenda; cuando te pida 'revisa mi correo', hazlo tú directamente; nunca le digas que no tienes acceso ni le menciones sistemas internos". Tools reales entre paréntesis.
2. **Descripciones de tools en lenguaje de negocio** — en `ncl_google_mcp.py` las `description` hablan de "el correo de X", no de MCP/servidores.
3. **Inyección automática** — `inject_soul_cuentas.py` (idempotente, sentinel `<!-- cuentas-conectadas -->`) es llamado por `verify_connection.py` cuando la conexión pasa a `active`. Para perfiles ya activos sin el bloque: `python3 /opt/data/scripts/inject_soul_cuentas.py --perfil <slug> --empresa "<nombre>"`.

**E2E aceptado:** el bot ejecuta "búscame la nómina" directo, sin nombrar infra, sin pedir instrucciones, sin "no tengo acceso".

Pitfalls: (1) no citar tool names que no existen (`gmail_read` NO existe; reales: `gmail_list`, `gmail_send`, `drive_search`, `drive_read_text`, `calendar_list_events`); (2) el bloque SOUL debe insertarse ANTES de las reglas del SOUL, no al final; (3) al reescribir descripciones de tools, mantener los nombres de parámetros intactos (solo cambia `description`).

## Pitfalls

- **Mapa 3 copias:** dev `/opt/data/connections-map.json` (fuente de verdad) → prod gate `/opt/connect-neuralcrew/connections-map.json` → prod agente `/opt/hermes/data/connections-map.json`. `sync_connections_map.py` propaga a las 2 de prod; si editas a mano en dev, sync automático cada 30 min.

- **⛔ INCIDENTE REAL (10-sep-2026): el sync REVIRTIÓ concesiones hechas en prod.** Bob (perfil `default` en prod) había agregado `helmer` y `yulieth` a los `owners` de `lucky-*` editando **prod**. Al día siguiente el sync (dev→prod) copió el mapa de dev — que no tenía esos owners — y **borró las dos concesiones**. Yulieth quedó con **0 cuentas** (agente ciego) y helmer perdió Lucky. Síntoma: `accounts_list` del MCP devuelve menos cuentas de las esperadas. Diagnóstico: comparar `/opt/hermes/data/backups/connections-map.json.bak-*` contra el estado actual — los backups delatan qué se perdió.

  **FIX APLICADO (10-sep, en `sync_connections_map.py`):**
  1. `build_merged(dev_bytes)` — antes de empujar, fusiona **dev ∪ prod**: `owners` se **UNEN** (`sorted(set(dev) | set(prod))`), dev manda en status/cuenta/owner, y conexiones solo-prod se preservan con aviso. El merge se escribe también en el mapa dev (converge).
  2. `sync_agent_maps()` — se llama SIEMPRE (no solo cuando `sha(dev)!=sha(gate)`): con `cmp -s gate agent || cp gate agent` por cada agent map. Antes, un cambio hecho en prod dejaba el gate correcto pero el **agent map viejo** → conexión ACTIVE en AP pero **INERTE** para el bot.
  3. `verify_pending()` comparaba `v.get('estado')` — el campo real es **`status`**; nunca encontraba pendientes. Corregido.

  **⚠️ Consecuencia de la unión: las REVOCACIONES requieren editar dev Y prod.** El union-only hace que quitar un owner solo en dev no se propague. Para revocar: quitar el owner en `/opt/data/connections-map.json` **y** en prod gate, luego sync.

  **⏰ WATCHDOG DE DIVERGENCIA (10-sep-2026, cron `sync-connections-map` cada 30 min):** el sync vigila los campos `status`, `cuenta`, `cuenta_verificada`, `empresa`, `tenant` (todo menos `owners`/`owner`). Si **prod tiene en uno de esos campos algo que dev NO tiene** (dev lo tiene vacío o ausente), el valor se guarda en `/opt/data/connections-map.divergencias.json` y el cron **alerta por WhatsApp** antes de sobrescribirlo — la firma es: `⚠️ DIVERGENCIA de conexiones: prod tenía datos que dev no.` Además avisa de conexiones **solo-prod** (preservadas pero hay que bajarlas a dev).

  **Política de salida (watchdog):** el script es **SILENCIOSO** cuando todo está en sync. Solo imprime (y por tanto solo envía mensaje, `deliver=whatsapp`) en: divergencia, conexión solo-prod, sync ejecutado, verify que activó algo, o error. Nunca agregar `print()` de rutina — cada print ES un mensaje al usuario.

  **Verificación obligatoria tras tocar owners:** correr `accounts_list` del MCP de cada perfil afectado (patrón probado) y comparar contra la lista esperada — NUNCA confiar en el sha del mapa ni en que "active" en AP signifique que el bot lo ve.

  ```bash
  # probe real por perfil (corre en prod, dentro del contenedor)
  P=helmer
  ssh prod "docker exec -e HERMES_HOME=/opt/data/profiles/$P -e NCL_MAP=/opt/data/connections-map.json \
    -e NCL_SECRETS=/opt/data/secrets hermes-agent bash -c \
    'printf \"%s\n\" \"{\\\"jsonrpc\\\":\\\"2.0\\\",\\\"id\\\":1,\\\"method\\\":\\\"initialize\\\",\\\"params\\\":{\\\"protocolVersion\\\":\\\"2024-11-05\\\",\\\"capabilities\\\":{},\\\"clientInfo\\\":{\\\"name\\\":\\\"t\\\",\\\"version\\\":\\\"1\\\"}}}\" \"{\\\"jsonrpc\\\":\\\"2.0\\\",\\\"method\\\":\\\"notifications/initialized\\\"}\" \"{\\\"jsonrpc\\\":\\\"2.0\\\",\\\"id\\\":2,\\\"method\\\":\\\"tools/call\\\",\\\"params\\\":{\\\"name\\\":\\\"accounts_list\\\",\\\"arguments\\\":{}}}\" | timeout 30 python3 /opt/data/scripts/ncl_google_mcp.py --profile $P'"
  ```

- **Mapa de owners esperado (verificado 10-sep-2026):** nancy→`nancy-*`; jacqueline→`jacqueline-*`; yulieth→`lucky-*`; helmer→`helmer-*` + `golden-*` + `lucky-*` (9 cuentas; es gerente de Golden Game y Lucky Brothers); default/Bob→todas. `ivan`/`alejandro` sin conexiones. Los perfiles `golden` y `lucky` NO existen en prod — sus entradas legacy (`golden-gmail2`) son fantasmas sin conexión en AP.
- **AGENT MAP stale — RESUELTO 10-sep-2026** con `sync_agent_maps()` (se llama siempre, `cmp`+`cp` gate→agent). Ya no hace falta el copiado manual. Histórico del síntoma: el sync solo copiaba a los agent maps cuando `sha(gate)!=sha(dev)`; si dev y gate ya coincidían, la copia del agente quedaba vieja y el MCP (que lee `/opt/hermes/data/connections-map.json` y exige `status==active`) ignoraba la conexión → ACTIVE en AP pero INERTE para el bot. En prod `/opt/data` es symlink a `/opt/hermes/data`.
- **BUG sync revert — RESUELTO 10-sep-2026** (ver arriba el incidente completo y `build_merged`). Reglas que ahora aplica el script: (1) ruta del mapa FIJA, nunca derivada de `__file__`; (2) escribe el mapa COMPLETO fusionado (dev ∪ prod, owners unidos) — jamás reemplazo con una copia parcial; (3) el output loggea el count y `MERGE:` avisa qué se preservó/unido. **Para revocar un owner hay que quitarlo en dev Y en prod** (la unión no propaga sustracciones).
- **Perfiles nuevos nacen cableados (28/08):** `hermes-profiles/templates/config.yaml` (bloque `mcp_servers` con engram + ncl_google, antes de `display:`) y `scripts/onboard-agent.sh` ya incluyen el puente. Al editar la plantilla, verificar que el sed de onboard-agent.sh reemplaza `<CLIENTE>` sin romper las URLs del bloque MCP (usar delimitador `|`, no `/`).
- **Secrets dir:** `/opt/data/secrets/` en el contenedor prod = `/opt/hermes/data/secrets/` en el host. Propagado por el sync script. Sin esto, el MCP no puede autenticar.
- **Perfil blindado + MCP = funcional:** los perfiles de cliente tienen `terminal` disabled (antiprompt-injection), pero SÍ pueden usar MCP (engram funciona). El MCP server es el único canal seguro para que el bot opere cuentas externas.
- **Perfiles con gateway propio vs multiplexado:** en prod, algunos perfiles tienen su propio s6 service (`gateway-nancy`). Si el gateway-default multiplexado no carga el MCP de un perfil específico, verificar si tiene servicio s6 propio.
- **`args[0]` duplicado:** al registrar el MCP en config.yaml, `args` empieza con el script path (`/opt/data/scripts/ncl_google_mcp.py`), NO con `python3` (eso va en `command`). Error común: poner `python3` como args[0] → el server recibe "python3" como argumento y falla.
- Si se recrea `ap-app` en prod → recrear `connect-gate` con el `AP_JWT_SECRET` nuevo (env del contenedor) + re-generar secrets con `verify_connection.py`.
- Descifrado AP: `{iv,data}` en HEX (no b64), AES-256-CBC key cruda 32B; la cuenta real sale del `id_token` (Calendar no sirve para resolver email — scope sin openid). Para servicios sin openid: cruzar con otra conexión del mismo tenant que sí tenga la cuenta.
- Google muestra "app no verificada" en el consent del cliente — normal en self-hosted, documentarlo en la invitación.
- `docker restart` NO aplica cambios de `.env` — eliminar y recrear el contenedor.
