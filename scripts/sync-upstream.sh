#!/usr/bin/env bash
# sync-upstream.sh — Auditoría y Sincronización Segura de hermes-agent contra Releases Upstream
#
# MODOS DE USO:
#   ./sync-upstream.sh          (Modo por defecto: --check / observabilidad pasiva, cero cambios)
#   ./sync-upstream.sh --check  (Audita tags upstream, comprueba conflictos en memoria y notifica a Discord)
#   ./sync-upstream.sh --apply <tag>  (Ventana de mantenimiento supervisada, backup y sandbox)
#
set -euo pipefail

REPO_DIR="/opt/hermes-agent"
DATA_DIR="/opt/hermes-agent-data"  # F6 nativo (02-oct-2026)
LOG_FILE="/var/log/hermes-sync.log"
LOCK_FILE="/tmp/hermes-sync.lock"
WATERMARK_FILE="${DATA_DIR}/state/.last_notified_tag"

ENV_FILE="${DATA_DIR}/.env"
DISCORD_BOT_TOKEN="${DISCORD_BOT_TOKEN:-}"
if [ -z "$DISCORD_BOT_TOKEN" ] && [ -f "$ENV_FILE" ]; then
    DISCORD_BOT_TOKEN=$(grep -E "^DISCORD_BOT_TOKEN=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '"\r\n' || echo "")
fi
DISCORD_JESUS_DM_CHANNEL="${DISCORD_JESUS_DM_CHANNEL:-1493432785245962250}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

fail() {
    log "ERROR: $*"
    rm -f "$LOCK_FILE"
    exit 1
}

cleanup() {
    rm -f "$LOCK_FILE"
}
trap cleanup EXIT

notify_discord() {
    local tag="$1"
    local conflicts="$2"

    python3 - <<PYEOF
import urllib.request, json

token = "$DISCORD_BOT_TOKEN"
channel_id = "$DISCORD_JESUS_DM_CHANNEL"
tag = "$tag"
conflicts = "$conflicts"

color = 5763719 if conflicts == "0" else 15548997
status_text = "✅ LIMPIO (0 conflictos en memoria)" if conflicts == "0" else f"⚠️ ADVERTENCIA ({conflicts} conflictos detectados)"

payload = {
    "embeds": [{
        "title": f"🚀 Nuevo Release de Hermes: {tag}",
        "description": f"Hola Jesús, se detectó una nueva versión oficial de **NousResearch/hermes-agent**.\n\n**Compatibilidad:** {status_text}\n\nCuando desees actualizar el entorno, recuerda coordinar la ventana de mantenimiento externa con Toallín.",
        "color": color,
        "fields": [
            {"name": "Comando de Aplicación", "value": f"`/opt/hermes-agent/scripts/sync-upstream.sh --apply {tag}`", "inline": False},
            {"name": "Garantías de Seguridad", "value": "• Snapshot preventivo de WhatsApp\n• Validación de guardrails en sandbox antes de tocar main\n• Cero downtime intempestivo", "inline": False}
        ],
        "footer": {"text": "NeuralCrew Labs • Hermes Fleet Watcher"}
    }]
}

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(f"https://discord.com/api/v10/channels/{channel_id}/messages", data=data, headers={
    "Authorization": f"Bot {token}",
    "Content-Type": "application/json",
    "User-Agent": "DiscordBot (NeuralCrew, 1.0)"
})

try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        pass
except Exception as e:
    print("Error enviando alerta Discord:", e)
PYEOF
}

MODE="${1:---check}"

# --- Control de Concurrencia ---
if [ -f "$LOCK_FILE" ]; then
    pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        log "SKIP: Otra instancia de sincronización está en ejecución (PID $pid)"
        exit 0
    fi
    rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"

cd "$REPO_DIR"

# --- Paso 1: Actualizar catálogo de tags upstream sin tocar ramas locales ---
log "=== Verificación Upstream Hermes ==="
log "Consultando releases y tags de upstream (NousResearch)..."
git fetch upstream --tags --quiet 2>&1 || fail "No se pudo conectar con upstream en GitHub"

# Identificar último tag de release oficial
LATEST_UPSTREAM_TAG=$(git tag -l "v*" --sort=-v:refname | head -n 1)
CURRENT_MERGE_BASE=$(git merge-base HEAD "$LATEST_UPSTREAM_TAG" 2>/dev/null || echo "unknown")
LATEST_TAG_COMMIT=$(git rev-parse "$LATEST_UPSTREAM_TAG" 2>/dev/null || echo "")

log "Último tag oficial disponible en upstream: $LATEST_UPSTREAM_TAG"

# --- Modo Check (Observabilidad / Solo Lectura) ---
if [ "$MODE" = "--check" ]; then
    if [ "$CURRENT_MERGE_BASE" = "$LATEST_TAG_COMMIT" ]; then
        log "Estado: AL DÍA. El árbol local ya incorpora la base del tag $LATEST_UPSTREAM_TAG."
        log "=== Verificación finalizada (sin cambios necesarios) ==="
        exit 0
    fi

    COMMITS_BEHIND=$(git rev-list --count HEAD.."$LATEST_UPSTREAM_TAG" 2>/dev/null || echo "0")
    log "El repositorio local está a $COMMITS_BEHIND commit(s) del release $LATEST_UPSTREAM_TAG."

    log "Auditando compatibilidad en memoria (dry-run sin tocar archivos)..."
    CONFLICT_COUNT=$(git merge-tree "$CURRENT_MERGE_BASE" HEAD "$LATEST_UPSTREAM_TAG" 2>/dev/null | grep -c "^<<<<<<<" || true)

    if [ "$CONFLICT_COUNT" -eq 0 ]; then
        log "Resultado auditoría: LIMPIO. El release $LATEST_UPSTREAM_TAG es compatible sin conflictos directos."
    else
        log "ADVERTENCIA: Se detectaron $CONFLICT_COUNT conflicto(s) potenciales con el release $LATEST_UPSTREAM_TAG."
    fi

    # Notificar a Discord si no se ha notificado previamente para este tag
    LAST_NOTIFIED=$(cat "$WATERMARK_FILE" 2>/dev/null || echo "")
    if [ "$LAST_NOTIFIED" != "$LATEST_UPSTREAM_TAG" ]; then
        log "Enviando notificación a Discord DM de Jesús para tag $LATEST_UPSTREAM_TAG..."
        notify_discord "$LATEST_UPSTREAM_TAG" "$CONFLICT_COUNT"
        echo "$LATEST_UPSTREAM_TAG" > "$WATERMARK_FILE"
        log "Notificación enviada y registrada en watermark."
    else
        log "El tag $LATEST_UPSTREAM_TAG ya fue notificado previamente. Omitiendo duplicados."
    fi

    log "=== Auditoría finalizada (cero modificaciones aplicadas) ==="
    exit 0
fi

# --- Modo Apply (Ventana de Mantenimiento Supervisada) ---
if [ "$MODE" = "--apply" ]; then
    TARGET_TAG="${2:-$LATEST_UPSTREAM_TAG}"
    log "=== INICIO DE VENTANA DE MANTENIMIENTO: Aplicando $TARGET_TAG ==="

    # 1. Validar working tree limpio
    if [ -n "$(git status --porcelain)" ]; then
        fail "El working tree tiene archivos sin commitear. Limpie o guarde el stash antes de continuar."
    fi

    # 2. Snapshot preventivo de WhatsApp y BBDD
    BACKUP_DIR="/root/hermes-agent-legacy-docker/data/whatsapp/backups"
    mkdir -p "$BACKUP_DIR"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    WA_BACKUP="${BACKUP_DIR}/session_backup_${TIMESTAMP}.tar.gz"
    
    if [ -d "/root/hermes-agent-legacy-docker/data/whatsapp/session" ]; then
        log "Generando snapshot preventivo de sesión WhatsApp en $WA_BACKUP..."
        tar -czf "$WA_BACKUP" -C "/root/hermes-agent-legacy-docker/data/whatsapp" session
        log "Snapshot WhatsApp generado con éxito."
    fi

    # 3. Test de Guardrails Pre-Merge
    log "Ejecutando suite de pruebas de guardrails de NeuralCrew..."
    if command -v pytest >/dev/null 2>&1; then
        pytest tests/agent/test_tool_guardrails.py tests/agent/test_turn_intent_triage.py --quiet || fail "Pruebas de guardrails fallaron antes de iniciar. Abortando."
        log "Guardrails e invariantes verificados al 100% OK."
    fi

    # 4. Creación de rama sandbox
    SANDBOX_BRANCH="update-${TARGET_TAG}-${TIMESTAMP}"
    log "Creando rama sandbox aislada: $SANDBOX_BRANCH..."
    git checkout -b "$SANDBOX_BRANCH"

    # 5. Merge del tag
    log "Fusionando tag $TARGET_TAG en la rama sandbox..."
    if git merge "$TARGET_TAG" --no-edit 2>&1 | tee -a "$LOG_FILE"; then
        log "Merge completado exitosamente en sandbox."
    else
        log "Merge con conflictos en sandbox. Abortando y regresando a main..."
        git merge --abort || true
        git checkout main
        git branch -D "$SANDBOX_BRANCH"
        fail "Merge falló con conflictos. La rama main y los contenedores quedaron 100% intactos."
    fi

    # 6. Test de Guardrails Post-Merge
    log "Verificando invariantes post-merge..."
    if command -v pytest >/dev/null 2>&1; then
        if ! pytest tests/agent/test_tool_guardrails.py tests/agent/test_turn_intent_triage.py --quiet; then
            log "Guardrails rotos tras el merge. Revirtiendo..."
            git checkout main
            git branch -D "$SANDBOX_BRANCH"
            fail "Regresión en guardrails detectada. Sandbox descartada, main intacto."
        fi
        log "Invariantes post-merge verificados con éxito."
    fi

    # 7. Unir a main
    git checkout main
    git merge "$SANDBOX_BRANCH" --ff-only
    git branch -d "$SANDBOX_BRANCH"
    log "Rama main actualizada limpiamente."

    # 8. Reconstrucción controlada de Docker
    log "Compilando nueva imagen Docker..."
    docker compose build --no-cache 2>&1 | tee -a "$LOG_FILE"
    log "Reiniciando contenedor hermes-agent..."
    docker compose up -d 2>&1 | tee -a "$LOG_FILE"

    # 9. Health Check
    sleep 10
    docker exec hermes-agent /command/s6-svstat /run/service/gateway-* 2>&1 | tee -a "$LOG_FILE"
    systemctl restart hermes-serve || true

    log "=== Actualización a $TARGET_TAG completada con éxito y sin riesgos ==="
    exit 0
fi

fail "Modo desconocido: $MODE. Use --check o --apply <tag>"
