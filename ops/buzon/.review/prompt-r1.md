Eres un reviewer independiente de código. NO implementaste este cambio. Tu trabajo es encontrar defectos reales, no elogiar.

REPO / WORKTREE (no salgas de aquí): /opt/hermes-agent-data/worktrees/buzon-push
COMMIT A REVISAR: fce8201c0c86c83f59a7fd3b71c5032e057ad52c
ARCHIVOS DEL CAMBIO:
- ops/buzon/notify.py
- ops/buzon/agent_handoff.py
- ops/buzon/test_notify.py
- ops/buzon/test_agent_handoff_webhook.py
- ops/buzon/PLAN.md (contexto, no es código a revisar)

CONTEXTO DEL PROBLEMA
Los 8 perfiles de la flota corren un cron `buzon-*` cada minuto que hace polling de ficheros en /opt/hermes-agent-data/inbox/<perfil>/from-*/ con un gate bash. Eso no cuesta tokens (el gate devuelve {"wakeAgent": false}) pero levanta ~10 procesos Python de scheduler a la vez, ~90 MB RSS cada uno, sobre 4 vCPU. El objetivo es notificar por webhook en el momento del depósito y bajar los crons a un barrido de 30 min como red de seguridad.

CONTRATO DEL RECEPTOR (léelo en el código, no me creas):
gateway/platforms/webhook.py
- POST /p/{profile}/webhooks/{route}, `serves_profile_prefix = True`
- Auth Generic V2: X-Webhook-Timestamp (epoch, ventana anti-replay) + X-Webhook-Signature-V2 = hex HMAC-SHA256(secret, "<timestamp>." + body)
- Idempotencia: `_header_delivery_id` prioriza `webhook-id`; TTL 3600 s, primero gana
- `event_type` se toma de payload["event_type"]
- `_route_allows_profile` puede restringir perfiles
- `_validate_signature` y `_validate_svix_signature` tienen la lógica exacta

QUÉ DEBES VERIFICAR, COMO MÍNIMO
1. La firma implementada en notify.py coincide byte a byte con lo que valida `_validate_signature` para la rama Generic V2 (incluido el orden `timestamp + "." + body` y el hexdigest en minúsculas).
2. El `webhook-id` es estable y colisiona de forma segura: ¿qué pasa con dos tickets distintos que no traen `ticket_id`/`id`/`msg_id`? ¿Puede la idempotencia del gateway tragarse un mensaje legítimo dentro de la hora?
3. `notify()` promete no lanzar nunca. Busca rutas donde una excepción se escape: json.dumps de un payload no serializable, encoding, tipos raros, `clock` que no es callable, `timeout` negativo, perfil con caracteres que rompan la URL.
4. El timeout es de 2 s. ¿Qué pasa si el gateway acepta la conexión pero no responde? ¿Y si el cuerpo es grande? ¿El timeout cubre también la lectura de la respuesta?
5. `agent_handoff.py`: el depósito es atómico y previo al aviso. Verifica que NINGUNA ruta de error del aviso pueda hacer que el proceso salga con código != 0 o que se pierda el archivo.
6. `_leer_secreto()`: ¿puede lanzar si el JSON del archivo de secretos no es un dict? ¿Y si el archivo tiene permisos denegados? ¿Se traga un secreto vacío y luego hace un POST que el receptor rechaza con 403 (gasto inútil)?
7. Seguridad: el secreto no debe imprimirse nunca en stdout/stderr ni quedar en logs. Revisa los mensajes de `_avisar()`.
8. Tests: ¿prueban de verdad el contrato o son auto-referenciales? El test de firma usa la misma fórmula que el módulo — ¿eso prueba algo o solo copia el bug? ¿Falta el caso de body con acentos/UTF-8? ¿Falta el caso de 403?
9. Portabilidad: el módulo debe ser stdlib puro y funcionar instalado fuera del repo (en /opt/data/scripts/). `agent_handoff.py` importa `notify` sin paquete: ¿rompe cuando se ejecuta desde otro directorio? (Ojo: el import es del mismo directorio del script — verifica si eso depende de sys.path[0] y si el fallback silencioso oculta un fallo real.)
10. Nada de variables de entorno nuevas para configuración no secreta (regla del repo, AGENTS.md).

REGLAS
- READ-ONLY. No edites, no commitees, no hagas checkout, no push.
- Puedes correr: git show / git diff / grep / `uv run --quiet --with pytest python -m pytest -q` en ops/buzon
- Puedes correr sondas cortas de solo lectura con `python - <<'PY' ... PY`
- No aceptes ninguna afirmación sin leer el código. Si algo no lo puedes verificar, dilo.

FORMATO DE SALIDA OBLIGATORIO (si no cumples esto, el veredicto se descarta):

FINDINGS
- [BLOCKER|MAJOR|MINOR] archivo:linea — qué está mal, por qué duele y cómo se arregla
(si no hay hallazgos escribe exactamente: FINDINGS: none)

VERDICT: APPROVE | APPROVE WITH NITS | REJECT

JUSTIFICATION
Dos o tres frases atadas a los criterios de arriba, no impresiones generales.

TESTS-EVIDENCE
Comandos exactos que corriste y su salida resumida (números reales).
