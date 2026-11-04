#!/usr/bin/env bash
# Reconocimiento: ¿puedo atribuir una edición de skill a perfil + sesión?
set -uo pipefail
S=/opt/data/profiles/roshi/sessions
echo "=== entradas de $S ==="
ls "$S" | head -12
echo "total: $(ls "$S" | wc -l)"
echo
echo "=== sessions.json (cabecera) ==="
head -c 700 "$S/sessions.json" 2>/dev/null
echo
echo
echo "=== ficheros de sesión ==="
find "$S" -type f | head -6
echo
echo "=== ¿algún transcript menciona skill_manage? ==="
grep -rl "skill_manage" "$S" 2>/dev/null | head -3 || echo "  ninguno"
echo
echo "=== ledger del gate (decisiones con session_id) ==="
tail -3 /opt/data/state/autoskill_gate.jsonl 2>/dev/null || echo "  sin ledger"
