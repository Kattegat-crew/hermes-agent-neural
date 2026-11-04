# Rollout 2026-08-27 — Diario de la wiki auto-publicado

## Qué se implementó

1. **Backup programado (PROD host 100.73.30.29):** crontab `30 3 * * *` →
   `docker exec outline-postgres pg_dump -U outline -d outline | gzip >
   /root/outline-backup-$(date +%Y%m%d).sql.gz`, retención 14 días
   (`find /root -name "outline-backup-*.sql.gz" -mtime +14 -delete`).

2. **API key de servicio "Ragnar (orquestador)":** generada con formato nativo
   `ol_api_` + 38 chars, hash sha256. Secret en `/root/.outline-apikey-ragnar`
   (PROD, 600) y `/opt/data/.outline-wiki-key` (DEV, 600). Probada end-to-end
   contra `collections.list` (200, 6 colecciones).

3. **Esqueleto NeuralCrew Interno (9 docs):** Diario, Arquitectura, VPS, Agentes,
   Programas, Runbooks, Tuits analizados (fila @mr_r0b0t ya cargada), Repos
   (5 repos reales), TikToks (vacía). Plantilla "Plantilla Diario de trabajo"
   creada vía `documents.templatize` (Qué se hizo / Bloqueos / Decisiones /
   Piezas / Contexto para mañana).

4. **Crons 23:00 rewired:** los `guardar-diario-memoria` de default/roshi/vigia
   cambiaron `script: daily_session_report.py` → `guardar_diario_wiki_step.py`
   (wrapper: reporte local + publicación en wiki). Job IDs:
   - default: `4e53d875e95d`
   - roshi: `4657b286f619`
   - vigia: `0b926127fbd5`
   Backups previos: `cron/jobs.json.bak-diariowiki` en cada home.

## Scripts (copias en /opt/data/scripts y en cada perfil)

- `publish_daily_wiki.py <Agente> [YYYY-MM-DD]` — busca/crea la página del día
  bajo "Diario", aplica plantilla (lee texto de la plantilla por el quirk 403 de
  templateId), añade sección `## <Agente> — <fecha>` con sesiones + commits git.
  Idempotente: `[SKIP]` si la sección ya existe; dedupe de bloques de sesiones
  compartidos (state.db común entre perfiles).
- `guardar_diario_wiki_step.py` — wrapper para el cron: detecta agente por
  HERMES_HOME (default|data→Ragnar, roshi→Roshi, vigia→Vigía, comms→Comms),
  corre daily_session_report.py y luego publish_daily_wiki.py.

## Errores encontrados y cómo se resolvieron

- **SQL por SSH con comillas anidadas** (INSERT con literales `"`): bash rompe.
  Solución: Python + subprocess argv, o heredoc local. `last4` dejó de calcularse
  inline → UPDATE aparte.
- **`docker run` curl primera vez se "cuelga"**: estaba descargando la imagen
  curlimages/curl. Reintento inmediato funciona.
- **301 "empty response"**: faltaban headers Host + X-Forwarded-Proto.
- **403 en search con collectionId** y **403 en create con templateId**:
  workarounds en SKILL.md principal.
- **Argumento vacío DIARIO_DIA creó doc sin título** (""): borrado (delete +
  permanent) y wrapper corregido para no pasar el arg.
- **Duplicación de sesiones** (3 perfiles, misma state.db): dedupe por substring
  en publish_daily_wiki.py + limpieza única de la página del día (regex split
  por `## `, conservando solo el primer par telegram+whatsapp).

## Verificación final

- Página `2026-08-27` con plantilla + secciones Ragnar/Roshi/Vigía y un solo
  bloque de sesiones.
- Re-test de los 3 wrappers → `[SKIP]` limpio en los 3 (idempotencia OK).
- Historial técnico registrado en `/opt/vps-brain/HISTORIAL_Y_CONTEXTO_VPS.md`
  (sección 2026-08-27).

---

# ACTUALIZACIÓN v2 — 2026-08-28: unificación + resúmenes + envío WhatsApp

## Qué cambió (orden de Jonathan)

1. **Unificación del código**: UNA copia canónica en `/opt/data/scripts/`
   (`publish_daily_wiki.py`, `daily_session_report.py`,
   `guardar_diario_wiki_step.py`). Los perfiles roshi/vigia usan **symlinks
   RELATIVOS** (`../../../scripts/x.py`) — los absolutos `/opt/data/...`
   quedan MUERTOS en el host (allí el árbol es `/root/hermes-agent-legacy-docker/data`).
   Los `.bak` viejos de perfiles se dejaron como respaldo histórico.
2. **Resúmenes reales**: `sessions_summary_agent.py` (canónico) consulta la
   state.db, extrae los pedidos reales del usuario (sin wrappers de
   plataforma) y genera 1-3 líneas por sesión vía LLM glm5.3-flash
   (max_tokens 3000 — el modelo gasta tokens en reasoning_content antes del
   content). Filtros: crons/tests fuera, sin CLI. Honestidad: si la sesión
   no registra resultado, dice "sin registro del resultado".
3. **Candado anti-mangle**: ejecutar sin NOMBRE_AGENTE → exit 2 (bug del
   27/08 creó sección "default" duplicada).
4. **Envío WhatsApp**: `resumen_diario_wa.py` extrae los bloques "###
   Resumen" de la página del día y los envía vía bridge (`POST /send`,
   127.0.0.1:3000 — SOLO desde el contenedor). Destinos: grupo
   `120363430610606995@g.us` ("Neural Golden-Lucky", 6 participantes —
   JID SIN CONFIRMAR con Jonathan) + DM Jonathan `573166910728`.
   **Candado**: no envía sin `/opt/data/scripts/.resumen_diario_wa_enabled`.
5. **Cron `resumen-diario-wa`** (id `7c0a0431a91d`, 07:15, no_agent,
   deliver local): script `resumen_diario_wa_wrapper.sh` — envuelve en
   `docker exec hermes-agent` porque los script-jobs corren en el HOST y
   allí 127.0.0.1:3000 NO existe (lección dura, crasheó el informe 07:12).

## Errores v2 y lecciones

- **Bug mío: doble envoltura del fence** (pasé `ses_txt` ya envuelto a
  `agent_section` que envuelve de nuevo) + dedup de commits contra texto
  re-serializado por Outline → página rota. Fix: dedup ANTES de armar la
  sección, commits solo 1×/página (`"### Commits del día" in text`).
- **glm5.3 `content=None` con max_tokens bajo**: quema tokens en
  `reasoning_content`. Fallback en script: si content vacío, usar
  reasoning recortado; si no, lista mínima sin LLM.
- **Namespace host vs contenedor**: LOS CRONS SCRIPT CORREN EN EL HOST.
  `/opt/data` = `/root/hermes-agent-legacy-docker/data`. `/opt/data` NO existe como ruta
  en el host (solo el bind dentro del contenedor). Symlinks relativos OK en
  ambos; `docker exec` para tocar el bridge; config.yaml del host es
  espejo cifrado (api_key enmascarada) — el LLM-call debe hacerse desde el
  contenedor o con la key real.
- **`resumen_diario_wa.py` NO soporta correr en el host** (usa urllib a la
  wiki): siempre vía wrapper docker exec. El run --dry directo en host
  crashea con Connection refused (wiki no alcanzable en ese netns).

## Verificación v2

- Simulación host exacta (chroot del host real): `[SKIP]` limpio en los 3
  perfiles con HERMES_HOME correcto; wrapper --dry imprime el mensaje
  completo; HOLD activo sin bandera.
- Página `2026-08-27` regenerada con formato v2: "Qué se hizo hoy" prefill,
  3 bloques `### Resumen`, 1 solo dump de sesiones + 1 de commits, fences
  balanceados (4).
