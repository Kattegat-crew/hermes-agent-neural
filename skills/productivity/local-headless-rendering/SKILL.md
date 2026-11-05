---
name: local-headless-rendering
description: "Use when a script must render HTML frames headless."
tags: [chromium, headless, frames, animatic, threejs, ffmpeg, render]
version: 1.0.0
author: curator-ragnar
triggers:
  - "chromium no genera el screenshot"
  - "renderizar frames de un HTML"
  - "animatic"
  - "three.js a mp4"
  - "headless en el servidor"
  - "chrome for testing"
  - "captura por frame"
---

# Render local headless — de HTML/three.js a PNG o vídeo, sin depender del harness

Clase de tarea: el render lo dispara **un script** (no `browser_exec`) y hace falta un navegador **local**
invocable por CLI. Casos: animatic 3D de una escena antes de pagar por clips generados, thumbnails a escala,
storyboard por frames, HTML→vídeo con ffmpeg.

## 1. Elige la vía correcta

| Situación | Vía |
|---|---|
| Documento con mucho texto → PNG/PDF de imprenta, entregable puntual | harness `browser_exec` + CDP (ver skill user-owned `html-to-print-rendering`) |
| N frames por script, en bucle, dentro de un pipeline | **binario local + CLI** (esta skill) |

El harness remoto no sirve para un bucle de capturas: cada frame necesita un proceso local con acceso a los
ficheros del trabajo (`file://`), y la temporización en tu mano.

## 2. No confíes en el `chromium` del sistema

En Ubuntu reciente `/usr/bin/chromium-browser` es el **stub del snap**: responde `--version` (y `--help`) pero
**no produce screenshots headless** desde una sesión no interactiva (systemd/ssh). Síntoma: el renderer aborta
con «chromium no creó el screenshot esperado» tras varios segundos.

- La prueba que decide es **un screenshot real**, no `--version`.
- Arreglo: instalar **Chrome for Testing** y apuntarlo con `CHROMIUM_BIN`. Receta, trampa de arquitectura y
evidencia medida: `references/local-chromium-server.md`.

## 3. Convención de cableado

- Los renderers de esta casa resuelven el binario por `CHROMIUM_BIN` → PATH → fallback. **No hardcodees la ruta
  en el script**: añade `CHROMIUM_BIN` al `.env` del proyecto y déjalo vacío (autodetección) en `.env.example`.
- El binario (~150 MB) vive **fuera del repo**; nunca trackeado.
- `--no-sandbox` es obligatorio corriendo como root en VPS/contenedor.

## 4. Presupuesto: es tiempo, no dinero

Un render por frame abre **un proceso de navegador por frame**: medido ≈**3,9 s/frame** a 360×640
(36 frames ≈ 2 min 20 s). Calcula antes de prometer plazos (5 s a 24 fps = 120 frames ≈ 8 min) y baja `fps`
o resolución en los pases de revisión.

A cambio: **costo $0** y validación de encuadre/ritmo antes de gastar en un proveedor de vídeo. Es el paso
correcto en un flujo «paso a paso» donde el usuario no firma gasto hasta ver algo.

## 5. Entregables del render

- El **MP4** (o PNG) y el **keyframe** (frame t=1 s): el keyframe suele reutilizarse como imagen base de la
  etapa siguiente (refiner/upscale), así que se guarda junto al vídeo, no en `/tmp`.
- Verifica el MP4 con `ffprobe` (resolución, fps, duración, tamaño) y adjúntalo al chat antes de declarar
  entregado: «build exit 0» no prueba que el vídeo se vea bien ni que tenga las dimensiones pedidas.
- Tras verificar el MP4, borra los directorios de frames intermedios (`frames_render/`, `frames_golden/`,
  `frames_lucky/`, `qa/`): a 1080p+ son gigabytes por proyecto, 100% regenerables desde el compose/build, y
  son el mayor consumidor de disco del workspace. El entregable vive en `entrega/` o `out/` y no se toca.
- En 9:16 (1080×1920) deja libres los últimos ~330 px verticales: la UI de Instagram (caption, botones) tapa
  esa franja. El pie de marca va alrededor de y≈1586, no pegado al borde inferior.

## Fuentes web en el compose: precarga explícita, nunca confíes en `document.fonts.ready`

Síntoma real (rendición oct-2026): «la tipografía cambia a mitad del video».
Causa raíz: los `@font-face` con `data:` URI cargan **lazy al primer uso** — `document.fonts.ready`
se resuelve ANTES de que el canvas pida la primera fuente, así que los primeros frames de cada
sesión de navegador se pintan con la fallback y, cuando las fuentes terminan de activar, el resto
de frames cambia de tipografía. Si el render reabre el navegador por chunks, la carrera se repite.

Fix verificado: en el HTML del compose, en vez de `fonts.ready.then(...)`, precargar cada cara usada
y verificar con check duro:
```js
const FACES = ['400 16px "DM Sans"', '500 16px "DM Sans"', '700 16px "DM Sans"', '400 16px "DM Serif Display"'];
window.ready = (async () => {
  await Promise.all(FACES.map(f => document.fonts.load(f)));
  await document.fonts.ready;
  window.__fontsOK = FACES.every(f => document.fonts.check(f));
})();
```
y en el renderer, tras `await page.evaluate(() => window.ready)`, abortar si `window.__fontsOK !== true`
(no seguir con la fallback silenciosamente).

Corolario: si el fix cambia cómo se pintan las fuentes, **invalida TODO el caché de frames** — apartar
los directorios `frames_*` (con `mv`, ver pitfall de `rm -rf`) y re-renderizar completo; reusar frames
con la fallback contamina el video entero.

## Pitfalls

- `rm -rf` recursivo sobre rutas `/opt` está bloqueado por la regla de deny del Admin (approvals.deny).
  Para descartar cachés regenerables gigantes (frames), apartarlos con `mv` a un nombre `.bak-*` y que el
  render escriba directorio nuevo; nunca intentar burlar la regla reformulando el comando.
- Antes de correr el `build.sh` de un proyecto, mira qué variable de entorno espera su binario de navegador:
  algunos pipelines de esta casa leen `CHROME_BIN` y otros `CHROMIUM_BIN`. Exportar la equivocada hace que el
  script caiga al stub del snap o falle en silencio.
- No concluyas «el navegador no funciona» por un `--version` exitoso: mide el artefacto.
- No bajes el primer binario de una lista de descargas sin filtrar por plataforma (ver referencia).
- Presupuesta minutos por frame, no segundos: subestimar convierte un render en un timeout aparente.
- Si el render alimenta un pipeline pago, verifica el resultado **antes** de encadenar el paso que cuesta.
- Correr el mismo build varias veces (retries, segundas pasadas) deja procesos background duplicados que
  notifican después: al recibir la notificación, compara con lo ya entregado antes de re-enviar archivos —
  si es una versión superada (v1 cuando ya salió v2), responde «sin cambios» en una línea.

## Soporte

- `references/local-chromium-server.md` — instalar un Chromium no-snap en un servidor, verificarlo y cablearlo,
  con la trampa de arquitectura (`linux64` vs `arm64`) y las medidas reales.
