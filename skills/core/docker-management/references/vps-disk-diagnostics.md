# VPS Disk Diagnostics

## Problem
Un VPS tiene el disco lleno y hay que identificar qué lo está consumiendo.

## Fast Path (3 pasos)

### Paso 1: Top-level view
```bash
du -sh /* 2>/dev/null | sort -rh | head -20
```
Identifica qué directorio raíz pesa más.

### Paso 2: Drill into big dirs
```bash
du -sh /opt/* 2>/dev/null | sort -rh | head -20
du -sh /root/* 2>/dev/null | sort -rh | head -20
du -sh /root/hermes-agent-legacy-docker/* 2>/dev/null | sort -rh | head -20
```
### Paso 3: Big files and Docker
```bash
find / -type f -size +50M -not -path "/proc/*" -not -path "/sys/*" -not -path "/dev/*" 2>/dev/null -exec ls -lh {} \; | sort -k5 -rh | head -20
docker system df                     # disk usage summary
docker image ls --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"  # image sizes
```

## Big Users (common)

| Source | Typical Size | What it is |
|--------|-------------|------------|
| Docker images | 3-30 GB | Old images, build layers, unused tagged images |
| Docker build cache | 0-32 GB | BuildKit cache (safe to prune) |
| Docker rootfs | 6-30 GB | Overlay filesystem for containers |
| /var/lib/docker/volumes | 0-800 MB | Named volume data |
| Backups | 0-3+ GB | Manual snapshots, DB dumps, config backups |
| /root/hermes-agent-legacy-docker/data/ | 9+ GB | state.db, sessions, profiles, lazy-packages, node_modules, home/ |
| /home/ | 0-500 MB | User data (orca, cuenta2, jon) |
| /tmp/ | 0-200 MB | Temp files, opencode cache, video caches |

## Safe Cleanup

| Action | Space freed | Risk |
|--------|------------|------|
| `docker image prune` | dangling images only | Low |
| `docker image prune -a` | ALL unused images | Medium — check with `docker ps` first |
| `docker builder prune -a` | Build cache | None |
| `docker container prune` | Stopped containers | None |
| `docker system prune` | containers + images + networks | Low |
| `docker system prune -a --volumes` | EVERYTHING including named volumes | HIGH — destroys data |

## Quick Commands

```bash
# Full picture
echo "=== DISK ===" && df -h /
echo "=== TOP DIRS ===" && du -sh /* 2>/dev/null | sort -rh | head -20
echo "=== DOCKER ===" && docker system df

# Targeted cleanup
docker image prune -a          # free image space
docker builder prune -a        # free build cache
docker container prune         # free stopped container space

# Remove specific big file
rm /path/to/big/file.tar.gz    # confirm first
```

## VPS SSH Diagnostics

From Hermes container, check remote VPS without manual login:

```bash
# Single VPS check
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 root@<IP> "echo OK"

# Full diagnostics
ssh -o StrictHostKeyChecking=no root@169.58.189.222 "echo '= VPS STATUS =' && hostname && uptime && df -h / && free -h && docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
```

> **Pitfall:** The Hermes container only has GitHub SSH keys by default. Connecting to external VPS IPs may require credentials shared by the admin. Verify connectivity with `echo OK` before running heavy commands.

## Session Example (2026-08-24)

### VPS .250 (Contabo, 147.93.3.250)
- 145 GB disk, 84% used (25 GB free) ⚠️
- 30.2 GB Docker images (8.9 GB reclaimable)
- 3.8 GB /opt/backups (3.3 GB is old v0.10 snapshot)
- 9.5 GB /root/hermes-agent-legacy-docker/data/ (3.9 GB home/, 1.1 GB node_modules, 567 MB archive)

### VPS .222 (Coolify Prod, 169.58.189.222)
- 290 GB disk, 12% used (256 GB free) ✅
- 29 containers active, webhook-gateway in restart-loop
- 23 GB RAM, 16 GB available

### Cleanup actions proposed
1. `docker image prune -a` on .250 → ~9 GB freed
2. Remove `/opt/backups/hermes_v0.10.0_snapshot_20260808.tar.gz` → 3.3 GB freed
3. Investigate webhook-gateway restart loop on .222