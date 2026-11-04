---
name: github-actions-failure-forensics
description: "Use when a GitHub Actions workflow run fails or is red"
tags: [github, actions, ci, workflow, diagnostico, logs, api]
author: Ragnar
version: "1.0"
created: 2026-09-06
category: github
metadata:
  hermes:
    tags: [github, actions, ci, workflow, diagnostico, failure, api, release-tags]
    related_skills: [github-push-container, github-actions-ci-cd]
---

# GitHub Actions / CI — Forense de workflow fallido

## When to Use

- Llega la notificación "Run failed: <workflow>.yml" (o un workflow queda rojo en el historial).
- Hay que saber POR QUÉ falla sin `gh` CLI ni acceso a la UI.
- Un workflow de CI con checks requeridos que bloquea (Required checks o branch protection).

## Acceso

Sin `gh` CLI, usar el token de GitHub (Vaultwarden, item `GitHub Credential`) con `curl`/`urllib`. El campo `credential` de ese item es una **URL** (`https://<user>:<token>@github.com`), no un PAT crudo; parsear el token. Headers: `Authorization: Bearer <token>` + `Accept: application/vnd.github+json`.

## Flujo de diagnóstico

1. **Listar runs del workflow** — `GET /repos/<org>/<repo>/actions/workflows/<workflow>.yml/runs?per_page=40`
   - Ver `event` (schedule/workflow_dispatch/push), `conclusion`, `created_at` por run.
   - **Si TODOS fallan desde el run #1 → no es regresión, es un estado persistente.** Anotarlo.
2. **Jobs del run** — `GET /repos/.../actions/runs/<run_id>/jobs?per_page=40`
   - `total_count: 0` con `conclusion: failure` → el workflow falló ANTES de despachar jobs (setup, reusable workflow, o un job que vive en un sub-run).
   - **Pitfall:** en un run `schedule`/`workflow_dispatch` de un workflow padre que `uses:` un reusable workflow, el endpoint de jobs del padre puede dar 0 aunque el fallo esté en un job real (aparece como check-run).
3. **Check-runs del commit** — `GET /repos/.../commits/<sha>/check-runs?per_page=100`
   - Lista cada check/job con su `name` + `conclusion`. Aquí se ve el job que falla (ej. "Pick release tags"). Verificar que no sea otro workflow (ej. lint) el que falla.
4. **Bajar el log del job** — `GET /repos/.../actions/runs/<run_id>/jobs/<job_id>/logs`
   - `job_id` = el `id` del check-run (del paso 3). El `details_url` del check-run apunta a `.../runs/<run_id>/job/<job_id>`.
   - Este endpoint suele funcionar con token de repo; el de run-level (`/actions/runs/<id>/logs`) pide **admin** (403/404).
   - El log baja como **texto** o zip; leer las líneas `##[error]` (suelen estar al final).
   - **Pitfall:** `output.summary`/`output.text` del check-run suele venir vacío — no confiar en él; ir al log.
5. **Confirmar causa + fix** antes de tocar nada; usar el log como evidencia, no suposiciones.

## Gotcha clásico: workflow que muestrea release tags y un fork sin tags

- Workflows tipo "Install & Update E2E" (`install-e2e.yml`) corren `scripts/.../pick-release-tags.sh` que lee los tags de release (`vYYYY.M.D[.N]`) vía `git tag`, y sale con `error: no release tags found ... A shallow clone has no tags` si no hay.
- **Un fork de un repo que sí tiene tags puede tener 0 tags** (GitHub no siempre propaga los tags del parent al fork).
- Verificar: `GET /repos/<org>/<repo>/tags` (0) vs `GET /repos/<parent>/tags` (tiene).
- **Fix:** en un clone del fork,
  ```bash
  git fetch https://github.com/<parent>/<repo>.git 'refs/tags/*:refs/tags/*'
  git push origin --tags
  ```
  Los commits a los que apuntan los tags ya están en el historial del fork, así que el push de tags funciona (verificado 06/09/2026).

## Gotcha: checkout shallow + fetch-tags

- `actions/checkout@v6` con `filter: blob:none` + `fetch-tags: true` ejecuta `git fetch --no-tags --depth=1 ... +refs/tags/*:refs/tags/*`. El refspec sí trae los tags **una vez que existen** en el repo; si no hay tags, el script falla con "no release tags found".
- **No confundir** "el checkout no trae tags" con "no hay tags en el repo". El diagnóstico de la causa es distinto.

## Recomendación

- Para un fork, revisar que el **sync automático de upstream también traiga tags** (`git fetch upstream --tags`) para que no se vuelva a quedar sin tags y el CI no se rompa.

## Referencias

- `references/install-e2e-fork-tags-2026-09.md` — caso real verificado: install-e2e fallando desde el run #1 por fork sin tags; receta completa de endpoints usados.
