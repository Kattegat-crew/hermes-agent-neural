---
name: hermes-skills-provisioning
description: "Install skills into Hermes profiles from catalogs."
version: 1.0.0
author: Ragnar
triggers:
  - skills: instalar skills / skills por perfil / catálogo de skills / por qué no tiene las skills / materializar skills / skills del reporte
  - perfiles: skills de un bot / perfil con skills / symlinks de skills / skills funcionales
  - catálogo: 100 skills por bot / 1175 skills / skills conceptuales / skills externas
---

# Hermes Skills Provisioning — Materializar un catálogo de skills en perfiles

Cómo llevar un catálogo grande de skills (100+ por bot) a perfiles Hermes **funcionales y utilizables**, distinguiendo los 3 tipos de entrada y verificando que cada una carga de verdad. Validado 26/08/2026 al materializar un catálogo de 1175 skills en 8 perfiles especialistas.

## Los 3 tipos de entrada de un catálogo (clave)

1. **[H] Local** — ya existe en `/opt/data/skills/<nombre>/`. Solo symlink.
2. **Externa importable** — vive en un repo externo (Corey Haines, Composio, Baoyu, alirezarezvani, Anthropic, ClawHub). Clonar → indexar → symlink tras scan de seguridad.
3. **Conceptual** — NO existe como paquete SKILL.md en ningún repo; es una capacidad/área de conocimiento (p. ej. `rust-lang`, `meta-ads-api`, `ffmpeg-advanced`, `etl-pipeline`). Hay que **AUTORARLA** como SKILL.md funcional adaptado al stack real.

**Pitfall crítico:** un catálogo "de espectro" (100+ por bot) mezcla los 3. Si el usuario pregunta "¿por qué los agentes no tienen todas las skills del reporte?", la respuesta honesta es esta clasificación en 3 tipos + plan de cierre — nunca prometer "todas instaladas" sin distinguir.

## Workflow

### 1. Delta check (qué falta realmente)
Script `scripts/check_skills_delta.py` — parsea las tablas del catálogo (`| # | skill | fuente | ★ | por qué |`), compara contra `/opt/data/skills` + repos externos, reporta presentes/faltantes por bot. Correrlo ANTES de prometer cobertura.

### 2. Importar repos externos
```bash
mkdir -p /opt/data/skills-ext && cd /opt/data/skills-ext
git clone --depth 1 https://github.com/coreyhaines31/marketingskills.git      # 50 skills
git clone --depth 1 https://github.com/ComposioHQ/awesome-claude-skills.git  # 33 dirs
git clone --depth 1 https://github.com/JimLiu/baoyu-skills.git               # 21 skills
git clone --depth 1 https://github.com/alirezarezvani/claude-skills.git      # 844 SKILL.md
```
- El layout varía: `marketingskills/skills/`, `awesome-claude-skills/` (raíz), `baoyu-skills/skills/`, `claude-skills/` (SKILL.md anidados bajo `marketing-skill/skills/` etc.).
- Indexar nombre→ruta del SKILL.md con `os.walk` (primera fuente gana). Script `scripts/link_external_skills.py`.

### 3. Autorar skills conceptuales
- Directorio fuente canónico: `/opt/data/skills-especialistas/<skill>/SKILL.md` (fuera de `/opt/data/skills` para no inflar el perfil de Ragnar).
- Clasificar por categoría según nombre+propósito: ads, seo, video, image, sql, social, comms, voice, compliance, dev, design, marketing, hooks-titles, productivity.
- Cuerpo con tooling REAL del stack (ffmpeg, psql/`EXPLAIN (ANALYZE, BUFFERS)`, curl a APIs Meta/Google Ads, modelos NaN-Builders, config Hermes) — NO plantillas genéricas. Incluir "Propósito real", "Cuándo usar", "Procedimiento" numerado y "Verificación" (entregable real antes de declarar hecho).
- Frontmatter: `name`, `description: "Use when: <propósito>..."`, `category`, `version`.
- **Dedupe por nombre entre bots**: un solo SKILL.md fuente, symlink a todos los perfiles que lo catalogan. Script `scripts/autorar_skills.py`.

### 4. Enlazar por perfil
```python
os.symlink(source_dir, os.path.join(profile_skills_dir, name), target_is_directory=True)
```
- Los perfiles usan symlinks a un directorio fuente común (mismo patrón que `/opt/data/skills` → `/root/hermes-agent-legacy-docker/data/skills`).
- Al copiar `config.yaml` de un perfil existente, limpiar el `skills.disabled` heredado (regex del bloque `skills:\n  disabled:\n(?:  - .*\n)*` → `disabled: []`) — el perfil ve solo sus symlinks.

### 5. Scan de seguridad liviano
Buscar en SKILL.md importados: `rm -rf /`, `curl .*|.*sh`, `wget .*|.*bash`, `base64 -d`, `eval (`, `sudo rm`, `> /etc/`. **Falso positivo conocido:** `himalaya` (documenta su instalador `curl | sh`). Las skills de terceros son vector de ataque conocido (1Password: "From magic to malware") — scan SIEMPRE.

### 6. Verificación (no auto-reportada)
- `hermes --profile <bot> doctor` — skills reconocidas, sin errores.
- Smoke test real: `hermes --profile <bot> chat -q "según tu skill X, cómo harías Y?"` → el bot responde usando la skill (prueba de que carga y es usable).
- Contar symlinks: `find /opt/data/profiles/<bot>/skills -maxdepth 1 -type l | wc -l` (NO `grep "->"` — falla por el flag).

## Grafos de skills por perfil (búsqueda rápida)

Cada perfil con skills enlazadas puede tener su propio grafo graphify para encontrar skills por tema y sus relaciones (categoría, related, conceptos, perfiles que la usan).

**RUTA CANÓNICA (trampa host/contenedor):** el árbol VIVO de skills en el host es `/root/hermes-agent-legacy-docker/data/skills/` — **NO existe `/opt/data/skills` como ruta de host** (es un espejo viejo que nadie lee; en el host `/opt/data` es otro directorio, no el bind mount). Los scripts corriendo desde el HOST deben usar `/root/hermes-agent-legacy-docker/data/...`; desde el CONTENEDOR, `/opt/data/...`. Enlazar con ruta equivocada = grafos de 1 nodo o 0 symlinks.

- Generador: `/opt/data/scripts/build_skills_graph.py` (auto-detecta host vs contenedor)
  - `--global` → `/opt/data/skills/graphify-out/graph.json` (catálogo completo core+especialistas+ext + nodos de perfiles con relation=used_by)
  - `--all-profiles` → `skills/graphify-out/graph.json` de cada especialista + roshi
- **Bugs corregidos del generador (28/08, backup .bak-20260828):** (1) `profile_skills` solo miraba el 1er nivel del perfil → las skills anidadas en categorías (`<cat>/<skill>/SKILL.md`, convención del vault) eran invisibles; (2) las skills que viven SOLO en el perfil nunca se escaneaban. Ahora auto-detecta el árbol (host=/root/hermes-agent-legacy-docker/data, contenedor=/opt/data) y escanea el dir completo del perfil.
- CLI de consulta: `/opt/data/.venv-graphify/bin/graphify query "<tema>" --graph <ruta>`
- **Pitfall crítico del CLI:** `graphify query` matchea por substring contra `label` + `source_file` únicamente (NO lee `summary`). El generador lo resuelve escribiendo el summary normalizado (sin diacríticos) en `source_file` del nodo y creando **nodos concepto** (relation=concept) con los términos clave de la descripción. Nunca regenerar el grafo sin esa capa — una búsqueda por concepto ("guion", "dashboards") fallaría con "No matching nodes found".
- Después de generar el grafo, dejar en el AGENTS.md del perfil la sección "Grafo de skills" (ruta del grafo + comando) — ver `profiles/<p>/AGENTS.md`.
- El CLI NO está en PATH del contenedor: usar ruta absoluta `/opt/data/.venv-graphify/bin/graphify`.

## Pitfalls
- El CLI `hermes` NO está en PATH del contenedor → usar `/opt/hermes/bin/hermes` (wrapper `/opt/hermes/hermes`).
- No borrar `/opt/data/skills-ext` ni `/opt/data/skills-especialistas` sin revisar los symlinks que apuntan a ellos.
- Las sesiones del CLI quedan en la DB (state.db), no en `.jsonl` — para ver la respuesta del smoke test leer la salida del comando, no buscar el archivo.
- Un catálogo "100 por bot" con duplicados entre bots: al des-duplicar, el total único es menor; reportar ambos números (filas de catálogo vs skills únicas).

## Scripts
- `scripts/check_skills_delta.py` — delta catálogo vs disco (generalizable a cualquier informe).
- `scripts/link_external_skills.py` — indexa repos externos + enlaza a perfiles + scan.
- `scripts/autorar_skills.py` — autor SKILL.md por categoría + symlinks con dedupe.
- Scripts de creación de perfiles especialistas (SOUL/AGENTS/MEMORY, config, skills): `/opt/data/scripts/gen_agentes_{souls,skills,clean_config}.py`.