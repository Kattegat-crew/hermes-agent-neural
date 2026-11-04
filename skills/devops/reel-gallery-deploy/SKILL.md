---
name: reel-gallery-deploy
description: "Use when deploying a public reel gallery to the VPS."
tags: [reels, galeria, nginx, vps, deploy, static]
---

# Galería pública de reels — reels.neuralcrewlabs.com

## Infra (operativa desde 29/08 — ACTUALIZADO 04/09)
- **Dominio**: `reels.neuralcrewlabs.com` — **Cloudflare PROXY (orange)** → PROD `169.58.189.222` (NO dev). El DNS fue revertido a PROD por el Admin; NO desplegar en el VPS dev (147.93.3.250).
- **Servidor**: VPS PROD `.222` / Tailscale `100.73.30.29`
- **Contenedor**: `reels-web` (nginx) puerto `9020` → docroot `/opt/reels` (bind host)
- **Portal estructura** (no es una página suelta):
  ```
  /opt/reels/
    index.html                    # portada (Golden / Lucky / galerías)
    golden-game/
    lucky-brothers/
      campañas/septiembre-2026/
        reels/<slug>/             # una carpeta por reel
        escenas/ clips/ voz/ guiones/ prompts/ assets/ copies/ historias/ eventos/ legal/ plan/
  ```
- **Cert**: Let's Encrypt (gestionado por NPM/Cloudflare en PROD — no por golden-web-proxy)
- **Acceso**: `ssh root@100.73.30.29` (Tailscale) — scp para subir assets, curl a `http://127.0.0.1:9020` para probar

## Desplegar un reel nuevo (en PROD)
```bash
B="/opt/reels/lucky-brothers/campañas/septiembre-2026/reels/<slug>"
ssh root@100.73.30.29 'mkdir -p "'$B'"/{escenas,clips,voz,guiones,assets-general,docs}'
scp escenas/*.png  root@100.73.30.29:"$B/escenas/"
scp index.html    root@100.73.30.29:"$B/"
# enlazar desde reels/index.html (tarjeta en el índice de la campaña)
```

## Deploy de una campaña nueva
```bash
CAMPAIGN="lucky-bingo"   # slug corto
mkdir -p /var/www/golden-webproxy/reels/$CAMPAIGN/{clips,voz,frames}
# copiar assets desde /root/marketing-campaign-generator/assets/...
# crear index.html de la campaña (patrón: tarjetas video/audio, dark theme, paleta del cliente)
# añadir tarjeta en /var/www/golden-webproxy/reels/index.html
```
**CRÍTICO**: todo DENTRO de `/var/www/golden-webproxy/` — el contenedor no ve rutas fuera del volumen montado (una vez se creó /var/www/reels suelto → 404 silencioso).

## Verificación (SIEMPRE externa)
```bash
# curl local NO sirve (resuelve /etc/hosts 127.0.0.1)
python3 -c "import urllib.request; r=urllib.request.urlopen('https://reels.neuralcrewlabs.com/'); print(r.status, len(r.read()))"
```
Checklist: root 200 + galería 200 + un video 200 con `Content-Type: video/mp4` + `Accept-Ranges: bytes` (206 en range request = streaming OK).

## Pitfalls
- Root del dominio sin index.html → nginx 403 (fue el bug del estreno)
- **Mapa público vs SSO (verificado 04-nov-2026 con curl externo):** para links a CLIENTES usar SOLO `https://reels.neuralcrewlabs.com/assets/<dir>/...` (NPM proxy_host 20 → reels-web :9020, sin auth — GET 200). NO usar `goldengame.com.co/va/...`: esa location está detrás del Universal Forward Auth (oauth2-proxy, `auth_request` en el server_proxy.conf de NPM) y devuelve 403 a cualquiera sin sesión. Symptom típico: el Admin ve el link "roto" porque su navegador sí tenía sesión. La raíz de reels.neuralcrewlabs.com también conserva SSO (solo el shell ~5 KB sin sesión); solo los paths /assets/ son públicos.
- Actualizar imágenes ya cacheadas por Cloudflare: añadir query param de versión (`?t=1103b`) a cada URL del HTML; no esperar a que el TTL expire.
- Empaquetar entregables zip con `python3 -m zipfile -c` o `zipfile.ZipFile(...)`: el binario `zip` no existe en el contenedor DEV.
- Range requests: nginx los sirve nativo para archivos estáticos; no romper con config rara de gzip en .mp4
- Cache-Control `no-store` en la galería para evitar HTML viejo
- Monid necesita frames por URL https de dominio público — publicarlos aquí y usarlos como input

## Referencias
- Galería activa: `/lucky/bingo/` (Bingo Millonario Lucky, sept 2026)
- Video: /root/marketing-campaign-generator (skill creative/monid-seedance-clips para generación)