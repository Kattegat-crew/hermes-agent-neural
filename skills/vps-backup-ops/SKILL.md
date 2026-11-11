---
name: vps-backup-ops
description: Use when verifying backup coverage or running backups.
tags: [backup, restic, vps, prod, dev, infraestructura, recuperacion]
license: MIT
metadata:
  hermes:
    tags: [backup, restic, vps, prod, dev, infraestructura, recuperacion]
    related_skills: [hermes-config-integrity, fleet-profile-forensics]
---

# Verificación y operación de backups VPS (restic master backup)

Skill para auditar que los master backups realmente cubren lo que importa, detectar archivos críticos sin respaldo ni git, y ejecutar/verificar un backup manual tras un cambio de rutas.

---

## When to Use (Cuándo usar)
- "¿X archivo/directorio está respaldado?" o auditar cobertura tras crear un script crítico fuera de git.
- Antes y después de corregir rutas en el script de backup.
- Verificación post-incidente: confirmar qué versión de un archivo es recuperable.

## Reglas siempre activas
- Un log `BACKUP FINALIZADO (ESTADO: SUCCESS)` NO prueba cobertura: el script maestro filtra sus `backup_paths` con `os.path.exists()` ANTES de disparar restic, y toda ruta inexistente se descarta en silencio. Verificar SIEMPRE el listado real de paths del último snapshot, nunca el log.
- Un archivo crítico solo está protegido si está EN GIT (`git ls-files`) Y en el listado de paths del snapshot restic. `/opt/data` está en `.gitignore` en PROD: todo script vivo únicamente en `/opt/data` es un punto único de fallo hasta que entre a git o a un path respaldado.
- Tras corregir una ruta de backup, probar con backup manual y releer el snapshot: un diff del script no es evidencia de cobertura.

## Procedimiento de verificación de cobertura (PROD vía `ssh prod`)
1. **Paths declarados por el script:**
   ```bash
   grep -n "backup_paths" -A 30 /opt/data/scripts/vps_master_backup.py
   ```
2. **Existencia en vivo de cada path** (`ls -la <path>`): una ruta vacía o inexistente se está excluyendo del snapshot aunque esté escrita en el script.
3. **Paths del último snapshot real:**
   ```bash
   restic -r rclone:onedrive:Backups/.222 \
     --password-file /opt/data/backup-keys/master-backup.key snapshots --latest 1
   ```
   Usar `--latest 1`: `--last` está deprecado y con un prefijo de ID suelto falla con "no matching ID found".
4. **Comparar:** toda ruta crítica viva ausente del snapshot es un agujero. Para un archivo puntual:
   ```bash
   restic ... snapshots --latest 1 --json | grep -c "<nombre_archivo>"
   ```
5. **Tras corregir una ruta:** correr `python3 /opt/data/scripts/vps_master_backup.py` y releer `snapshots --latest 1` confirmando que el path nuevo aparece.

## Referencia rápida de la infraestructura
- Repos: PROD → `rclone:onedrive:Backups/.222`, DEV → `rclone:onedrive:Backups/.250`. Key: `/opt/data/backup-keys/master-backup.key` (en el servidor respectivo).
- Agenda: backup maestro 03:00 (cron), verificación `check_backups_prod.py` 06:30 con notificación a Discord.
- Dumps de DB en staging: `/opt/data/backups/staging/dumps` (se limpian tras el snapshot).
- El script identifica servidor por IP (169.58.189.222 = prod, 147.93.3.250 = dev); no pasar `--server` asumido.
