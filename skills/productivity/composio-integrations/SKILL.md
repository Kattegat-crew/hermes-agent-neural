---
name: composio-integrations
description: "Use when connecting tools via Composio CLI or MCP."
tags: [composio, integrations, oauth, instagram, facebook, cli]
version: 1.0.0
---

# Composio Integrations

Composio es una capa de *tool-calling para agentes*: un catálogo de 1,400+ integraciones con OAuth administrado, que tu agente invoca por intención (`search` → `execute`). Es SaaS hosted, código cerrado (no self-hosteas ni extiendes los conectores).

## Distinción estratégica vs ActivePieces (DECISIÓN del Admin 03/09)

- **ActivePieces** = iPaaS self-hosted (flows visuales, triggers, conexiones OAuth en NUESTRO VPS). Es el **hub OAuth multi-tenant de clientes** con la puerta `connect.neuralcrewlabs.com`: tokens de clientes quedan en nuestro VPS, marca 100% NeuralCrew, ilimitado gratis.
- **Composio** = complemento del **lado interno/agencia**: publicación automática a redes (IG/FB), Gmail para flujos propios, Sheets, o cualquier app que no esté en AP. Rapidísimo de conectar, maneja el OAuth solo.
- **NO sustituye a AP** para custodia de tokens de clientes: en Composio los tokens quedan en la **nube de Composio** (hosted). Para conexiones de clientes multi-tenant → seguir con AP + puerta connect.
- **Apps Meta/Google propias** se implementan con calma aparte para el flujo de clientes; por ahora Composio managed auth cubre lo interno.

## Instalación (VPS sin root — necesita unzip)

```bash
# El instalador exige unzip. Sin root/ sudo, crear un wrapper de usuario (Python zipfile):
mkdir -p ~/.local/bin
cat > ~/.local/bin/unzip <<'PY'
#!/usr/bin/env python3
import sys, os, zipfile
def main():
    argv = sys.argv[1:]; dest = "."; files = []; i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("-"):
            flags = a.lstrip("-")
            if not flags: i += 1; continue
            if "d" in flags:  # -oqd / -d <dir>: -d consume el siguiente arg
                if i + 1 < len(argv): dest = argv[i + 1]; i += 2
                else: i += 1
                continue
            i += 1; continue
        files.append(a); i += 1
    if not files: sys.stderr.write("unzip: no archive specified\n"); return 1
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(files[-1]) as z: z.extractall(dest)
    return 0
sys.exit(main())
PY
chmod +x ~/.local/bin/unzip
export PATH="$HOME/.local/bin:$PATH"   # persistir en ~/.bashrc
curl -fsSL https://composio.dev/install | sh
```

Clave del wrapper: el instalador llama `unzip -oqd <dir> <archivo>` — la `d` va combinada; hay que consumir el siguiente argumento como directorio. `composio --version` = 0.4.0 OK.

## Login (headless)

```bash
composio login --no-browser --no-wait --no-skill-install
# → imprime URL: https://dashboard.composio.dev/?cliKey=...  (el usuario la abre)
composio login --poll --no-skill-install   # completa cuando el usuario ya autorizó
# → devuelve { email, current_org, organizations }
```

## Conectar cuentas (managed auth = no crear app)

```bash
composio link gmail --no-browser --no-wait
# → devuelve redirect_url (https://connect.composio.dev/enhanced/link/...) + connected_account_id
composio link instagram --no-browser --no-wait
composio connections list --toolkit <toolkit>   # ver status + word_id
```

- **Managed auth** (default): usa las credenciales de la propia app de Composio. Aplica NO SOLO a cuentas personales: **verificado que funciona con cuenta Instagram BUSINESS** (`account_type: BUSINESS`). No creas app de Google/Meta.
- **Custom auth config**: para traer TU propia app (white-label / scopes específicos) — el consent muestra tu marca, pero el **token queda en la nube de Composio** igual. Para clientes que no cambian la puerta blanca.
- El **link que se manda es de Composio** (`connect.composio.dev`), no de NeuralCrew, salvo custom auth + tu propio portal.
- Verificar siempre con una lectura (no enviar nada real) antes de usar: `composio execute GMAIL_LIST_LABELS --account <word_id> -d '{}'`.

## Ejecutar tools

```bash
# SIEMPRE pasar --account (word_id de connections list), -d '{}' es obligatorio
composio execute <SLUG> --account <word_id> -d '{}'
composio execute <SLUG> --account <word_id> --dry-run -d '{ ... }'   # valida sin ejecutar
composio execute <SLUG> --account <word_id> --get-schema              # ver inputs
```

Pitfalls: `-d` es obligatorio (sin él → 'Invalid JSON input'); sin `--account` puede fallar si hay varias conexiones; `permission_group` a veces `ask_every_call` (pedirá confirmación por llamada).

## Publicación a Instagram (verificado)

Tools disponibles: `INSTAGRAM_POST_IG_USER_MEDIA` / `_PUBLISH` (postear reels/imagen), `INSTAGRAM_GET_IG_USER_MEDIA` (listar), `INSTAGRAM_GET_USER_INFO`, `INSTAGRAM_GET_USER_INSIGHTS`.

- **Reels**: `{ ig_user_id, media_type: "REELS", video_url: "https://publico.mp4", caption, share_to_feed: true }` — el video debe estar en una **URL pública** que Meta pueda descargar (nuestros reels ya viven en goldengame.com.co y reels.neuralcrewlabs.com).
- **Imagen**: `{ ig_user_id, media_type: "IMAGE", image_url, caption }` o subir el archivo con `image_file`. Nota: cuando el tool tiene `image_file` Y `video_file`, `--file` es ambiguo ('multiple file_uploadable inputs') → pasar el campo explícitamente en `-d`, o usar `image_url` con URL pública. La pieza debe ser accesible públicamente (subir al docroot /opt/reels/ o goldengame.com.co).
- El auth config de IG usa por defecto la app managed de Composio (Config redirect URI solo si usas custom auth).

## Publicación a Facebook

Conectar `composio link facebook`; luego `FACEBOOK_CREATE_POST` / `FACEBOOK_CREATE_PHOTO_POST`.

## Scheduling / programación

Composio NO tiene 'publicar a las X horas' nativo para un post puntual. Para programar: **cron de Hermes** que dispare el `composio execute` a la hora deseada. Los crons de Hermes corren en el HOST (no contenedor) — envolver con `docker exec` si hace falta alcanzar la red del contenedor. Script envuelve el execute a la hora programada.

## Consultas y estado

```bash
composio search "<use case>" --limit <N>   # JSON; --human da formato legible
composio connections list --toolkit <tk>
composio execute <SLUG> --get-schema
```

## Referencias

- `references/session-2026-09-03.md` — estado de conexiones (word_ids, cuentas), el post Bingo Millonario (imagen + copy mejorado) y las opciones/decisiones de publicación de esa sesión.
- **MCP (16-sep-2026):** la flota ahora opera Composio por MCP (`composio` + `composio_write` con gate). Para publicar/leer desde el agente, enrutar cuentas multi-cliente y diagnóstico → skill `composio-mcp-ops`. Esta skill queda como referencia del CLI (`composio search/execute/link`) y de las decisiones estratégicas AP vs Composio.
