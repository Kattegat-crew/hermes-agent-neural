#!/bin/bash
# buzon_handoff_gate.sh — Gate genérico de handoffs para perfiles en DEV.
#
# CONTRATO con el runner (cron/scheduler_prompt.py): la ULTIMA linea no vacia de stdout
#   {"wakeAgent": false}  -> salta el turno del agente (0 tokens)
#   {"wakeAgent": true}   -> el agente corre y lee el prompt del gate
#
# Uso: buzon_handoff_gate.sh <agente>
# Si no se pasa agente, intenta deducirlo del directorio actual o variable de entorno.

set -u

AGENT="${1:-}"
if [ -z "$AGENT" ]; then
    if [ -n "${HERMES_PROFILE:-}" ]; then
        AGENT="$HERMES_PROFILE"
    else
        AGENT="$(basename "$PWD")"
    fi
fi

if [ -z "$AGENT" ] || [ "$AGENT" = "scripts" ] || [ "$AGENT" = "hermes-agent-data" ]; then
    echo "ERROR: Se requiere especificar el nombre del agente receptor." >&2
    printf '%s\n' '{"wakeAgent": false}'
    exit 1
fi

BASE="/opt/hermes-agent-data"
INBOX_DIR="${BASE}/inbox/${AGENT}"
STATE="${BASE}/state/buzon_${AGENT}.seen"
MAX_MSGS=5

_log() { printf '%s [%s] %s\n' "$(date -Is)" "$AGENT" "$*" >>"${BASE}/logs/buzon_handoff.log" 2>/dev/null || true; }

mkdir -p "$(dirname "$STATE")" "${BASE}/logs" 2>/dev/null || true
touch "$STATE" 2>/dev/null || true

GOT_SIG=""
trap 'GOT_SIG="TERM"' TERM
trap 'GOT_SIG="INT"' INT

if [ ! -d "$INBOX_DIR" ]; then
    printf '%s\n' '{"wakeAgent": false}'
    exit 0
fi

# 1. Listar archivos entrantes exclusivamente en from-* y pending/ (podando done/ y failed/)
LIST="$(find "$INBOX_DIR" \( -name done -o -name failed \) -prune -o \( -path "$INBOX_DIR/from-*/*" -o -path "$INBOX_DIR/pending/*" \) -type f -name "*.json" -print 2>/dev/null | sort)"
[ -n "$GOT_SIG" ] && { _log "senal $GOT_SIG durante escaneo; silencio"; printf '%s\n' '{"wakeAgent": false}'; exit 0; }

if [ -z "$LIST" ]; then
    printf '%s\n' '{"wakeAgent": false}'
    exit 0
fi

# 2. Filtrar mensajes nuevos contra el estado visto
NEW=""
COUNT=0
while IFS= read -r f; do
    [ -z "$f" ] && continue
    # Usamos la ruta relativa para identificar univocamente el mensaje (ej: from-bragi/ticket-01.json)
    rel="${f#$INBOX_DIR/}"
    if ! grep -qxF "$rel" "$STATE" 2>/dev/null; then
        NEW="${NEW}${f}
"
        COUNT=$((COUNT + 1))
        [ "$COUNT" -ge "$MAX_MSGS" ] && break
    fi
done <<< "$LIST"

if [ -z "$NEW" ]; then
    printf '%s\n' '{"wakeAgent": false}'
    exit 0
fi

# 3. Construir el prompt estructurado para el agente
echo "📥 Tienes $COUNT encargo(s) / mensaje(s) nuevo(s) en tu buzón ($INBOX_DIR):"
echo ""

printf '%s' "$NEW" | while IFS= read -r f; do
    [ -z "$f" ] && continue
    rel="${f#$INBOX_DIR/}"
    echo "=== [$rel]"
    cat "$f" 2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception as e:
    print(f"(error leyendo JSON: {e})")
    raise SystemExit
print("ID:", d.get("id", "s/n"), "| De:", d.get("de", "desconocido"), "| Asunto:", d.get("asunto", "Sin asunto"))
if d.get("prioridad"):
    print("Prioridad:", d.get("prioridad"))
print("Fecha:", d.get("creado_en", "-"))
tarea = d.get("tarea") or d.get("mensaje") or ""
print("Instrucción/Tarea:\n" + tarea.strip())
archivos = d.get("archivos") or []
if archivos:
    print("Archivos adjuntos:", archivos)
' 2>/dev/null || echo "(no se pudo parsear el archivo $rel)"
    echo ""
done

echo "INSTRUCCION: Estos encargos son para ti ($AGENT). Léelos, verifica los insumos/archivos,"
echo "ejecuta la acción solicitada y devuelve el resultado o notificación correspondiente."
echo "Al terminar, mueve el ticket a done/ o utiliza el script /opt/data/scripts/agent_handoff.py para responder."
echo ""

# Contrato de despertar
printf '%s\n' '{"wakeAgent": true}'

# 4. Registrar en el archivo de estado los procesados
printf '%s' "$NEW" | while IFS= read -r f; do
    [ -z "$f" ] && continue
    rel="${f#$INBOX_DIR/}"
    echo "$rel" >>"$STATE" 2>/dev/null || true
done

_log "Despertado $AGENT por $COUNT mensaje(s) nuevo(s)"
exit 0
