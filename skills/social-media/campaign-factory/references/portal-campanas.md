# Portal /campanas/ — cadena de datos, scope real y pitfalls (verificado 13-oct-2026)

## Cadena SSOT → portal

1. Fuente de verdad: `planning/*/calendario.jsonl` (auto-descubrimiento: TODO calendario.jsonl bajo planning/ es una campaña).
2. `scripts/portal_sync.py build` genera `assets/portal/campanas/<slug>/index.html` (tarjetas por fila: estado, copy truncado 220, métricas, links).
3. `--deploy` = rsync ADITIVO hacia `PROD:/opt/reels/campanas/` (sin --delete por diseño: causó pérdida real de guiones/plan el 22-sep-2026). Guardia fail-closed: si no puede listar el remoto aborta; si hay entradas que el build no genera y no son legacy (`sep2026`, `index.html`) aborta pidiendo ALLOWLIST o borrado manual.

## Scope: qué SÍ y qué NO muestra el portal

- SÍ: solo piezas del calendario de redes (slots, estados, métricas del harvest, links por fila).
- NO: entregables producidos de la carpeta de campaña (pendones, boletas, urna, registro, estáticos, banners TV en `assets/campanas/<slug>/03-piezas` y `04-aprobadas`). portal_sync.py NUNCA mira esa carpeta.
- Implicación: "no veo todo lo producido en el portal" no es un bug de sync — es el scope. Si el Admin quiere ver entregables, hay que extender portal_sync.py (código nuevo → SDD), no re-sincronizar.

## Pitfalls

- **Slug fantasma:** filas con `campaign` distinto dentro del calendario de otro mes (ej. 2 filas sep con `campaign=halloween-2026` en calendario-sep2026) crean una página de campaña aparte con poquísimo contenido. El índice la lista igual y confunde. Corrección: corregir el campo campaign en el JSONL y BORRAR la página fantasma a mano en PROD (el rsync aditivo no la elimina solo).
- **Páginas obsoletas persisten en PROD:** deploy aditivo ⇒ cualquier página vieja/renamed queda viva hasta borrado manual (con estado de fechas de build desactualizado, se ve "regenerado hoy" en el footer del índice pero la página hija no existe en el build actual).
- **Links IG/FB vacíos:** el harvest guarda views/interactions pero no las URLs de las publicaciones → posts.jsonl sin `url` → tarjetas sin enlaces IG/FB aunque la pieza esté publicada. Gap conocido; verificar en content-intel/data/posts.jsonl antes de culpar al portal.
- **Piezas sin `asset_drive_id`** (reels, carruseles) salen "sin enlaces" — solo stories/posts tienen Drive URL hoy.

## Diagnóstico en vivo (comandos probados)

- Índice y contadores: `ssh prod 'sed -e "s/<[^>]*>/ /g" /opt/reels/campanas/index.html'` → por campaña: N piezas · N publicadas · vistas.
- Tarjetas de una campaña: extraer `<div class="card".*?</div>\n</div>` con regex (0 tarjetas con patrón equivocado ≠ página vacía; el card se cierra así).
- Conteo de links: `>Drive<`, `>IG<`, `>FB<`, `sin enlaces` en el HTML.
- SSO: la raíz y /campanas/ dan 302 → auth.neuralcrewlabs.com: esperado, el índice es privado. No es fallo.
- Verificar por fila: `python3 -c` sobre calendario.jsonl contando drive_url / portal_url / asset_drive_id.
