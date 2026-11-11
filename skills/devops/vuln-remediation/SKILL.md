---
name: vuln-remediation
description: Use when patching critical PHP or Node CVEs on DEV/PROD.
version: 1.0.0
author: Ragnar
license: internal
metadata:
  hermes:
    tags: [security, php, nodejs, docker, cve, remediation]
    related_skills: [docker-management, systematic-debugging, vps-deployment-ops]
---

# Remediation de vulnerabilidades de runtime (PHP/Node) — NeuralCrew

Metodología destilada del plugin devin-vuln-fixes (Cognition, github.com/CognitionAI/devin-marketplace, skills fix-php-vuln/fix-node-vuln) adaptada a nuestra infra: 2 hosts (DEV 147.93.3.250, PROD 169.58.189.222), todo en Docker Compose, acceso `ssh prod` / `ssh dev` (DEV también desde dentro del runtime).

## Ciclo obligatorio
1. **Inventario SOLO LECTURA**: barrer TODOS los contenedores (`docker ps` + `exec <c> php -v / node -v / python3 -c 'import certifi...'`) y el host. Un runtime por contenedor; anotar versión, exposición (¿sirve web? ¿hace salidas?) y vía (imagen upstream, paquete distro, build fuente). NO decidir fix de builds distro comparando `php -v` con versiones upstream: consultar el changelog del vendedor.
2. **Gate de aprobación**: presentar tabla al Admin y esperar OK explícito antes de editar. Ofrecer en el mismo mensaje minor/major upgrades y cambios de base para aprobar de una vez.
3. **Parcheo**: elegir el target fijo más pequeño por vía (mismo tag de imagen reconstruido, paquete de seguridad distro, o backport). No adivinar tags/digests: verificar en el registry ANTES de editar. Si la imagen upstream no existe aún, NO migrar de major bajo presión (p. ej. no saltar de Mautic 5 a 7 por un parche).
4. **Verificación en runtime real**: `php -v`/`node -v` dentro del contenedor, diff de `php -m`/`php -i` viejo vs nuevo, smoke test HTTP del servicio, logs sin fatales. Los fixes solo surten efecto tras recreate + restart de TODOS los workers (`docker restart` NO propaga env nuevos — usar `docker compose up -d`).
5. **Criterio de cierre**: cada deployment verificado fijo o reportado bloqueado con siguiente paso concreto. Documentar en el ticket correspondiente.

## Mitigaciones interinas PHP2Shell (CVE-2026-109618/109619) — solo reducen exposición
- `session.upload_progress.enabled=0` en php.ini o pool FPM (NO `ini_set()`, NO `.user.ini`) + restart de todos los workers. Nuestra vía estándar: bind mount RO de `zz-security.ini` en `conf.d`.
- `post_max_size` 8M (sin uploads) / 32M (con uploads); límites de proxy en body/multipart/headers.
- En 8.5: `fatal_error_backtraces=0`.
- **PROHIBIDO usar RLIMIT_AS / RLIMIT_DATA como mitigación**: disparan la asignación vulnerable.
- Mitigación ≠ fix. Etiquetar siempre.

## Node (oct-2026: CVE-2026-111497 + 2 bypass TLS)
- Versiones fijas: 22.23.4 / 24.22.1 / 26.12.1. Node 20 y 18: SIN parche → migración.
- Node compila su propio bundle NSS: NO hereda `/etc/ssl/certs` del host. `/etc/environment` del host NO propaga a contenedores. Vía en contenedores: `NODE_OPTIONS=--use-openssl-ca` en compose + mount del bundle limpio del host en `ca-certificates.crt:ro` (verificar `docker inspect` → campo `.RW=false`).
- Test de verificación: handshake a `https://dv-g3b-emudhra.we-have-a-problem.com/` debe RECHAZAR; control positivo `api.github.com` debe dar 200.

## Vulnerabilidades de kernel TCP (patrón oct-2026: CVE-2026-98432)
- El contenedor comparte el kernel del host: auditar SIEMPRE a nivel host, no dentro del contenedor. Verificar `uname -r` contra el TRACKER de la distro (no contra versiones upstream — Ubuntu/Debian re-versionan los backports).
- Chequeo de exposición: `uname -r` + `sysctl net.mptcp.enabled` + `sysctl net.ipv4.tcp_migrate_req` + `ss -Mlnp` (listeners MPTCP reales). MPTCP activo sin listeners ≠ explotable vía PoC, pero el bug subyacente puede afectar el handshake TCP normal.
- Mitigación estándar mientras no hay kernel parcheado (regla oficial Red Hat/AlmaLinux, reversible, sin impacto en tráfico normal): `nft add table ip cve_<id>; nft add chain ip cve_<id> pre '{ type filter hook prerouting priority -300; }'; nft add rule ip cve_<id> pre meta l4proto tcp ip hdrlength gt 5 counter drop` (dropea IPv4-TCP con opciones IP; el regla es transitoria — aceptable si el reboot final es a kernel parcheado).
- Desactivar MPTCP si no se usa: `/etc/sysctl.d/90-disable-mptcp.conf` con `net.mptcp.enabled = 0` + `sysctl -w`. Go ≥1.24 abre listeners MPTCP por defecto; si se desactiva, Go cae a TCP normal.
- El reboot que aplique el kernel parcheado es obligatorio: un update de kernel sin reboot NO activa el fix.

## Trampas conocidas (verificadas en incidente 21-oct-2026)
- `docker restart` preserva metadatos del contenedor: env/mounts nuevos requieren recreate.
- **grep sobre bundles PEM NO prueba nada**: los subjects van en base64 dentro del bloque PEM. Verificar confianza SOLO con handshake real (curl/node/python contra el dominio de prueba) o decodificando con `openssl s_client` (mirar el nombre REAL del root — puede diferir del publicado: "emSign Root TLS CA - G3" ≠ "emSign ECC Root CA - G3").
- **Montar solo el archivo `ca-certificates.crt` es insuficiente**: OpenSSL/Go/curl también leen el DIRECTORIO `/etc/ssl/certs/` (archivos hash .0 individuales del store viejo). Montar el directorio completo RO: `/etc/ssl/certs:/etc/ssl/certs:ro`.
- Runtimes que NO leen el store del sistema: Java (JVM: `/etc/ssl/certs/java/cacerts`) y Node con bundled NSS. `--use-openssl-ca` puede ser no-op en builds custom (ActivePieces/outline): probar el handshake SIN flags manuales antes de dar por bueno el flag.
- `update-ca-certificates -f` REGENERa desde `/usr/share/ca-certificates/` del paquete VIEJO del contenedor → puede RE-crear la confianza comprometida (regresión vista en metabase/stirling). Copiar también `/usr/share/ca-certificates/mozilla/*` del host antes de regenerar.
- Go cachea el store al arrancar: tras cirugía hace falta restart del proceso. Contenedores con `readonly_rootfs=true` no admiten cirugía in-container → solo mount vía compose.
- Cirugía in-container (vaciar `/etc/ssl/certs/` del contenedor y copiar el set limpio del host con `docker cp`) es EFÍMERA: se pierde al recreate. La persistencia exige mount en Compose (o Coolify).
- Probar SIEMPRE sin flags manuales: lo que importa es el env del proceso real.
- Un `docker inspect` `.RW=false` = solo lectura (false NO significa vulnerable).
- Alpine/busybox leen `/etc/ssl/cert.pem` (no el .crt): copiar ambos paths al parchear.
- `curl:000` es ambiguo (rechazo O fallo de red): desambiguar con `-sS` o un control positivo (google debe dar 200).

## Backports distro verificados (para builds propios)
- Debian bookworm: `8.2.35-1~deb12u1` · Ubuntu noble: `8.3.6-0ubuntu0.24.04.13` · jammy: `8.1.2-1ubuntu2.28`. remirepo NO publica same-day.

## Triage multi-CVE a escala de flota (auditoría disparada por fuente externa: video, advisory, alerta)
Destilado de la auditoría «Octubre Negro» (24-oct-2026): 12 CVEs de un video + investigación paralela, verificados en vivo contra DEV y PROD con evidencia de comando.

1. **Obtener la lista exacta de la fuente**: video → descargar con yt-dlp (necesita `curl-cffi`: `uvx --from "yt-dlp[default,curl-cffi]" yt-dlp ...`) y transcribir STT; no fiarse de la descripción/oEmbed.
2. **Inventario de versiones por contenedor** (una línea por servicio, tolerante a contenedores sin CLI):
   - Redis: `docker exec <c> redis-cli INFO server | grep redis_version` (imagem sin tag ≡ auditar por exec, nunca por nombre de imagen).
   - Postgres: `docker exec <c> postgres --version`. Metabase: `GET /api/session/properties` → campo `version.tag`. NPM: `package.json` del contenedor + `docker inspect --format '{{.Config.Image}}'`.
   - PHP embebido (Coolify): `docker exec coolify php -v` — la FECHA de build del binario decide si trae el parche.
3. **Detección pasiva de hallazgos**: `redis-cli PING` sin auth respondiendo `PONG` = hallazgo (sin requirepass). `docker ps --format '{{.Names}} {{.Ports}}' | grep '->'` para mapeos publicados; `ufw status` + `iptables -L DOCKER-USER -n` para el control REAL (las publicaciones de puertos Docker bypasean ufw — DOCKER-USER es lo que decide exposición externa).
4. **Prueba de exposición desde vantage externa**: curl al IP público desde el OTRO host. PROD→su propio IP es ambiguo (hairpin); `000` desde otro host = filtrado. `PermitRootLogin`/fail2ban: revisar `/etc/ssh/sshd_config` y `journalctl -u ssh --since '-24h' | grep -ci failed`.
5. **Clasificación por CVE**: comparar versión contra el minor parcheado del vendedor (no contra "latest"); para RCE de kernel revisar `lsmod` (p. ej. sin `ksmbd` cargado, las 2 RCE SMB del oct-2026 no tienen vía remota); para componentes de librería (LiteLLM backdoor 1.107.0) verificar versión pinned local y dejar regla de NO actualizar a la versión comprometida.
6. **Cierre**: reporte MD + ticket en el foro `tickets-tecnicos` (tags: Pendiente + responsable-en-tag + PROD/DEV + categoría; mención real `<@ID>` verificada en el campo `mentions` del API; mensaje <2000 chars; adjuntar el MD al hilo). Separar explícitamente «ya cerrado/verificado» de «acciones pendientes» para que el Admin no re-audite.

## Pre-rollout
- Revisar GHSA-w8hw-w9fx-j79w y GHSA-6wmf-4rv5-p3rp: circuló claim no verificado de que el fix 8.5.12 era incompleto. Confirmar antes de desplegar cualquier imagen con PHP 8.5.
- Snapshot/backup antes de tocar; rollback = digest anterior (sigue vulnerable: mantener mitigación mientras tanto).

## Endurecimiento de host con vps-forge en servidores VIVOS (no máquinas limpias)

La skill `vps-forge` del catálogo (github.com/mountain-beaver/vps-forge) tiene dos modos y confundirlos rompe el servidor: su script de forja es EXCLUSIVO para máquinas limpias; en producción usar únicamente el modo auditoría.

- Auditoría read-only de un host vivo (con checksum de no-modificación):
  `ssh <host> 'bash -s' < /opt/hermes-agent-data/skills/devops/vps-forge/scripts/audit.sh`
  Score de referencia PROD (23-oct-2026): 71/100, 0 FAIL. Tras correrla, borrar `/tmp/vpsforge-audit.sh` del host (el audit se copia ahí y genera un WARN `tmp_exec` falso).
- WARN `exposure.docker ... publicly` = falsa alarma si DOCKER-USER filtra: el audit marca "publicly" todo lo publicado en 0.0.0.0, pero Docker bypasea ufw y decide `iptables -S DOCKER-USER`. Cadena que solo hace RETURN en 80/443 y DROP al resto = esos puertos públicos bloqueados para internet. Verificar la cadena ANTES de abrir incidentes.
- Cambios hardened por fases con deadman: SSH crypto drop-in (`01-vps-forge-crypto.conf` de la propia skill), sysctl drop-in, etckeeper, restic. Una fase a la vez, cada una con deadman de rollback y prueba de sesión SSH NUEVA antes de cerrar la actual.
- WARN `backups.job` no ve snapshots del proveedor ni cron externos — contrastar antes de duplicar jobs.
- WARN `compromise.cpu` puede ser solo procesos legítimos picando CPU en ese instante — correlacionar con el servicio dueño antes de asumir minería.

## Live-restore antes de actualizar el suite Docker

Sin `"live-restore": true` en `/etc/docker/daemon.json`, cualquier `apt upgrade` de docker-ce/containerd reinicia el daemon y TIRA TODOS los contenedores (~48 en PROD, sitios de clientes incluidos). Revisar daemon.json ANTES del upgrade; en la ventana de mantenimiento habilitar live-restore en el mismo cambio para que futuras actualizaciones del suite no corten servicios. Suite vigente al cierre (23-oct-2026): docker 29.9.0→29.9.2 + containerd/buildx/compose = los únicos upgradables restantes en PROD; DEV delegado a Roshi/Codex (SSH de Ragnar sin llave autorizada en el host y `/host` monta mínimo).