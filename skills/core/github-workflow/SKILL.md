---
name: github-workflow
description: "Use when doing GitHub PRs, issues, auth or CI work"
version: 2.0.0
author: NeuralCrew
tags: [github, git, pull-request, issues, ci, auth, repo, workflow]

---

# Github Workflow

## Propósito y Alcance
Habilidad consolidada de clase que centraliza los flujos de:
- `github`
- `github-actions-ci-cd`
- `github-auth`
- `github-code-review`
- `github-issue-to-pr`
- `github-issues`
- `github-pr-workflow`
- `github-push-container`
- `github-repo-ingestion`
- `github-repo-management`
- `github-ro-mount-workflow`

## Arquitectura y Protocolos
Esta skill opera como despacho unificado. El detalle procedural y gotchas específicos de cada caso se encuentran preservados en:
`references/`

## Casos de Uso Disponibles
- **github**: Ver [references/github.md] ⚠️ FALTA: file:///root/hermes-agent-legacy-docker/skills/core/github-workflow/references/github.md
- **github-actions-ci-cd**: Ver [references/github-actions-ci-cd.md](file:///root/hermes-agent-legacy-docker/skills/core/github-workflow/references/github-actions-ci-cd.md)
- **github-auth**: Ver [references/github-auth.md](file:///root/hermes-agent-legacy-docker/skills/core/github-workflow/references/github-auth.md)
- **github-code-review**: Ver [references/github-code-review.md](file:///root/hermes-agent-legacy-docker/skills/core/github-workflow/references/github-code-review.md)
- **github-issue-to-pr**: Ver [references/github-issue-to-pr.md](file:///root/hermes-agent-legacy-docker/skills/core/github-workflow/references/github-issue-to-pr.md)
- **github-issues**: Ver [references/github-issues.md](file:///root/hermes-agent-legacy-docker/skills/core/github-workflow/references/github-issues.md)
- **github-pr-workflow**: Ver [references/github-pr-workflow.md](file:///root/hermes-agent-legacy-docker/skills/core/github-workflow/references/github-pr-workflow.md)
- **github-push-container**: Ver [references/github-push-container.md](file:///root/hermes-agent-legacy-docker/skills/core/github-workflow/references/github-push-container.md)
- **github-repo-ingestion**: Ver [references/github-repo-ingestion.md](file:///root/hermes-agent-legacy-docker/skills/core/github-workflow/references/github-repo-ingestion.md)
- **github-repo-management**: Ver [references/github-repo-management.md](file:///root/hermes-agent-legacy-docker/skills/core/github-workflow/references/github-repo-management.md)
- **github-ro-mount-workflow**: Ver [references/github-ro-mount-workflow.md](file:///root/hermes-agent-legacy-docker/skills/core/github-workflow/references/github-ro-mount-workflow.md)


---

## Pitfalls de este entorno (verificado 03-nov-2026)

- **Remotos en SSH fallan aunque gh esté autenticado**: varios repos tienen `git@github.com:...` y no hay llave SSH. Convertir a HTTPS (`git remote set-url origin https://github.com/<org>/<repo>.git`) y asegurar `gh auth setup-git` con el HOME correcto (`HOME=/opt/hermes-agent-data/home`).
- **Workspace con archivos de otro usuario bloquea rebase y pull**: si el rebase falla con `Permission denied` al crear o borrar archivos, el árbol tiene ficheros de root. No insistir. Alternativa sin escribir en el árbol: subir el HEAD a una rama (`git push origin HEAD:refs/heads/<rama>`), abrir PR con `gh pr create` y mergear con `gh pr merge <n> --squash --delete-branch`. El remoto queda correcto y el problema de permisos se reporta como pendiente.
- **Un fetch que muere por timeout deja la ref del remoto obsoleta**: si el push se rechaza por no ser avance rápido pero el conteo local dice 0/0, verificar contra la verdad del servidor con `git ls-remote origin main` antes de concluir.

- **Repositorios públicos exigen sanear la plantilla**: al copiar las reglas de gobernanza a un repo público, quitar nombres de clientes, IPs de host y nombres de ítems del gestor de secretos. Verificar con una búsqueda de esos términos sobre el contenido publicado antes de dar por cerrado; una regla interna filtrada revela arquitectura.
- **Crear gobernanza sin copia local**: cuando el repo no existe en disco, subir los archivos con `gh api --method PUT repos/<org>/<repo>/contents/<ruta>` en base64, y verificar después con `contents/<ruta>`. Evita clones desechables.
