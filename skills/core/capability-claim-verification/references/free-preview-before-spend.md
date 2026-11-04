# Preview gratis antes de pagar (caso marketing-campaign-generator, 11-sep-2026)

Regla de la casa: ningún clip pago sin haber mirado antes algo gratis. Aquí las dos piezas que lo hicieron posible.

## 1. Draft 3D «rústico» por escena (three.js) — coste $0

`scripts/draft_renderer.py` construye un **animatic 3D** por escena (objetos box/sphere/plane, cámara con zoom/pan/rotate, fondo HEX, fps y duración) sin npm ni puppeteer: captura frames con **chromium headless** y los ensambla con ffmpeg. Su `keyframe.jpg` (t≈1 s) alimenta además al refiner como imagen base.

**El bloqueo real no es el renderer, es el binario.** El `chromium-browser` del sistema puede ser un **snap** (`2:1snap1-0ubuntu2`): `--version` responde y da hasta el número de versión, pero **no produce screenshots headless** (`chromium no creó el screenshot esperado`). No concluyas «el renderer three.js no funciona»: es el binario.

**Arreglo verificado** — Chrome for Testing, sin tocar el sistema:

```bash
mkdir -p /opt/chrome-for-testing && cd /opt/chrome-for-testing
# PITFALL: filtrar por plataforma. downloads.chrome[0] puede ser linux-arm64
# y en un host x86 tumba con 'cannot execute binary file: Exec format error'.
URL=$(curl -s https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin);\
print([x["url"] for x in d["channels"]["Stable"]["downloads"]["chrome"] if x["platform"]=="linux64"][0])')
curl -sL -o chrome.zip "$URL" && unzip -q chrome.zip
chmod +x /opt/chrome-for-testing/chrome-linux64/chrome
```

Cableado: `CHROMIUM_BIN=/opt/chrome-for-testing/chrome-linux64/chrome` en el `.env` del repo (documentado vacío en `.env.example`, se autodetecta si está vacío).

Prueba que cierra el punto (y evidencia para el usuario): renderiza un plan de escena a 360x640/12 fps y verifica con `ffprobe`: `h264`, 360x640, 36 frames, 3,00 s → **coste $0**.

## 2. Medir la locución antes de locutarla

Sintetizar el texto tal cual y medir con `ffprobe` convierte «el guión suena bien» en «el guión cabe»:

```python
import asyncio, edge_tts, subprocess
tmp = "/tmp/escena.mp3"
asyncio.run(edge_tts.Communicate(texto, "es-CO-GonzaloNeural", rate="+0%").save(tmp))
dur = float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
    "-of","default=noprint_wrappers=1:nokey=1", tmp], capture_output=True, text=True).stdout)
```

Notas de uso:
- La voz de medición es una referencia (`es-CO-GonzaloNeural`), no la voz de marca: sirve para detectar guiones que no caben, que es el error caro.
- Si `edge-tts` no está disponible, el chequeo se **omite con aviso** y el resto del lint sigue: no conviertas un problema de red/paquete en un falso bloqueo.
- En tests, simula `edge_tts` y `ffprobe` (monkeypatch) para que la suite sea hermética y no dependa de internet.
- Umbrales probados: exceso > 0,75 s por escena = error; exceso menor = aviso con el % de aceleración que lo arreglaría; uso < 55 % de la ventana = aviso de aire muerto.

## 3. Por qué importa (caso real)

Aplicado a los guiones del fin de semana detectó que **G2 Tunja** declaraba 60 s y su narración medía **105,2 s** (escena 3: 56,1 s dentro de una ventana de 26 s) y que **L1 Chiquinquirá** declaraba 38 s midiendo 40,0 s. Eso convierte una discusión de opiniones («¿recortamos?») en una decisión con números: o se aplica el recorte documentado en las notas del propio guión, o la pieza es de ~105 s.
