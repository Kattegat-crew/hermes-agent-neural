---
name: git-worktree-tidy
description: "Use when pruning or cleaning up git worktrees safely"
tags: [git, worktree, limpieza, tidy, prune, poda, ramas]
license: MIT
---

# Git worktree tidy

Mantenimiento de worktrees. La creación y el uso diario están en la skill canónica
`software-development/using-git-worktrees`; aquí va la **poda segura**.

## Diagnóstico

1. `git worktree list` — rutas en uso, commit y rama de cada worktree.
2. `git worktree list --porcelain` — formato parseable para scripts.
3. **Antes de tocar nada**, verificar trabajo sin guardar en cada ruta:
   - `git -C <ruta> status --porcelain` (cambios sin commitear)
   - `git -C <ruta> log @{u}.. --oneline` (commits sin push)
4. Cerrar lo que esté vivo ahí: procesos, contenedores, editores.

## Limpieza segura

5. `git worktree remove <ruta>` — se niega si hay cambios; eso es una **protección**, no un estorbo.
   `--force` **descarta** ese trabajo: usarlo solo después de verificar y respaldar.
6. Respaldo barato antes de podar: `git -C <ruta> bundle create /tmp/<rama>.bundle --all`.
7. `git worktree prune --verbose` — elimina metadatos de worktrees que ya no existen en disco.
8. Ramas huérfanas: `git branch -vv` para verlas, `git branch --merged main` para las ya integradas;
   borrar con `git branch -d` (seguro) y `-D` solo tras confirmar que no hay trabajo sin integrar.

## Reglas

- **Nunca** `rm -rf` una ruta de worktree a mano: los metadatos quedan en `.git/worktrees/<nombre>` y el
  prune no los detecta. Siempre `git worktree remove`.
- Un worktree con submódulos o contenedores propios necesita limpieza previa (`docker compose down`) o el
  borrado falla a medias.
- En la flota: los worktrees del host se limpian por SSH (`ssh dev`); nada de worktrees dentro del contenedor.
