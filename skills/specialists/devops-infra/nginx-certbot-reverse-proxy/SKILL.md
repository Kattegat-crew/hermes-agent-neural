---
name: nginx-certbot-reverse-proxy
description: "Use when adding HTTPS domains behind a shared nginx proxy"
tags: [nginx, certbot, reverse-proxy, tls, letsencrypt, coolify, webhook-routing, devops]
---

# Nginx + Certbot Reverse Proxy

## Overview

Add HTTPS domains to apps running on Coolify containers behind a shared nginx proxy. Use certbot for Let's Encrypt certificates and configure reverse proxy rules including webhook endpoints.

## When to Use

- Adding a new domain with HTTPS to an app on a Coolify host
- Configuring reverse proxy rules in a shared nginx instance
- Setting up Let's Encrypt certificates with certbot
- Routing `/webhook/` paths to backend services on different ports
- Troubleshooting SSL or proxy issues for existing domains

## When NOT to Use

- Apps that manage their own TLS (e.g., Cloudflare tunnel)
- Internal-only services (use HTTP on localhost)
- First-time nginx installation (configure base nginx first)

## Core Pattern

```
DNS (A record) → Cloudflare → VPS IP
  └─> nginx (shared proxy)
       ├─> server_block: example.com → proxy_pass http://<HOST_IP>:<port> (contenedor)
       ├─> location /webhook/ → proxy_pass http://<HOST_IP>:<port> (mismo proxy)
       └─> certbot → /etc/letsencrypt/live/<domain>/
```

## Quick Reference

| Component | Path/Port |
|-----------|-----------|
| Certificates | `/etc/letsencrypt/live/<domain>/` |
| Nginx config | `/opt/golden-web-proxy/nginx.conf` or `/etc/nginx/sites-available/` |
| Certbot | `certbot certonly --webroot -w /var/www/golden-webproxy -d <dominio>` (HOST)
| Coolify port | Varies per project (check `docker ps` for port mappings) |
| DNS | A record: `@` and `www` → VPS IP |

## Implementation

### 1. Configure nginx server block

```nginx
server {
    listen 80;
    server_name example.com www.example.com;

    location / {
        # Ver F-2: topoloxía de red
        # Nginx en CONTENEDOR → apunta a HOST_IP:puerto
        # Nginx en HOST     → apunta a 127.0.0.1:puerto
        proxy_pass http://147.93.3.250:<COOLIFY_PORT>;  # contenedor → host
        # proxy_pass http://127.0.0.1:<COOLIFY_PORT>;  # host local
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /webhook/ {
        proxy_pass http://147.93.3.250:<COOLIFY_PORT>;  # mismo destino
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 2. Get certificate with certbot

```bash
# Este VPS: certbot en el HOST, autenticador webroot (no --nginx containerizado)
certbot certonly --webroot -w /var/www/golden-webproxy -d example.com -d www.example.com

# Alternativa: --standalone si puerto 80 está libre (no aplica si nginx ya corre)
# certbot certonly --standalone -d example.com -d www.example.com

# --nginx NO funciona aquí: el nginx es contenedorizado (golden-web-proxy),
# certbot no puede acceder a su config de nginx para auto-configuración.
```

### 3. Update server block for HTTPS

```nginx
server {
    listen 443 ssl;
    server_name example.com www.example.com;

    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    # ... proxy rules same as above
}

server {
    listen 80;
    server_name example.com www.example.com;
    return 301 https://$host$request_uri;
}
```

### 4. Reload nginx

```bash
nginx -t && systemctl reload nginx
```

### 5. Verify

```bash
# HTTP status
curl -sI https://example.com | head -1
# Expected: HTTP/2 200

# SSL certificate
openssl s_client -connect example.com:443 -servername example.com </dev/null 2>/dev/null | openssl x509 -noout -dates

# Webhook endpoint
curl -X POST -H "Content-Type: application/json"   -d '{"test": true}' https://example.com/webhook/endpoint

# Test other domains on same proxy
curl -sI https://other-domain.com | head -1
```

## Common Mistakes

| Error | Cause | Fix |
|-------|-------|-----|
| proxy_pass to port 80 | Proxying to nginx itself, not the app | Use the Coolify container's port (check `docker ps`) |
| Webhook 404 | `/webhook/` not in server block | Add `location /webhook/` with same proxy_pass |
| Other domains broken | Editing shared nginx config affects all | Test all domains after changes |
| SSL not working | Certbot didn't complete or config not updated | Check certbot logs, verify cert file exists |
| CORS fails after adding domain | Domain not in app's CORS_ORIGINS | Add domain to `.env` CORS_ORIGINS in the app |
| Cloudflare confusion | Panel warnings are generic behind Cloudflare | Verify with real `curl` to the domain |

## Real-World Impact

- Proxying to port 80 instead of the app port creates a redirect loop
- Forgetting `/webhook/` in the server block breaks webhook delivery
- Shared nginx configs mean changes to one domain can break another (e.g., golden)
- Behind Cloudflare, DNS propagation warnings in Coolify are generic — always verify with `curl`
