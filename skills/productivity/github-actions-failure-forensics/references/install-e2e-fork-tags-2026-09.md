# Caso real (06/09/2026): install-e2e verde roto por fork sin tags

Reproducción del flujo completo de forense sobre `Kattegat-crew/hermes-agent`
(fork de `NousResearch/hermes-agent`), workflow `install-e2e.yml`.

## Síntoma
- Correo automático a captain@neuralcrewlabs.com: "Run failed: .github/workflows/install-e2e.yml - main".
- GitHub manda los avisos de fallo de workflow al email de la cuenta de GitHub del repo.

## Cómo se diagnosticó (endpoints usados, sin gh CLI)
1. `GET /repos/Kattegat-crew/hermes-agent/actions/workflows/install-e2e.yml/runs?per_page=40`
   → TODOS `conclusion: failure` desde el run **#1 (21/08/2026)**. No regresión; estado persistente.
2. `GET /repos/.../actions/runs/<run>/jobs` → `total_count: 0` (falla antes de despachar jobs).
3. `GET /repos/.../commits/1feb940/check-runs?per_page=100` → check-run **`Pick release tags` = failure**
   (además `All required checks pass` y `hadolint` por otros workflows).
4. `GET /repos/.../actions/jobs/<job_id>/logs` (job_id = id del check-run) → log de texto (vía token),
   línea clave:
   ```
   error: no release tags found in ...
          A shallow clone has no tags: fetch with tags (actions/checkout
          with fetch-depth: 0, or fetch-tags: true).
   ##[error]Process completed with exit code 1.
   ```
   El `git checkout` del job corrió `git fetch --no-tags --depth=1 ... +refs/tags/*:refs/tags/*`.

## Causa raíz real
- `GET /repos/Kattegat-crew/hermes-agent/tags` → **0 tags**; `GET /repos/NousResearch/hermes-agent/tags` → **sí tiene** (v2026.8.31, v2026.8.27, …).
- El fork no heredó los tags del parent. `pick-release-tags.sh` corre `git tag` y no encuentra nada.

## Fix aplicado y verificado
```bash
cd <clone del fork>
git fetch https://github.com/NousResearch/hermes-agent.git 'refs/tags/*:refs/tags/*'
git push origin --tags      # con token (base64 -w0 para http.extraheader)
```
- Tras el push, `git tag` = 37 y `scripts/.../pick-release-tags.sh --count 5` devuelve `["v2026.3.12","v2026.4.16","v2026.5.29.2","v2026.8.3","v2026.8.31"]`.
- Dispatch manual (`POST /actions/workflows/install-e2e.yml/dispatches`, ref=main, inputs tag-count=1)
  → run #34: **`Pick release tags` = success** y la matriz `update`/`installer` arrancó.
- Los checks requeridos se desbloquearon.

## Lecciones
- El checkout `fetch-tags: true` + shallow SÍ trae tags una vez que existen en el repo; el fallo era que el fork no tenía tags.
- La causa no era el checkout; por eso un PR de `fetch-depth: 0` fue innecesario (se cerró).
- El endpoint de jobs del workflow padre puede dar 0 aunque haya un job fallando (buscar en check-runs).
- El log de run-level (`/actions/runs/<id>/logs`) pide admin (403/404); el de job (`/actions/jobs/<id>/logs`) funciona con token de repo.
- `POST .../dispatches` devuelve 204 sin cuerpo (no parsear con json.loads).
