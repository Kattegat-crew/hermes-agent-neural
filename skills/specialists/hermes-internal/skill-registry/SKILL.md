---
name: skill-registry
description: "Use when reindexing skills after installing or renaming them"
tags: [skills, indice, registro, reindexar, frontmatter, symlinks, perfiles, engram]
license: MIT
metadata:
  author: gentleman-programming
  version: "1.0"
---

## Activation Contract

Use this skill after installing, removing, creating, moving, or renaming skills, or when a delegator needs a fresh skill index.

## Hard Rules

- The registry is an index, not a compiler or summary. `SKILL.md` remains the source of truth.
- Do not generate or inject compact rules by default; preserve author intent by passing exact skill paths to subagents.
- Always write `.atl/skill-registry.md` regardless of SDD persistence mode.
- Save the registry to Engram as `topic_key: skill-registry` when available, with `capture_prompt: false`.
- Skip `sdd-*`, `_shared`, and `skill-registry`; deduplicate by skill name, preferring project-level skills over user-level skills.
- Add `.atl/` to `.gitignore` when possible unless explicitly disabled.

## Decision Gates

| Situation | Action |
| --- | --- |
| Same skill exists globally and in project | Keep the project-level skill |
| Same skill exists in multiple global locations | Keep the first source in scan order |
| No skills found | Write an empty registry so agents stop searching blindly |
| Agent will delegate work | Select matching registry rows and pass their `SKILL.md` paths |

## Execution Steps

1. Scan all known user and project skill directories for `*/SKILL.md`.
2. Read frontmatter only as needed to extract `name` and `description` trigger text.
3. Render `.atl/skill-registry.md` with scanned sources, registry contract, skill name, trigger/description, scope, and exact path.
4. Persist to Engram when available using `title: skill-registry`, `topic_key: skill-registry`, `type: config`, and `capture_prompt: false`.
5. Return the registry path, skill count, cache status, and whether Engram was updated.

## Output Contract

Return:
- Project name and `.atl/skill-registry.md` path.
- Number of indexed skills.
- Whether the cache was hit or regenerated.
- Any skipped or duplicate skills when relevant.

## References

- `docs/skill-style-guide.md` — how skills should be authored before indexing.
- `skills/_shared/skill-resolver.md` — how delegators use the index.

## Indexing Pitfalls

- **Layouts duales de perfiles**: los perfiles Hermes usan symlinks a vaults centrales
  (`/opt/data/skills` core 378, `/opt/data/skills-especialistas` 851, `/opt/data/skills-ext`
  — NO copias). Cada perfil especialista tiene su grafo en `skills/graphify-out/graph.json`.
- **Symlinks que solo resuelven en contenedor**: los symlinks de perfiles a vaults
  parecen rotos desde el HOST; solo se resuelven DENTRO del contenedor Hermes.
- **Espejo muerto `/opt/data` en el host**: `/opt/data` EXISTE en el host como espejo
  viejo que NADIE lee (no es el bind mount). El árbol vivo es `/root/hermes-agent-legacy-docker/data`.
  Scripts con rutas hardcodeadas `/opt/data` corriendo desde el host escriben al espejo
  muerto y pierden el trabajo. Siempre verificar con `read_file` tras escribir.
- **Skills anidadas en categorías**: escanear recursivamente `<cat>/<skill>/SKILL.md`
  (convención del vault), no solo el 1er nivel del perfil.
- **Skills que viven SOLO en el perfil**: no se escanean si el generador solo mira el
  vault — escanear también el dir del perfil. Regenerar grafos con
  `python3 /opt/data/scripts/build_skills_graph.py --all-profiles` (global: `--global`).
