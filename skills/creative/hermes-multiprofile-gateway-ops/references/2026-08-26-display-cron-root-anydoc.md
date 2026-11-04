# Sesión 26/08/2026 — display por perfil, cron root y reinicio s6 (evidencia)

## 1. Bots filtran cadena de pensamiento/comandos en Discord (Ley 5)

- **Síntoma usuario:** "Ahora está mostrando toda la línea de pensamiento y comandos que ejecuta".
- **Causa raíz (verificada en código):** `gateway/display_config.py` — para Discord el default es
  `_TIER_HIGH = {tool_progress: "all", tool_preview_length: 40, busy_ack_detail: True, interim_assistant_messages: True}`.
  Los 8 config.yaml de perfil NO tenían bloque `display`, así que `resolve_display_setting` caía al default
  por plataforma (paso 3 de la resolución: per-platform override → global → `_PLATFORM_DEFAULTS` → `_GLOBAL_DEFAULTS`).
- **Fix aplicado:** bloque `display` en los 8 perfiles (ver `templates/display-profile.yaml`) con backup
  `config.yaml.bak-display` ×8. Verificado: `resolve_display_setting(cfg, 'discord', 'tool_progress') → 'off'`
  y `show_reasoning → False` para los 8 (idéntico al default Ragnar).
- **Por qué aplica sin reinicio:** `user_config = _load_gateway_config()` (run.py:27982) corre DENTRO de
  `_profile_runtime_scope(profile_home)` (run.py:15580) → lee el config del perfil enrutado; caché por mtime
  invalida al editar.

## 2. Cron one-shot no_agent "silent" sin error (Ley 6)

- Los crons `no_agent` con `script` corren como ROOT en este VPS: `/opt/data/cron/output/<job_id>/` propiedad
  `root root` (job `gateway-restart-fix-memoria` e67d3212d788).
- El campo `script` debe ser relativo al scripts dir del scheduler; para root `get_hermes_home()` = `/root`,
  no `/opt/data`. El script `gateway_restart_once.sh` no existía bajo `/root` → el job escribió
  `Status: silent (empty output)` con `last_status: ok`, SIN error.
- **Diagnóstico:** `docker exec -u root hermes-agent sh -c 'ls -la /opt/data/cron/output/<job_id>/'` (¿dir root?)
  + verificar si el script existe en `/root/.hermes/scripts/` o `/root/scripts/`.
- **Fix:** `docker exec -u root hermes-agent sh -c 'cp /opt/data/scripts/<s> /root/.hermes/scripts/ && cp /opt/data/scripts/<s> /root/scripts/'`.

## 3. Post-check de reinicio s6 engañoso (Ley 1, evidencia extra)

- `docker exec -u root hermes-agent bash /opt/data/scripts/gateway_restart_once.sh` (apuntando a
  `s6-svc -r /run/service/gateway-default`) → log "restarting gateway-default via s6", exit=0, pero
  post-check a +25s seguía mostrando PID 64919 (el mismo).
- El turno en curso se interrumpió poco después ("previous turn was interrupted by a gateway shutdown") y el
  gateway volvió online → el restart SÍ se ejecutó; el ciclo graceful de s6 tardó más que los 25s del post-check.
- **Lección:** un único poll inmediato NO prueba que el reinicio falló. Confirmar con el siguiente inbound o
  con la interrupción de sesión.

## 4. Lectura de archivos por los bots (anydoc)

- `read_file` extrae nativamente `.docx`, `.xlsx`, `.ipynb`; PDF y Office legacy requieren el paquete opcional
  `firecrawl-anydoc` en la VERSIÓN EXACTA `==0.1.6` (`tools/lazy_deps.py:298` spec `"tool.doc_extract"`).
  Instalar 0.1.8 deja `feature_missing=True` (version mismatch) y el lazy-install falla (venv sin pip).
- Instalación: `uv pip install --python /opt/hermes/.venv/bin/python "firecrawl-anydoc==0.1.6"`.
  Si `site-packages` es de root: `docker exec -u root hermes-agent sh -c 'chown -R hermes:hermes /opt/hermes/.venv/lib/python3.13/site-packages/'`
  (puede tardar >60s; usar background).
- Quirk PDF: un PDF ASCII sin comprimir (stream plano) engaña al heurístico binario de read_file
  (`is_binary: false`) y se vuelca como texto crudo; los PDF reales con FlateDecode se extraen limpio.
- Verificación directa:
  ```python
  import sys; sys.path.insert(0,'/opt/hermes')
  from tools.read_extract import extract_document_text, is_extractable_document
  print(is_extractable_document('/ruta/x.pdf'))       # True tras instalar 0.1.6
  print(extract_document_text('/ruta/x.pdf')[:200])
  ```