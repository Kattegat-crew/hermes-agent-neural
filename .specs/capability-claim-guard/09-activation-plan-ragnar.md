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
build no versionado (3.3 MB). Un release nuevo se crea con el mecanismo oficial que ya existe,
`/opt/hermes-agent-data/releases/dashboard/bin/promote-release <sha>` (§3-E2): construye la SPA
dentro del release nuevo, lo deja inmutable `root:root`, hace swap atómico de `current`, reinicia la
unidad y revierte solo si el health falla. **No** se copian archivos dentro del release inmutable ni
se apunta `current` a un worktree de desarrollo.

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

1. `feat/capability-claim-guard-ragnar` limpio y con la suite en verde (§5 y §8 de
   `08-integration-ragnar.md`: 147 tests de guarda + 997 del slice streaming/turnos, 0 fallos).
2. `git -C /opt/hermes-agent diff --stat 9daf7b8fae..feat/capability-claim-guard-ragnar` = 31 archivos
   (17 de código —`agent/`, `hermes_cli/`—, 8 de tests y 14 de spec, incluidos los documentos de
   integración y el probe nuevo), ninguno de `skills/` ni `docs/` (el árbol sucio ajeno no se toca);
   intersección medida con `git status --porcelain` del root = **0 rutas** (59 entradas sucias hoy,
   todas ajenas).
3. `readlink /opt/hermes-agent-data/releases/dashboard/current` y backup legibles; existe
   `/opt/hermes-agent-data/releases/dashboard/bin/promote-release` (root:root) y el card tiene root.
4. Espacio en `/opt` ≥ 2 GB (release medido 771 MB + build 3.3 MB; `/opt` tenía 24 GB libres).

### E — Ejecutar (orden obligatorio; flag OFF durante todo el despliegue)

**Precondición de privilegio.** `promote-release` hace `chown -R root:root` y `systemctl restart`,
así que corre como root. Hoy `sudo -n` en este host **no** está disponible (pide contraseña): el card
que ejecute E2 debe tener root (shell de root o `SUDO_PASSWORD`). Si no lo tiene, se detiene y lo
declara (`needs_input`) — no se improvisan `chown`/`chmod`, no se copia código a mano al release y no
se apunta `current` a un worktree.

**E1. Código del gateway default (primero: es la fuente que clona el release).** Merge fast-forward
sobre la rama viva del root (los archivos sucios son `skills/`, `docs/` y `scripts/backup_audit.py`,
ajenos al diff; `hermes_cli/web_dist/` está en `.gitignore:93`, así que el build de E2 no ensucia el
árbol):
```
NEW=$(git -C /opt/hermes-agent rev-parse feat/capability-claim-guard-ragnar)
git -C /opt/hermes-agent merge --ff-only feat/capability-claim-guard-ragnar
git -C /opt/hermes-agent rev-parse HEAD | grep -qx "$NEW"
git -C /opt/hermes-agent status --porcelain | diff - "$B/root.status"   # solo el drift ajeno previo
```

**E2. Dashboard: release nuevo con el mecanismo oficial (sin `--skip-build`).**
```
NEW=$(git -C /opt/hermes-agent rev-parse HEAD)
sudo /opt/hermes-agent-data/releases/dashboard/bin/promote-release "$NEW"
```
Lo que el script hace (leído el 2026-11-03, no supuesto):
1. `rev-parse` del SHA en `/opt/hermes-agent` (de ahí que E1 vaya antes: `clone --shared` sólo ve
   commits, así que el árbol sucio no importa y no hace falta stash).
2. Build acotado en el root: `HERMES_WEB_BUILD_LIGHT=1`, `NODE_OPTIONS=--max-old-space-size=2048`,
   `RAYON_NUM_THREADS=2`, `node scripts/build/web.mjs` → `hermes_cli/web_dist` (node v26.8.2
   medido). Sin `--skip-build` para no copiar el build viejo que hoy vive en el root.
3. `git clone --shared /opt/hermes-agent releases/<sha10>` + `git checkout <sha>` + copia de
   `web_dist` (el release actual, `cd397afc64`, ocupa 771 MB medidos; `/opt` tiene 24 GB libres).
4. Inmutabilidad: `chown -R root:root`, `chmod 755` dirs / `644` files, `+x` en `hermes`,
   `activate` y `scripts/*`.
5. Swap atómico de `current` (symlink temporal + `Path.replace`).
6. `systemctl restart hermes-dashboard.service` (el cgroup se lleva `browser_harness.daemon`
   722419: las sesiones de browser control caen, ya avisado en §2).
7. Health `/api/health` con `ok: true` e **rollback automático** al `current` previo si falla.

**E2-bis. Aserción del commit servido.** El script imprime `version`/`commit` pero **no** los compara
con el SHA pedido, así que la verificación explícita del requisito ("el daemon nuevo reporta el
source commit esperado") es este paso, obligatorio:
```
SERVED=$(curl -s http://127.0.0.1:9112/api/health | python3 -c 'import json,sys;print(json.load(sys.stdin)["commit"])')
test "$SERVED" = "$NEW" || { echo "MISMATCH served=$SERVED want=$NEW"; <rollback Dashboard de §4>; exit 1; }
curl -s -o /dev/null -w 'dashboard=%{http_code}\n' --max-time 5 http://127.0.0.1:9112/   # 302
/opt/hermes-agent-data/releases/dashboard/bin/hermes --version                          # mismo commit
```
El launcher `bin/hermes` vive fuera de los releases y hace `sys.path.insert(0, .../current)`, así que
sigue el swap sin re-acuñarse; sólo si `--version` no reporta el commit nuevo se re-acuñan con
`ensure_install_launchers(<release>, <bin>)` (el API que mintó el launcher actual).

**E3. Reinicio del gateway default con drenaje** (el dashboard ya lo reinició E2; **no** reiniciar de
nuevo ni tocar `hermes-agent-roshi.service`):
- Confirmar hijos idle (sin `ssh/scp/bash` en vuelo) y que WhatsApp lleva > 60 s sin tráfico.
- `systemctl restart hermes-agent.service` (TimeoutStopSec 360 s drena cron/WhatsApp),
  `hermes gateway status` exit 0 y `journalctl -u hermes-agent -n 60 --no-pager`.

**E4. Flag ON (última acción).**
```
HERMES_HOME=/opt/hermes-agent-data hermes config set agent.capability_claim_guard.enabled true
HERMES_HOME=/opt/hermes-agent-data hermes config get agent.capability_claim_guard   # enabled: true
```
No requiere reinicio: la guarda lee la config por turno (test
`test_edited_config_is_seen_on_the_next_turn`), y una sesión ya abierta la toma en el turno siguiente.

## 4. Rollback (dry-run ejecutado en este card sobre un worktree desechable)

Dry-run real (worktree detached en `9daf`, merge `--ff-only` de la rama integrada → HEAD
`93697dbb6e` = branch head, árbol limpio), después `git revert --no-edit` de los 8 commits
(93697dbb6e, 51479cd8d9, 78ed036423, 338d5dfce6, 8ccc035c21, 856c93d66a, a8106d317b, cba1f10dbe):

```
REVERT_HEAD=df238ceca5
DIFF_VS_BASE=0          # git diff --stat 9daf..HEAD → 0 líneas tras los reverts
DIRTY=0                 # git status --porcelain vacío
worktree_removed=YES
```

Es decir: el rollback de código devuelve el árbol **byte a byte** al estado `9daf`. Worktree de
prueba eliminado con `git worktree remove --force`; `git worktree list` vuelve a sus 5 entradas (ninguna
residual). El mismo dry-run se había hecho antes de la ronda 2 con 5 commits y el mismo resultado.

| Origen | Acción | Efecto |
|---|---|---|
| Falso positivo / latencia | `HERMES_HOME=/opt/hermes-agent-data hermes config unset agent.capability_claim_guard.enabled` | OFF en el siguiente turno, **sin reinicio**, sin tocar código |
| Dashboard | Repuntar `current` al target guardado en `dashboard-current.path` con swap atómico (`ln -sfn "$(cat "$B/dashboard-current.path")" .../.current.tmp && mv -T .../.current.tmp .../current`) + `sudo systemctl restart hermes-dashboard.service` | vuelve a `cd397afc64`; verificar `/api/health` → `commit` = `cd397afc64c91e…` |
| Código gateway | `git -C /opt/hermes-agent revert --no-edit <commits de la integración>` + `systemctl restart hermes-agent` | árbol idéntico a `9daf` (probado); `reset --hard` sigue prohibido por el árbol sucio ajeno |
| Release nuevo | tras repuntar `current`, `sudo rm -rf /opt/hermes-agent-data/releases/dashboard/releases/<sha10>` | libera ~771 MB (medido en el release actual); los commits siguen en la rama |

Nota: tras un rollback por revert, reactivar exige revertir los reverts (o un merge nuevo); no se
reutiliza el SHA viejo porque el árbol ya no coincide.

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
5. **Aislamiento** — no basta `config get`: la guarda debe responder por el perfil que POSEE la
   sesión y fallar cerrada cuando no hay perfil propietario. Probe de runtime (sin hogares reales,
   4 homes desechables; el argumento es la raíz de código a importar):
```
# contra el árbol integrado (pre-deploy)
cd /opt/hermes-agent && python .specs/capability-claim-guard/probes/ccg_probe_profile_scope.py /opt/hermes-agent
# contra el código servido (post-deploy, el release que apunta current)
python .specs/capability-claim-guard/probes/ccg_probe_profile_scope.py \
  /opt/hermes-agent-data/releases/dashboard/current
# esperado 6/6: fork shape (sin _session_db, forma de agent/background_review.py:920) = OFF,
# wire_turn del fork = sin evidencia, dueño OFF/ambiente ON = OFF, dueño ON/ambiente OFF = ON,
# config ilegible = OFF, y sólo homes desechables tocados
```
   Además, en el home default `hermes -p heimdall config get agent.capability_claim_guard` debe seguir
   OFF (el flag no se propaga entre homes) y `is_enabled()` sin agente es **False por diseño**
   (fail-closed: no hay perfil propietario que responder).

Aceptación: 0 denegaciones falsas, 0 texto retractado, reparaciones ≤ 2, delta de primer chunk
medido y registrado, y `git status` del root solo con el drift ajeno previo.

## 6. Evidencia que este card deja lista (sin ejecutar)

- Rama `feat/capability-claim-guard-ragnar` (9 commits: 4 cherry-picks, 2 de código de la ronda 2 y 3 de
  documentación), 147 tests de guarda + 997 del slice streaming/turnos en verde sobre el código final,
  RED 44 fallos en base `9daf`, ruff y health limpios, canario 31/31.
- Ronda 2 (hallazgos del review cerrados, detalle en §8 de `08-integration-ragnar.md`): scope fail-closed
  con RED→GREEN propio, probe de runtime `6/6` contra el fix y `4/6` contra `ce34c19c5c`, rollback
  re-dry-run en `93697dbb6e` (reverts → `df238ceca5`, diff 0, dirty 0), y §3-E replanteado sobre
  `promote-release` con la aserción de commit servido que el script no hace.
- Comandos de §3 verificados en seco: `curl` dashboard = 302 real; `hermes gateway status` exit 0
  real; `config set/unset` probado contra home desechable (no el real).
- Nada de §3-E se ejecutó: el root sigue en `9daf7b8fae`, sin merge, sin reinicio, sin flag.
