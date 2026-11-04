#!/usr/bin/env bash
# Prueba de punta a punta del gate de autoskills (F3).
# Se ejecuta DENTRO del contenedor, con el mismo entorno que usa el gateway.
HOOK=/host/root/hermes-agent-legacy-docker/scripts/hooks/guard_autoskill_create.py
prueba () {
  local titulo="$1"; local json="$2"; local esperado="$3"
  printf '%s' "$json" | python3 "$HOOK" > /tmp/out.txt 2>/tmp/err.txt
  local rc=$?
  echo "── $titulo"
  echo "   esperado : $esperado"
  echo "   rc       : $rc"
  if [ -s /tmp/out.txt ]; then echo "   stdout   : $(head -c 400 /tmp/out.txt)"; else echo "   stdout   : (vacio)"; fi
  [ -s /tmp/err.txt ] && echo "   stderr   : $(head -c 200 /tmp/err.txt)"
  echo
}

prueba "D1 · nombre de un reference existente" \
  '{"tool_name":"skill_manage","tool_input":{"action":"create","name":"meta-capi-tracking","content":"---\nname: meta-capi-tracking\ndescription: x\n---\npeso pluma"}}' \
  "exit 2 + bloqueo OMITIR"

prueba "D2 · nombre de una clase de core/" \
  '{"tool_name":"skill_manage","tool_input":{"action":"create","name":"video-reel-pipeline","content":"---\nname: video-reel-pipeline\ndescription: x\n---\npeso pluma"}}' \
  "exit 2 + bloqueo EDITAR"

prueba "D3 · casi identico (plural)" \
  '{"tool_name":"skill_manage","tool_input":{"action":"create","name":"meta-capi-trackings","content":"---\nname: meta-capi-trackings\ndescription: x\n---\npeso pluma"}}' \
  "exit 2 + bloqueo EDITAR (regla D3)"

prueba "D3b · casi identico (guion_bajo)" \
  '{"tool_name":"skill_manage","tool_input":{"action":"create","name":"docx_generacion_verificacion","content":"---\nname: docx_generacion_verificacion\ndescription: x\n---\npeso pluma"}}' \
  "exit 2 + bloqueo EDITAR (regla D3)"

prueba "PERMITIDO · caso genuinamente nuevo" \
  '{"tool_name":"skill_manage","tool_input":{"action":"create","name":"calibracion-telescopio-andino","content":"---\nname: calibracion-telescopio-andino\ndescription: rutina de calibracion optica\n---\nprocedimiento"}}' \
  "exit 0 + indice de clase en stdout"

prueba "IRRELEVANTE · otra herramienta" \
  '{"tool_name":"terminal","tool_input":{"command":"ls"}}' \
  "exit 0 silencioso"

prueba "NO-OP · patch en vez de create" \
  '{"tool_name":"skill_manage","tool_input":{"action":"patch","name":"meta-ads-ops","old_string":"a","new_string":"b"}}' \
  "exit 0 silencioso"

prueba "MULTIOP · lote con un create duplicado" \
  '{"tool_name":"skill_manage","tool_input":{"operations":[{"action":"patch","name":"x","old_string":"a","new_string":"b"},{"action":"create","name":"oauth-multi-tenant-integration","content":"---\nname: oauth-multi-tenant-integration\ndescription: x\n---\ny"}]}}' \
  "exit 2 + bloqueo (detecta el create dentro del lote)"

prueba "MALFORMADO · payload invalido" \
  'esto no es json' \
  "exit 0 (no rompe el flujo)"

echo "=== ledger del gate ==="
tail -12 /opt/data/state/autoskill_gate.jsonl 2>/dev/null || echo "(sin ledger en /opt/data/state)"
