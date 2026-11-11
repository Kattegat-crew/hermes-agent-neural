---
name: reel-portal-protocol
description: "Use when producing campaign reel pieces for NC portal."
tags: [reels, portal, campanas, guiones, seedance, publicacion, qa, neuralcrew]
---

# Protocolo de Reel — Portal NC Reels (ESTRICTO)

## Qué es
Cada reel de campaña (Golden Game / Lucky Brothers) se llena pieza por pieza en un orden fijo y se publica en el portal canónico **https://reels.neuralcrewlabs.com/v2/**.

**Jerarquía del portal:** Cliente (Golden/Lucky, en el sidebar) → 📅 Campañas («Septiembre — Bingo Millonario…», «Agosto — Pilotos…») → 🎬 Reels (numerados por campaña: Reel 1, Reel 2…). No hay tabs superiores; todo nace del menú lateral.

**Seguridad:** el portal está detrás de SSO Pocket ID (oauth2-proxy-universal → auth.neuralcrewlabs.com). Los usuarios entran con login; para verificar despliegues cuando el browser público redirige a login, comparar `md5sum /opt/reels/v2/index.html` (origen) contra la build local — el HTML es un solo archivo generado.

**⚠ 08/09 — El SSO amuralló TODOS los assets:** cualquier `https://reels.neuralcrewlabs.com/<path>` (keyframes .png incluidos) responde 302→auth. Los pipelines que pasan URLs públicas del portal como `first_frame` a Seedance/Monid (BASE de `run_pacho.py`) quedan rotos. Verificar `curl -s -o /dev/null -w '%{http_code}' URL` ANTES de lanzar un lote pagado; si da 302, subir las imágenes por otra vía (o pedir a Jonathan excepción de rutas de media en el oauth2-proxy — NO tocarlo sin orden suya).

## Estructura de datos (prod, root@100.73.30.29)
```
/opt/reels/
  v2/index.html                      ← portal canónico (generado, no editar a mano)
  golden/campañas/<slug>/
    campaña.json                      ← nombre, mes, periodo, premio, mecanica, retention, sedes, eventos, notas, docs_shared
    guiones/                          ← md de la serie (G1, G2…)
    reels/<slug-reel>/
      reel.json                       ← {"nombre": "Reel 1 — …", "guion": "...", "master": "...", "notas": {sección: texto}}
                                        (guion/master aceptan nombre relativo O ruta; se resuelven con resolve())
      guion-detallado.md              ← pieza 1
      prompts-seedance.md             ← pieza 2
      hero.png + hero-reference.png   ← pieza 3
      escenas/ (o scene-*.png)        ← pieza 4
      clips/*.mp4 (Seedance)          ← pieza 5
      clips/*-vozlimpia.mp4           ← pieza 6
      voz/*.wav + voz-limpia/         ← pieza 7
      assets/ overlays/               ← pieza 8
      documentos/                     ← pieza 9
      estado.json                     ← pieza 10 (schema: piezas{s,f,fecha,nota})
      final.mp4 o *-final.mp4         ← pieza 11
  lucky/campañas/<slug>/ …            ← idem
  campanas/sep2026/                   ← docs COMPARTIDOS entre clientes (plan/, investigación)
  _archive/                           ← páginas viejas (NO tocar)
```
**Descubrimiento automático:** el generador escanea `<cliente>/campañas/*/campaña.json` y `reels/*/` — crear la carpeta + JSONs basta para que aparezca en el menú. No se edita el generador por campaña nueva.

## Llenado de secciones de campaña (v4.1)
- `campaña.json`: `notas` por sección (plan/guiones/copys/eventos/historias/legal/prompts). `camp_sec(sec,title)` lee `<campaña>/<sec>/`: primer .md renderizado (`render_all=True` en guiones), imágenes en grid, docx/pdf como tarjetas; si vacío cae a `notas[sec]` y si no, a 'Pendiente — subir a sec/'.
- `reel.json.notas` cubre guion/master/hero/clips-voz/voz/reel-final — las piezas sin material se marcan honestamente, NUNCA se inventan.
- Una sección con `.empty` no está rota: es contenido no producido. Contar secciones 'vacías' exigiendo md-h1/class="ic"/<video> etc., no `class="empty"`.

## QA de layout sin atravesar el login
- `/snap/bin/chromium --headless=new --no-sandbox --disable-gpu --virtual-time-budget=6000 --window-size=W,H --dump-dom URL` — el snap NO lee `file:///root/...` (sandbox): servir la build con `python3 -m http.server 8931 --bind 127.0.0.1` y medir ahí.
- Medidor temporal: banner `<div id=qa>` con setTimeout que reporta `DOC sw/cw`, `SB sw/cw` y elementos con scrollWidth>clientWidth; leer del dump con `grep -oE '<div id="qa"[^>]*>[^<]*</div>'`.
- Sidebar fijo sin scroll lateral: `#sidebar{overflow-x:hidden}` + etiquetas flexibles con `min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis` (los botones .sp sin min-width:0 empujaban el sidebar a 615px).

## Campaña nueva (pasos)
1. `mkdir -p /opt/reels/<cliente>/campañas/<año-mm-nombre>/reels/ /…/guiones/`
2. `campaña.json` (copiar de una existente y editar mes/nombre/periodo/eventos/notas; `docs_shared` opcional).
3. Regenerar portal (abajo). La campaña aparece en el menú con sus 8 secciones.

## Reel nuevo (pasos)
1. `mkdir /…/reels/reel<N>-<slug>/` + `reel.json` + `estado.json` inicial (todo pending).
2. Llenar las 11 piezas EN ORDEN (abajo). Tras CADA pieza: actualizar estado.json y regenerar el portal.

## Las 11 piezas, EN ORDEN (no saltar)
1. **Guion** — `guion-detallado.md` (cinematográfico: diálogo LITERAL del DOCX aprobado, tabla escena|visual|narración). La narración oficial del DOCX manda; cualquier corrección de Jonathan/Chucho es LITERAL y reemplaza la anterior. Medir duración de locución con faster-whisper, no estimar.
2. **Master prompt** — `prompts-seedance.md` o integrado en el guion: lenguaje visual, bloque CHARACTER (continuidad), NEGATIVOS (sin texto/números/logos inventados — se añaden en post).
3. **Hero** — `hero.png` + `hero-reference.png` (personaje aprobado + referencia de recorrido). QA visual con vision_analyze ANTES de usarlo.
4. **Escenas** — keyframes `scene-N.png` (composición BLOQUEADA: Seedance anima, no rediseña). Escena partida = un keyframe con varias cámaras. QA visual por keyframe.
5. **Clips Seedance** — `clips/*.mp4`, `generate_audio:true` + DIALOGUE reforzado ("AUDIO REQUIREMENT (MANDATORY)… un video mudo es REJECTED"). REGLAS: (a) gate de pago firmado por Jonathan por lote ANTES de submit; (b) guarda anti-duplicado: listar runs Monid, no relanzar en paralelo (1 submit = 1 pago); (c) tras COMPLETED, STT con faster-whisper: no transcribe el diálogo → toma muda, NO publicar; (d) prompt completo mostrado antes del primer lanzamiento de cada lote. Nombre ÚNICO por run (nunca sobrescribir tomas).
6. **Clips con voz** — `fit_voice.py` (atempo uniforme, TTS ElevenLabs). Criterio: mean ≤0.3s y worst ≤0.5s = OK; peor = re-medir TTS y ajustar duración del clip (~+1s margen). NO fal sync-lipsync (rechazado por Jonathan).
7. **Voz** — WAVs ElevenLabs por escena en `voz/` + fit en `voz-limpia/`. Voces: Goldie='Kate' (qWWAqFomnJ99VwQLREfT), Lucky='Voz_Lucky' (U9tZtg3uJtVgXPkvosWR), empleada='Angie' (YPh7OporwNAJ28F5IQrm).
8. **Assets/Overlays** — cartelas, logos, cifras, balota 53, contador en `assets/`. Texto/cifras NUNCA quemados en el render.
9. **Documentos** — DOCX/md de producción (reportes, guiones fuente) en `documentos/`.
10. **Estado** — `estado.json` al día (piezas con s: done|in_progress|pending|n/a).
11. **Reel final** — solo tras aprobación (gate de Jonathan). Montaje CapCut: voz de marca + overlays + música. Subir `final.mp4`, marcar done.

## Publicación al portal (cada pieza / campaña / reel)
```bash
cd /root/hermes-agent-legacy-docker/data/workspace && python3 gen-portal-spa.py
scp -q nc-portal-dev/index.html root@100.73.30.29:/opt/reels/v2/index.html
```
Verificación antes de reportar "publicado": (1) todos los `go('…')` del html apuntan a un id existente (python); (2) HEAD 200 de los media URLs (si hay login SSO, verificar desde origen vía ssh); (3) navegador/móvil 390px sin overflow — si el browser público redirige a login, servir la build en localhost y verificar estructura; (4) videos con voz: descargar del CDN y transcribir (no confiar en hash local).

## Pitfalls conocidos (lecciones pagadas con dólares)
- **Cloudflare cachea por URL** (max-age 14400): reemplazar un archivo con el mismo nombre sigue sirviendo el viejo. El generador añade `?v=<mtime>` a todos los media. Tokens CF del Vaultwarden NO tienen permiso Cache Purge.
- **Monid/Seedance**: body `input.content` (text + image_url first_frame), respuesta `runId` camelCase, costo en `cost.value`, video en `output.content.video_url`. Recuperar runs COMPLETED por ID antes de re-submit.
- **Sobrescritura de tomas**: nunca descargar dos runs al mismo nombre (S1 de Pacho: 3 generaciones pagadas, una muda recuperada del TOS). Nombre único por run.
- **Guion maestro vs DOCX**: el DOCX aprobado (Informe Final de Guiones) es la única autoridad de locución.
- **Fuente literal + lotes paralelos (19-oct-2026, reels 22-oct)**: Bob puede dejar en PROD un acta literal palabra-por-palabra del texto aprobado (`/opt/data/workspace/reels/<campana>/GUIONES-V2-APROBADOS-LITERAL.md`) y OTRO agente/proceso ya pudo haber generado lotes de prompts en el repo DEV desde ese literal. Antes de regenerar guiones/prompts: (1) escanear el repo por lotes existentes del mismo reel (`reel2-*-v*` en `assets/campanas/<cliente>/02-guiones/`, comparar mtimes contra la ventana de la sesión); (2) leer el acta literal en PROD y sus DELTAS (correcciones del literal vs handoff); (3) los ajustes posteriores del Admin en chat (p. ej. duración 20 s, «boleta diaria» vs «del día») PREVALECEN sobre el acta y se registran en el spec como decisión de producción; (4) los lotes duplicados/conflictivos se ARCHIVAN como procedencia (nunca borrar), y se anota en el spec cuál versión se produce para que el pipeline no tome la equivocada.
- **Rutas**: scripts corren en el HOST — rutas `/root/hermes-agent-legacy-docker/data/...`, nunca `/opt/data/...` (espejo muerto). Prod vía `ssh root@100.73.30.29`.
- **SSO Pocket ID en reels**: instalado por otro agente (Gemini); NO quitar el login sin orden de Jonathan. El portal es el MISMO con o sin login.
