---
name: vps-host-repo-access
description: "Use when reading host VPS repos from the container."
tags: [docker, socket, vps, host, git, nsenter, contenedor]
---

# VPS Host Repo Access (docker socket)

Los repos en el HOST del VPS (147.93.3.250) NO están montados en el contenedor hermes. La vía probada es el docker socket montado (`/var/run/docker.sock`, grupo `hostdocker`).

## ⚠️ Pitfall crítico al montar rutas de contenedor

**Docker `-v` monta RUTAS DEL HOST, no del contenedor.** Una ruta como `/opt/data/profiles/sindri/...` (que existe dentro del contenedor hermes) NO existe en el host — docker crea un directorio VACÍO en el host y lo monta. El script dentro del contenedor recibe una carpeta vacía y falla sin error visible.

**Síntomas:** `sh /tmp/x.sh` no produce output, `python3 /tmp/script.py` dice "can't find __main__ module", `cat /tmp/x` da EOF.

**Fix: pasar scripts por stdin en vez de mount:**

```bash
# En lugar de:  docker run ... -v /opt/data/.../script.sh:/tmp/x.sh:ro ...
# Hacer:
docker run -i --rm --entrypoint /bin/sh -v /root/<repo>:/repo <image> -c \
  'cat > /tmp/x && sh /tmp/x' < /opt/data/.../script.sh
```

## Patrones verificados

### 1. Lectura/estado general (archivos, .env nombres, outputs)
```bash
docker run --rm --network host -v /root/<repo>:/repo:ro alpine sh -c 'cd /repo; ls; grep -oE "^[A-Z_]+" .env'
```

### 2. Git — CRÍTICO: la imagen alpine/git tiene ENTRYPOINT ["git"], NO "sh".
```bash
docker run --rm --entrypoint sh -v /root/<repo>:/repo:ro alpine/git -c \
  'cd /repo; git config --global --add safe.directory /repo; \
   git branch --show-current; git log --oneline -12; git status --short; \
   git log -1 --format="%ci %h %s"'
```

### 3. Servicios del host con systemd (nsenter, funciona desde cualquier contenedor)
`systemctl` no existe dentro de alpine/python — pero se puede ejecutar **en el host** via nsenter:

```bash
# daemon-reload + restart
docker run --rm --pid=host --privileged --entrypoint /bin/sh -v /etc/systemd/system:/etc/systemd/system alpine -c '
  apk add -q util-linux 2>/dev/null
  nsenter -t 1 -m -p -- systemctl daemon-reload
  nsenter -t 1 -m -p -- systemctl restart <unit>.service
  sleep 2
  nsenter -t 1 -m -p -- systemctl is-active <unit>.service'

# alternatives probadas y FALLIDAS (no repetir):
# - dbus-next (D-Bus desde contenedor): EOFError al deserializar
# - pip install systemctl: el binario no se instala en PATH
# - systemctl.py (gdraheim): no existe tal paquete con ese nombre
```

### 4. SSH a otros VPS desde el contenedor
```bash
docker run --rm -v /root/.ssh:/keys:ro alpine sh -c '
  apk add -q openssh-client 2>/dev/null
  timeout 15 ssh -i /keys/id_ed25519 -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 \
    root@<IP> "comando"`
```

### 5. Servicios HTTP (health check rápido, sin systemd)
```bash
docker run --rm --network host alpine sh -c 'wget -qO- -T5 http://127.0.0.1:<port>/health'
```

### 6. Transferir archivos entre contenedor ↔ workspace del agente
El workspace del agente (`/opt/data/...`) NO existe en el host del docker (ver pitfall
crítico arriba) — ni en modo lectura ni escritura. Para pasar archivos REALES:
- **Texto/scripts**: stdin (`docker run -i ... python3 - < script.py`) o base64 inline.
- **Binarios (mp3/wav/png) host→agente**: `docker run -v /ruta/host:/src:ro alpine tar -c -C /src . > ws/archivo.tar` y `tar -xf` local.
- **Binarios agente→host**: `base64 -w0 archivo | docker run -i --entrypoint /bin/sh alpine -c 'cat > /tmp/g.b64; base64 -d > /out/x'` (mount de dir del host en /out).
- OJO: `docker run -v` con una ruta inexistente del host CREA el dir como root — si luego
  el agente no lo ve, es porque ese dir vive en el host, no en el contenedor.

### 7. Correr pytest del repo en contenedor desechable (verificación de parches)
```bash
docker run --rm -i --entrypoint /bin/sh -v /root/<repo>:/repo python:3.13-alpine -c '
  apk add bash >/dev/null 2>&1
  pip install -q pytest edge-tts pillow >/dev/null 2>&1
  cd /repo && bash -c "python3 -m pytest tests/ -q 2>&1 | tail -4"'
```
Pitfalls comprobados: (a) `apk add` combinado (py3-pytest + bash + ffmpeg en un solo
comando) puede fallar silencioso → instalar en pasos separados y verificar con echo.
(b) Varios tests del pipeline lanzan `bash` por subprocess (placeholder clips con ffmpeg):
sin `apk add bash` dan 99 falsos FAILED que NO son del parche. (c) ffmpeg en alpine via
apk dentro del mismo run a veces no aplica a los tests → mejor `apk add ffmpeg bash`
antes de pytest. Antes de atribuir un fallo a tu cambio, corrié la suite SIN tu parche
o revisa el error (127/bash not found, PIL missing = entorno, no código).

## Pitfalls
- Mount `:ro` → `git fetch` falla (`'.git/FETCH_HEAD': Read-only file system`). Usar refs locales: `git rev-list --left-right --count HEAD...origin/main`.
- `git status/log` sin `safe.directory` salen vacíos silenciosos — siempre setearlo primero.
- Nunca imprimir valores de secretos; solo nombres de claves (`grep -oE "^[A-Z_]+" .env`).
- `systemctl` no existe dentro de alpine/python → usar nsenter (patrón #3 arriba).
- `openssl` no existe en alpine → usar `python3 -c 'import secrets;print(secrets.token_hex(32))'`.

## Auditoría de estado de un repo (receta)
1. `git log -1` + `git status --short` + ahead/behind vs origin → detectar trabajo sin commitear/pushear.
2. Comparar `docs/JOURNEY.md` (suele estar al día) contra `README.md` (suele estar viejo) — el estado verídico está en JOURNEY + Engram.
3. Buscar artefactos reales (outputs, mp4, manifests) con `find` antes de afirmar que algo existe/no existe.
4. Engram: `mem_search` con `project: <nombre-repo>` explícito (la búsqueda default por proyecto `hermes` devuelve "No memories found" — hay que pisar el project).

## Caso conocido: video-ai-generator
- Repo: `/root/marketing-campaign-generator` (Kattegat-crew/marketing-campaign-generator, rama canónica `main`), worker HTTP en :8090.
- **Estado operativo vigente (28/08): JWT activo en POST, AP en .222, lip-sync Ruta 1 IMPLEMENTADO en fal-client (reference2video), D2 cleanup aplicado, pendientes** → ver `references/video-ai-generator-operaciones-2026-08-28.md`.
- **Schema Seedance r2v en fal** (lip-sync nativo, límites audio_urls/image_urls, endpoint, ejemplo talking-head): `references/seedance-r2v-fal-schema.md`.
- El skill `video-ai-generator` de este perfil está DESACTUALIZADO y es una copia parcial del de `default` (/opt/data/skills/). El de default y `skills/creative/video-reel-pipeline` (global) son los que tienen el detalle operativo.
