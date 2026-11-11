---
name: portal-reels-ops
description: Operación y deploy del portal de producción de reels
---

# Portal de Producción — reels.neuralcrewlabs.com

## Estado (13-oct-2026)
- La RAÍZ ya no es redirect - sirve el LIBRO DE PRODUCCION completo (~408 KB, titulo "Portal de Produccion · NeuralCrew Labs", 100 secciones, 4 campanas, 1 tablero por cliente).
- /campanas/ sigue canonico para campanas (portal_sync.py). /v2/ es legacy (deep links de reels viejos, backup index.html.bak-reel3) - no editar.
- El libro se genera en el repo m-c-g desde fragmentos rescatados del v2 (herramientas de rescate y generador versionadas en el repo, con tests pytest).

## Como se arma el libro — DOS FUENTES (clave del diseno)
El v2 se congelo el 22-sep-2026, asi que NO tiene campanas posteriores. Por eso el generador lee dos fuentes:
1. **Campanas historicas (ago, sep)** -> fragmentos RESCATADOS del v2, insertados tal cual (fidelidad byte a byte, 90/90 verificados).
2. **Campanas nuevas (oct-2026 en adelante)** -> GENERADAS desde el arbol `assets/campanas/<periodo>-<slug>/` (ramas 00-contrato .. 05-metricas). Funciones `campanas_del_arbol()` + `ramas_del_arbol()`.

Reglas de la campana del arbol:
- El nombre visible sale de `planning/<carpeta>/campaign.yaml` y es **POR MARCA** (`nombre_publico`): Golden "El Sorteo del Terror", Lucky "La Noche Encantada de la Suerte". Helper `_nombre_marca(carpeta, cli)`.
- Una campana puede ser COMPARTIDA por 2 marcas: se genera una seccion por cliente y el **id lleva el prefijo del cliente** (`golden-2026-10-halloween-03-piezas`). Sin el prefijo, el test de ids unicos falla (12 duplicados).
- Al agregar una campana al arbol, se refleja sola en el libro en <=30 min (cron). No hay que tocar el generador.

## Assets de reels nuevos — entrega inmediata (14-oct-2026)
- Indice aditivo `portal/reels/<cliente>/<carpeta-campana>.json` + fragmentos `portal/libro/<cliente>/<campana>/r1-*.html`. Helpers `reels_del_arbol()` / `_fragmento_reel()` en `scripts/build_portal_libro.py`; pruebas aisladas `tests/test_portal_reel_assets.py`.
- NO registrar una campana nueva compartida en `manifest.campanas`: `campanas_del_arbol()` la excluiria para AMBAS marcas y perderia las ramas vivas de octubre. El indice nuevo es independiente por cliente.
- Jonathan autorizo la subida de CADA asset del reel a reels al terminar su generacion/edicion, antes de continuar la produccion. Es un paso obligatorio de entrega, NO un nuevo cron ni un watcher automatico del filesystem.
- Upload por `_to_portal()` de `planning/calendario-oct2026/publish.py`, namespace `2026-10-halloween/golden/reel-01`; versiones nuevas, conservar anteriores. Verificar GET + SHA-256 completo para PNG/MP3/WAV/TXT/MP4; HTML puede recibir inyección de infraestructura y debe verificarse por contenido y assets.
- Clips MP4 de animación (verificado 14-oct, 3/3 sha match): scp directo a PROD `/opt/reels/assets/<namespace>/<sha8>-<NOMBRE>_CLIP_V01.mp4` + registrar la etapa en `portal/reels/<cliente>/<campana>.json` (clave `etapas.animacion`) + fragmento `portal/libro/<cliente>/<campana>/r1-animacion.html` (y `r1-estado.html` para el estado real de producción) + regenerar libro con ambas suites pytest + deploy con `.sync_all.lock`, backup fuera de webroot y sustitución atómica. Verificación final: GET con UA de navegador y sha256 de los bytes descargados == sha256 del clip local.
- Actualizar fichas y catalogo; ejecutar ambas suites del portal; regenerar el libro. Deploy inmediato con `.sync_all.lock`, backup de index FUERA de webroot y sustitucion atomica. El cron existente vuelve a generar las mismas fuentes, sin editarlo.
- Root conserva SSO. Un GET 200 que acaba en auth NO prueba el libro; comprobar URL final y titulo. Verificar origen `reels-web` y hash local/remoto. El browser sobre el mismo HTML local prueba render y media, NO el flujo externo autenticado.
- Verificación de DOS canales (verificada 14-oct): el GET EXTERNO a la raíz devuelve solo el shell de SSO (~5,7 KB SIN marcadores del libro — parece roto pero no lo está), mientras que los assets directos (PNG/MP4/MP3 bajo /assets/) SÍ son públicos y se verifican por GET + sha256 completo. La comprobación canónica del libro servido es INTERNA: `ssh root@100.73.30.29 'docker exec reels-web wget -qO- http://127.0.0.1/ | sha256sum'` debe == `sha256sum assets/portal/index.html` (libro completo ~464 KB); grep de marcadores (ids de sección, hashes sha8 de assets) sobre esa salida interna confirma la versión servida.
- Algunos GET con User-Agent generico reciben 403; repetir solo la lectura con UA de navegador. `resize_page` puede no cambiar `innerWidth`; verificar metricas y usar `emulate(viewport=...)` si hace falta. Browser Use con data URL del libro completo puede romper IPC (`BrokenPipeError`); preferir documento mini o Chrome DevTools. Los `pageId` pueden reordenarse: comprobar titulo/URL antes de operar.
- No subir spend gates, secretos ni audit logs privados. Subir assets NO aprueba imagen/voz ni autoriza animacion, redes, pauta, commit o push.
- Runbook versionado: `portal/reels/README.md`. Reel inicial: `/#golden-2026-10-halloween-r1`.

## Deploy automatico (NO deployar a mano sin verificar antes)
- Tras merge a main de m-c-g, el cron del sistema /etc/cron.d/reels-sync-all ejecuta scripts/sync_all.sh cada 30 min - regenera assets/portal/index.html y lo sube a PROD /opt/reels/index.html.
- ANTES de deploy manual - revisar /var/log/reels-sync-all.log (linea "[sync_all] libro: N lineas de salida" + "fin OK") y comprobar el HTTP en PROD. Lo mas probable es que el cron ya lo hizo.
- El deploy usa el redirect versionado como fallback si el libro no existe.
- El cron corre como root - vigilar archivos root:root en el repo (normalizar chown hermes:hermes).

## Verificacion de superficie (patron probado)
1. curl interno en el contenedor reels-web (docker exec) - HTTP 200 + bytes + <title>.
2. Contar marcadores con "grep -o '<pat>' archivo | wc -l" - NUNCA grep -c (cuenta LINEAS, en HTML minificado devuelve 1 y da conteos falsos).
3. Comparar PROD vs build local patron por patron (mismos contadores = misma version servida).
4. Render headless desktop 1440 + movil 390 y prueba funcional del JS (buscador/filtros) sobre la version final.
5. **Si Chrome headless del host NO arranca** (timeout incluso con un HTML de 97 bytes; error `Failed to send GetTerminationStatus message to zygote`) -> via alternativa VERIFICADA: `browser_exec` + `data:text/html;base64,<html>` (**`file://` NO carga** en ese navegador) y medir con `js()` / `cdp('Emulation.setDeviceMetricsOverride', width=..., height=..., mobile=True)`.
   - Si `browser_exec` falla con `Failed to write to the client cache`: hay archivos de OTRO dueno en `~/.cache/uv` (uv corrio como root en el home de hermes; se vieron 7.644) -> `ssh root@147.93.3.250 'chown -R hermes:hermes /opt/hermes-agent-data/home/.cache/uv'`.
   - NUNCA `pkill -f chrome-for-testing`: el patron coincide con la propia linea de comandos del shell y **se auto-mata** (SIGKILL). Usar el truco del corchete: `pkill -f "[c]hrome-for-testing"`.
   - Para renderizar rapido, extraer un **HTML mini** (sidebar + 1-2 secciones): el libro completo (100 secciones y 100+ imagenes apuntando a PROD) cuelga el render.
   - Medir es la evidencia: p.ej. `document.querySelector('.md-table table').getBoundingClientRect().width` contra el ancho del `.content`.

## Protocolo push concurrente en main de m-c-g
El repo tiene varios escritores autonomos (crons del pipeline + sesiones). Si el push es rechazado (non-fast-forward):
1. git fetch - git log HEAD..origin/main --oneline para ver el commit ajeno.
2. git show --stat del commit ajeno - verificar que NO solape archivos con los propios.
3. git pull --no-rebase (merge limpio) - NUNCA rebase ni push --force.
4. push y verificar - hash local == ls-remote - y que el cambio del commit ajeno sobrevivio (grep de su contenido).

## Pitfalls del generador
- <link> a Google Fonts cuelga el render headless sin red - bloquear fuentes o usar timeout al capturar.
- Los assets referencian reels.neuralcrewlabs.com/assets/... - verificar existencias (274/275 resuelven; el faltante es typo del v2 original).
- IDs de seccion - los fragmentos ya traen su propio <div class="section" id=...>, no envolver en otro igual (IDs duplicados rompen anclas del menu).
- **Estructura de tabla**: el CSS del v2 espera `<div class="md-table"><table>`. Emitir `<table class="md-table">` NO rompe el color pero SI el ancho: la tabla queda en su ancho natural (515 px de 1023) y se ve un hueco negro a la derecha. Sintoma visual tipico de esta clase de error.
- **Alineacion de encabezados numericos**: `.md-table th{text-align:left}` gana por especificidad a `.num` -> hace falta `.md-table th.num{text-align:right}` (el th queda a la izquierda de sus valores).
- **El tablero es UNA vista por cliente**, no una copia por campana: generarlo dentro del bucle de campanas producia 4 tableros identicos (260 filas repetidas, +31 KB).
- **META: grep/leer el HTML NO sustituye medir el render.** Los dos defectos mas caros (tablero x4, tabla a la mitad) salieron de MEDIR, no de leer el codigo.
