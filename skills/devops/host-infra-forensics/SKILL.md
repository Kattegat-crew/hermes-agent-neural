---
name: host-infra-forensics
description: "Use when a self-hosted service is unreachable remotely"
tags: [forensics, tailscale, systemd, reachability, netns, docker, diagnostico, self-hosted]
license: Apache-2.0
metadata:
  author: "roshi"
  version: "1.0"
  tags: [forensics, tailscale, systemd, docker, netns, reachability, hermes-desktop]
  category: devops
---

# Host / infra forensics desde el contenedor

Diagnosticar "el servicio X no me responde" separando **tres planos independientes** antes de proponer arreglo:

1. **Salud del servicio** (¿el proceso escucha y responde localmente?).
2. **Camino de red / identidad** (¿el cliente puede alcanzar la IP del servicio? tailnet, DNS, firewall).
3. **Auth / sesión** (¿llegó la petición y fue rechazada, o nunca llegó?).

Regla dura: **el log del cliente NO es evidencia suficiente.** Un timeout en el cliente puede ser servicio caído, red caída o IP equivocada. Probar cada plano en la fuente donde vive.

## When to Use

- Un cliente remoto (Hermes Desktop, navegador, otro VPS, un bot) no puede alcanzar un servicio self-hosted.
- Hay que saber si el problema es el server, la red o la sesión — sin acceso SSH interactivo (solo hay el contenedor Hermes).
- Sospecha de nodo Tailscale offline, unit systemd rota, o puerto que no escucha.

## Herramientas del contenedor contra el host

`/host` = raíz del host (bind). **Identidad de árbol:** `/opt/data` del contenedor == `/host/root/hermes-agent-legacy-docker/data` del host. Verificar SIEMPRE con inodo antes de editar/afirmar algo:

```bash
stat -c '%d:%i %n' /opt/data /host/root/hermes-agent-legacy-docker/data
```

**Procesos del host** (el /proc del contenedor no los ve):

```bash
for p in /host/proc/[0-9]*; do c=$(tr '\0' ' ' < $p/cmdline 2>/dev/null); \
  case "$c" in *patron*) echo "$(basename $p): $c";; esac; done
cat /host/proc/<PID>/cgroup          # -> /../nombre.service  (mapea systemd)
stat -c %y /host/proc/<PID>          # hora de arranque real
```

**Tabla TCP del host** — OJO: `/proc/net/tcp` del contenedor y `/host/proc/net/*` son la netns del LECTOR. Hay que entrar a la netns del host:

```bash
docker run --rm --net=host node:20-alpine sh -c 'grep -i ":2398\|:1F9A" /proc/net/tcp'
# campos: direccion:puerto_hex ... estado 0A=LISTEN ; 9112=2398, 8090=1F9A
```

**systemd del host** (solo lectura):

```bash
docker run --rm --pid=host -v /:/hostroot node:20-alpine \
  chroot /hostroot /bin/bash -lc \
  'systemctl is-active <svc>; systemctl show <svc> -p WorkingDirectory,ExecStart,FragmentPath,DropInPaths,ActiveEnterTimestamp --no-pager'
```

Alternativa sin docker: leer `/host/etc/systemd/system/<svc>.service` + drop-ins `.d/` y backups `*.pre-rename-*` / `*.bak-*` (dicen de dónde se movió el servicio). Usar `--privileged` solo como último recurso y para inspección read-only.

**Tailnet del host** — ejecutar el binario del host contra el socket del host (Go estático, corre desde el contenedor):

```bash
TS="/host/usr/bin/tailscale --socket=/host/run/tailscale/tailscaled.sock"
$TS status --json      # Self + peers: HostName, DNSName, Online, LastSeen, KeyExpiry, Expired
$TS ping --c 1 --timeout 3s <ip>
$TS netcheck           # DERP/UDP: confirma que la red Tailscale está sana
```

**Logs del host:** `/host/root/hermes-agent-legacy-docker/data/logs/` (`agent.log`, `errors.log`, `gateway.log`, `dashboard-auth.log` = audit JSONL de auth del dashboard).

## Caso: el browser del agente no arranca (`chrome-not-running`)

Síntoma: `browser_exec` falla con `browser-harness: daemon default didn't come up` y el log (`<home>/.config/browser-harness/tmp/bu-default.log`) dice `fatal: chrome-not-running`.

**El harness NO usa un Chrome local:** lee `browser.cdp_url` (config) y se conecta a ese endpoint. En esta flota apunta a un nodo remoto por Tailscale (`http://100.102.79.4:9222`). Si ese nodo está offline, TODOS los perfiles se quedan sin browser.

Diagnóstico y workaround (sin tocar el config global, que es de otro perfil):

1. Confirmar que el endpoint está muerto: `curl -s --max-time 8 http://<cdp_url>/json/version`.
2. Levantar un Chrome headless local (Playwright ya lo trae) **en background**:
   `.../chrome-linux64/chrome --headless=new --remote-debugging-port=9222 --user-data-dir=<home>/.chrome-profile --no-sandbox --disable-dev-shm-usage --disable-gpu about:blank`
   (sin `--headless=new` muere con `Missing X server or $DISPLAY` — el contenedor no tiene X).
3. Verificar: `curl -s http://127.0.0.1:9222/json/version`.
4. Override SOLO en el config del perfil propio, appendeando al final del YAML:
   `browser:` / `  cdp_url: http://127.0.0.1:9222`
   El editor de archivos bloquea configs de Hermes — usar `printf ... >> config.yaml` por terminal.
5. `read_raw_config()` cachea por (mtime, size) ⇒ **el cambio se aplica en la siguiente llamada, sin reiniciar nada**.

Reversible: guardar copia (`config.yaml.bak-<fecha>`) y quitar el bloque cuando el nodo vuelva.

## Técnicas

- **Fingerprint de cliente:** para probar qué máquina produjo un log del cliente, casar sus líneas por timestamp contra el audit del server (ej. `[native-oauth] loopback listening` del Desktop ↔ evento `native_authorize_start` con `ip` en `dashboard-auth.log`). Identidad probada, no supuesta.
- **Ventana sin eventos server-side = las peticiones nunca llegaron** ⇒ problema de camino de red, no de app ni de auth.
- **"Responde desde el propio host" ≠ "responde desde el cliente":** una IP tailnet contesta localmente aunque el peer esté offline. Probar siempre desde el lado del cliente.
- **Audit por cliente/IP:** agregar con Python (JSON por línea) → first/last ts, conteo por evento, `reason`. Distingue "nunca llegó" de "llegó y lo rechazaron".
- **Timeouts largos (~10-15 s) antes del fallo = connect timeout**, no 401/404 (esos son instantáneos).
- **Distinguir caché de sesión real:** líneas tipo `Remote backend is ready` pueden venir de un descriptor cacheado; si en el mismo minuto el server no registró tickets/sesión, esa conexión no existió.

## Pitfalls

- No concluir "servicio caído" cuando el cliente está offline; ni al revés.
- **Unit systemd con path viejo:** si el directorio de `WorkingDirectory` se movió, el proceso ya arrancado sigue vivo (inode renombrado) y el servicio "parece" sano, pero **al reiniciar falla**. Verificar que el path existe antes de prometer que un restart es seguro.
- Revivir el server cuando el plano roto es la red del cliente quema tiempo y no arregla nada.
- No tocar config del host sin OK del usuario: este flujo es de **diagnóstico read-only**; los cambios se proponen con evidencia.

## Verification

Reportar por plano, con evidencia citada: (1) servicio: PID, puerto LISTEN, respuesta HTTP/health local; (2) red: estado del peer/tailnet y alcanzabilidad desde el cliente; (3) auth: eventos del audit en la ventana de fallo. Recién entonces proponer el arreglo, marcando qué queda pendiente de OK del usuario.

## References

- `references/desktop-remote-gateway-tailnet-2026-09.md` — caso completo: Hermes Desktop no arranca porque el nodo Tailscale del PC está offline (strings de error exactos, audit del gateway y checklist de arreglo).
