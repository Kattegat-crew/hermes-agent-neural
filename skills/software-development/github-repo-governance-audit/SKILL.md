---
name: github-repo-governance-audit
description: "Use when auditing GitHub org governance via REST API."
version: 1.0.0
author: Ragnar — NeuralCrew Labs / Digital Expressions
license: internal
hermes:
  tags: [github, api, auditoria, gobernanza, ci, proteccion, planes]
  related_skills: [github-workflow, github-actions-failure-forensics, git-history-secret-purge, github-push-container]
triggers:
  - auditoria: auditar github / como trabajamos en github / diagnostico de repos / gobierno de repos
  - proteccion: proteger main / branch protection / rulesets / 403 upgrade
  - ci: runs de actions rojos / secrets de actions / deploy roto
---

# Auditoría de Gobierno GitHub por API REST

## When to Use

- El Administrador pide auditar "cómo trabajamos en GitHub", diagnosticar el
  flujo de PRs/CI/deploys, o revisar protección, secrets, dependencias y
  accesos de la cuenta/org.
- Antes de ejecutar cualquier fase del plan de gobernanza (F0–F3), para tener
  línea base verificada y no asumir estado desde memoria.
- Cuando un workflow de deploy falla de forma masiva y hay que hallar la causa
  raíz a nivel de step, no solo el run rojo.

No usar para: pushear cambios (`github-push-container`), forensia detallada de
un único run (`github-actions-failure-forensics`) ni escribir gobernanza en
repos (`github-workflow`).

Procedimiento read-only (verificado 04-nov-2026 contra `Kattegat-crew`, plan
Free) para diagnosticar el flujo real de trabajo de una cuenta/org antes de
proponer o ejecutar cambios de gobernanza. Nunca escribir durante la auditoría.

## Autenticación

- PAT clásico del vault con header `Authorization: Bearer <token>`.
- En el contenedor el token vive en el env del proceso gateway: leer de
  `/proc/<pid-gateway>/environ` (`GITHUB_PERSONAL_ACCESS_TOKEN=`).
- Auditar siempre el header `x-oauth-scopes` de `GET /user`: si trae
  `delete_repo`, `admin:org` o `workflow`, el token es llave maestra y ese
  hallazgo va al informe (riesgo, no capacidad).

## Checklist de endpoints (uno por dimensión)

| Dimensión | Endpoint | Qué mirar |
|---|---|---|
| Inventario | `GET /user/repos?per_page=100` (o `/orgs/:org/repos`) | private, size_kb, pushed_at, fork, default_branch |
| Ramas | `GET /repos/:r/branches?per_page=100` | cantidad, prefijos, ramas muertas por fecha |
| Protección | `GET /repos/:r/branches/<default>/protection` | 403 = muro de plan Free (ver abajo) |
| Rulesets | `GET /repos/:r/rulesets` | mismo 403 en Free para privados |
| PRs | `GET /search/issues?q=org:ORG+type:pr+is:merged` | total mergeadas históricas; ~0 = no existe flujo PR |
| Workflows | `GET /repos/:r/actions/workflows` | state active/disabled; archivo borrado deja runs huérfanos |
| Runs | `GET /repos/:r/actions/runs?per_page=100` | agregar por conclusion; % de fallo global |
| Causa raíz | `GET .../runs/:id/jobs` → steps | qué step falla exactamente |
| Secrets | `GET /repos/:r/actions/secrets` | array vacío = CI/CD sin credenciales |
| Colaboradores | `GET /repos/:r/collaborators` | un solo admin = punto único de falla |
| Seguridad | `GET /repos/:r` → `security_and_analysis` | null en privados Free; dependabot off |
| Salud comunidad | `GET /repos/:r/community/profile` | health_percentage (28 = sin plantillas/CODEOWNERS) |
| Merge settings | `GET /repos/:r` | delete_branch_on_merge, allow_squash_merge |
| Commits | `GET /repos/:r/commits?sha=<default>&per_page=100` | 0 "Merge pull request" confirma push directo a main |
| Consumo | `GET /users/:u/settings/billing/usage?year=&month=` | minutos Actions vs allowance (Free 2.000/mes) |
| Exposición | `GET /search/code?q=<patron>+repo:ORG/repo` | ghp_, sk-, AKIA, IPs de prod en repos públicos |

Ejecutar como un solo script Python (urllib + bearer) que agrega todo a JSON;
las llamadas sueltas pierden la vista agregada y disparan rate limits.

## Muros duros de plan Free (verificados, no son configurables)

- **Repos privados en Free:** `branches/*/protection` y `/rulesets` responden
  403 "Upgrade to GitHub Pro or make this repository public". Tampoco hay
  environments con required reviewers ni exigencia real de CODEOWNERS.
- **Sí funciona en Free:** PATCH de settings de repo (delete_branch_on_merge,
  allow_squash_merge), workflows CI como gates, Dependabot alerts/updates,
  plantillas, firma SSH de commits, tags/releases.
- Consecuencia: sin upgrade (Pro $4/mes u Org+Team), la disciplina se impone
  solo con workflows — p.ej. un `pr-guard.yml` que falla el check si `main`
  recibe un push que no proviene de un PR aprobado.

## Patrones de diagnóstico ya verificados

- **Deploy rojo en el step "Setup SSH" = `actions/secrets` vacío.** No tocar el
  YAML: confirmar la causa con `/runs/:id/jobs` (steps success/failure/skipped).
- **Deploy que se dispara con push a ramas personales** (main/jonathan/
  jemadiar): riesgo latente — al cargar secrets, cualquier push despliega a
  producción sin revisión. Reportarlo como hallazgo de alto impacto.
- **Fork divergente público:** comparar con `GET /repos/:r/compare/<upstream>:main...main`
  (ahead_by/behind_by) y buscar exposición con code search antes de proponer
  borrar/espejar.

## Línea base Kattegat-crew (04-nov-2026) — re-auditar antes de confiar

10 repos (9 privados + fork público de hermes-agent 106 ahead/34.394 behind);
316 runs: 228 fallos (72%); 3 deploys caen 100% por secrets vacíos; 3 PRs
mergeadas históricas; 0 merge-commits en main; 9/9 sin protección (403); cero
Dependabot/releases/plantillas; commits verificados ~1%; m-c-g 1.77 GB sin LFS.

Plan de corrección F0–F3 y KPIs:
`/opt/data/brain/ops/2026-11-04-diagnostico-gobierno-github.md`

## Relacionadas

`github-workflow` (paraguas de PR/CI/push) · `github-actions-failure-forensics`
(forensia de un run rojo) · `git-history-secret-purge` (si la auditoría
encuentra secretos en historial).
