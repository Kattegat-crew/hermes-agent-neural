---
name: static-portal-generator
description: "Use when building multi-client static portals from files."
version: 1.0.0
author: Ragnar (NeuralCrew Labs)
license: MIT
tags: [portal, static-site, nginx, multicliente, galeria, docker, cloudflare]
---

# Static Portal Generator

Generate, deploy, and maintain multi-client static HTML portals served from a single nginx/reverse-proxy endpoint. Patterns emerged from reels.neuralcrewlabs.com (Golden + Lucky campaign portal).

## When to Use

- Building a public gallery or portal showing assets (video, audio, images, docs) for **multiple clients/brands** under one domain
- Deploying campaign material organized by client → campaign → section
- Content is static HTML/CSS/JS served by nginx — no build framework needed
- Need to inventory remote filesystem contents and generate pages with real file references

## Architecture

```
Cloudflare → NPM/proxy → nginx container (:port) → docroot
                                ↓
domain.com/*
```

One domain, one docroot. All clients as subdirectories:
```
/var/reels/
├── index.html                    (portada: cards per client)
├── assets/portal.css             (shared design system)
├── client-a/gallery/             (interleaved content)
│   ├── clips/  scenes/  voz/
├── client-b/gallery/
├── client-a/pages/               (HTML pages for client A)
│   └── campaign/section/index.html
└── client-b/pages/
```

## Pipeline

### 1. Inventory (SSH scan)
```bash
ssh root@SERVER "find /var/reels -maxdepth 5 -type f \\(-name '*.mp4' -o -name '*.wav' -o -name '*.png' \\| ..."
```
Produce JSON: `{"path": {"size": N, "size_h": "4.8MB"}}`

### 2. Content (campaign.yaml or docs)
Extract real campaign data from source-of-truth files. NEVER invent stats.

### 3. Generate (Python script)
Single generator reads inventory + content JSON → all HTML pages:
- Shared CSS/JS (dark theme, client-specific accent colors)
- Correct relative paths to real assets
- Responsive grids for video/image/audio
- Vanilla JS lightbox, native `<video>` and `<audio>` players

### 4. Deploy
```bash
# Streaming migration:
tar czf - -C /var/source dir/ | ssh root@TARGET "tar xzf - -C /var/reels/"
# Or scp for generated HTML:
scp -r ./portal/ root@TARGET:/var/reels/
```

### 5. Verify (curl external)
```bash
curl -sf -o /dev/null -w "%{http_code}" https://DOMAIN/client/gallery/
curl -sf -o /dev/null -w "%{http_code}" -r 0-1000 https://DOMAIN/client/clips/S1.mp4  # 206 = range OK
```

## Critical Pitfalls

### 🔴 Docker volume mount resolves against HOST, not container
When running `docker run -v /path/in/container:/dest` from INSIDE a container (e.g. hermes-agent), the path resolves against the **HOST** filesystem. Inside hermes-agent: `/opt/data/workspace` = `/root/hermes-agent-legacy-docker/data/workspace` on host.

**Fix:** Always use the HOST path for `-v` mounts:
```bash
# WRONG (mounts empty dir)
docker run -v /opt/data/workspace/nc-portal-dev:/usr/share/nginx/html:ro nginx:alpine
# RIGHT (host path)
docker run -v /root/hermes-agent-legacy-docker/data/workspace/nc-portal-dev:/usr/share/nginx/html:ro nginx:alpine
```

**Verify mount:** `docker exec <container> ls /usr/share/nginx/html/` — if empty, mount path is wrong.

### 🔴 Asset cross-contamination between clients
**The #1 mistake.** NEVER reference Client A's assets on Client B's pages, even if files exist in the same docroot.

**Root cause:** Files from one client end up in another's folder during migration. The generator blindly uses whatever image it finds — Client A's mascot appears on Client B's card.

**Prevention:**
- Map each client's REAL asset directories before generating
- Client A pages → Client A assets only. Zero sharing.
- After deploy, visually verify BOTH clients on mobile — HTTP 200 ≠ correct content
- If a file has the wrong client name, verify what it actually depicts

### 🔴 Server migration mid-transition
Old nginx stopped, new one active, DNS on old → 404. Verify with `curl -I` from outside VPS.

### 🟡 Generator needs production inventory
Read files on PRODUCTION server — don't hardcode from dev.

### 🟡 Streaming tar timeout
`docker run tar | ssh tar` may timeout at 60s. Use `timeout 300`.

### 🟡 CSS/JS path resolution
Use absolute paths (`/assets/portal.css`) to avoid relative path breakage at different depths.

## Design System

- Inter font (Google Fonts CDN)
- Dark theme: `#000` bg, `#0A0A0E` surfaces, `#1E1E24` borders
- Client accents: per-brand colors
- Zero shadows — depth via border + hover transform
- Video-first cards, styled audio lists, image grid + lightbox
- Mobile-first responsive grid: `auto-fill minmax(320px, 1fr)`

## SPA Variant (Single-Page App with Sidebar)

For internal production dashboards (not public galleries), a single-page app with sidebar navigation is preferred over multi-page:

```
┌─ HEADER ──────────────────────────────────────┐
│  🎬 NC·REELS    [Client A]  [Client B]       │
├──── SIDEBAR ──────┬────── CONTENT AREA ───────┤
│ 📋 Campaign       │  [Selected section]        │
│   ├ Pre-prod      │                            │
│   │ ├ Guion       │  Content scrolls to the    │
│   │ ├ Master P.   │  selected section via      │
│   │ ├ Hero        │  anchor links from sidebar  │
│   │ ├ Ambient.    │                            │
│   ├ Producción    │                            │
│   │ ├ Escenas     │                            │
│   │ ├ Clips       │                            │
│   │ ├ Voz         │                            │
│   │ └ Reel final  │                            │
│   ├ Eventos       │                            │
│   ├ Legal         │                            │
├──── FOOTER ───────┴────────────────────────────┤
```

**Structure:** One `index.html` with embedded CSS/JS + inline data object. Sidebar collapses per-client with `▸` toggle. Mobile: hamburger slide-in. Content sections stack vertically; sidebar links scroll to anchors.

**User-mandated rules (Jonathan, 02/09 — do not regress):**
- ONE page total. No per-client landing pages — clients switch via header tabs.
- Both client sidebars must be **exactly identical**, same predetermined section set (Resumen, Guion, Master prompt, Hero, Ambientaciones, Escenas, Clips, Voz, Reel final).
- Hierarchy is **Campañas → Reels → sections**: each reel expands into its 8 sections; a placeholder "Reel N+1 — Próximo" pre-renders the same section set so production info has a landing spot.
- Campaign badge at top of each client view. New campaigns = new block under the current one, never a new page.
- Workflow for the next reel: guion → tabla producción → master prompt → hero personaje → ambientaciones all cascade into that reel's sections. "La información del reel ES toda la información de la campaña."

**Production pipeline order (encode in sidebar):**
1. **Pre-producción:** Guion → Tabla producción → Master prompt → Hero personaje → Ambientaciones
2. **Producción:** Escenas → Clips → Voz → Reel final
3. **Campaña:** Plan → Eventos → Legal

**Data-driven for next reel:** New content = new entries in the data object. Generator reads remote inventory via SSH and embeds real file references.

**Generator:** `/opt/data/workspace/gen-portal-spa.py`
**Dev server:** nginx:alpine container on `:8080` (see Docker Dev Server pattern below)

## Docker Dev Server Pattern

For previewing generated sites before pushing to production:

```bash
# Create container with correct HOST path (see pitfall below)
docker run -d --name portal-dev --restart unless-stopped \
  -p 8080:80 \
  -v /root/hermes-agent-legacy-docker/data/workspace/nc-portal-dev:/usr/share/nginx/html:ro \
  nginx:alpine

# Verify
curl -sf -o /dev/null -w "%{http_code}" http://<host-ip>:8080/
```

**Host path resolution:** From inside hermes-agent container, `/opt/data/workspace` = `/root/hermes-agent-legacy-docker/data/workspace` on host. Docker `-v` mounts always resolve against HOST.

### 🔴 VPS .250 provider port whitelist (hit 02/09/2026)
The dev VPS (147.93.3.250) has a provider-level security group that exposes ONLY ports 3010, 3020, 6080. Every other port (8080, 9112, 3000, 9119, 80, 443...) times out from the Internet — even with `network: host` or `-p` publishing, and despite no ufw/iptables/nftables on the host. Do NOT burn time debugging host firewall rules; it's upstream.

**Working alternatives:**
1. Publish to prod .222 under a staging path: `scp index.html root@100.73.30.29:/opt/reels/v2/` → live at `https://reels.neuralcrewlabs.com/v2/` (HTTPS, instant).
2. Tailscale-only preview for the user.
3. Ask the provider to open the port (slow).

### 🔴 Audit ALL asset paths per client, not just one (hit 02/09/2026)
Cross-contamination was fixed in ONE `src=` and shipped — the bug survived in 4 places (portada, hub, campaña, reel poster) because the generator had multiple hardcoded client paths (`/lucky/bingo/...` vs `/va/lucky/bingo/...`). Before deploy: `grep` every `src=`/`href=` in the generated HTML for the OTHER client's directory names, and grep the generator for stale folder constants. HTTP 200 on both clients ≠ correct content.

## NeuralCrew Reference

- Domain: `reels.neuralcrewlabs.com` | Server: VPS .222 | Container: `reels-web` :9020
- **SPA v2 (current):** `https://reels.neuralcrewlabs.com/v2/` — prod docroot `/opt/reels/v2/`
- SPA Generator: `/opt/data/workspace/gen-portal-spa.py` (v2: single-page sidebar, Campañas→Reels hierarchy; regenerate with `python3 gen-portal-spa.py` then `scp` to `/opt/reels/v2/`)
- Legacy Generator: `/opt/data/workspace/gen-reels-portal.py` (multi-page, superseded)
- Dev dir: `/opt/data/workspace/nc-portal-dev/` · dev server: `nc-portal-dev` container (network host, nginx:alpine, `/root/hermes-agent-legacy-docker/data/workspace/nginx-portal.conf`) — .250 port 8080 is provider-blocked (see pitfall), treat dev server as local-only
- Content: `/opt/data/workspace/portal-content.json`