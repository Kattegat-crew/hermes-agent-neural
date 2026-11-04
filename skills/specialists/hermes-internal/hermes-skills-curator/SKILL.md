---
name: hermes-skills-curator
description: "Use when running or auditing the skills curator."
tags: [hermes, curator, skills, adopt, archivado, ciclo-de-vida]
---

# Hermes Skills Curator — ciclo de vida de skills

El `hermes curator` es el sistema de ciclo de vida de las skills de Hermes: rastrea uso, marca inactivas, archiva (nunca borra) y consolida. Vive dentro del contenedor y en un modelo auxiliar, así que hay que entender qué toca y qué NO toca antes de asumir que encontró algo nuevo.

## Dónde vive el catálogo REAL (crítico)

- **Ruta cierta:** `~/.hermes/skills/` **dentro del contenedor `hermes-agent`** (en DEV/PROD: `/opt/data/home/.hermes/skills/`). Aquí está la verdad: `docker exec hermes-agent find ~/.hermes/skills -name SKILL.md | wc -l`.
- **`/opt/data/skills/` en el gateway es OTRA cosa** — suele estar casi vacío (solo `graphify-out/` y alguna skill suelta) y NO es la fuente del catálogo que ve el agente.
- Para ver el catálogo que el agente realmente carga, usar `skills_list`/`skill_search` o escanear la ruta del contenedor — no la del gateway.

## Qué gestiona y qué NO

| Pool | Quién la ve | Auto-procesada por `curator run` |
|---|---|---|
| **Bundled** (viene con Hermes) | curator-managed | sí |
| **Adoptadas** (`created_by: agent`) | curator-managed | sí |
| **Unmanaged** (sin marca de procedencia) | nadie | **NO — se ignoran hasta `adopt`** |

**El `curator run` solo revisa las curator-managed.** Las skills nuevas aterrizan SIEMPRE en la pila `unmanaged` y ahí se quedan hasta que corras `hermes curator adopt <nombre>`. Si un `curator run` reporta "no changes", NO significa que no haya skills nuevas — significa que no hay cambios en las pocas que gestiona.

## El porqué del `adopt` (no es decorativo)

Una skill sin `created_by: agent` en el frontmatter es **unmanaged**. Consecuencia concreta: `skill_manage` (editar/actualizar la skill) la rechaza con **`not curator-managed, created_by=None`**. `hermes curator adopt <nombre>` declara procedencia y **desbloquea la escritura**.

Verificar el estado con `hermes curator status`:

```
curator: ENABLED
  runs:           N
  last summary:   auto: <cambios>; llm: skipped (consolidation off)
curator-managed skills: X total  (agent-created=N  bundled=M)
  active  N  stale 0  archived 0
unmanaged (no provenance marker): Y total
  pre-dates marker  A   foreground-created  B
```

## Pitfalls verificados

1. **`curator status` y `curator usage` son pesados** — cuelgan >60s en foreground (timeout). Correr SIEMPRE en background: `docker exec hermes-agent hermes curator status > /tmp/cu.txt 2>&1` con `background=true`, y leer el archivo.
2. **La adopción NO sobrevive al rebuild del contenedor.** Tras recrear `hermes-agent`, el contador `agent-created` vuelve a 0 y las skills vuelven a `unmanaged`. Hay que **re-adoptar** tras cada rebuild. Usar un bucle: `for s in <lista>; do docker exec hermes-agent hermes curator adopt $s; done`.
3. **Consolidación (pass LLM de merge) está OFF por defecto** (modo `prune-only`). Se activa con `curator.consolidate: true` en config o `--consolidate`. El `curator run` la saltea: "llm: skipped (consolidation off)".
4. **El curator archiva skills idle ≥90d y las marca stale ≥30d.** Para skills de agencia que se usan de vez en cuando, marcarlas `pin` (nunca auto-transiciona) — si no, riesgo de que el curator las archive.
5. Las skills **bundled y hub-installed quedan fuera de alcance** siempre — no se tocan.

## Decisiones de tradeoff al adoptar

- `adopt` = entregar la skill al curator (gestión, prune, archive, consolidación).
- `pin` = bloquear cualquier transición automática (protección para skills usadas con poca frecuencia).
- El riesgo de adoptar en masa: skills que no usas en 30d se marcan stale y a los 90d se archivan. Balancear adopt vs pin según frecuencia real de uso.

## Referencia de comandos

Ver `references/commands.md` para la matriz completa de subcomandos y el formato de salida.
