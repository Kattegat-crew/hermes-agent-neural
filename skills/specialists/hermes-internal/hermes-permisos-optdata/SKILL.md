---
name: hermes-permisos-optdata
description: "Use when /opt/data paths break the gateway's write access."
tags: [permisos, chown, gateway, contenedor, optdata, docker, troubleshooting]
version: 1.0.0
author: Ragnar (NeuralCrew Labs)
license: MIT
platforms: [linux]
metadata:
  hermes:
    category: devops
    tags: [permisos, gateway, contenedor, audio, cache, chown, troubleshooting]
    related_skills: [hermes-memory-maintenance, hermes-admin-operations, voice-message-transcription]
---

# Permisos de /opt/data que rompen al gateway (uid 10000)

Clase de fallo recurrente en este entorno: un proceso corre como **root** y crea o deja un
archivo/carpeta dentro de `/opt/data`; después el gateway (que corre como **uid 10000 /
`hermes`**) no puede leer ni escribir ahí y **una función del bot se rompe en silencio**.

## Síntomas ya vistos

| Síntoma visible | Path típico | Causa |
|---|---|---|
| Nota de voz que "no se pudo descargar" (`PermissionError` al cachear audio) | `/opt/data/audio_cache/` | Carpeta `drwx------ root root` |
| `Refusing to write MEMORY.md: ... could not be read right now` | `/opt/data/MEMORY.md`, `USER.md` | Lock o dueño cambiado |
| Hook `post_tool_call` con `Permission denied` en rutas del repo | `/root/hermes-agent-legacy-docker/data/repos/...` | Rutas root dentro del árbol de datos |
| `insufficient permission for adding an object to repository database .git/objects` | repo bajo `/opt/data/repos/...` | `git` invocado con dueño distinto |
| `Failed to cache voice: [Errno 13] Permission denied: '/opt/data/audio_cache/audio_*.ogg'` en `gateway.log` | caché de audio entrante | Igual que el primero |
| Cron job muere con `PermissionError: [Errno 13] Permission denied: '/opt/data/logs/errors.log'` | `/opt/data/logs/*.log` | El cron del host corre `docker exec hermes-agent ...` (**root** dentro del contenedor) y deja el log con dueño `root:root` |

## Diagnóstico (3 comandos)

```bash
grep -iE "permission denied|failed to cache voice|refusing to write" /opt/data/logs/gateway.log \
  /opt/data/logs/agent.log | tail -20       # el error real y su ruta exacta
ls -ld /opt/data /opt/data/audio_cache /opt/data/cache/audio   # dueño y permisos (se espera hermes/hermes)
id                                            # confirma que el shell es uid 10000 = hermes
```

## El mapa de rutas (memorizarlo)

- **`/opt/data` del contenedor == `/root/hermes-agent-legacy-docker/data` del host** (misma copia física).
- Los perfiles viven en `/opt/data/profiles/<perfil>/` (host: `/root/hermes-agent-legacy-docker/data/profiles/...`).
- Por eso un `chown` hecho desde el host se refleja al instante dentro del contenedor.

## El fix (no hay sudo en el contenedor)

El shell del contenedor es `hermes` y **no tiene sudo**, así que el arreglo se hace desde el
host DEV, que sí es root, apuntando a la ruta equivalente:

```bash
ssh dev 'chown -R 10000:10000 /root/hermes-agent-legacy-docker/data/audio_cache && chmod 755 /root/hermes-agent-legacy-docker/data/audio_cache'
```

Y se **verifica desde el contenedor** (no desde el host) con una escritura real:

```bash
touch /opt/data/audio_cache/_t && rm /opt/data/audio_cache/_t && echo "ESCRITURA OK (uid $(id -u))"
```

Si la carpeta tenía contenido que no se puede leer (root 700), **no borrarla**: moverla con
`mv /opt/data/<dir> /opt/data/<dir>.root-bak-<fecha>` (basta permiso de escritura en el padre,
que es de `hermes`) y recrearla vacía como `hermes`.

## Fix sin salir del contenedor: `docker exec` (nuevo, 11/09/2026)

No hace falta `ssh dev`: dentro del contenedor **sí existe el CLI de docker** y `docker exec hermes-agent ...` entra como **uid 0**. Es el camino rápido para reparar un archivo root-owned:

```bash
docker exec hermes-agent id                                   # uid=0(root) ✅
docker exec hermes-agent chown hermes:hermes /opt/data/logs/errors.log
docker exec hermes-agent chmod 644 /opt/data/logs/errors.log
stat -c '%U:%G %a %n' /opt/data/logs/errors.log                # verificar desde el contenedor
```

Ojo: `chown` desde el shell de `hermes` falla con `Operation not permitted` (no hay sudo). El `docker exec` es el atajo; `ssh dev` sigue siendo el camino canónico cuando el árbol entero está mal.

## Causa estructural de los logs root-owned (y su cura)

El cron del host (`/etc/cron.d/...`) ejecuta `docker exec hermes-agent /bin/bash /opt/data/scripts/gateway-fleet-health.sh` **cada 5 min sin `-u hermes`** → todo lo que ese proceso escribe queda `root:root`. Si el log rota o se recrea, `errors.log` nace root y **cualquier job o sesión que registre un error revienta** (caso real: `informe-diario-exacto` murió así el 11/09/2026).

Cura aplicada: `gateway-fleet-health.sh` termina con una normalización idempotente —

```bash
for f in /opt/data/logs/errors.log /opt/data/logs/agent.log /opt/data/logs/gateway.log; do
  chown hermes:hermes "$f" 2>/dev/null || true
done
chmod 644 /opt/data/logs/errors.log 2>/dev/null || true
```

Reglas de esa línea: `|| true` para que **nunca aborte** el vigía cuando corre como `hermes` (el mismo script se invoca también desde el cron del perfil vigia, sin privilegios); se ejecuta al final, tras el `printf` de alertas; no usa `-R` ni toca el árbol completo.

**Verificación que vale** (hazla tal cual): deja el log root-owned a propósito (`docker exec hermes-agent chown root:root /opt/data/logs/errors.log`), corre el script como lo corre el host (`docker exec hermes-agent bash /opt/data/scripts/gateway-fleet-health.sh`) y comprueba que vuelve a `hermes:hermes` y que una escritura real desde `hermes` funciona.

## Después del fix

- **Si era el caché de audio:** avisar al usuario que **reenvíe la nota de voz** — el audio
  perdido no se recupera — y reportar la causa en una línea (no hace falta pedirle que reinicie nada).
- **Si era memoria:** seguir `hermes-memory-maintenance`.
- Anotar en la bitácora del día qué proceso corrió como root, si se puede identificar (`ps -eo user,comm`),
  para que no vuelva a crear carpetas root dentro de `/opt/data`.

## Pitfalls

- **No usar `sudo`**: no existe en el contenedor. Cualquier receta con `sudo` falla; el camino es `ssh dev`.
- **No cambiar permisos del árbol completo** (`chown -R /opt/data`) para "arreglar todo": rompe
  otros servicios y puede tocar la sesión de WhatsApp.
- **NUNCA tocar `/opt/data/whatsapp/session/`** (emparejamiento activo; blindaje de arquitectura).
- **No confundir cablear permisos con arreglar la causa:** si el proceso root vuelve a crear la
  carpeta, el fallo regresa; documentarlo y escalarlo al Admin.
- **Un 403 en la API de Google Drive con un `secrets/*-drive.json` no es un problema de permisos
  de disco** — es scope/consentimiento del token; no mezclar diagnósticos.

## Related

- `hermes-memory-maintenance` — locks y permisos de `MEMORY.md` / `USER.md`.
- `voice-message-transcription` — protocolo de notas de voz (este skill cubre el caso "no baja").
- `hermes-admin-operations` — operación y auditoría del gateway.
