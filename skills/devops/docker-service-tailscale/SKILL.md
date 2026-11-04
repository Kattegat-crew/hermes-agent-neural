---
name: docker-service-tailscale
description: "Use when reaching a Docker service via Tailscale IP."
tags: [tailscale, docker, red, puerto, vps, bind]
category: devops
---

# Expose Docker Services via Tailscale

## When to use
- A service runs inside Docker on the VPS
- Need to access it from another device on the Tailscale network
- No public IP or port forwarding available
- Quick access without setting up nginx/reverse proxy

## Prerequisites
- Tailscale installed and running on the host VPS
- Know the VPS Tailscale IP (check Tailscale admin console)
- Service is already running inside Docker

## Steps

### 1. Find the VPS Tailscale IP
- Open Tailscale admin console
- Look up the machine name → check "ADDRESSES" column
- Example: `100.86.8.81`

### 2. Start/bind the service to 0.0.0.0
The service must listen on `0.0.0.0` (not just `127.0.0.1`):

```bash
# Example: Hermes dashboard
cd /opt/hermes
.venv/bin/python3 -c "from hermes_cli.web_server import start_server; start_server(host='0.0.0.0', port=9119, open_browser=False, allow_public=True)"

# For any Python app, bind to 0.0.0.0:PORT
# For Node/Next.js, set HOST=0.0.0.0
# For Fastify, set host=0.0.0.0
```

### 3. Verify it's running
```bash
python3 -c "import urllib.request; r = urllib.request.urlopen('http://localhost:PORT'); print('Status:', r.status)"
```

### 4. Access from another device
Open browser to: `http://<TAILSCALE_IP>:PORT`

## General pattern for any service

| Service | How to bind to 0.0.0.0 |
|---------|----------------------|
| Python (uvicorn/fastapi) | `uvicorn app:app --host 0.0.0.0 --port PORT` |
| Python (flask) | `flask run --host 0.0.0.0 --port PORT` |
| Node/Next.js | `HOST=0.0.0.0 PORT=3000 npm run dev` |
| Next.js (standalone) | `HOST=0.0.0.0 PORT=3000 node .next/standalone/server.js` |
| Fastify | `app.listen({ host: '0.0.0.0', port: 3000 })` |
| Docker container | Use `-p 0.0.0.0:PORT:PORT` in docker run or docker-compose |

## Important Notes
- `allow_public=True` or equivalent may be needed for services with auth checks
- No robust authentication on Tailscale-only access — trusted networks only
- Process may need restart if it crashes (use `nohup` or background process)
- Tailscale IP can change, verify before each use
- If the service is already running and bound to localhost only, restart it with `0.0.0.0`

## Troubleshooting
- **Can't connect**: Verify service is bound to `0.0.0.0`, not `127.0.0.1`
- **Process died**: Restart the service command
- **Wrong IP**: Check Tailscale admin console for current IP
- **Firewall**: Tailscale handles its own routing, no firewall config needed for Tailscale IPs