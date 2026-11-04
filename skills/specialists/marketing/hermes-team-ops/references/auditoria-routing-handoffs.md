# Auditoría de ruteo Discord por perfil + buzones de handoff

Verificado en vivo 03-nov-2026 (DEV, audit de la implementación de Roshi: 9 rutas discord + 6 WA, matching 17/17 PASS, gate con dedupe OK).

## Arquitectura implementada (estado 03-nov-2026)

- `profile_routes` en `/opt/hermes-agent-data/config.yaml`: rutas `- name:` (platform: discord/whatsapp, chat_id, profile). Canales sin ruta → perfil default. Hilos hijos de foro heredan la ruta del `parent_chat_id`.
- Buzones: `/opt/data/inbox/<agente>/{from-*,pending,done,failed}` — un agente deja trabajo para otro con `agent_handoff.py send`.
- Vigías `buzon-<agente>`: cron `*/1` con `script: buzon_<agente>_gate.sh` (wrapper de `scripts/buzon_handoff_gate.sh <agente>`); si hay novedad emiten `{"wakeAgent": true}` + prompt que inyecta el contenido; si no, salen en ~20 ms sin arrancar agente (0 tokens).
- Dedupe: state por agente (ej. `state/buzon_<id>.seen`) — la 2ª corrida sobre el mismo contenido devuelve `false`.

## Receta de auditoría independiente (7 pasos)

1. **Backup pre-cambio real:** contar rutas en el backup de config (debe tener 0 si es estado pre-cambio). `ls -la /opt/hermes-agent-data/config.yaml*`.
2. **Parsear rutas EN VIVO con el módulo real del gateway**, no con parser a mano:
   `/opt/hermes-agent/.venv/bin/python` (el system python NO importa `gateway.*`) con `sys.path.insert(0, '/opt/hermes-agent')`; `from gateway.profile_routing import parse_profile_routes, match_profile_route`. Extraer el bloque desde el primer `- name:` de `profile_routes` hasta el fin de la lista y construir los dicts crudos.
   - CRÍTICO: el bloque se mueve de línea entre backup y live (612→595). NUNCA usar rangos de línea fijos — anclar en marcadores `- name:`.
3. **Casos mínimos de matching (17):** los 9 canales dueños; 1 hilo hijo (parent_chat_id); 3 canales SIN ruta esperando `None` (caen a Ragnar); WhatsApp lid y número por si se rompió. Aceptar solo 17/17.
4. **Gate de handoff:** `bash /opt/hermes-agent-data/scripts/buzon_handoff_gate.sh <id-test>` con buzón vacío → `false` (~20 ms); crear `inbox/<id-test>/from-test/pending/msg.json` → `true` + prompt; correr 2ª vez → `false` (dedupe). LIMPIAR después: `rm -rf inbox/<id-test>` + borrar el state.
5. **Vigías:** perfiles en `profiles/<p>/cron/jobs.json`; PERO el del default (`buzon-ragnar`) vive en el store central `/opt/hermes-agent-data/cron/jobs.json`. Evidencia de ejecución real: `last_run_at` reciente, `last_status: ok/completed`, cadencia 60 s.
6. **Gateway y plataformas:** `systemctl status hermes-agent` (PID) + `grep -a "Connected as" logs/agent.log` post-restart. Las rutas se cargan al arrancar; como el gateway reescribe config.yaml en runtime, re-contar rutas tras el rewrite.
7. **Entregas de cron vs ruteo:** campo `deliver: discord:<chat_id>` en jobs.json = entrega de mensajes, no ruteo. Un cron del default entregando al canal de otro perfil NO es interferencia; el dueño de la ruta es quien responde ahí.

## Trampas encontradas (no repetir)

- **Log de handoffs silencioso:** el gate escribe su log con `|| true`; si `logs/buzon_handoff.log` es root:root 644, el gate (corre como hermes) no puede escribir y la trazabilidad de despertares muere sin error visible. Fix: `chown hermes:hermes` + probar escritura real como hermes.
- **Prueba sintética ≠ aceptación:** matching 17/17 + gate OK no prueba el despertar real de un perfil por buzón. La aceptación "entrega ≤ 1 min" exige un handoff real observable; sin él, el ticket queda En revisión.
- **Standalone:** perfiles con `gateway.standalone: true` (roshi, vigia) no son servidos por el gateway multiplexado — ver warning `gateway.run: profile 'X' is standalone` en agent.log al arrancar.
- **Repo vivo:** auditar `git -C /opt/hermes-agent status --porcelain` (branch + nº de dirty) y reportarlo; los scripts nuevos en `hermes-agent-data/` NO están versionados.
- **Ruido de logs:** errores Langfuse OTLP 404 cada 5 s llenan `errors.log` (1,5 MB) — filtrar con `grep -av "langfuse\|otlp"` antes de buscar errores reales.

## Rutas activas (referencia rápida, 03-nov-2026)

- Discord: freyja-social, archivo-bragi-content (bragi), vili-ads (vili), finanzas + analytics (heimdall), leads-tickets (ullr), archivo-multimedia (sindri), desarrollo-front (brokkr), hermodr-soporte (hermodr). Sin ruta → default/Ragnar: #general, crons-ads, hilo de tickets del bot.
- WhatsApp: lid/número de Chucho → roshi; lid/número de Plon → default. Intacto tras el cambio.
