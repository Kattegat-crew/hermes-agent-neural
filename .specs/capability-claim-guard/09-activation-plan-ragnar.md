# Plan de ACTIVACIÓN — capability claim guard en Ragnar (default)

Estado: **plan escrito, NO ejecutado**. Este card (`t_88df1ba6`) integra código y pruebas; la
activación la ejecuta el card siguiente **solo tras review PASS**. Medido el 2026-11-03 20:10–05.

## 1. Alcance y autorización

- Perfil objetivo: **Ragnar = profile `default`**, home `/opt/hermes-agent-data`, config
  `/opt/hermes-agent-data/config.yaml` (sha256 `8dd245e9a382c0fa42b11e802b1db849e81553308da7ef50755ae6e40faaf582`, 600 `hermes:hermes`).
- Los otros 12 homes (`/opt/hermes-agent-data/profiles/*/config.yaml`) **no** reciben la clave:
  sin clave la guarda queda OFF por defecto (verificado por test y por `config get` real).
- **No se toca** `hermes-agent-roshi.service` ni la sesión de WhatsApp.
- Sin push, sin deploy, sin tocar Langfuse ni el canario F4 en este card.

## 2. Topología real medida (no la del supuesto del card)

| Superficie | PID | Código servido | Unidad / notas |
|---|---|---|---|
| Gateway default (Ragnar: Telegram/CLI/cron) | 4085894 | `/opt/hermes-agent` (launcher `home/.local/bin/hermes`) | `hermes-agent.service`, `User=hermes`, `HERMES_HOME=/opt/hermes-agent-data`, `KillMode` default (control-group), `Restart=on-failure`, `TimeoutStopSec` 360 s por defecto |
| Dashboard (puerto 9112) | 3632884 | `releases/dashboard/current` → **`releases/cd397afc64` (viejo, SIN guarda)** | `hermes-dashboard.service`, `KillMode=control-group`, `--skip-build`, SPA en `hermes_cli/web_dist` |
| Gateway roshi (dispatcher kanban) | 4085904 | `/opt/hermes-agent` | `hermes-agent-roshi.service`; es el **padre** de los workers kanban 919229 y 926810 |

Hijos vivos del gateway default en la medición: `cron.scheduler` (945728), bridge de WhatsApp
`node …/whatsapp-bridge/bridge.js` (4103576) y un `bash` con un `ssh` en vuelo hacia DEV. Un
`restart` sin drenar mata los tres.

Cgroup del dashboard: `3632884` + `browser_harness.daemon` (722419) + hijos transitorios
(`vitals`, `quota status`). Reiniciarlo mata el daemon de navegador (las sesiones de browser control
caen); hay que asumirlo y avisar, no "descubrirlo" en el reinicio.

**Corrección al supuesto del card:** el dispatcher/worker kanban **no** vive en el cgroup del
dashboard sino bajo el gateway roshi (`ps -o ppid` de 919229/926810 → 4085904). Por eso el card
acierta al prohibir tocar roshi: reiniciarlo sí mataría cards en vuelo (la mía y `t_41c59ea4`).
Reiniciar el dashboard no las mata.

Otra restricción real: el release `cd397afc64` ya está **viejo** y su `hermes_cli/web_dist` es un
build no versionado (3.3 MB). Un release nuevo exige construir la SPA en ese checkout
(`web: node ../scripts/build/web.mjs` → `hermes_cli/web_dist`), no copiar archivos dentro del
release inmutable ni apuntar `current` a un worktree de desarrollo.

## 3. D-I-V-E (cada paso con su comando exacto)

### D — Detectar / diagnosticar (lectura, 2 min)

```
systemctl is-active hermes-agent.service hermes-dashboard.service hermes-agent-roshi.service
systemctl show hermes-dashboard.service,hermes-agent.service -p MainPID -p KillMode -p ExecStart -p WorkingDirectory
curl -s -o /dev/null -w 'dashboard=%{http_code}\n' --max-time 5 http://127.0.0.1:9112/   # esperado 302
hermes gateway status                                                                    # exit 0
sqlite3 /opt/hermes-agent-data/kanban.db "select status,count(*) from tasks group by status;"
ps -o pid,ppid,etime,cmd --ppid $(systemctl show -p MainPID --value hermes-agent.service)
```
Abortar si: gateway no `active`, dashboard ≠ 302, o hay tool calls en vuelo en el gateway default
(hijos `bash`/`ssh`/`scp`).

### I — Inventariar / backup (antes de tocar nada)

```
TS=$(date +%Y%m%dT%H%M%S); B=/opt/hermes-agent-data/backups/ragnar-ccg-$TS
mkdir -p -m 700 "$B"
cp -p /opt/hermes-agent-data/config.yaml "$B/config.yaml"
sha256sum /opt/hermes-agent-data/config.yaml > "$B/config.sha256"
readlink -f /opt/hermes-agent-data/releases/dashboard/current > "$B/dashboard-current.path"
systemctl show -p MainPID --value hermes-agent.service > "$B/pid.gateway"
systemctl show -p MainPID --value hermes-dashboard.service > "$B/pid.dashboard"
git -C /opt/hermes-agent rev-parse HEAD > "$B/root.head"
git -C /opt/hermes-agent status --porcelain > "$B/root.status"
HERMES_HOME=/opt/hermes-agent-data hermes config get agent.capability_claim_guard > "$B/flag.before"
```
El backup del config se hace **con la CLI** en la ejecución, nunca editando YAML a mano
(`hermes config set` es el único writer atómico).

### V — Verificar prerrequisitos

1. `feat/capability-claim-guard-ragnar` limpio y con 488 tests verdes (§5 de `08-integration-ragnar.md`).
2. `git -C /opt/hermes-agent diff --stat 9daf7b8fae..feat/capability-claim-guard-ragnar` = 30 archivos
   (27 de código/spec + 3 de documentación), ninguno de `skills/` ni `docs/` (el árbol sucio ajeno no se toca).
3. `readlink /opt/hermes-agent-data/releases/dashboard/current` y backup legibles.
4. Espacio en `/opt` ≥ 2 GB (release nuevo ≈ 800 MB + build).

### E — Ejecutar (orden obligatorio; flag OFF durante todo el despliegue)

**E1. Dashboard nuevo release (solo si Desktop debe quedar cubierto).**
```
NEW=<commit integrado>; R=/opt/hermes-agent-data/releases/dashboard/releases/$NEW
test ! -e "$R"
git -C /opt/hermes-agent worktree add --detach "$R" "$NEW"
( cd "$R/web" && npm ci && npm run build )          # genera hermes_cli/web_dist
PYTHONPATH="$R" /opt/hermes-agent/.venv/bin/python - <<'PY'
from pathlib import Path
from hermes_cli._launchers import ensure_install_launchers
print(ensure_install_launchers(Path("/opt/hermes-agent-data/releases/dashboard/releases/NEW"), Path("/opt/hermes-agent-data/releases/dashboard/bin")))
PY
```
`ensure_install_launchers` es el API que mintó el launcher actual (no se escribe a mano).
Cambio de symlink atómico: `ln -sfn "$R" /opt/hermes-agent-data/releases/dashboard/.current.tmp && mv -T /opt/hermes-agent-data/releases/dashboard/.current.tmp /opt/hermes-agent-data/releases/dashboard/current`.

**E2. Código del gateway default.** Merge fast-forward sobre la rama viva del root (los archivos
sucios son `skills/` y `docs/`, ajenos al diff):
```
git -C /opt/hermes-agent merge --ff-only feat/capability-claim-guard-ragnar
git -C /opt/hermes-agent status --porcelain | diff - "$B/root.status"   # solo el drift ajeno previo
```

**E3. Reinicios con drenaje.**
- Dashboard: `systemctl restart hermes-dashboard.service` → el daemon de navegador muere; verificar
  `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:9112/` = 302 y `journalctl -u hermes-dashboard -n 40`.
- Gateway default: primero confirmar hijos idle (sin `ssh/scp/bash` en vuelo) y que WhatsApp lleva
  > 60 s sin tráfico; después `systemctl restart hermes-agent.service` (TimeoutStopSec 360 s drena
  cron/WhatsApp), `hermes gateway status` exit 0 y `journalctl -u hermes-agent -n 60 --no-pager`.
- **No** tocar `hermes-agent-roshi.service`.

**E4. Flag ON (última acción).**
```
HERMES_HOME=/opt/hermes-agent-data hermes config set agent.capability_claim_guard.enabled true
HERMES_HOME=/opt/hermes-agent-data hermes config get agent.capability_claim_guard   # enabled: true
```
No requiere reinicio: la guarda lee la config por turno (test
`test_edited_config_is_seen_on_the_next_turn`), y una sesión ya abierta la toma en el turno siguiente.

## 4. Rollback (probado en seco en este card)

| Origen | Acción | Efecto |
|---|---|---|
| Falso positivo / latencia | `HERMES_HOME=/opt/hermes-agent-data hermes config unset agent.capability_claim_guard.enabled` | OFF en el siguiente turno, **sin reinicio**, sin tocar código |
| Dashboard | `ln -sfn` al target guardado en `dashboard-current.path` + `systemctl restart hermes-dashboard` | vuelve a `cd397afc64` |
| Código gateway | `git -C /opt/hermes-agent revert --no-edit <5 commits integrados>` + `systemctl restart hermes-agent` | rama viva vuelve al comportamiento anterior sin destruir el árbol sucio ajeno (`reset --hard` prohibido) |
| Release nuevo | `git -C /opt/hermes-agent worktree remove <R>` tras repuntar `current` | libera ~800 MB; los commits siguen en la rama |

Criterio de abort: dos reinicios fallidos, `gateway status` ≠ 0, o cualquier mensaje publicado y
retractado en el canario → rollback completo por tabla.

## 5. Canario real (post-activación, con aprobación)

Precondición: identificar el backend que usa Desktop (`ps` del proceso `serve` → `/proc/<pid>/cwd`).
Si sale del release del dashboard, E1 es obligatorio; si sale del launcher PATH, E2 ya lo cubre.

Casos (Telegram default y Desktop, texto):

1. **Capacidad disponible** — pedir una acción que use una tool instalada (p. ej. búsqueda web).
   Esperado: cero denegaciones falsas; el texto empieza a publicarse tras el holdback de 200 B; sin
   retracción (`grep` de eventos de reparación en `logs/`).
2. **Ausencia real** — pedir una capacidad no instalada. Esperado: la negativa veraz pasa tal cual
   (no se "repara" una ausencia real), máx. 2 intentos de reparación.
3. **Interino/streaming** — respuesta larga (> 4096 caracteres en Telegram): el split por límite se
   mantiene y ningún bloque se re-emite ni se borra.
4. **Voz** — nota de voz en Telegram: la transcripción y la respuesta TTS no se truncan; medir el
   delta de primer chunk respecto a la línea base del día.
   Aviso medido: `hermes gateway status` reporta `voice.stop_phrases` como string entrecomillado
   (`["stop", "para", "corta"]`) y **todos los lectores lo ignoran** — es un defecto previo del
   home default, ajeno a esta guarda; no bloquea el canario pero invalida cualquier prueba de
   barge-in por voz hasta que su dueño lo corrija.
5. **Aislamiento** — `hermes -p heimdall config get agent.capability_claim_guard` (muestra) debe
   seguir OFF; el flag no se propaga entre homes.

Aceptación: 0 denegaciones falsas, 0 texto retractado, reparaciones ≤ 2, delta de primer chunk
medido y registrado, y `git status` del root solo con el drift ajeno previo.

## 6. Evidencia que este card deja lista (sin ejecutar)

- Rama `feat/capability-claim-guard-ragnar` (5 commits: 4 cherry-picks + esta documentación), 488
  tests verdes, RED 44 fallos en base `9daf`, ruff y health limpios, canario 31/31.
- Comandos de §3 verificados en seco: `curl` dashboard = 302 real; `hermes gateway status` exit 0
  real; `config set/unset` probado contra home desechable (no el real).
- Nada de §3-E se ejecutó: el root sigue en `9daf7b8fae`, sin merge, sin reinicio, sin flag.
