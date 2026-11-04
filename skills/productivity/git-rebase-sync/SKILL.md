---
name: git-rebase-sync
description: "Use when syncing a branch by rebase and force-with-lease"
tags: [git, rebase, sincronizacion, sync, conflictos, force-with-lease, rama]
license: MIT
---

# Git rebase & sync

Mantener una rama propia al día con `main`/upstream sin merges sucios y sin reescribir historia ajena.
Para crear y usar worktrees, la skill canónica del dominio es `software-development/using-git-worktrees`.

## Flujo probado

1. **Árbol limpio primero.** `git status --porcelain` debe salir vacío; si no, `git stash push -u` (y anotar el stash).
2. **Traer referencias sin tocar el árbol:** `git fetch --prune origin`.
3. **Rebase sobre la base actual:** `git rebase origin/main` (o `git pull --rebase --autostash origin main`).
4. **Conflicto:** `git diff --name-only --diff-filter=U` para listarlos → resolver archivo por archivo → `git add <archivo>` → `git rebase --continue`.
   Nunca `git rebase --skip` a ciegas: descarta cambios que no son tuyos.
5. **Verificar antes de publicar:** correr build/tests del repo. "Sin conflictos" no significa "sin romper".
6. **Publicar:** `git push --force-with-lease`. Nunca `--force`. Si el remoto avanzó desde el fetch, el lease aborta → volver al paso 2.
7. **Salida de emergencia:** `git rebase --abort` restaura el estado previo exacto. `git reflog` es el paracaídas si ya se hizo `--continue`.

## Reglas

- Rebase solo en ramas propias o no compartidas. En una `main` compartida: merge o PR.
- `--force-with-lease` protege solo si se hizo `fetch` antes; sin fetch la garantía es ilusoria.
- Un commit por unidad de trabajo con mensaje `tipo(scope): qué` — facilita resolver conflictos futuros.
- Repos del host: trabajar **in-place** por SSH. Prohibido clonar el repo dentro del contenedor (ver `AGENTS.md`).
- Antes de rebases grandes: `git branch respaldo/<rama>-<fecha>` como punto de retorno barato.
