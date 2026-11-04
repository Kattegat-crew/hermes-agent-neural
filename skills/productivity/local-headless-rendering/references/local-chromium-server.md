# Chromium no-snap en un servidor (para renders por script)

Caso trabajado: 11-sep-2026, host DEV del stack de NeuralCrew. El pipeline de reels tiene una capa «draft
rústico» que renderiza un animatic 3D (three.js dentro de `draft_renderer.html`) capturando **un screenshot por
frame** con la CLI de Chromium y ensamblando con ffmpeg. Estaba desactivada de facto: el chromium del sistema
era el stub del snap de Ubuntu.

## Diagnóstico en dos comandos

```bash
command -v chromium chromium-browser     # el del PATH
ls -la /usr/bin/chromium-browser         # ~2 KB = stub de snap
chromium-browser --version               # puede responder y AUN ASÍ no servir
```

La prueba que decide es **un screenshot real** desde una sesión no interactiva (ssh/systemd), no `--version`.

## Instalación (Chrome for Testing: sin snap, sin tocar el sistema)

```bash
mkdir -p /opt/chrome-for-testing && cd /opt/chrome-for-testing
URL=$(curl -s https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print([x['url'] for x in d['channels']['Stable']['downloads']['chrome'] if x['platform']=='linux64'][0])")
curl -sL -o chrome.zip "$URL" && unzip -q chrome.zip && rm chrome.zip
BIN=/opt/chrome-for-testing/chrome-linux64/chrome
chmod +x "$BIN" && "$BIN" --version   # Chrome for Testing 153.0.8010.36
```

**Trampa real (la sufrí):** la lista `downloads.chrome` **no está ordenada por plataforma**; tomar el primer
elemento bajó `linux-arm64` y falló con `cannot execute binary file: Exec format error`. **Filtra siempre por
`platform == 'linux64'`** en hosts amd64.

## Verificación (PNG real)

```bash
D=$(mktemp -d); cp draft_renderer.html $D/x.html
timeout 90 "$BIN" --headless=new --disable-gpu --no-sandbox \
  --screenshot=$D/frame.png --window-size=360,640 "file://$D/x.html"
file $D/frame.png     # PNG image data, 360 x 640  ← evidencia
```

`file://` funciona aquí (es local); en el harness remoto se bloquea y hay que usar data-URLs.

## Cableado

```bash
# .env del proyecto (gitignored)
CHROMIUM_BIN=/opt/chrome-for-testing/chrome-linux64/chrome
# .env.example (trackeado, para que sea autodetectable)
CHROMIUM_BIN=
```

El renderer busca `CHROMIUM_BIN` → PATH (`chromium-browser`, `chromium`) → fallback. Añadirlo al `.env` que el
servicio carga (`EnvironmentFile` del unit) evita el clásico «funciona por CLI pero no desde el service».

## Resultado medido

Animatic three.js real: **36 frames, 360×640, h264, 3,00 s, ~2 min 20 s, costo $0** + `keyframe.jpg`
reutilizable como imagen base de la etapa siguiente. Sirve para validar encuadre y ritmo antes de pagar clips.
