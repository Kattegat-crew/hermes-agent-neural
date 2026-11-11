# Taxonomía de destinos para la memoria nativa

`MEMORY.md` es una **caché always-on**, no un archivo: se paga en cada turno de cada sesión.
El criterio no es "¿es importante?" sino **"¿esto tiene que estar en el prompt antes de cualquier
herramienta, o basta con poder leerlo cuando toque?"**. Lo que se retira nunca se borra: queda
verbatim en `memoria-archivo/` y, cuando se rutea, también en su lugar natural.

## Árbol de decisión (en orden)

1. ¿Es identidad, autoridad, prohibición o gate que cambia la conducta **antes** de cualquier tool?
   → **keep** en `MEMORY.md` (corto, sin historia).
2. ¿Solo importa cuando se trabaja en un repo concreto (ruta, build, commit, quirk)?
   → **repo** (`<repo>/PROJECT_MEMORY.md` / `AGENTS.md`), commiteado.
3. ¿Es un procedimiento o pitfall de una tarea que se repite?
   → **skill** (`skill_manage` sobre la skill del dominio; `references/<tema>.md` si es largo).
4. ¿Es conocimiento de cliente, negocio, arquitectura o una decisión con porqué?
   → **brain** (`entities/`, `concepts/`, `ops/`, `analysis/`).
5. ¿Es topología de infra, puertos, contenedores, catálogo de APIs/keys?
   → **vault** (`/opt/vault/ARCHITECTURE.md`, `AGENTS.md`) o `/opt/vps-brain/HISTORIAL_Y_CONTEXTO_VPS.md`.
6. ¿Es un episodio buscable (qué pasó tal día, id de job, incidente)?
   → **engram** (`mem_save`), recuperable por búsqueda semántica/FTS.
7. ¿Nada de lo anterior, pero es dato verificable que podría volver?
   → **archive** (verbatim + `mem_recall`), sin nota dedicada.
8. ¿Duplicado o superado por otra entrada? → **merge** en la entrada vigente (el gate exige cobertura ≥50%).

Si dudas entre `archive` y `brain` y la entrada tiene **datos duros** (NIT, IDs, cuentas, hosts,
cifras, fechas de cierre contractual), va a `brain`: eso se consulta, no se adivina.

## Fichas por destino

### brain — `/opt/data/brain/`
- `entities/<slug>.md` — clientes, personas, sistemas.
- `concepts/<slug>.md` — cómo funciona algo (arquitectura, pipeline, modelo de negocio).
- `ops/<slug>.md` — procedimiento operativo o incidente con resolución.
- `analysis/<YYYY-MM-DD>-<slug>.md` — auditoría/informe fechado.
- Frontmatter obligatorio: `id`, `type`, `tags`, `updated_at`; enlaces `[[otra-nota]]`.
- Tras escribir: actualizar `/opt/data/brain/index.md` si es nota estructural y añadir línea en
  `/opt/data/brain/log.md`.
- No duplicar: comprobar con `python3 /opt/data/tools/memory_graph.py "<tema>"` antes de crear.

### repo — memoria del proyecto
- Archivos: `PROJECT_MEMORY.md` (estado y decisiones), `AGENTS.md` (reglas de trabajo),
  `.agents/rules/*.md` (reglas duras), `ARCHITECTURE.md` (topología).
- Solo hechos locales a ese repo; el agente los lee al entrar al proyecto.
- Commit convencional obligatorio (`docs:` / `chore:`) y `git status` limpio después.

### skill — procedimiento reutilizable
- Usar `skill_manage(action="patch")` sobre la skill del dominio; si el volumen es alto,
  `write_file` en su `references/`.
- Una regla por lección, imperativa, con el porqué. Nada de narrar el incidente.

### vault — infraestructura
- `/opt/vault/ARCHITECTURE.md` (repos, contenedores, bases, puertos), `/opt/vault/AGENTS.md`
  (APIs, keys, modelos), `/opt/vps-brain/HISTORIAL_Y_CONTEXTO_VPS.md` (cambios de servidor).
- Credenciales: jamás en texto plano; el gestor es Vaultwarden.

### engram — episodios y estado buscable
- `mem_save(title=..., content="**What/Why/Learned**", type=..., project=...)`.
- Usar cuando el valor está en "poder encontrarlo", no en tenerlo cargado.
- Anotar el `id` devuelto en el plan: `{"kind":"engram","observation_id":N}`; el apply verifica
  que la observación existe y su cobertura.

### archive — lo demás
- `memory_apply.py` escribe `nativa-<perfil>-<target>-<ts>.jsonl` (una entrada por línea, con
  `idx`, `sha1`, `action`, `destination`, `summary`, `text` verbatim) y un `.md` legible.
- Recuperación: `mem_recall.py "<token>"` (busca archivo + brain + repos + skills + vault + Engram).

## Qué NO se mueve nunca

- Quién es el Admin, quiénes son los socios, quién autoriza qué (autoridad).
- Prohibiciones y gates: gasto sin firma, publicar sin aprobación, tocar sesión de WhatsApp,
  `git push` sin autorización.
- Rutas canónicas que se necesitan para el primer comando de una sesión (DEV/PROD, Vaultwarden, brain).
- Preferencias de respuesta del Admin (van en `USER.md`, no en el archivo de proyecto).

## Ejemplos resueltos

| Entrada original (resumen) | Acción | Destino |
|---|---|---|
| "Radar DIAN v3, resumen ejecutivo del correo, operativo PROD 13-oct" | move | `brain/ops/radar-dian.md` + `mem_save` del cierre |
| "Pipeline publicación reels: LOCK anti-duplicado, commit 0ef15a1" | move | `brain/concepts/pipeline-publicacion-reels.md` |
| "HERMES-DSML-GUARD desplegado en DEV: anti-fuga DSML" | move | skill `hermes-runtime-ops` (`references/dsml-guard.md`) |
| "8 pagos del 01-oct fuera de la hoja 1j0v…" | archive | conciliación ya cerrada; recall por fecha/ID |
| "Nunca ejecutar generación paga sin firma de Plon" | keep | invariante de conducta |

## Regla de oro de recuperación

Antes de decir "no tengo ese dato" o de reconstruirlo desde cero:

```bash
python3 /opt/data/skills/core/memory-compaction/scripts/mem_recall.py "<tema, ID, ruta o nombre propio>"
```

Si aparece en `[archivo-memoria]`, el dato sigue vivo: se puede citar y, si vuelve a usarse en cada
sesión, se reincorpora a `MEMORY.md` con `memory(action="add")` y se marca `keep` en el próximo plan.
