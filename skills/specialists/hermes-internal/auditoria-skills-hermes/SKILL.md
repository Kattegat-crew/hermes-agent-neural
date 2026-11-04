---
name: auditoria-skills-hermes
description: "Use when auditing or counting skills in a Hermes fleet."
tags: [hermes, skills, auditoria, conteo, canon, symlinks, sync, flota]
---

# Auditoría de skills en una flota Hermes

Disparadores: "recuento de skills", "accesibilidad de skills por agente", "por qué el agente no encuentra una skill", "lógica vs realidad del catálogo", informes de inventario de habilidades.

## Ritmo de trabajo probado

1. Scripts ya escritos y verificados: `/opt/data/profiles/roshi/workspace/tools/skills_audit_{a..o}.py`.
   Intérpretes correctos:
   - `markdown` y `yaml` viven en `/opt/hermes/.venv/bin/python`.
   - `/opt/data/.venv/bin/python` tiene `PyMuPDF` (fitz) y `PIL`.
   - **El `python3` del sistema NO tiene `yaml`** → `tools.skills_tool` falla al importarlo.
   - Runtime real: `HERMES_HOME=/opt/data/profiles/<perfil> /opt/hermes/.venv/bin/python script.py`.
2. Guardar salidas crudas como evidencia: `workspace/reports/evidence/recon_<letra>.txt`.
3. Informe en `workspace/reports/` + conversión a PDF; verificar con `tools/verifica_pdf.py` (páginas + strings clave), nunca a ojo.

## Modelo mental de la resolución de skills

- `get_skills_dir()` = `$HERMES_HOME/skills` (perfil). `get_external_skills_dirs()` lee `skills.external_dirs` del `config.yaml` **del perfil**. `get_scan_ordered_skills_dirs()` fija precedencia **proyecto → local → externos**, first-wins por nombre.
- Embudo real: `SKILL.md` presentes → nombres únicos → **− `skills.disabled`** → **− `platforms` incompatibles** = lo que devuelve `skills_list()` (`count: N`). El `.skills_prompt_snapshot.json` guarda MÁS entradas que las visibles: no usarlo como fuente del conteo real.
- Prueba dura: `skill_view(name=...)` sobre una skill del catálogo. El error es la evidencia: `Permission denied` = symlink a ruta host; `not found` = fuera del universo de dirs.
- `skill_manage(create)` escribe en `<perfil>/skills` **o en `skills.create_dir` si está configurado** (nunca en `external_dirs`).
  - ⚠️ **CORRECCIÓN 2026-09-17**: la versión anterior de esta skill decía "NUNCA en el catálogo central". Es **falso para el perfil `default` (Ragnar)**: su `HERMES_HOME=/opt/data`, así que `get_skills_dir()` = `/opt/data/skills` = **el canon mismo**. Por eso el canon tiene 361 skills sueltas en la raíz y 178 creaciones de agente dentro. Su `create_dir` está en `None`: **Ragnar escribe directo en el catálogo compartido**.
  - Verificar SIEMPRE antes de opinar: `HERMES_HOME=<home> python -c "...skill_utils.get_skills_dir(), get_skill_create_dir()"`.

## Acta de mutaciones: `.curator_ledger.jsonl` (la fuente de verdad de "quién creó qué")

Vive en `<HERMES_HOME>/skills/.curator_ledger.jsonl` (**una por perfil**, no una global). Append-only, 1 línea JSON por mutación:
`{id, ts, actor, action: create|patch|write_file, skill, evidence.session_id, before[], after[]}`.

- `actor=curator` ⇒ lo escribió el **fork de revisión en background** (la autoskill). `actor=agent` ⇒ el agente en primer plano. `actor=user` ⇒ CLI firmado por el usuario.
- Derivación: `tools/skill_ledger.py::derive_actor()` → override explícito → señal `is_background_review()` (`tools/skill_provenance.py`) → por defecto `agent`.
- Es la forma **barata y exacta** de contar autoskills: 644 líneas del canon (Ragnar) = 178 creates (157 fork + 21 foreground), 251 patch, 215 write_file. Sin LLM, sin adivinar por fecha.

## Autoskills: cómo se disparan (leído en el código)

En `agent/turn_finalizer.py:797`: al cerrar el turno, si `_iters_since_skill >= _skill_nudge_interval` (config `skills.creation_nudge_interval`, default 10; flota en 15) y `skill_manage` está entre las tools válidas → `_spawn_background_review()` clona el agente con **solo `memory` + `skill_manage`** y le ordena fusionar/actualizar la biblioteca ("CLASS-LEVEL skills… not one-session-one-skill"). Corre **después** de entregar la respuesta, y **los cron lo saltan** (`skip_background_review`).

## Frontera de propiedad: `external_dirs` (read-only) vs `create_dir` (curado) — PROBADO 2026-09-17

Probado en un `HERMES_HOME=/tmp/probe-home` con `config.yaml` mínimo (no tocar la config real para probar):

| `create_dir` | `is_external_skill_path(create_dir/skill)` | Efecto |
|---|---|---|
| dentro de un `external_dir` | **True** | el fork de revisión **se niega a escribir** ("externally owned and read-only to autonomous curation") → se pierde la autocuración |
| fuera de los `external_dirs` | **False** | ✅ curado y editable |

`tools/skill_manager_tool.py:350` es el guardián. Orden de escaneo: `proyecto → local → create_dir → externos`, **first-wins por nombre** (el local sombrea al canon sin avisar).

⇒ **Regla de oro de arquitectura**: un canon compartido se declara en `external_dirs` (lectura para todos, escritura solo por promoción firmada); el sedimento escribible de cada agente vive en su dir local o en un `create_dir` **fuera** de los externos. Centralizar la escritura en un único directorio mata la autocuración y contamina el canon.

## Pitfalls verificados (2026-09-16)

- **Symlinks con ruta del host**: un perfil puede enlazar a `/root/hermes-agent-legacy-docker/data/skills/<x>`, inaccesible dentro del contenedor (`/root` es 0700 root) → `stat` da `PermissionError`, no `ENOENT`. Ese árbol es el mismo inodo que `/opt/data/skills`: se repara re-apuntando el prefijo, sin copiar.
- **Enlaces "sanos" con ruta incorrecta**: apuntan a la raíz del catálogo cuando la skill vive bajo categoría (`/opt/data/skills/grounded-citations` vs real `/opt/data/skills/research/grounded-citations`).
- **Duplicados silenciosos**: misma skill en `<categoria>/<slug>` y en la raíz del perfil → first-wins decide sin avisar.
- **Deriva de contenido**: comparar `md5(SKILL.md)` copia vs original; un perfil puede tener decenas de versiones divergentes sin que nadie lo sepa.
- **Los grafos graphify mienten por exceso**: cuentan nodos `type=skill` que el perfil no puede cargar; verificar contra `skill_view`.
- `os.walk(followlinks=True)` NO cuenta un dir-symlink roto: hay que evaluar `os.path.islink` + `os.path.exists` en el nivel 1 (si no, se reporta "0 rotos" por error).
- Los enlaces de perfil se crean por nombre de skill a nivel 1: si la skill vive categorizada en el catálogo, el enlace queda colgado.

## Reparación medida (propuesta P0, requiere OK del dueño)

1. Re-apuntar el prefijo de los symlinks del perfil (backup del listado antes: `ls -l > symlinks.bak`):
   `ln -sfn /opt/data/skills/<ruta real de la skill> <perfil>/skills/<nombre>` — el árbol host
   `/root/hermes-agent-legacy-docker/data/skills` y el canon `/opt/data/skills` son el MISMO inodo: no se copia nada.
   Cuidado con las anidadas: el enlace debe apuntar a la ruta completa del `SKILL.md` (`<categoria>/<skill>`).
2. Declarar `skills.external_dirs` en el `config.yaml` de CADA perfil (hoy sólo el default, cuya entrada
   `/opt/data/.omh/skills` no existe y se descarta en silencio): el acceso al catálogo deja de depender de symlinks frágiles.
3. Limpiar la entrada muerta y regenerar el grafo de skills del perfil (graphify) — los grafos viejos dejan nodos fantasma.
4. Verificación dura: `skills_list()` (count antes vs después) + `skill_view` sobre 3 skills antes invisibles.

## Generar el PDF (receta que funciona)

```bash
/opt/hermes/.venv/bin/python tools/md2html.py informe.md informe.html
/opt/data/.venv/bin/python tools/html2pdf.py informe.html informe.pdf
```

- **PyMuPDF 1.28.2: `story.draw(page)` NO sirve** (pide un `Device`). Usar `story.write_with_links(rectfn)` con `rectfn(rect_num, filled) -> (mediabox, where, Matrix(1,1))`; devuelve los bytes del PDF paginado.
- No hay `reportlab`, `fpdf`, `weasyprint`, `pandoc` ni LibreOffice en esta flota: la ruta válida es markdown (venv Hermes) + PyMuPDF Story (venv `/opt/data/.venv`), con CSS embebido en el HTML.
- Los comandos largos con heredoc pueden ser bloqueados por el guardarraíl del gateway: escribir el script a archivo y ejecutarlo.

## Depuración: clasificar y consolidar ANTES de borrar (regla del dueño)

Nunca borrar por criterio suelto. Secuencia obligatoria:

1. **Clasificar** por origen y destino — 6 clases: C1 canon de valor general · C2 autoskill/sedimento de agente · C3 vendor/terceros · C4 duplicados y sombras (mismo nombre en 2+ rutas) · C5 stubs (<600 bytes) · C6 huérfanas (fuera de todo canon).
2. **Detectar solape** con dos señales complementarias: (a) familias por prefijo (`hermes-*`, `oauth-*`, `reel-*`…); (b) Jaccard ≥ 0,30 sobre tokens de `nombre + description` con single-linkage. La descripción sola da clusters pobres (son cortas): hay que sumar los tokens del nombre.
3. **Fusionar** en un paraguas de clase (2 de 3: mismo disparador de entrada · solape confirmado · mismo dueño y misma fase del flujo), bajando el detalle a `references/<caso>.md` y los comandos a `scripts/`. En 2026-09-17 eso dio **19 paraguas para 200 skills** del canon.
4. **Recién entonces borrar** lo redundante: idénticos por md5 (borrar), divergentes (diff → elegir maestro → archivar el perdedor), stubs (archivar). Manifiesto firmado por el dueño ANTES de ejecutar.
5. Un lote por sesión, con gate duro en el script (`--firma`) y verificación con `skill_view` del paraguas.

## Flota de especialistas: verificar el MAPEO perfil ⇄ catálogo (2026-09-17)

Cuando exista un informe/documento que asigne un catálogo de skills a cada perfil, **nunca asumir que se aplicó bien**. Receta verificada:

1. Extraer el catálogo del documento (DOCX: `zipfile` + `word/document.xml`; cada celda de tabla sale en su propia línea tras reemplazar `</w:tc>` por un separador y `</w:p>` por `\n`). Parsear filas por posición: `[nº, nombre, FUENTE, ★, por-qué]`.
2. Índice real de cada perfil: `os.listdir(<perfil>/skills)` + `os.path.islink` + `os.path.realpath` → y **clasificar el destino con prefijo con barra final** (`/opt/data/skills-especialistas/` ANTES de `/opt/data/skills/`; si no, `skills-especialistas` se cuenta como `skills` — error cometido y corregido aquí).
3. Resolver real: `hermes -p <perfil> skills list --source all` (cuidado: **sin `-p` hereda el perfil del env de la sesión**; decir `-p default` explícito para Ragnar). Devuelve `N hub-installed, N builtin, N local — N enabled, N disabled`.
4. Matriz de confusión: `|enlaces(X) ∩ catálogo(Y)|` para todos los pares → revela desplazamientos sistemáticos. Medido en la flota NeuralCrew: **54 % de los enlaces de cada perfil pertenecían al catálogo del bot SIGUIENTE** (off-by-one de instalación), sólo 46 % al propio, y 25 % de cada catálogo no estaba en ningún perfil.
5. Descartar hipótesis con datos: round-robin (`pos % 8`) y corte alfabético (densidad de posiciones) → probados y descartados; la distribución era dispersa con densidad 0,13–0,16 y 819/850 skills enlazadas por un solo perfil.
6. Calidad de la biblioteca compartida: contar la frase plantilla y el tamaño. En `skills-especialistas`, **850/850 con la misma frase** ("Se invoca cuando la tarea pide esta capacidad"), mediana 907 B, **0 con cuerpo >3 KB**, 0 con `references/`, `triggers` u `owner` → son rótulos, no conocimiento.
7. **Detector de boilerplate**: normalizar el cuerpo (borrar el primer párrafo variable) y contar md5 → si N archivos comparten hash, no son N skills. Medido: **850 cascarones = 15 cuerpos distintos** (280 idénticos en `productivity`, 122 en `ads`…).
8. **Forense de generación**: buscar el script por la frase/fecha (`grep -rl "<frase plantilla>" /opt/data --include=*.py`, `ls -la --time-style=full-iso` vs la fecha de creación de los archivos). Aparecieron la cadena completa: `check_skills_delta.py` (05:38) → mirrors descargados (05:41) → `link_external_skills.py` (05:43) → `extract_autorar.py` + `skills_a_autorar.json` (05:47) → `autorar_skills.py` (05:48). Señal de trabajo no hecho: `import shutil` **nunca usado** y **0 referencias a los corpus** en el generador.
9. **Bug de parseo típico de DOCX→MD**: la conversión pega encabezados al final de la línea anterior (`... |# Catálogo de skills — X · 51–100`). Un `re.match(r"^### ...")` falla y **las filas se atribuyen al bloque anterior** → off-by-one silencioso (medido: Hermóðr recibió 95 filas de Brokkr). Reproducir siempre el parseo del script sospechoso contra la **verdad del DOCX** antes de culpar a los datos.
10. **Sobre-etiquetado de fuentes**: verificar cada etiqueta `[H]/[CH]/[AZ]/[CP]/[B]` contra el repo real. Medido: solo **43 de 371** etiquetas `[CH]` existían en el repo de Corey Haines (que tiene 50 skills). Un catálogo puede ser una lista de deseos con nombres inventados.
11. **Emparejamiento léxico ≠ adaptación**: nombre→nombre da coincidencias gruesas (`offer-ads`→`ads`) y descripción→descripción da **0 fuertes** cuando el catálogo está en español y las fuentes en inglés. Para re-autorar hay que usar **pase semántico con LLM + revisión humana por lote**.
12. **Herramienta de re-mapeo ya escrita**: `workspace/tools/r1_remapeo.py` — lee la verdad del **DOCX** (no del MD), resuelve cada nombre por el tag de fuente del informe (`H`→canon, `CH`→marketingskills, `AZ`→claude-skills, `CP`→awesome-claude-skills, `B`→baoyu, resto→especialistas), y emite manifiesto `add/keep/remove/protegidos/unresolved`. Flags: `--dry-run` (default), `--simular`, `--apply --firma "<nombre>"` (gate duro: aborta sin firma), `--modo real|todo`, `--verify`, `--forzar-refs`. Salvaguardas incorporadas: los ADD se validan contra un `SKILL.md` existente, y **no retira** skills citadas en `AGENTS.md`/`SOUL.md`/`MEMORY.md` del perfil salvo `--forzar-refs`. Solo toca symlinks cuyo destino real esté bajo los 3 árboles conocidos, y escribe `rollback_<ts>.sh` + `estado.json` con `aprobada_por`.

## R2 ejecutado (2026-09-18): retirar cascarones y dotar el sedimento REAL

Cierre de referencia: `workspace/reports/r2-{lote0-destinos,faseA,faseB,faseB2}-20260918.md`.

1. **Clasificar por lote antes de tocar nada.** 850 cascarones → 543 fusionar · 4 nutrir · 303 archivar. Un JSON por lote con esquema fijo (`{cascaron, destino, paraguas, seccion, evidencia}`) y checkpoint cada 15 entradas: 0 incidencias de esquema, 0 rutas inválidas.
2. **Fan-out de subagentes: 3–4 concurrentes como máximo.** 10 en paralelo → HTTP 429 en 7 de 10 y el lote se pierde entero. Con oleadas de 4+4+3: 11/11 lotes sin un fallo. Un hijo por lote, lote autocontenido (fuente + lista + ruta de salida).
3. **El pase semántico manda, el léxico no sirve.** Coincidencia del clasificador por nombres vs. el pase que lee el paraguas: 31/87 y 36/58. Obligatorio abrir el `SKILL.md` del paraguas candidato y citar la **sección exacta** (`google-ads-api` → `paid-ads`; `branding-web` → `brand-guidelines`). Los paraguas comodín (`ads`, `video`, `content-production`) son legítimos si la cita es concreta.
4. **Curaduría humana paraguas-por-paraguas antes de aplicar** (59 mapeos revisados a mano → 9 reemplazos, 1 rechazo: `animatic` no cabe en `local-headless-rendering`).
5. **Dotar = `copia`, nunca symlink.** Cada skill real se copia como directorio con `SKILL.md` dentro de `<perfil>/skills/` (los árboles externos son read-only por `external_dirs`). Verificado: 310/310 directorios reales, cero symlinks.
6. **Gate duro + rollback.** `r2_aplicar.py`: dry-run por defecto, `--apply --firma "<nombre>"` obligatorio, `estado.json` con `aprobada_por`, `snapshot_antes` y `rollback_<ts>.sh` (probado antes de re-aplicar).
7. **Guardarraíl de perfil inexistente.** El plan traía nombres de bot (`Hermóðr`) en vez de directorio (`hermodr`) → no-op silencioso. Transliterar (`ð→d`, sin tildes, minúsculas) y **abortar (exit 3)** si el perfil no existe en disco.
8. **Verificar con el resolver real, no con el plan**: `hermes -p <perfil> skills list --source all` + comprobación en disco de cada ruta. Baseline vs. post: el conteo de enabled BAJA (salen ~100 fichas vacías por bot) — eso es el éxito, no un fallo.

## R2-bis ejecutado (2026-09-19): dotar módulo — el pase semántico sobre los "unresolved"

Cierre: `workspace/reports/r2bis-dotacion-20260919.md`. Herramientas: `tools/r2bis_{analisis,corpus_index,candidatos,plan}.py`.

1. **El léxico no encuentra; el contenido sí.** De las 887 etiquetas del catálogo V6 sin skill real con ese nombre, el **55 % (471) SÍ está cubierta por una skill de otro nombre** (`hook-first-3s`→`ad-creative`, `cac-ltv`→`saas-metrics-coach`, `negative-keywords`→`ads`). El nombre falla, el procedimiento manda. **Nunca declarar "no existe" por grep de nombre.**
2. **Doble verificación del diagnóstico.** Los "unresolved" del manifiesto R1 coincidían (82–118 por bot) con el conteo propio → dos métodos, mismo número. Antes de creerte un hueco del catálogo, contrástalo con el manifiesto previo.
3. **Pre-filtro léxico de candidatos: NO sirve como decisión** (daba `duet-strategy`→`pricing-strategy` por la palabra "strategy"). Se descartó y los hijos grep-earon libre a partir del `por_que` traducido. Sirve solo como pista, jamás como veredicto.
4. **Los hijos DERIVAN la ruta al citar** (drift `marketingskills`↔`claude-skills`; algunos devuelven la ruta dentro del campo `real`). El generador del plan debe **resolver por NOMBRE contra el índice del corpus** (`rev = {ruta: nombre}`) — con eso, 0 no-resueltos.
5. **Verificar las citas de los hijos, pero bien:** grep de las primeras N palabras da **falsos negativos** (las citas cruzan líneas markdown, tablas y prefijos `fichero.md:87`). Lo que funciona: normalizar (colapsar espacios, quitar `*#`|>_"'()`, prefijo `fichero.md:NNN`) y comprobar si **algún 3-grama** de la cita aparece en el contenido real del directorio citado. Medido: **760/776 = 98 %**.
6. **Oleadas de 4 y checkpoint cada 10.** 19 lotes de 45 en 5 oleadas (4+4+4+4+3); 19/19 completos, 0 pérdidas. El hijo reescribe el JSON de salida completo cada 10 entradas (sobrevive a un corte).
7. **Números honestos = "ya presentes" ≠ "nuevas".** De 279 enlaces propuestos, **172 ya los había puesto R2** y solo 107 son nuevos. Antes de presumir dotación, contar el solape contra el perfil en disco: un mapeo que confirma el trabajo previo vale, pero no se cuenta dos veces.
8. **Etiquetas imposibles → backlog de autoría, no de enlace.** 78 etiquetas sin nada real que las cubra (9 %) van a un `r2bis_autorias.json` con su `por_que`; eso es R5 (autorar), no dotar.

## R2-bis listado y limpieza definitiva (2026-09-19): el pase de bisturí

Cierre: `workspace/reports/r2bis-lista-enlaces-20260919.md` (lista bot por bot) · `workspace/reports/limpieza-inventario-20260919.md`. Herramientas: `tools/r2bis_plan.py`, `tools/limpieza_plan.py`.

1. **"Nueva" no es "no existe en la ruta plana".** El planificador comprobaba `exists(profiles/<bot>/skills/<skill>)` y habría **duplicado 5 skills** que el perfil ya tenía **anidadas** bajo carpeta de categoría (`skills/autonomous-ai-agents/hermes-agent/`, `research/llm-wiki/`). Un perfil puede anidar skills: la comprobación va con `os.walk` buscando `*/<skill>/SKILL.md` (`ya_en_perfil()`). Síntoma de la discrepancia: 112 vs 107 "nuevas".
2. **Dos números distintos para la misma cosa = método distinto, no error.** El informe decía 107 (contaba anidadas); el planificador decía 112 (solo ruta plana). Se reconcilia listando el caso a caso, nunca promediando.
3. **La limpieza se decide por trazabilidad, no por tamaño.** Antes de borrar: grep de referencias vivas (SOUL.md/SKILL.md) **y** de citas en informes publicados. Los `plan/*.json` y `tools/skills_audit_*.py` del enfoque léxico **están citados** en los informes del 16–17/09 → grupo D, solo con `--incluir-citados`. Borrarlos rompería la cadena de evidencia.
4. **Guardarraíl de referencias con `grep -F`, jamás sin él:** con `.` como comodín, `.skills_prompt_snapshot.json.bak` matcheó 5 SKILL.md inocentes. Y para entradas ocultas el nombre no es buscable: se grepea la **ruta completa**.
5. **Limpieza en dos pasos con gate duro:** `--apply --firma` mueve a `limpieza/papelera_<ts>/` (mv instantáneo) + `restaurar_<ts>.sh` + `estado_<ts>.json`; `--purgar --firma` borra la papelera. Sin firma: exit 3. El paso reversible primero permite verificación en vivo antes del borrado irreversible.
6. **Declara la irreversibilidad en el propio informe:** borrar `.archive/` invalida los rollbacks de Fase A que se restauran desde ahí. Y dependencia de orden: `forecasting` no se toca hasta que R2-bis enlace `commercial-forecaster` (citada en `heimdall/SOUL.md`).
7. **Residuos "obvios" que NO lo son:** los 2 directorios vacíos por bot (`.hub/index-cache`, `.hub/quarantine`) son runtime de Hermes, no sobras del retiro. Comprobar antes de proponer un borrado.

## Entregable

Informe MD + PDF en `workspace/reports/`, evidencia cruda en `workspace/reports/evidence/`, y resumen ejecutivo en el chat con: acervo total y distinto, embudo de accesibilidad del perfil auditado, y divergencias lógica vs realidad priorizadas P0/P1/P2. No mutar nada durante una auditoría: sólo medir y recomendar.

## Sincronización canon ⇄ espejo con gate de firma (2026-09-20)

Contrato: `scripts/sync_container_skills.sh [--check | --apply --firma TOKEN [--adopt-drift] [--commit]] [--json /ruta.json]`
Motor: `scripts/sync_skills_sync.py` (toda la lógica; el `.sh` solo parsea flags, documenta y ejecuta).

- **Paridad por CONTENIDO, nunca por conteo.** El sync anterior comparaba *nombres* y hacía `rm -rf` del espejo: una skill **modificada** dentro del contenedor (mismo nombre, contenido nuevo) pasaba como "paridad 100%" y se perdía sin aviso. Ahora el inventario es `sha256` de **todos** los archivos de cada skill (no solo `SKILL.md`) más el `mtime` máximo del conjunto.
- **Tres clases de diferencia:** `nuevas` (viven en el espejo y no en el canon → candidatas a adopción), `drift` (mismo path, contenido distinto), `faltantes` (en el canon y no en el espejo → pendientes de despliegue).
- **Dirección del drift por mtime:** "espejo más nuevo" = edición de agente dentro del contenedor (candidata a `--adopt-drift`); "canon más nuevo" = pendiente de despliegue (lo resuelve `--apply` sin tocar el canon).
- **Gate de firma (bloqueo duro en código):** `--apply` exige `--firma TOKEN`, validado contra el `sha256` guardado en `/root/.sync-firma.sha256` (chmod 600). Ese archivo lo crea **solo el dueño** (`printf '%s' 'TOKEN' | sha256sum | awk '{print $1}' > /root/.sync-firma.sha256`). Sin archivo o con token inválido → **exit 1** y nada se toca. Un agente nunca crea, lee ni guarda ese token.
- **Nada se destruye sin respaldo:** toda skill nueva o con drift se archiva en `data/archive/sync_<ts>/` **antes** del despliegue. Con `--adopt-drift`, el contenido del contenedor se promueve al canon y el canónico previo queda en `.../canon_previo/`.
- **Verificación final por contenido** tras desplegar. Códigos de salida: `0` paridad, `2` diferencias detectadas en `--check`, `1` error o gate cerrado.
- **Cron diario (solo lectura):** `20 5 * * * /root/hermes-agent-legacy-docker/scripts/sync_container_skills.sh --check >> /var/log/skills-sync-check.log 2>&1`.
- **Pitfall esperado:** editar una skill *en el canon* deja `drift` hasta que se firme un `--apply`; el `--check` diario lo reporta. No es un fallo: es el gate haciendo su trabajo.

### Vigilancia diaria y frescura del grafo (2026-09-20)

Dos piezas nuevas, ambas de solo lectura sobre el canon:

- **`scripts/skills_sync_daily.sh`** — corrida diaria (cron `20 5 * * *`): ejecuta `sync_container_skills.sh --check`,
  persiste el diagnóstico en `data/state/skills_sync_last.json` y, si hay diferencias, deja un aviso
  **máquina-legible** en `data/state/skills_sync_alert.json` (con `drift`, `drift_hint`, `new_in_container`,
  `new_hint` y la resolución firmada) más un bloque `🚨 ALERTA` en `/var/log/skills-sync-check.log`.
  Con paridad deja `OK <timestamp>`. De paso refresca el grafo (ver siguiente punto).
- **`scripts/sync_graph_consumers.sh`** — el repo reconstruye `graphify-out/graph.json` en cada commit (hook en
  segundo plano), pero **los consumidores eran copias manuales** y se quedaban viejas (se detectó un grafo de 03:31
  con consumidores de 02:41). Este script iguala `data/brain/graphify-out/graph.json` y
  `data/profiles/roshi/graphify-out/graph.json` verificando **sha256** copia por copia (`--check` solo reporta).

**Cambio de contrato en el sync (`--adopt-new`).** El `--apply` adoptaba por defecto cualquier skill que viviera
solo en el espejo → una **baja del canon** (p. ej. el par `microsoft[-_]clarity-automation` consolidado) volvía al
catálogo en el siguiente sync. Ahora la adopción es **opt-in** (`--adopt-new`) y el solo-espejo se **archiva y poda**.
Nota histórica: el mismo defecto lo detectó Toallín por su lado (`54123f1316`, guarda por `mtime` vs último commit)
y quedó subsumido por el flag explícito; su heurística de `mtime` se conserva como **hint de dirección** en el reporte.

**Higiene de la firma.** El gate vive en `/root/.sync-firma.sha256` (sha256, 600, root). Regla: el token en claro
lo maneja **solo el dueño**; los agentes no lo crean, no lo leen ni lo guardan. Si un token llega a circular por un
canal de chat, conviene **rotarlo** (mismo comando de creación con un token nuevo).

### Autocuración con sedimento por perfil (Opción C, 2026-09-20)

**Modelo de escritura de la flota:**

| Capa | Ruta | Quién escribe | Quién lee |
|---|---|---|---|
| Canon (SSOT) | repo `skills/` → espejo `/opt/hermes/skills` | **solo promoción firmada** (`--apply --firma`) | los 12 perfiles (`external_dirs`) |
| Sedimento | `<HERMES_HOME>/skills` de cada perfil | el agente y el fork de curación (sin firma) | su perfil (local gana por nombre) |

- Los **11 perfiles** tienen `create_dir: None` → el `create_dir` efectivo es su dir local: **el fork autónomo SÍ puede curar ahí** (no está en `external_dirs`, así que el guardián *"externally owned"* no aplica).
- El **perfil default** tenía `create_dir: /opt/hermes/skills/specialists` (dentro del espejo): el fork no podía escribir y el primer plano escribía donde el sync pisa. Se eliminó esa línea → ahora cura en `data/skills` como los demás.
- **Promoción:** `scripts/sync_container_skills.sh --apply --firma <TOKEN> --adopt-sediment` recorre los 12 sedimentos, promueve al canon (`specialists/<nombre>`), respalda en `data/archive/sync_<ts>/sedimento/`, limpia el sedimento y despliega el espejo con verificación por contenido.
- **Clasificación del sedimento por mtime vs. último commit:** *creada por agente* (posterior → candidata a promoción) vs *re-siembra bundled* (anterior → **no** se promueve: es el sembrador de `tools/skills_sync.py`, que reinyecta skills del paquete en el dir local).
- **Detector de sombras:** si un sedimento contiene una skill cuyo nombre ya vive en el canon, se reporta como `🚫 SOMBRA` y **no se promueve** (crear así sombrearía la canónica, porque el dir local se escanea antes que `external_dirs`). Se revisa a diario en el JSON de alerta (`data/state/skills_sync_alert.json`, campo `sedimento_sombra`).
- **Guardarraíl duro pendiente (infra):** bloquear la creación de un nombre canónico desde `skill_manage` requiere parchear `tools/skill_manager_tool.py` y **montarlo** (hoy no está montado: solo lo están `gateway/run.py`, `gateway/display_config.py`, `plugins/platforms/discord/adapter.py`, `tools/mcp_tool.py`). Aplica al recrear el contenedor.
- **Prueba end-to-end (2026-09-20):** sedimento `prueba-sedimento-roshi` → detectada como *creada por agente* → promovida a `skills/specialists/`, sedimento limpio, paridad 718/718 verificada por sha256; sombra de prueba (`1password`) reportada y **no** promovida; re-siembra detectada y **no** promovida. Artefactos de prueba respaldados en `data/archive/pruebas_C_20260920/`.
