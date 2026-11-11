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
| `scripts/nan_session_login.py` | `/opt/hermes-agent-data/scripts/nan_session_login.py` |
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

## Créditos del plan (requiere sesión de navegador)

`/api/usage/credits` **no acepta la API key** (`401 session_required`): exige la cookie
`nan_session` del dashboard. NaN entra por *magic link* al correo, así que la sesión se
regenera en dos pasos (caduca cada ~14 días):

```bash
python3 scripts/nan_session_login.py --request          # manda el link a digitalexpresions1@gmail.com
# abrir el correo y copiar la URL .../api/auth/login/verify?token=...
python3 scripts/nan_session_login.py --link "<esa URL>" # canjea y guarda el secret
```

El script verifica la cookie contra `/api/usage/credits` antes de escribir
`/opt/data/secrets/nan-session.json` (0600). El informe avisa cuando quedan 4 días o menos
de sesión y declara `sesión caducada (HTTP 401)` si expiró, en vez de inventar el porcentaje.

## Límite conocido

Sin la cookie, del plan NaN solo se puede ver el **uso por modelo en tokens** (lo que da
`/api/usage/quota` con la API key). Los % de créditos, el saldo de packs y su caducidad
dependen del secret de sesión.
