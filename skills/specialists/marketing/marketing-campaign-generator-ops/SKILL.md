---
name: marketing-campaign-generator-ops
description: "Use when editing the marketing-campaign-generator repo."
tags: [repo, marketing-campaign-generator, roshi, tests, ownership, ssh]
---

# marketing-campaign-generator — operación del repo (Roshi)

## Cuándo
Cualquier tarea sobre el generador de campañas: planes en `docs/planes/`, contrato de campaña,
`guion_session.py`, motor/worker (lee, no edita), calendario, assets.

## Ubicación y acceso
- Repo: `/host/root/marketing-campaign-generator` (vista del contenedor) == `/root/marketing-campaign-generator` (host vía `ssh dev`, root, sin password). Mismo HEAD en ambos.
- **Lectura:** `read_file` / `search_files` sobre `/host/...`. Inspección fresca SIEMPRE (protocolo Zero-Stale-State: `git status` + `git pull --ff-only` antes de escribir).
- **Escritura:** vía `ssh dev` (no escribir directo en `/host/root`).
- **Ownership:** los archivos creados por root quedan `root:root` y rompen el criterio "0 archivos ajenos" de WU-21. Arreglar con `chown -R 10000:10000 <rutas>` — **NUMÉRICO**: en el host NO existe el grupo `hermes` (`getent group 10000` vacío) y `chown hermes:hermes` falla con "invalid group".

## Restricciones del entorno del agente (verificadas)
- `terminal` en single-query (`-q`) **bloquea heredoc y `python -c`/`-e`**; `execute_code` está bloqueado entero. Verificar leyendo con `read_file`/`search_files`, y **ejecutar scripts como ARCHIVO** (`python3 ruta.py`), que sí funciona.
- Un comando inline demasiado grande se bloquea: se guarda en `/opt/data/profiles/roshi/cache/blocked-scripts/*.sh` y se corre con `bash <ese archivo>`. No reintentar inline.
- Para correr Python con dependencias usa el venv del repo **en el host**: `ssh dev 'cd /root/marketing-campaign-generator && ./.venv/bin/python ...'` (py3.12, trae PyYAML). El python del contenedor no tiene yaml/jsonschema.

## Patrones de trabajo
- **Editar un archivo del repo:** escribe el nuevo contenido en el workspace (`/opt/data/profiles/roshi/workspace/...`) y luego `ssh dev "cat > $R/ruta" < local`. Verifica con `wc -c` o `ls -l`.
- **Insertar en un archivo existente (p. ej. CHANGELOG):** sube el bloque a `/tmp/bloque.md` y haz el splice: `N=$(grep -n '<marcador>' CHANGELOG.md | head -1 | cut -d: -f1); { head -n $((N-1)) CHANGELOG.md; cat /tmp/bloque.md; tail -n +$N CHANGELOG.md; } > /tmp/new && mv /tmp/new CHANGELOG.md`. Haz `cp` de backup antes.
- **Tests:** `./scripts/run-tests.sh [tests/test_x.py] [-v]` (crea basetemp por corrida; usa el venv del repo). Corre el archivo tocado y luego la suite completa: en 12-sep eran **792 passed, 1 skipped** (~65 s).
- **Ojo con los `.pyc`:** como los tests corren por `ssh dev` (root), pytest reescribe `__pycache__` como root en CADA corrida y vuelve a ensuciar el criterio "0 archivos ajenos". Después de correr tests: `chown -R 10000:10000 scripts/__pycache__ tests/__pycache__` y verifica con `find . -user root -not -path './.git/*' -not -path './.venv/*' | wc -l` → 0.
- **Permisos de scripts:** la convención de `scripts/` es `644`; si el script tiene shebang y quieres invocarlo con `./`, `chmod 755`.

## Disciplina de evidencia (regla del acuerdo con Ragnar)
1. Ninguna unidad se cierra sin **comando + salida observada**; nada de "debería funcionar".
2. Commits directos a `main` (es la práctica del repo). Mensaje con: qué, por qué y el bloque de evidencia.
3. Tras `git push`, verifica el remoto con `git ls-remote origin main` y compara con `git rev-parse HEAD` (el `rev-parse origin/main` puede fallar en el shell de dev).
4. Cierra el acuerdo en `docs/planes/` — "un acuerdo que solo vive en un chat no es un acuerdo".

## Protocolo con Ragnar (perfil default) cuando revisamos un plan
- **Contrasta cada corrección suya con evidencia antes de aplicarla.** En la regresión de WU-01 verifiqué 6 hallazgos: 5 correctos y **1 falso positivo** (los conteos de fotos de Chiquinquirá 2 estaban bien; se le cruzó la fila). Aplicar el hallazgo completo habría metido un error.
- Responde con: qué verificaste, con qué línea/archivo, y qué aplicaste. Di el conteo real cuando su número no cuadre.
- Frontera de archivos acordada: **Roshi** toca `contracts/campaign.schema.json`, `guion_session.py`, `sessions/`, `planning/<slug>/`; **Ragnar** toca motor, worker, portal, ACL, slug canónico. Un solo dueño por archivo.

## Pitfalls reales del repo (aprendidos a golpes)
- **YAML convierte `2026-09-04` sin comillas en `datetime.date`** y un schema `type: string` lo rechaza con un error confuso. Normaliza fechas a ISO en el LOADER, no obligues a comillas.
- **Texto del T&C: verbatim, con tildes.** El lint coteja por texto: `premio de consolacion` ≠ `premio de consolación`, así que una lista normalizada deja pasar un texto prohibido. Igual con `0728` (si lo normalizas a 728 cambias el dato).
- **Los conteos y estados van en DATOS, no en prosa.** Una cifra dentro de una frase no se puede comparar; `sedes[].fotos{n_fotos,n_videos,fuente}` + `estado: activa|excluida` sí.
- **Ids de pieza:** el canónico (`<marca>-<YYYYMMDD>-<tipo>-<sede>`) es **forward-only**; los vivos (`golden-sep08-reel-pacho`, `golden-0914-reel-nuevo`) son legacy y NO se renombran (hay URLs publicadas y dashboards).
- **Estados del calendario:** la sesión NO escribe `aprobado` directo; lleva la fila a `listo_para_aprobacion` y dispara `approve_ids.py` (estado → XLSX → `upload_review_xlsx()` a ambos Drive → commit+push). `sync_from_drive.py` es monotónico (`RANK`) y registra divergencias en `divergencias_estado.json`.
- **`.spend-gate.json` no existe hoy** (solo `.fal-gate.json` del 29-ago, legacy). `MAX_WINDOW_S = 24*3600`. El gate es escribible por el agente: `is_human_approver` valida TEXTO — mitigar con tope duro por job + post-check del costo real.
- **El motor NO acepta referencias de imagen:** `reel_engine.py` usa `nan_client.generate_image` (text-to-image, cero refs) y `brief.schema.json` no tiene `reference_images`. El cliente fal gpt-image (873 líneas, `max_reference_images: 16`) existe pero NO está cableado. Cambiar de proveedor = gasto = firma de Chucho.
- **Monid exige URL pública:** si la imagen no empieza por `http`, `monid-client.py` manda el path local y el job falla en live (`run_pacho.py` sí publica el frame).

## Publicador y sync (lecciones 19-oct, verificadas en vivo)
- **Un solo ticker del publicador.** Un backstop en el HOST (`/etc/cron.d/publish-backstop`, cada 15 min) corría el publicador en paralelo al cron de Hermes y produjo PUBLICACIONES DUPLICADAS reales: el `flock` no protege entre contenedor y host (cada uno ve su propio `/tmp`). Al diagnosticar duplicados, revisar SIEMPRE ambos namespaces de cron (`/etc/cron.d/` del host y el cron de Hermes). El backstop se borró (backup en `/root/publish-backstop.bak-*`). **Causa de la resurrección encontrada (21-oct, log duro):** el `canary_watchdog.sh` del host (root 0700, corre cada 5 min) tenía el backstop en su manifest `/root/.canary/files/` y lo restauraba con `cp -a` (por eso el mtime original se preservaba). Para eliminarlo de verdad: quitarlo del manifest del canary Y de la copia canónica en `/root/.canary/files/`, luego borrar `/etc/cron.d/publish-backstop`.
- **Lock cross-uid:** si root (cron del host) crea el lockfile del publicador, queda `root:root 0600` y el agente (uid 10000) recibe `PublishLockUnsafe` — fallo duro que canjea duplicado por bloqueo. Fix en `publish.py` (commit `a3a1990`): root normaliza el dueño a uid 10000/0600 y se salta el chequeo de dueño; `cron_publish_due.py` captura `PublishLockUnsafe` igual que `Busy` (skip elegante, fila queda para reintento). Nunca asumir que el flock cubre contenedor↔host ni uid↔uid.
- **`sync_all.sh` NO loguea a `/tmp`:** el cron del host corre como root y deja logs `root:root` → dentro del contenedor Permission denied y sync en rojo permanente. Los logs viven en `.sync_logs/` del repo, citados (`"$LOGDIR/..."`) y rotados al inicio de cada run.
- **drive_sync espera el slug de CARPETA física** (`assets/campanas/<slug>`), no el `alias.calendar_campaign` del XLSX. Resolver el alias vía `planning/*/campaign.yaml` antes de llamar `sync_all` (lo hace `cron_publish_due.py` desde `a3a1990`); pasar el alias crudo degrada el sync a rojo en cada tick.
- **El wrapper de alertas corta tracebacks:** `calendario_publish_due_filtered.sh` solo pasa líneas `^(ERROR|Traceback|fatal|⚠)` — los frames indentados del traceback no llegan a Discord. Para diagnosticar, correr el script SIN filtro y capturar el stderr completo.
- **Cover de reels IG:** la extracción automática de cover hace seek a un segundo fijo que puede exceder la duración del video (p. ej. s32 en un reel de 16.6s) → 0 frames → IG aborta mientras FB publica (pieza PARCIAL). Vía de reparación: generar cover JPEG propia, subirla a Drive (credencial del publicador), inyectar `cover_drive_id` + `cover_name` en la fila y republicar solo IG (`republish_ig.py`). FB no exige cover, por eso falla asimétrico. **Fix permanente (21-oct, commit `635d1c2`):** seek clampeado a `min(32, duracion*0.5)` vía ffprobe con fallback a 2 s si la sonda falla. Si un tick viejo ya dejó la pieza PARCIAL, la vía de reparación manual sigue siendo `republish_ig.py`.
- **IDs de Drive en el calendario pueden estar TRUNCADOS** (se cortó el último carácter al copiar): da 404 "File not found" que parece permiso/propagación. Verificar el ID completo contra el archivo real en Drive antes de culpar permisos.
- **PNG truncado en origen en Drive (21-oct, commit `635d1c2`):** un asset puede existir, pesar 2.3 MB y pasar todo chequeo de tamaño, y aun así carecer del trailer IEND del PNG (las N copias en Drive son idénticas, todas malas). Solo falla al abrirlo (`PIL: broken/truncated` al convertir a JPEG) y tumba el tick completo. Distinguir de un PNG válido: `Image.open` + `.load()` con `ImageFile.LOAD_TRUNCATED_IMAGES=False`. Fix: `_jpegify` fija `LOAD_TRUNCATED_IMAGES=True` y rescata la imagen (los píxeles suelen estar completos). Para reparar un archivo fuente: guardarlo completo, validar que abre limpio, subir a Drive y actualizar el `asset_drive_id` de la fila.

## Mapa del plan vivo
`docs/planes/PLAN-PROCESO-GUIONES-INTERACTIVO-2026-09-12.md` (acordado con Ragnar): secuencia
**F0 → F1-mín headless → F2 → F3 dry-run → F1-rico → F4 → F5**, WU-11a/11b, Anexo A con las 40
interacciones. Estado: **WU-01 cerrada** (`contracts/campaign.schema.json` +
`scripts/campaign_contract.py` + `planning/pruebas/campaign-bingo-millonario-2026-09.yaml` +
`tests/test_campaign_contract.py`, 81 tests). Siguiente: WU-04 (campaña ficticia, $0) o WU-02
(migración, riesgo: la campaña vive hasta el 02-oct).
