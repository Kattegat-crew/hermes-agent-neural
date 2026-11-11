---
name: vault-access
description: "Access secrets: read .env first (fast), fallback to Vaultwarden if missing. Use when you need an API key, token, password, or any secret."
triggers:
  - need api key
  - need token
  - need password
  - need secret
  - api key de
  - token de
  - password de
  - secret de
  - credentials
  - donde esta el
  - busque el
  - access key
---

# Vault Access — Guía para Agentes

**REGLA #1**: Buscar secretos en este orden (fallback):
1. **Primario: `.env`** — rápido, cubre el 90% de los casos. Cada servicio tiene su archivo `.env` sincronizado desde el vault cada 30 min.
2. **Fallback: Vaultwarden** — cuando el `.env` no tiene la clave, o el valor está vacío. Usar `vw` CLI (recomendado) o `bw` CLI.

**REGLA #2**: Los `.env` se regeneran desde el vault cada 30 minutos (timer systemd). El vault es la fuente de verdad; los `.env` son la caché local. Si un valor cambió en el vault, el `.env` se actualiza solo.

**REGLA #3**: Nunca imprimir valores de secretos a transcripts, logs, o reportes.

## Cómo leer un secreto

### Paso 1 — Buscar en el `.env` (primario)

```bash
# Cada servicio tiene su .env sincronizado desde el vault
# Ejemplo: leer DATABASE_URL de NCA
source /neuralcrew_agent/.env
echo $DATABASE_URL

# Ejemplo: leer secrets de Twenty
source /opt/docker/twenty/.env
echo $PG_DATABASE_PASSWORD
```

**Archivos .env por servicio:**

| Servicio | Archivo |
|----------|---------|
| NCA (nca-api) | `/neuralcrew_agent/.env` |
| Golden Game | `/root/golden-game-landing/.env` |
| Paradise Casino | `/root/paradise-casino/paradise-casino-landing/.env` |
| ActivePieces (local) | `/root/activepieces/.env` |
| Coolify | `/data/coolify/source/.env` |
| Cloudflare | `/root/.config/cloudflare/credentials.env` |
| Reel Worker | `/root/video-ai-generator/.env` |
| ActivePieces (prod) | `/opt/docker/activepieces/.env` |
| Formbricks (prod) | `/opt/docker/formbricks/.secrets.env` |
| Langfuse (prod) | `/opt/docker/langfuse/.secrets.env` |
| Twenty (prod) | `/opt/docker/twenty/.env` |
| Outline (prod) | `/opt/outline/.env` |
| Paperless (prod) | `/opt/paperless/.env` |
| PocketID (prod) | `/opt/pocket-id/.env` |
| Webhook Gateway (prod) | `/opt/docker/webhook-gateway/.env` |
| Webhook Paradise (prod) | `/opt/docker/webhook-gateway/.env.paradise` |
| Webhook Redemptions (prod) | `/opt/docker/webhook-gateway/.env.redemptions` |
| Hermes (prod) | `/opt/hermes/.env` |

**Si la clave no está en el `.env` o el valor está vacío → Paso 2.**

### Paso 2 — Buscar en el vault (fallback)

#### Opción A — `vw` CLI (recomendado)

El comando `vw` está instalado en el PATH del sistema (`/usr/local/bin/vw`). Gestiona autenticación, sesión y caché en memoria automáticamente sin leaks.

```bash
# 1. Obtener un campo específico directamente
vw get "Terceros/NAN - API Key" -f NAN_API_KEY
vw get "Apps/NCA/Postgres NCA - credentials - prod" -f DATABASE_URL

# 2. Obtener todos los campos de un item
vw get "Formbricks - credentials - prod"

# 3. Exportar todos los campos como variables de entorno
eval $(vw env "Terceros/NAN - API Key")

# 4. Listar o buscar items en el vault
vw list "Terceros"
vw list "Hermes"
```

#### Opción B — `bw` CLI nativo (alternativa)

```bash
# Setup (una vez por sesión) — NO hardcodear passwords, usar el bot env
set -a; . /root/.bw-bot.env; set +a
bw config server https://vault.neuralcrewlabs.com 2>/dev/null
bw logout 2>/dev/null || true
SESSION=$(bw login agents@neuralcrewlabs.com --passwordenv BW_PASSWORD --raw 2>/dev/null)

# Buscar un item por nombre
bw list items --search "Formbricks" --session "$SESSION"

# Obtener un item completo
bw get item <item-id> --session "$SESSION"

# Al terminar
bw logout --session "$SESSION" 2>/dev/null
```

## Colecciones en el vault

```
NeuralCrew Labs/
├── Agents/              (legacy, vacío)
├── Apps/
│   ├── ActivePieces     (local, MUERTO)
│   ├── ActivePieces-Prod
│   ├── AI-Platform      (leak público, no-rotar)
│   ├── Formbricks       (prod)
│   ├── Langfuse         (prod)
│   ├── NCA              (postgres, redis, qdrant, telegram, discord, whatsapp)
│   ├── Outline          (prod)
│   ├── Paperless        (prod)
│   ├── PocketID         (prod)
│   ├── Twenty           (prod)
│   ├── Webhook-Gateway-Prod
│   └── Webhooks         (golden, paradise)
├── Empresa/
├── Hermes/
│   ├── API              (JWT secret)
│   ├── Dashboard        (basic auth, session token)
│   ├── Git              (GitHub credential)
│   ├── Global           (API server key, OpenCode-Go)
│   ├── MCPs             (Notion, Google OAuth)
│   └── WhatsApp         (Baileys creds + tctokens)
├── Infra/
│   ├── Cloudflare       (API tokens)
│   └── Coolify          (APP_KEY, DB, Redis, Pusher)
├── Terceros/
│   └── IA               (NAN, FAL, Monid, TokenRouter, Amazon SP-API)
└── Vault Ops            (admin token — SOLO humanos)
```

## Agregar un secreto nuevo

**REGLA DE ORO**: Secreto nuevo → PRIMERO al vault → DESPUÉS al mapping → timer lo regenera. **NUNCA** escribir el .env a mano.

### Escenario 1: Agregar campo a un item que YA existe

**Ejemplo**: Agregar `STRIPE_API_KEY` al item `Twenty - credentials - prod`

```bash
# 1. Login al vault
set -a; . /root/.bw-bot.env; set +a
bw config server https://vault.neuralcrewlabs.com 2>/dev/null
bw login agents@neuralcrewlabs.com --passwordenv BW_PASSWORD 2>&1 | tail -1
SESSION=$(bw unlock --passwordenv BW_PASSWORD --raw)

# 2. Obtener el item actual
bw get item ba729aa0-b6e2-44f9-a74e-fad1f7fdcd27 --session "$SESSION" > /tmp/item.json

# 3. Agregar el campo (vía Python)
python3 -c "
import json, base64
item = json.load(open('/tmp/item.json'))
item['fields'].append({'type': 1, 'name': 'STRIPE_API_KEY', 'value': 'sk_live_...'})
encoded = base64.b64encode(json.dumps(item).encode()).decode()
print(encoded)
" > /tmp/encoded.txt

# 4. Aplicar el cambio
bw edit item ba729aa0-b6e2-44f9-a74e-fad1f7fdcd27 --session "$SESSION" "$(cat /tmp/encoded.txt)"

# 5. Agregar mapping en vault-to-env-map.json:
#    { "item": "Twenty - credentials - prod", "field": "STRIPE_API_KEY", "env": "STRIPE_API_KEY" }

# 6. El timer lo regenera en ≤30 min
```

### Escenario 2: Crear un servicio nuevo completo

**Ejemplo**: Servicio "Supabase" con API_KEY y DB_URL

```bash
# 1. Login al vault (misma sesión de arriba)

# 2. Crear colección (si no existe)
COLL_JSON='{"object":"collection","name":"Apps/Supabase","organizationId":"b045a3d2-9728-49ca-a009-a63acca13a14"}'
COLL_ID=$(echo "$COLL_JSON" | bw create org-collection --organizationid b045a3d2-9728-49ca-a009-a63acca13a14 --session "$SESSION" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
echo "Collection created: $COLL_ID"

# 3. Crear item con campos
ITEM_JSON=$(python3 -c "
import json, base64
item = {
    'object': 'item',
    'type': 1,
    'name': 'Supabase - credentials - prod',
    'organizationId': 'b045a3d2-9728-49ca-a009-a63acca13a14',
    'collectionIds': ['$COLL_ID'],
    'fields': [
        {'type': 1, 'name': 'SUPABASE_API_KEY', 'value': 'eyJ...'},
        {'type': 1, 'name': 'SUPABASE_DB_URL', 'value': 'postgresql://...'}
    ]
}
print(json.dumps(item))
")
ITEM_ID=$(echo "$ITEM_JSON" | bw create --session "$SESSION" --organizationid b045a3d2-9728-49ca-a009-a63acca13a14 | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
echo "Item created: $ITEM_ID"

# 4. Crear directorio y .env vacío
mkdir -p /opt/supabase
touch /opt/supabase/.env
chmod 600 /opt/supabase/.env

# 5. Agregar target en vault-to-env-map.json:
cat >> /opt/vault/timer/vault-to-env-map.json << 'EOF'
,
{
  "file": "/opt/supabase/.env",
  "mode": "0600",
  "restart": "cd /opt/supabase && docker compose restart supabase",
  "mappings": [
    { "item": "Supabase - credentials - prod", "field": "SUPABASE_API_KEY", "env": "SUPABASE_API_KEY" },
    { "item": "Supabase - credentials - prod", "field": "SUPABASE_DB_URL", "env": "SUPABASE_DB_URL" }
  ]
}
EOF

# 6. El timer lo regenera en ≤30 min (o ejecutar manualmente)
python3 /opt/vault/timer/sync-env.py "$SESSION"
```

### Escenario 3: Agregar secreto via UI (sin CLI)

1. Abrir `https://vault.neuralcrewlabs.com` en el navegador
2. Login con tu cuenta
3. Ir a la colección correcta → "Nuevo item" → "Nota segura" o "Inicio de sesión"
4. Agregar campos con nombre = nombre de la variable de entorno
5. Guardar
6. Agregar el mapping en `vault-to-env-map.json`
7. El timer lo regenera

## Timer — cómo funciona

- Cada 30 min, `vault-sync.sh`:
  1. Login al vault
  2. Sync de items
  3. Python `sync-env.py` lee el mapping y actualiza cada .env
  4. Reinicia el servicio afectado (si se configuró)
- Logs: `/var/log/vault-sync.log`
- Mapping: `/opt/vault/timer/vault-to-env-map.json`

## Errores comunes

| Error | Causa | Fix |
|-------|-------|-----|
| "Item not found" | Nombre no coincide exactamente | Buscar con `bw list items --search` |
| "Session expired" | Token de bw venció | Re-hacer unlock |
| .env no se actualiza | Timer no corre | `systemctl status vault-sync.timer` |
| Secret wrong value | Vault no sincronizado | `bw sync --session $SESSION` |
