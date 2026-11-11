# Canonical por ruta en SPA (bug clasico, fijado 09-nov-2026 en golden/paradise)

## Regla dura
Una SPA que sirve el MISMO index.html para todas las URLs del sitemap tiene un
contrato roto: el canonical estatico apunta a la raiz y Google fusiona todo al
home (síntoma: INSPECT_URL responde NEUTRAL "Google no reconoce esta URL" en las
subpaginas mientras el home sale PASS). Corregir en las 3 capas a la vez:

1. **Build**: `scripts/prerender-routes.mjs` (existe en ambos repos, testeado con
   tests/prerenderRoutes.test.mjs) genera `dist/<ruta>/index.html` con
   canonical/og:url/title/description desde `src/utils/seoMeta.js` (ROUTE_SEO) y
   rutas desde `public/sitemap.xml`. Va al final del `npm run build`.
   Fuente unica: sitemap + seoMeta; no duplicar textos.
   Cuando se anada una ruta al sitemap, ROUTE_SEO DEBE tener su entrada o el
   contrato seoGeo.test.mjs falla (y la pagina sale con title de home).
2. **nginx**: en el bloque de rutas conocidas usar `try_files $uri $uri/index.html /index.html;`
   — JAMAS `$uri/` a secas: nginx emite el 301 de slash con `Location` en el esquema
   del ORIGEN (http detras de Cloudflare Flexible) y encadena un segundo 301 por XFP;
   Google acaba indexando `http://.../ruta/` (variante fuera del sitemap).
3. **Host canonico**: 301 `www -> apex` y 301 `X-Forwarded-Proto http -> https` al inicio
   del server block. Criterio anti-bucle: los healthchecks directos al origen llegan SIN
   cabecera XFP → la condicion `= "http"` es falsa → no redirigen. Verificar SIEMPRE con
   `docker run --rm -v nginx.conf:/etc/nginx/conf.d/default.conf:ro nginx:alpine nginx -t`
   antes de commitear.

## Verificacion post-deploy (las 22 URLs deben dar OK)
Por cada URL del sitemap: `curl -s -o p.html -w '%{http_code} %{num_redirects}\n' URL`
debe imprimir `200 0` y el canonical del HTML debe ser EXACTAMENTE esa URL
(sin slash final, https, apex). Despues: reenviar `GOOGLE_SEARCH_CONSOLE_SUBMIT_SITEMAP`
p por API (pide re-proceso) + ping IndexNow por dominio
(`api.indexnow.org/indexnow`, HTTP 200 = aceptado; clave = public/<32hex>.txt de cada sitio).

## Notas operativas
- La cuenta Composio `Captain-NeuralSearch` es siteOwner de ambas propiedades GSC.
  El navegador cloud (captain@) sale "not-verified" en Search Console → no hay
  request-indexing por browser; no existe API de "solicitar indexacion": se
  re-somete el sitemap y se espera re-proceso (horas-dias).
- **Worktrees de build (bucle 09-nov):** NUNCA `ln -sfn REPO/node_modules WT/node_modules` a ciegas — puede producir self-loop (`node_modules -> sí mismo`) y corromper el repo principal; los builds mueren en SILENCIO exit 216. Verificar `readlink node_modules` tras cada ln; ante build sospechoso `npm ci` limpio (~40 s, 132 pkgs); todo pipeline de build con `set -o pipefail` — `npm run build 2>&1 | tail -N` traga el fallo y deja dist viejo (auditorías sobre dist stale dan falsos rojos).
- **qa_landing fuentes:** `--project-dir` lee `dist/index.html` LOCAL (stale si no rebuild); la verdad en producción es `--url`; pasar SIEMPRE `--brand` correcto (el default golden-game contamina el check L08 de paradise). Bloque legal estatico en HTML (consent +18 T&C redes, hidden section via prerender) es lo que hace pasar L05/L06/L14/L18 sin JS — no sustituye el checkbox funcional del modal.
- `google_search_console_motley-velvet` es cuenta de OTRO cliente — jamas usarla.
- `postbuild.mjs` (eventos) y `prerender.mjs` (paradise) corren ANTES en el build;
  desde 10-nov prerender-routes INYECTA el shell en las páginas dedicadas que
  tienen entrada en ROUTE_SHELL (conserva su `<head>`, añade body dentro de
  `#root`; guard anti-doble-inyección) — ver `numeros-contacto-canoncios.md` §
  CTA. Rutas dedicadas SIN entrada en ROUTE_SHELL siguen preservándose intactas.
- Deploy canónico de estos landings: Coolify API POST `deploy?uuid=` (golden
  `dmkvyhsn4okm2xnsvvsl0fko`, paradise `vqskmdscj1xnviiglrpkqjfy`); token en
  Vaultwarden "Coolify - MCP API token"; status del deployment se lee en
  GET `deployments/<uuid>` (`finished`/`exited` = ok).
- git: el filtro deny `*git push*-f*` revienta si el mensaje del commit va DESPUES
  del push en la misma cadena o menciona `X-Forwarded`. Poner el commit -F heredoc
  ANTES del `git push` y escribir "cabecera XFP" en el body.
