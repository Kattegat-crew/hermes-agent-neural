# vigia-quota — informe 2×/día de cuotas de suscripciones

Snapshot versionado del pipeline que genera el informe de cuotas (OpenCode Go, Codex,
Antigravity y NaN/nan.builders) y lo publica en el hilo de Discord de Vigía.

La copia **viva** está en el home de datos (`/opt/hermes-agent-data`); este árbol es su
respaldo reproducible en el repo canónico. Si cambian los scripts en runtime, se copian
aquí y se commitea; el runtime es la fuente de verdad operativa.

## Mapa de despliegue (origen en este repo → destino en el host)

| Aquí | Destino real |
|---|---|
| `scripts/quota_digest.py` | `/opt/hermes-agent-data/scripts/quota_digest.py` |
| `scripts/nan_quota.py` | `/opt/hermes-agent-data/scripts/nan_quota.py` |
| `scripts/vigia_post_thread.sh` | `/opt/hermes-agent-data/scripts/vigia_post_thread.sh` |
| `scripts/tests/test_quota_digest.py` | `/opt/hermes-agent-data/scripts/tests/test_quota_digest.py` |
| `profiles/vigia/scripts/vigia_quota_digest.sh` | `/opt/hermes-agent-data/profiles/vigia/scripts/vigia_quota_digest.sh` |
| `profiles/vigia/scripts/vigia_nan_quota_watch.sh` | `/opt/hermes-agent-data/profiles/vigia/scripts/vigia_nan_quota_watch.sh` |

## Tests

Deterministas, sin red y sin Hermes vivo (13 casos):

```bash
cd ops/vigia-quota && python3 -m unittest scripts.tests.test_quota_digest
```

## Job de cron

- Perfil `vigia` · id `4c1895eb0113` · nombre `quota-digest-2x`
- `0 8,20 * * *` America/Bogota · `no_agent` (stdout del script)
- `deliver local`: el wrapper publica en el hilo con `vigia_post_thread.sh`, porque el
  perfil `vigia` no tiene la plataforma Discord configurada.
- Las operaciones sobre otro perfil se hacen con `HERMES_HOME=<dir del perfil> hermes cron ...`

## Límite conocido

El % de créditos del plan NaN y la caducidad de packs extra exigen **cookie de sesión** del
dashboard: `/api/usage/credits` y `/api/auth/me` responden `401 session_required` con la API
key (que solo sirve para inferencia, runs, workspaces y `/api/usage/quota`). El informe
declara esa limitación en cada tirada en vez de estimar el porcentaje.
