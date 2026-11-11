---
name: skills-espejo
description: "Use when syncing runtime and repo skills trees."
version: 1.0.0
author: NeuralCrew
tags: [skills, espejo, mirror, rsync, sync, hermes, repo]

license: MIT
---

# Espejo de Skills (runtime ↔ repo)

## When to Use
- Cuando el Admin pide «corre skill espejo» tras editar skills en cualquiera de los dos árboles.
- Antes de generar un PR de skills o de auditar el catálogo, para garantizar que runtime y repo estén idénticos.

Procedimiento verificado (04-nov-2026, 362=362, 0 diferencias residuales) para sincronizar el árbol vivo de skills (`/opt/data/skills`) con el árbol versionado del repo (`/opt/hermes-agent/skills`, rama `upgrade/v0.22.6`).

## Diagnóstico previo (no confundir herramientas)
- `check_skills_delta.py` NO es el espejo: compara catálogos remotos de perfiles vs disco. No sirve para sincronizar runtime↔repo.
- Detectar divergencia real: `diff -rq /opt/data/skills /opt/hermes-agent/skills` excluyendo dirs de estado dot-prefixed (`.curator*`, `.usage*`, `.hub`, `.locks`, `.bundled_manifest`).

## Sincronización (bidireccional, newer-wins)
1. **Repo → runtime** (bajar lo versionado): `rsync -a --update /opt/hermes-agent/skills/ /opt/data/skills/` — sin `--delete` (nunca borrar skills solo-runtime).
2. **Runtime → repo** (subir skills locales): mismo rsync invertido, luego `git add skills/ && git commit` (Conventional Commits, identidad `Jemadiar1`).
3. **EXCLUSIONES OBLIGATORIAS en ambos sentidos**: `--exclude='.curator*' --exclude='.usage*' --exclude='.hub' --exclude='.locks' --exclude='.bundled_manifest'` y `--exclude='graphify-out'` (estado del curador/hub/uso y el grafo generado NO son skills).
4. Regenerar el grafo de enrutamiento tras sincronizar: `python3 /opt/data/scripts/build_skills_graph.py --global` → `/opt/data/skills/graphify-out/graph.json` (verificar nodos/aristas leyendo el JSON).

## Verificación de cierre
- Conteos iguales: `find <árbol> -mindepth 3 -maxdepth 3 -name SKILL.md | wc -l` (362 en ambos lados al cierre; depth 3 porque las skills viven en `categoria/skill/SKILL.md` — depth 2 subcuenta).
- `diff -rq` residual = 0 (excluyendo estado).
- Repo limpio: `git status --short | wc -l` = 0 tras el commit.

## Pitfalls
- El ruido `rsync: chgrp ... __pycache__ ... Operation not permitted` es benigno (pycache de root); los archivos sí se transfieren. No reintentar por eso.
- Nunca commitear al repo si otro worker está commiteando ahí: revisar `git log --oneline -3 -- skills` antes; commitear SOLO como commit propio encima del suyo, nunca rebase/push sin autorización.
- El push de skills a GitHub se hace SOLO con aprobación explícita del Admin (por ej. vía PR abierto); el espejo local deja el commit sin push.
- Las skills `.rollback-broken/` y los pycache se espejan como el resto del árbol (no filtrarlos del rsync); el filtrado va solo sobre dirs de estado dot-prefixed.

## Nota de curación
Esta skill nació porque la umbrella `skill-library-ops` quedó bloqueada por el escaneo de seguridad (12 hallazgos preexistentes en sus referencias que exigen confirmación humana para editar). Cuando un curador con confirmación humana pueda tocar `skill-library-ops`, fusionar este procedimiento como referencia dentro de esa skill y eliminar esta hija.
