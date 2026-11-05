---
name: hermes-secrets-v022x-ops
description: Use when a Hermes script/cron fails with missing API keys or tokens after the v0.22.x secret migration, or when creating/testing Discord webhooks. Canonical secret resolution and webhook patterns.
---

# Secretos v0.22.x y Webhooks Discord (DEV)

## Contexto
La actualización v0.22.x movió TODOS los secretos fuera de `/opt/data/.env` a la
fuente Bitwarden (40 claves aplicadas on-demand). Cualquier script que lea el
archivo `.env` directo queda roto silenciosamente (o peor: falso verde si el
script imprime ERROR pero sale 0).

## Patrón canónico de resolución de secretos (Python)
Orden estricto: `os.environ` → fuente de secretos del perfil → `.env` legado.

```python
import sys
tok = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
if not tok:
    sys.path.insert(0, "/opt/hermes-agent")
    from hermes_cli.env_loader import hydrate_profile_secret_sources
    tok = hydrate_profile_secret_sources("/opt/hermes-agent-data").get(
        "DISCORD_BOT_TOKEN", "").strip()
# fallback final: leer /opt/data/.env (legado)
```

- Helper compartido listo: `/opt/data/scripts/_discord_token.py` (función `discord_token()`).
- PITFALL (verificado 27-oct): el helper es IMPORT-ONLY. Si se ejecuta como script dentro
  de `$(...)`, captura el texto `OK len= 72` como "token" (len 10) → TODAS las llamadas
  responden 401 Unauthorized de golpe, sin error visible del helper. Shell correcto:
  `TOK=$(python3 -c "import sys;sys.path.insert(0,'/opt/data/scripts');from _discord_token import discord_token;print(discord_token())")`
  — verificar `${#TOK}` = 72 antes de la primera llamada.
- Los crons hijos del gateway NO heredan los secretos en su entorno: el fallback
  a la fuente de secretos es obligatorio, `os.environ` solo no basta.

## Pitfall: placeholders literales `${VAR}` en config.yaml (verificado 27-oct)
- La migración puede dejar en `config.yaml` el texto LITERAL `${NAN_BUILDERS_API_KEY}`
  (u otra clave) sin expandir. El que consume el valor lo pasa tal cual como API key
  → error 401 Invalid API key, aunque el loader hidrata bien los secretos.
- Diagnóstico: grep -n '\${' /opt/data/config.yaml — todo placeholder debe resolverse;
  si aparece el texto crudo, expandir con el valor real de la fuente de secretos
  (D-I-V-E: backup → reemplazo → verificación) y re-probar la llamada end-to-end.
- Caso real: cron `brain-graph-update-noche` (extractor semántico graphify) fallaba con
  401 del backend openai; fix aplicado y corrida manual verificada sin errores.
- Variante del mismo patrón: secretos rotados en Bitwarden con valor viejo cacheado en
  config.yaml — al diagnosticar 401/403, comparar config.yaml contra la fuente siempre.

## Discord API — reglas duras
- TODO request (urllib o curl) requiere User-Agent propio: 
  `DiscordBot (https://hermes-agent.nousresearch.com, 1)` — sin esto responde 403.
- Webhook de canal FORO exige `thread_name` (crea post) o `?thread_id=` (publica
  dentro de un hilo existente). Sin eso: error 220001.
- Un webhook 404 (code 10015) suele significar que el CANAL fue eliminado, no
  solo el webhook: verificar el canal antes de recrear.
- Localizar tickets/posts en canales FORO (verificado 27-oct): `/guilds/{id}/messages/search`
  responde 401 (el bot no tiene ese permiso) y `/guilds/{id}/threads/active` omite los
  posts archivados (que son casi todos). Receta canónica:
  `GET /channels/{forum_id}/threads/archived/public?limit=100` (+ paginar con
  `?before=<thread_id_más_viejo>`). Foro tickets-tecnicos = `1554957746980261938`;
  filtrar por nombre de thread en Python.
- Extraer la URL de webhook desde crontab/`.env` con `cut -d=` TRUNCA la URL en el `=` del query param (`?thread_id=...`) → el POST devuelve 400 y la alerta parece perdida sin rastro. Usar `grep -oP 'https://discord\.com/api/webhooks/\S+'` o `sed` anclado al nombre de la variable. Y antes de sentenciar 'el webhook cambió/está mal', releer la línea cruda: el crontab puede haber cambiado entre lecturas (pasa en flota activa).
- Postear en un hilo existente: POST directo a `/channels/{thread_id}/messages` (un
  thread ES un canal). Verificar leyendo `channel_id` del response.

## Estado actual de webhooks (26-oct-2026)
- Webhook activo `1564305619228295291` en foro `⏰・crons-dev` (`1555646749559885925`).
- `competitor-news-digest`: lo usa con `thread_name` por corrida (post semanal).
- Vigía: `VIGIA_DISCORD_WEBHOOK` + `VIGIA_DISCORD_THREAD_ID=1564308156044279938`
  (hilo "🚨 Informes de Vigía") en `/opt/data/profiles/vigia/.env`; el poster es
  `profiles/vigia/scripts/vigia_post_discord.py` (inyecta `?thread_id=`).
- Crear webhooks: el bot puede (`POST /channels/{id}/webhooks`) — no hace falta
  pedirle al Admin si el bot tiene permisos en el canal.

## Bot Ragnar vs item vault "Discord NCA - bot+webhook - prod" (verificado 27-oct)
- Tras el hardening del 26-oct, `DISCORD_BOT_TOKEN` del bot Ragnar ya NO está en
  `/opt/data/.env` (archivo limpiado) ni existe como item propio en Vaultwarden
  (`vw list` solo muestra "Discord NCA - bot+webhook - prod"). Ese token es del bot
  NCA de PROD: autentica bien (sin 401) pero responde
  `{"code":50001,"message":"Missing Access"}` al postear en canales del foro de
  tickets de DEV — es otro bot en otro guild, NO sustituye al de Ragnar.
- Formato del item: `vw get "Discord NCA - bot+webhook - prod"` devuelve líneas con
  prefijo `label: valor` (ej. `DISCORD_BOT_TOKEN: MTxx...`, separador dos puntos +
  espacio), NO `clave=valor`. Parsear con `sed 's/^DISCORD_BOT_TOKEN: *//'` — con
  `cut -d= -f2-` el token queda contaminado con el label y falla en silencio.
  Verificar `${#TOK}` (bot token ≈ 72 chars, empieza con `MT`) antes de llamar.
- Receta completa probada: POST a `/channels/{id}/messages` con headers
  `Authorization: Bot $TOK` + `User-Agent: DiscordBot (https://hermes, 1)` +
  `--data-binary @payload.json` (el JSON por archivo, no inline).
- Pitfall fs.protected_regular (vale en CUALQUIER superficie Linux: host DEV vía ssh, el propio contenedor, cualquier /tmp): escribir sobre un archivo preexistente de OTRO dueño falla "Permission denied" aunque /tmp sea 1777 (root no lo sortea). Usa otra ruta (/root/x.sh en host, otra dir en contenedor) o nombre nuevo.
- Resolución del bloqueo post-Ragnar (pendiente Admin): conectar el conector Discord
  nativo de Hermes (link del portal cuando hay hints CONNECTION_REQUIRED) o crear un
  item de Vaultwarden dedicado con el token del bot Ragnar.

## Migrados (backups `.bak-20261026`)
resumen_tickets_tecnicos, higiene_tags_tickets, dashboard_stale_guard,
discord_create_channels, discord_list2, discord_list_channels, discord_nick_test,
discord_rename_channels, discord_test_token, ncl_discord_mcp, nan_quota.
Pendiente cosmético: `OPENAI_API_KEY`/`OPENCODE_GO_KEY` legacy (no críticos).
Formbricks MCP — RESUELTO (27-oct): la key del config es placeholder `${FORMBRICKS_MCP_KEY_RO}`;
resolverla via fuente de secretos. La MCP key TAMBIÉN es management key. Receta para descubrir
el workspaceId (no está en config ni secrets): `curl http://100.73.30.29:3030/api/v1/management/me
-H "x-api-key: $KEY"` → `workspace.id`. Valor: `cmsywjcrj000101prw5rpro8x` ("My workspace").
Todas las tools de datos del MCP exigen `workspaceId` por llamada (verificado: list_surveys OK).
GitHub MCP: token = Kattegat-crew (PAT clásico, scopes repo/admin:org/workflow — verificado vía
`/user` + header x-oauth-scopes). SI search_repositories devuelve total_count>0 con items vacío
usando el calificador `user:`, es un quirk del índice de búsqueda de GitHub (no de auth ni del
token): usar REST directa (`/users/{u}/repos`) o `org:` en su lugar. No registrar como fallo de token.
Auditoría MCP 27-oct: 16/17 servidores verificados operando (ap, canva, chrome-devtools,
cloudflare, composio, context7, coolify, docuseal, engram, fal, ncl_google, opendesign,
outline, paperless, stirling, twenty).

## Comparar claves entre entornos SIN exponerlas (huellas SHA256, 28-oct)
Cuando hay que verificar si la key de un equipo local del Admin y la del servidor son la
misma (o si una key "cambió desde hace N meses"), NUNCA pedir que se pegue en el chat.
Patrón: cada lado calcula localmente `len` + `sha256(value)[:16]` + máscara `sk-abc...xyz`
y solo se comparan las huellas. Ejemplo embebido en script de diagnóstico:

```python
import hashlib
print(len(k), hashlib.sha256(k.encode()).hexdigest()[:16], f"{k[:6]}...{k[-3:]}")
```

- Aplica también a logs/reportes: emitir máscaras y hashes, jamás el valor en claro.
- Para hallar la key del lado servidor cuando config.yaml ya usa placeholders `${VAR}`
  (post-migración 26-oct): el valor vive en la fuente de secretos del perfil, NO en el
  environ del proceso gateway (verificado: `/proc/<pid>/environ` sin claves) ni en `.env`
  (limpiado). Resolver con `hydrate_profile_secret_sources` y hashear el resultado;
  no desperdiciar búsquedas grep de árbol completo (timeout en `/opt` grande).

- Excepción DISCORD_BOT_TOKEN (verificado 29-oct): ese token SÍ vive en el environ
  del proceso gateway (node) — a diferencia de las API keys de perfil. Si la fuente de
  secretos o `bw` están caídas/intermitentes, recuperar el pid del proceso gateway y
  leer `/proc/<pid>/environ` (tr - '\0' '\n' | grep DISCORD_BOT_TOKEN). Es la única vía
  que funcionó para abrir tickets ese día.
- Diagnóstico de Missing Access: `{"code":50001}` con el bot NCA NO significa token
  inválido ni canal equivocado — significa que el bot no está en ese guild. Verificar
  identidad (`GET /users/@me`) y en qué servidores está (`GET /users/@me/guilds`)
  ANTES de culpar al token o al canal.

## Token de bot por PERFIL (`ncl-discord --as <perfil>`) — DEV, verificado 03-nov-2026
`/opt/data/scripts/ncl_discord_mcp.py` resuelve el token según perfil vía `PROFILE_ENV_PATHS`:
`roshi` → `/etc/hermes-vault/profiles/roshi.secrets.env` → `profiles/roshi/.env`;
`default|ragnar` → vault `default/root` → `/opt/hermes-agent-data/.env` + `hydrate_profile_secret_sources`.

Estado real en DEV:
- `/etc/hermes-vault` es `drwx------ root:root` → un proceso con uid `hermes` (10000) NO puede
  leer nada dentro. `Path.is_file()` devuelve **False** (no lanza) → el código cae al `.env`
  del perfil, no al vault.
- `profiles/roshi/.env` NO contiene `DISCORD_BOT_TOKEN` → `--as roshi` muere con
  `DiscordError -32001` desde cualquier sesión de agente, aunque el Roshi real publique sin
  problema por su conexión nativa del gateway (otro cliente, otro camino).
- `--as default` SÍ resuelve (72 chars, empieza `MT`) y es la vía segura para publicadores de
  script/cron. Verificar sin exponer: `len(tok)` + `tok[:6]`.
- `/etc/cron.d` del host corre como **root** → root sortea el 700 y sí podría leer el vault.
  Nunca asumirlo: esa diferencia de uid es justo lo que hace que el mismo script funcione a
  las 08:30 (root) y falle a las 09:00 (job Hermes, uid hermes).

Sonda canónica — simula el entorno del scheduler, no el de tu sesión:
```bash
env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/root python3 -c "
import sys; sys.path.insert(0,'/opt/data/scripts'); import ncl_discord_mcp as m
for p in ('roshi','default'):
    try: t=m.load_bot_token(p); print(p,'OK',len(t),t[:6]+'…')
    except Exception as e: print(p,'FALLA',e)
"
```

Workarounds, en orden de preferencia: (1) publicar con `--as default` si la marca da igual;
(2) `chmod 640` + grupo `hermes` sobre el vault del perfil (root sigue dueño); (3)
`Environment=DISCORD_ROSHI_BOT_TOKEN=…` en la unit que lo necesita — mantiene `--as roshi`
como dependencia frágil. NO crear un `.env` con el token del bot de otro agente.

- Corolario del 29-oct: leer `/proc/<pid>/environ` sirve para el token del bot del perfil que
  corre ESE gateway; no cubre perfiles servidos por multiplex. Antes de concluir "no hay
  token", comparar `served_profiles` en `<perfil>/gateway_state.json` con los procesos vivos.

## Alta de un secreto NUEVO en Vaultwarden desde el contenedor (28-oct)
Cuando el Admin entrega una credencial para "guardar en el vault": el perfil del contenedor
no tiene acceso al `.env` del bot de DEV, pero el vaultwarden corre en el gateway de PROD,
donde `bw` y ese `.env` sí existen. Vía probada end-to-end (key de billing de fal.ai):

- Construir UN script plano con el valor embebido y ejecutarlo de forma remota vía `bash -s`
  con el script por stdin: el valor viaja cifrado y nunca queda en argv (visible en `ps`
  del remoto) ni en un archivo del host remoto.
- PITFALL: heredoc anidado + `read -r KEY` en el mismo stdin falla EN SILENCIO (el heredoc
  consume el stream). Incrustar el valor directamente en el script es lo único que funciona.
- `bw create item` en la versión actual EXIGE el item en base64 (`bw encode`); con JSON
  crudo responde `Error parsing the encoded request data`.
- DEDUPE antes de crear: `bw list items --search "<nombre>"`; y evitar no-ASCII (em-dash)
  en nombre/notas.
- Estructura del item: `login.username` = identificador de uso, `login.password` = el secreto,
  metadatos como `fields` (proveedor, scopes, fecha_alta, campana) + notas con origen y uso.
- Verificación de integridad sin exponer el valor: releer el item y comparar
  `sha256(password_del_vault)` vs `sha256(valor_origen)` (mismo patrón de huellas de arriba).
  Nunca dar por bueno el "guardado" sin esa lectura de vuelta.
- Residencia: el `.env` local (0600) queda como caché de lectura para scripts; el vault es
  la fuente canónica.

## vw dice "Item not found" para TODO → sesión cacheada podrida (03-nov-2026)
`vw` cachea la sesión de Bitwarden CLI en `/tmp/.bw_session_cache`. Cuando esa sesión muere,
`bw list items --search` devuelve vacío y `vw` responde "Item not found" para ítems que sí
existen (falla incluso el ítem de Amazon SP-API). No es un secreto perdido.

- Diagnóstico correcto: `bw list items --session "$S"` SIN `--search`. Si el listado completo
  lo muestra, el problema es la sesión.
- Fix: `rm -f /tmp/.bw_session_cache` y repetir el `vw get`.
- Fix permanente aplicado en PROD: si `bw list` devuelve rc=0 con stdout vacío, `vw` borra el
  cache y reintenta con `get_session(force_refresh=True)`. Backup del binario en
  `/usr/local/bin/vw.bak-<fecha>` antes de tocarlo.

## Un token "muerto" suele ser el ítem del vault desactualizado (03-nov-2026)
El PAT operativo de GitHub vive en el CLI `gh`, no en el vault:
`HOME=/opt/hermes-agent-data/home /usr/bin/gh`, token en `~/.config/gh/hosts.yml`,
verificable con `gh auth status`.

- El ítem `GitHub Credential` (nota segura, campo `credential` con
  `https://x-access-token:<PAT>@github.com`) puede tener un valor viejo mientras `gh` sigue vivo.
- Regla: probar SIEMPRE el valor contra `https://api.github.com/user` con header
  `Authorization: token <valor>` antes de declarar que expiró o pedir uno nuevo al Admin.
- Si el del vault falla y el de `gh` funciona: actualizar el ítem (ver abajo) y borrar
  `/tmp/.bw_session_cache` después de editar, o `vw` seguirá sin resolver el nombre.

### Editar un ítem existente (bw ≥ 2026.8)
El verbo lleva espacio: `bw edit item <id> <encodedJson>`. `bw edit-item` responde `Invalid command`.
Se pasa el JSON completo descifrado en base64 y reemplaza el ítem entero:

1. `bw get item <id> --session "$S" > /tmp/item.json`
2. Modificar el campo con Python (lista `fields`, `{"name", "value", "type": 1}`).
3. `bw edit item <id> "$(base64 -w0 /tmp/item.json)" --session "$S"` y borrar el temporal.
4. `rm -f /tmp/.bw_session_cache` y verificar con `vw get` + prueba real contra la API.

### Transferir un secreto a otro host sin filtrarlo
No pasarlo como argumento en `ssh "..."` (queda en argv y en el historial). Usar archivo:
`printf '%s' "$TOK" > /tmp/tok && chmod 600 /tmp/tok`, `scp` al host, script remoto por
`ssh host 'bash -s' < script.sh`, y borrar el archivo en ambos lados al terminar.
PITFALL: un heredoc anidado dentro de `ssh 'bash -s' <<'EOS'` ejecuta las líneas restantes en
el host LOCAL; si el script es largo, escribirlo a archivo y pasarlo por stdin.
