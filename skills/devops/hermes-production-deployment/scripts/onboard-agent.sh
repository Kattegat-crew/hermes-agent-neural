#!/bin/bash
# Script de autoconfiguración para nuevos perfiles Hermes de NeuralCrew Labs
# Uso: ./deploy-profile.sh <nombre-cliente> [github-user]
# Ejemplo: ./deploy-profile.sh golden-game

set -e

BOLD='\033[1m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  NEURALCREW LABS — Deploy de Perfil Hermes     ║${NC}"
echo -e "${BOLD}║  Autoconfiguración interactiva                 ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# === PASO 1: Identificar cliente ===
CLIENTE="${1:-}"
if [ -z "$CLIENTE" ]; then
  echo -e "${CYAN}¿Nombre del cliente? (ej: golden-game, lucky-club, bendabal)${NC}"
  read -r CLIENTE
fi
CLIENTE=$(echo "$CLIENTE" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
echo -e "${GREEN}✓ Cliente: $CLIENTE${NC}"

# === PASO 2: Información del usuario ===
echo ""
echo -e "${CYAN}═══ Información del Usuario ═══${NC}"
echo -e "¿Nombre del usuario final?"
read -r USER_NAME
echo -e "¿Cargo del usuario?"
read -r USER_ROLE
echo -e "¿Email del usuario?"
read -r USER_EMAIL
echo -e "¿Teléfono del usuario?"
read -r USER_PHONE

# === PASO 3: Información de la empresa ===
echo ""
echo -e "${CYAN}═══ Información de la Empresa ═══${NC}"
echo -e "¿Nombre de la empresa?"
read -r COMPANY_NAME
echo -e "¿NIT / ID fiscal?"
read -r COMPANY_NIT
echo -e "¿Sitio web?"
read -r COMPANY_URL
echo -e "¿Teléfono de la empresa?"
read -r COMPANY_PHONE
echo -e "¿Dirección?"
read -r COMPANY_ADDRESS

# === PASO 4: Integraciones ===
echo ""
echo -e "${CYAN}═══ Integraciones ═══${NC}"
echo -e "¿Tiene Twenty CRM? (s/n)"
read -r HAS_CRM
echo -e "¿Usa Google Calendar? (s/n)"
read -r HAS_CALENDAR
echo -e "¿Usa WhatsApp? (s/n)"
read -r HAS_WHATSAPP
echo -e "¿Usa Telegram? (s/n)"
read -r HAS_TELEGRAM
echo -e "¿Necesita acceso a navegación web? (s/n)"
read -r HAS_WEB

# === PASO 5: Preferencias ===
echo ""
echo -e "${CYAN}═══ Preferencias del Asistente ═══${NC}"
echo -e "Tono preferido? (formal/casual/técnico) [formal]"
read -r TONE
TONE="${TONE:-formal}"
echo -e "Idioma principal? (es/en) [es]"
read -r LANG
LANG="${LANG:-es}"

# === PASO 6: Crear estructura de directorios ===
echo ""
echo -e "${CYAN}═══ Creando estructura... ═══${NC}"

BASE="/root/hermes-agent-legacy-docker/data/profiles/$CLIENTE"
mkdir -p "$BASE"/{cron,skills}
mkdir -p "$BASE/../shared/skills"
echo -e "${GREEN}✓ Directorios creados en $BASE${NC}"

# === PASO 7: Generar config.yaml ===
TPL="/root/hermes-agent-legacy-docker/data/hermes-profiles/templates"
cp "$TPL/config.yaml" "$BASE/config.yaml"
sed -i "s|<CLIENTE>|$CLIENTE|g" "$BASE/config.yaml"
echo -e "${GREEN}✓ config.yaml generado${NC}"

# === PASO 8: Generar SOUL.md ===
cp "$TPL/SOUL.md" "$BASE/SOUL.md"
sed -i "s|\[NOMBRE DEL USUARIO\]|$USER_NAME|g" "$BASE/SOUL.md"
sed -i "s|\[CARGO\]|$USER_ROLE|g" "$BASE/SOUL.md"
sed -i "s|\[EMPRESA\]|$COMPANY_NAME|g" "$BASE/SOUL.md"
echo -e "${GREEN}✓ SOUL.md generado con personalidad de $USER_NAME${NC}"

# === PASO 9: Generar AGENTS.md ===
cp "$TPL/AGENTS.md" "$BASE/AGENTS.md"
sed -i "s|\[Nombre de la empresa\]|$COMPANY_NAME|g" "$BASE/AGENTS.md"
sed -i "s|\[NIT\]|$COMPANY_NIT|g" "$BASE/AGENTS.md"
sed -i "s|\[URL\]|$COMPANY_URL|g" "$BASE/AGENTS.md"
sed -i "s|\[Teléfono\]|$COMPANY_PHONE|g" "$BASE/AGENTS.md"
sed -i "s|\[Dirección\]|$COMPANY_ADDRESS|g" "$BASE/AGENTS.md"
echo -e "${GREEN}✓ AGENTS.md generado con datos de $COMPANY_NAME${NC}"

# === PASO 10: Generar MEMORY.md ===
cp "$TPL/MEMORY.md" "$BASE/MEMORY.md"
sed -i "s|\[Nombre del usuario\]|$USER_NAME|g" "$BASE/MEMORY.md"
sed -i "s|\[Cargo\]|$USER_ROLE|g" "$BASE/MEMORY.md"
sed -i "s|\[Teléfono\]|$USER_PHONE|g" "$BASE/MEMORY.md"
sed -i "s|\[Email\]|$USER_EMAIL|g" "$BASE/MEMORY.md"
echo -e "${GREEN}✓ MEMORY.md generado${NC}"

# === PASO 11: Configurar Engram ===
ENG_DIR="/root/hermes-agent-legacy-docker/data/.engram"
if [ -d "$ENG_DIR" ]; then
  echo "{\"project_name\": \"$CLIENTE\"}" > "$BASE/.engram-config.json"
  echo -e "${GREEN}✓ Engram configurado para proyecto: $CLIENTE${NC}"
fi

# === PASO 12: Resumen ===
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  ✅ PERFIL LISTO PARA USAR                      ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BOLD}Cliente:${NC}     $CLIENTE"
echo -e "${BOLD}Usuario:${NC}     $USER_NAME ($USER_ROLE)"
echo -e "${BOLD}Empresa:${NC}    $COMPANY_NAME"
echo -e "${BOLD}Ubicación:${NC}   $BASE"
echo ""
echo -e "${BOLD}Archivos creados:${NC}"
echo "  ├── config.yaml    (modelo: deepseek-v4-flash)"
echo "  ├── SOUL.md        (personalidad: $TONE)"
echo "  ├── AGENTS.md      (datos de $COMPANY_NAME)"
echo "  ├── MEMORY.md      (preferencias de $USER_NAME)"
echo "  └── cron/          (directorio listo para tareas)"
echo ""
echo -e "${YELLOW}Próximos pasos:${NC}"
echo "  1. Revisa y ajusta los archivos generados"
echo "  2. Agrega cronjobs: reporte diario, recordatorios"
echo "  3. Activa el perfil: hermes profile use $CLIENTE"
echo "  4. Verifica: hermes chat --profile $CLIENTE"
echo ""
echo -e "${GREEN}¡Perfil $CLIENTE listo para producción!${NC}"