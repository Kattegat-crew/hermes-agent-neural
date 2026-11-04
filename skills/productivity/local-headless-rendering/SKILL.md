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

## Pitfalls

- No concluyas «el navegador no funciona» por un `--version` exitoso: mide el artefacto.
- No bajes el primer binario de una lista de descargas sin filtrar por plataforma (ver referencia).
- Presupuesta minutos por frame, no segundos: subestimar convierte un render en un timeout aparente.
- Si el render alimenta un pipeline pago, verifica el resultado **antes** de encadenar el paso que cuesta.

## Soporte

- `references/local-chromium-server.md` — instalar un Chromium no-snap en un servidor, verificarlo y cablearlo,
  con la trampa de arquitectura (`linux64` vs `arm64`) y las medidas reales.
