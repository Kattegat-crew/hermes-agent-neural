# Verificar el generador de campañas: sondas en vivo + auditoría de afirmaciones

**Cuándo:** piden "¿cómo funciona exactamente el generador?", "¿de verdad funciona así?", o hay que auditar una
infografía / README / plan contra la realidad del repo `marketing-campaign-generator`.

**Regla madre:** el estado real se prueba con **sondas**, no leyendo documentación. Un "✅" del README o una
infografía bonita describen el **diseño**; separa siempre tres cosas: *existe el código* ≠ *corrió de verdad* ≠ *está roto*.

## 0. Pre-flight (protocolo de repos vivos)

- Accesos verificados: `ssh dev` = host del contenedor (vmi3151337, DEV y donde corre el worker); `ssh prod` = VPS prod (vmi3513784).
- `cd /root/marketing-campaign-generator && git status --porcelain && git pull --ff-only` (o la ruta `/host/root/...` desde el contenedor).

## 1. Sondas (comandos que ya funcionaron)

- **Gate de gasto** — `python3 scripts/spend_gate.py --status`: hoy los 4 proveedores (fal, monid, nan, elevenlabs)
  **CERRADOS**. `--dry-run` no exige gate; un intento real sin gate sale con **exit 3 antes de tocar la red**.
- **Worker** — proceso: `for p in /host/proc/[0-9]*; do tr '\0' ' ' < "$p/cmdline" | grep -q reel_worker && echo $p; done`.
  En el host: `systemctl is-active reel-worker.service && curl -s 127.0.0.1:8090/health`. El :8090 **no** es alcanzable
  desde el contenedor (red separada) → sondear por `ssh dev`.
- **Calendario y estados** — `planning/calendario-sep2026/calendario.jsonl`, 1 fila por pieza. Estados reales:
  `a_producir`, `listo_para_aprobacion`, `aprobado`, `publicado`. Publicación **real** = filas con `media_ids` +
  `publicado_en` + `aprobado_por`. Cuenta los totales parseando el JSONL, nunca de memoria.
- **Publicador** — `cron_publish_due.py` (ventana slot ±2 h) → `publish.py`, que **aborta si `estado != 'aprobado'`**
  (salvo `--force`). Wrappers en `/opt/data/scripts/calendario_*.sh` (resuelven la ruta del repo con fallbacks).
- **Crons de Hermes** — `jobs.json` (del perfil y del default en `/opt/data/cron/jobs.json`), `executions.db`
  (tablas `executions`, `cron_incidents`) y **la respuesta real de cada corrida** en
  `/opt/data/cron/output/<job_id>/<fecha>.md`: 0 bytes = corrida silenciosa; ahí se ve si el *script* hizo su trabajo
  pero falló el *paso del agente* (distinguirlo evita reportar una publicación como caída cuando sí salió).
- **Flows ActivePieces (PROD)** — `ssh prod "docker exec -i ap-db psql -U postgres -d activepieces -P pager=off" <<'SQL' ... SQL`.
  Tablas: `flow` (id, `status`, `"externalId"`, `metadata->>'displayName'`) y `flow_run` (`"flowId"`, `status`,
  `created`, `"stepsCount"`, `"failedStep"->>'name'`). Contar OK/FAILED por flow es la prueba dura de si el pipeline
  "desatendido" existe.

## 2. Ejecutar el eslabón gratis en vez de creerle al doc

- **Linter de guion** (gratis, mide la voz real): `.venv/bin/python scripts/guion_lint.py <guion>.md` **en el host**
  → `VOZ medido real: {...} -> total Xs`; `--no-voice` corre offline. Contrato: exit 0 = OK, 1 = errores.
- **Guion → brief** (gratis): `python3 scripts/scene_plan.py <guion>.md --out brief.json` → imprime
  `RESULTADO: brief valido (approved_to_spend=false, gate cerrado)` + tope de gasto 0.
- **Motor** (dry-run es el default): `reel_engine.py --brief b.json --dry-run --base /tmp/x` → cadena
  `job_started → refine_ok → tts_ok → monid_skipped → mix_ok → audit_ok → concat_ok → reel.mp4` + `audit-report.json`.
  Un brief mínimo por escena necesita `input_image` (ruta local que exista) **o** `prompt_image`; sin eso **falla cerrado**
  (`FileNotFoundError`). Esto es la prueba de que las etapas 3–6 están construidas, con $0.

## 3. Resultado de la auditoría (12-sep-2026) — tabla de referencia

| # | Eslabón | Estado real |
|---|---|---|
| 1 | Guión humano | ✅ real (20+ guiones vivos) |
| 2 | Revisión del guión gratis | ✅ real, probado (linter mide 56.9 s en pieza de 60 s) |
| 3 | Borrador 3D gratis | ✅ construido (`draft_renderer.py`, chromium + three.js) |
| 4-6 | Imagen → video → voz | ⚠️ construido, **LIVE nunca ejecutado** (gate cerrado por diseño) |
| 7 | Portal + aprobación por chat | ✅ real (302 SSO; `aprobado_por` en cada fila) |
| 8 | Publicación IG/FB | ✅ real **por crons + Composio** (10 piezas con `media_ids`), **no** por ActivePieces |
| 9 | Métricas e informes | ✅ real (posts.jsonl, dashboards, paquete 7:30); cierre de campaña sin estrenar |

Números que la infografía acertó al dígito: 64 piezas = 36 `a_producir` + 18 `listo_para_aprobacion` + 10 `publicado`;
2 canales, 2 marcas, $0 sin firma. Matiz a corregir en el material del cliente: los "18 por aprobar" están en
`listo_para_aprobacion`, y `aprobado` pendiente era **0**; y la voz de Lucky **ya estaba registrada**, no "en elección".

## 4. Pitfalls

- **"ENABLED" ≠ "funciona"** de un flow AP: hay que ver `flow_run` y el `failedStep`.
- **Correr scripts del repo:** los que usan dependencias del `.venv` (edge-tts, etc.) se corren **en el host**
  (`ssh dev` + `/root/marketing-campaign-generator/.venv/bin/python`); el `python3` del contenedor sirve para los
  stdlib-only. Invocar el venv del repo desde el contenedor no es viable.
- **Temporales creados por `ssh` en el host quedan root-owned**: no se borran desde el contenedor (`Permission denied`);
  se limpian con el mismo `ssh` que los creó.
- **No confundir dry-run con live**: el motor corre dry-run por defecto y el paso pagado aparece como `monid_skipped`.
  Declarar que "el pipeline genera el reel" porque el dry-run produjo un mp4 es sobre-vender.
- El `approved_by` del gate de gasto **no es prueba criptográfica** (protege de accidentes y de agentes cooperativos).

## 5. Forma del entregable

Veredicto corto arriba → paso por paso con la evidencia observada → números/discrepancias contra el material del
cliente → "qué falta para que sea tal cual lo prometido". Dejar el informe + artefactos de la prueba en el workspace
(`workspace/verificacion-mcg/`: informe `.md`, `audit-report.json`, `logs.jsonl`, `reel.mp4`) y limpiar el host.
