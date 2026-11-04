---
version: "1.0"
author: Ragnar
metadata:
  hermes:
    tags: [rollback, upgrade, hermes, vps, backup, git, gateway]
    related_skills: [hermes-latency-diagnosis, hermes-gateway-s6-ops]
---

# Rollback de una actualización fallida de Hermes (DEV, checkout vivo)

## When to Use

- Un upgrade/port de Hermes rompió el runtime o la config (regresiones
  verificadas) y el Admin decide restaurar el estado pre-actualización.
- «reestablecer el repositorio a la versión antes de la actualización».

Procedimiento inverso al update: restaurar el checkout y el runtime al estado
pre-actualización cuando el upgrade/port rompió el sistema. Caso real 4-nov-2026:
rollback de `upgrade/v0.22.6` a `pre-v0.22.6` en `/opt/hermes-agent` (DEV).

## Reglas previas (no negociables)

1. **Congelar al agente que hizo el upgrade** antes de tocar nada: matar sus
   sesiones/procesos (agy, codegraph) para que nadie más escriba en el árbol.
2. **Snapshot del estado malo ANTES del rollback**: tag `pre-rollback-<fecha>`
   sobre la rama del upgrade + backup completo fuera del repo
   (`/opt/hermes-backups/<dir>/`: `state.db` del perfil (puede ser >1 GB),
   `config.yaml`, parches, tarballs). Sin esto, el port futuro no es auditable.
3. Identificar la **base pre-upgrade exacta** (commit del árbol bueno):
   `git log --format='%h %ci %s'` y el tag/rama donde vivía.

## Reconstruir el árbol pre-upgrade

El problema clave: los cambios sin commitear NO viajan en el upgrade (ni en el
replay ni en el rollback). Reconstruirlos desde el respaldo:

```bash
cd /opt/hermes-agent
# 1. rama de rollback desde el árbol bueno pre-upgrade
git checkout -B rollback/pre-<ver>-<fecha> <commit-pre-upgrade>

# 2. cambios TRACKED que existían sin commitear: parche binario desde el backup
#    (dif entre la base pre-upgrade y el estado malo capturado antes de tocar)
git apply --binary /opt/hermes-backups/<dir>/git-dirty-tracked.patch

# 3. archivos UNTRACKED del fork (skills locales, tools, secrets layout): tarball
#    del respaldo; aplicar SIN sobreescribir lo que el parche ya restauró
sudo tar -xzf /opt/hermes-backups/<dir>/untracked-files.tgz -C /opt/hermes-agent --skip-old-files
```

- Contar los cambios aplicados y comparar contra el conteo del snapshot
  (`patch + tarball − solapes`). En el caso real: 78 cambios (38 patch + 48
  tarball, con solapes).
- Si el backup solo tiene tarball de untracked y NO parche de tracked, el parche
  se puede reconstruir así: `git diff <pre-upgrade-base> <estado-malo> --binary`
  si el estado malo ya capturó los archivos; si no, esos cambios se perdieron —
  decirlo, no fingir.

## Restaurar runtime

```bash
# state.db del perfil desde el backup (conserva sesiones/contexto reales)
sudo systemctl stop <gateway>   # o el mecanismo del host
sudo cp /opt/hermes-backups/<dir>/state.db /opt/hermes-agent-data/state.db
# reinicio canónico del gateway (NO solo compose):
sudo /opt/hermes-agent/scripts/container_boot.py   # vía ssh al host si es remoto
```

Post-verificación obligatoria:

```bash
cd /opt/hermes-agent && git branch --show-current && git log -1 --format='%h %s' && git status --porcelain | wc -l
/opt/hermes-agent/.hermes/bin/hermes --version   # debe mostrar el hash local del rollback
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8642/health   # 200
# plataformas conectadas (discord/telegram/whatsapp/webhook) en el health/gateway_state
```

## Pitfall de la operación real (causa raíz del falso «bug» del upgrade)

- **Los normalizadores de config silencian valores nuevos**: el build v0.22.6
  rechazaba `tool_progress_grouping: replace` (`_norm_choice` en
  `gateway/display_config.py`) y caía a `accumulate` — síntoma: los mensajes de
  progreso se APILAN en vez de reemplazarse, y parece bug de runtime.
  **Lección**: tras cualquier upgrade, auditar la config vigente contra las
  tuplas de normalización del código nuevo (`display_config.py` y similares)
  ANTES de culpar al gateway. El rollback a la rama que SÍ acepta el valor
  elimina la regresión sin tocar código.
- **`/opt/vault` es `root:700`**: el daemon hermes (uid 10000) NO puede escribir
  informes ahí. Fix: escribir a `/opt/hermes-agent-data/cron/output/` y copiar
  como root vía `ssh dev "cp ... /opt/vault/"`.
- **Percibir lentitud ≠ culpa del runtime**: medir con baseline de 5 prompts y
  aislar TTFT del proveedor (ver `hermes-latency-diagnosis`); en el caso real el
  84% del tiempo de un turno era TTFT del proveedor, no del código.

## Evidencia reproducible del caso

Informe completo: `/opt/vault/reporte-rollback-hermes-dev-2026-11-04.md`
(rama `rollback/pre-v0.22.6-20261104`, HEAD `59069cbdc5`, backup
`/opt/hermes-backups/pre-rollback-20261104/`, tag `pre-rollback-20261104`
preserva el port para rehacerlo con SDD + reviewer independiente).
