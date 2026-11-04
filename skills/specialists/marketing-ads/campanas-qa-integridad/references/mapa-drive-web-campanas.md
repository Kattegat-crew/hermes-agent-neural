# Mapa vivo: Drive de campañas ↔ superficie web (relevado 11/09/2026)

Levantado con evidencia (API de Drive + config real de prod/servicios), **no de memoria**.
Se pidió como "ubicaciones y recursos que se están utilizando" para guiones + escenas.

## 1. Drive — cuenta y raíz

- **Shared Drive `Neural Crew Labs`**; cuenta operativa `captain@neuralcrewlabs.com`
  (Jonathan Parra, cuota 30 GB).
- **Credenciales (probar en orden, usar la primera que refresque):**
  `/opt/data/secrets/neuralcrew-drive.json` → `golden-drive.json` → `lucky-drive.json`
  → `jonathan-drive.json` → … (son las materializadas de Activepieces).
  ⚠️ El token raíz `/opt/data/google_token.json` puede estar **expirado/revocado**
  (`invalid_grant`); no es la fuente confiable.
- **Python con `google-api-python-client`:** `/opt/data/.venv/bin/python` (el python del
  sistema no lo trae).
- Probe re-ejecutable: `scripts/drive_map_campanas.py` (lista drives, busca carpetas por
  nombre, resuelve rutas completas y lista hijos de las raíces de campaña).

## 2. Drive — rutas reales de campaña (con IDs)

```
Neural Crew Labs / Clientes / {Golden|Lucky} / Marketing {Golden|Lucky} /
  Campañas / <slug> /
    00-contrato/ 01-docs/ 02-guiones/ 03-piezas/ 04-aprobadas/
    Calendario_BingoSep2026_Golden_Lucky.xlsx   ← el calendario vive aquí, por cliente
```

| Elemento | ID |
|---|---|
| Marketing Golden | `1tE9VPKJrwpfLPerLVnHEKgzzhsrgtPBJ` |
| Marketing Lucky | `1dsNfnm4go8JzBtwJsOqvOJfkyM5xpBvK` |
| Campaña Golden (`bingo-millonario-golden-sep2026`) | `1yjMyLNPD_YTDuk5Vi2WOD4bCOxklvFIi` |
| Campaña Lucky (`bingo-millonario-lucky-sep2026`) | `18tSR5HnHBRKfJDUk_051WsSjXGy7MdqT` |
| Golden `02-guiones` / `03-piezas` / `04-aprobadas` | `1G1mrrug9U_pzWqbCpswMuU4QYiAkxDql` / `1EOqKqoPAz4h68O4OgUOl1S-DUU4Arkrk` / `1i2zAXQjR32FT7nZ35wCwvOAYJlUmBd8g` |
| Lucky `02-guiones` / `03-piezas` / `04-aprobadas` | `18l8XCSb-Vrarreafiyc-sBMdOq5FHD-B` / `1FY-8Gyvcr5SxfPqDaQs1libTPhTYNbvG` / `1k-NZUj8rt7hWbcZ8VEfE7_epC2laaLk-` |

**Árbol de un reel dentro de `03-piezas/Reels/`** (ahí viven escenas y guion del reel):

```
03-piezas/Reels/Reel Campaña bingo lucky/
  Reel 1 Bingo-intro/  Escenas Reel 1/   (scene-1..5, 2a/2b/2c, lucky studio, lucky hero)
  Reel 2- Chiquinquira/  Escenas/        (scene-1..5.png, hero lucky, Referencia de recorrido)
                         Guion/          (Guion_Cinematografico_Final_Lucky_Grand_Paradise)
                         Master prompt/ Voces/ Videos/ Final/
03-piezas/Funza/Reel 3- Funza ya listo/
```

IDs de referencia: `Reel 2- Chiquinquira` `1lTCkYKYDsKDSXW8L9oRbWDur0aIIUZ3l` ·
`Escenas` `17_xVv7D8XIlwKkkvKKqJJwagJcWZ3l9O` · `Guion` `1pD-cDC1ZqyxTiM5FZ2i36ag_BKGDECYF` ·
`Reel 1 Bingo-intro / Escenas Reel 1` `1RHlpd8DOyMDYDQOOh2lXoogNcubzM4iW`.
Golden no tiene carpeta "Escenas" suelta fuera del reel: sus keyframes de Goldie viven en el
repo (`assets/golden/Scene *.png`) y en Drive dentro de `03-piezas/Reels`.

## 3. Superficie web — quién sirve qué

Front: **Cloudflare** → **Nginx Proxy Manager en PROD (.222 / 100.73.30.29)** es el ÚNICO dueño
de :80/:443. La tabla viva está en su sqlite (no inventarla):

```sql
select domain_names, forward_scheme, forward_host, forward_port from proxy_host;
-- /opt/docker/nginx-proxy-manager/data/database.sqlite
```

| Dominio | Upstream | Qué es |
|---|---|---|
| `reels.neuralcrewlabs.com` | `172.19.0.1:9020` | contenedor **reels-web** (nginx:alpine, volumen `/opt/reels` → web root) |
| `goldengame.com.co` (+www) | `172.19.0.1:9001` | landing Golden (Coolify) — **ahí viven los reviews `/va/<TOKEN>/<VERSION>/review.html`** |
| `paradiseclubcasinos.com.co` (+www) | `172.19.0.1:9002` | landing Paradise |
| `neuralcrewlabs.com` | `172.19.0.1:9003` | sitio de agencia |
| `dashboard.` / `auth.` / `ap.` / `crm.` | `:3011` / `:3043` Pocket ID / `:8088` Activepieces / `:3020` Twenty | panel de servicios, SSO, flows, CRM |

- **SSO:** `oauth2-proxy-universal` (`/opt/docker/oauth2-proxy/oauth2-proxy.cfg`) protege reels:
  `provider="oidc"` (Pocket ID), `client_id="universal-sso"`, `cookie_domains/.neuralcrewlabs.com`.
  Por eso un `curl` a reels devuelve **302 → `auth.neuralcrewlabs.com/authorize`** y no 200.
- **⚠️ `neuralcrew.com` NO es del equipo**: responde 302 a `atom.com/name/NeuralCrew` (dominio
  parqueado/en venta). El ecosistema real es `neuralcrewlabs.com` + dominios de cliente
  (`goldengame.com.co`, `paradiseclubcasinos.com.co`). No usarlo en piezas ni links.

## 4. Cadena de publicación (dev → prod)

```
repo/worker en .250 (dev)  --ssh/scp-->  root@100.73.30.29:/opt/reels/<marca>/campañas/<mes>/reels/<reel>/clips/
previews locales en .250:  /var/www/golden-webproxy/{va,reels}
link de revisión con token: https://goldengame.com.co/va/<TOKEN>/<VERSION>/review.html   (publish-review.sh)
```

Regla del usuario (02/09/2026): **.250 = solo desarrollo, nada público sale de ahí**; el staging
se sube a prod por Tailscale. Los scripts del generador (`run_scenes.py`, `run_scene1.py`,
`run_t2.py`) son los que hacen ese scp a `.222:/opt/reels/...`.

## 5. Interlock Drive ↔ web ↔ worker

Los tres planos comparten los mismos slugs (`bingo-millonario-{golden,lucky}-sep2026`,
`septiembre-2026`, `reel2-chiquinquira`) y el **calendario XLSX vive en Drive de cada cliente**:
`planning/calendario-sep2026/sync_from_drive.py` → `calendario.jsonl` → crons de publicación.
Drive = entregable formal · portal = vitrina de revisión · worker/repo = fábrica.
