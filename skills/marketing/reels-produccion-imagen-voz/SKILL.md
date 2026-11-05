---
name: reels-produccion-imagen-voz
description: Produce reels con voz natural y gasto controlado.
version: 1.5.0
category: marketing
tags: [reels, fal, monid, seedance, elevenlabs, spend-gate, produccion, animacion, montaje, ffmpeg, golden, lucky]
---

# Producción imagen + voz de reels (piloto verificado)

Procedimiento verificado E2E el 13-oct-2026 (Golden Reel 1 «El susto es quedarte en casa»): una imagen GPT Image 2 vía fal con referencias y una toma ElevenLabs, sin reintentos, con evidencia de costo en audit sidecars. Fuente de verdad del lote: `assets/campanas/<campana>/02-guiones/<lote>/lote-preparado.json` en el repo m-c-g (DEV /opt/marketing-campaign-generator).

## Cadena obligatoria
1. `lote-preparado.json` debe existir con referencias verificadas en disco. Nunca improvisar el prompt fuera del lote aprobado.
2. El gate de gasto requiere autorización explícita del HUMANO en el chat (ej. «Autorizado, procede» / «Dale»); el agente JAMÁS se auto-autoriza sin esa orden. Al recibir la confirmación del Admin en el chat, el agente registra la autorización sin pedirle abrir terminal: `python3 scripts/spend_gate.py --authorize --by "Jonathan (Admin, autorizado en chat)" --purpose "<lote y estimado>" --providers fal,elevenlabs --hours 2`. Validar antes de submit: `python3 scripts/spend_gate.py --status` → ok true + expires_at vigente.
3. Cargar credenciales solo al momento del submit: FAL_KEY desde el `.env` del repo si no está en env; ElevenLabs vía `elevenlabs_client._load_key()`.
4. Un solo submit por proveedor. Antes de llamar: afirmar que los archivos de salida NO existen (`assert not out.exists()`), escribir audit `submitting`; después actualizar a `generated_unreviewed` o `failed_no_retry`. Jamás reintentar automáticamente.

## Internals del cliente que se usan deliberadamente
- `fal_image_client._run(model, payload, out, editing=True)` devuelve `(path, request_id, provider_url)`: captura request_id y URL que la CLI no expone. Payload con `build_payload("gpt-image-2", prompt, "720x1280", "medium", 1, "png", images=[...])`; referencias locales via `_as_image_input` (data URI).
- `elevenlabs_client._tts_raw(key, voice_id, texto, speed=1.0)` devuelve `(status, bytes)` con el gate como choke point dentro; WAV con `_to_wav(data, wav)`; duración con `probe_duration(wav)`.
- Output canónico: `output_layout.scene_output_dir(reel, escena, version)` → `assets/<reel>/sNN/vN/{frames,audio,audit}` + `ensure_dirs`.
- ElevenLabs responde 401 si se envían `xi-api-key` Y `authorization` juntos: enviar solo xi-api-key.

## Verificación sin gastar de más
- PNG: reabrir con PIL y afirmar dimensiones exactas. Audio: `ffprobe` + `ffmpeg -f null -` (decodifica sin errores). `git diff --check` para whitespace.
- QA visual con `vision_analyze` sobre el PNG real; si el slot de visión falla, NO inventar veredicto: declarar QA pendiente o evidencia alternativa.
- Reportar el encuadre tal cual: gpt-image-2 edit puede ignorar "medium close-up" y devolver cuerpo completo. Sin reintentos: escalar al humano.
- El cobro final de fal NO viene en la respuesta del cliente: nunca citar la estimación base del repo como cargo real.

## Animación (Monid Seedance 2.0 Mini — verificada 14-oct-2026)
- El gate es POR PROVEEDOR: abrir `fal` NO autoriza `monid`. Cuando el Admin autorice en el chat («Autorizado, procede»), registrar `monid` con `python3 scripts/spend_gate.py --authorize --by "Jonathan (Admin, autorizado en chat)" --purpose "<lote video>" --providers monid --hours 2 --merge` y validar `gate_status("monid")` antes del submit. Firma vencida/ausente = el cliente corta antes de la red (sin gasto) y se debe pedir confirmación en chat al Admin.
- Batch canónico: `scripts/batch_golden_terror_reel1.py` (patrón `batch_golden_bingo.py`): un submit por escena, sin reintentos automáticos; clip → `assets/<reel>/sN/v1/video/clip.mp4`.
- Preflight del keyframe: GET + User-Agent de navegador (HEAD sin UA = 403 de Cloudflare → falso negativo que aborta el lote).
- Diagnóstico de rechazo del proveedor (verificado con S3): el run puede quedar `status=COMPLETED` con `output` VACÍO, `video_url=None` y `billedUnits=0` — NO reenviar ni asumir fallo de red: leer `providerResponse.error` del run (GET /v1/runs/<id> con Authorization Bearer). Caso real: ByteDance rechazó el keyframe por personas reales (`InputImageSensitiveContentDetected.PrivacyInformation`, httpStatus 400) y NO cobró ($0). Manejo: reportar al humano con opciones (regenerar keyframe sin personas reales, o escena estática con Ken Burns); jamás reintentar el mismo frame.
- Workaround VERIFICADO 14-oct (S3 V02, elección del Admin): regenerar el keyframe con personas estilo Pixar (CGI claramente caricaturesco — vampiro, bruja, gato, esqueleto) PASA el filtro de ByteDance al primer intento (run 01M4WH34KWV1VFGF5MXESMQ6ZT, $0.38115, clip 5.09 s 720×1280 aac OK). Es la vía preferida cuando la escena necesita gente; lo que dispara el rechazo son personas fotorrealistas/aún disfrazadas. Subir versiones nuevas conservando las anteriores (keyframe V02 `bcc003e3`, clip `cb9a9e3d`).
- Verificación de clips antes de subir: ffprobe (720×1280, 24 fps, duración, pista aac).

## Audio de referencia y sincronía
- Para foto + audio usar `reference_image` + `reference_audio`, no `first_frame` + `reference_audio`. El esquema publicado no expresa todas las restricciones cruzadas.
- Verificar éxito upstream y MP4 real; `COMPLETED` del wrapper puede contener HTTP400 y output null.
- Guía de alineación conservando voz1.0, límites de ASR, xfade y loudness: [referencia de audio y sincronía](references/seedance-audio-referencia-y-sincronia.md).

## Vía de imagen directa OpenAI (SUPERADA 27-oct; conservada como histórico)
- DECISIÓN ACTUALIZADA 27-oct: sin credencial OpenAI, el Admin aprobó fal; la comparativa del día fijó `gpt-image-2.5/flare/edit` vía fal como PRIMARIO para estáticos (ver sección siguiente). Esta vía directa solo se reactiva si el Admin entrega la key.
- Dirección original del Admin: los estáticos de campaña se generarían por OpenAI DIRECTO (CLI/API `images.generate` / `images.edit`) en lugar de fal, para no gastar saldo. El CLI `openai` ya está instalado en el contenedor y `images.edit` acepta `-I <imagen>` para anclar identidad con los turnarounds aprobados por marca (p. ej. `assets/sheets/golden/goldie-turnaround.png`, `lucky-master.jpg`). Mientras no exista la key, los estáticos siguen por fal (FAL - API key en Vaultwarden).
- Bloqueo verificado 27-oct: NO existe credencial OpenAI válida. La `OPENAI_API_KEY` dentro de `~/.codex/auth.json` en DEV es un placeholder (4 chars → HTTP 401 contra api.openai.com) y Vaultwarden (69 entradas revisadas) no tiene ningún ítem de OpenAI. Pendiente: el Admin crea la key en platform.openai.com → guardar en Vaultwarden («OpenAI - API key») y cablear al `.env`.
- Pitfall: Codex CLI NO genera imágenes — es agente de código (exec/review/mcp/sandbox; 0.164.0 en DEV como app-server daemon, binario bajo `~/.codex/packages/app-server-daemon/.../bin/codex`). Su sesión OAuth de ChatGPT (`tokens` en auth.json) NO habilita la API de imágenes. Antes de planear la vía GPT, validar la key con una llamada barata (test 401) en vez de asumirla.

## Estáticos de campaña vía fal — comparativa de modelos (verificada 27-oct, campaña Aguinaldo)
- Metodología: UNA pieza de prueba, mismo prompt y misma referencia de personaje (turnaround aprobado por marca), 3 endpoints de fal en paralelo; QA de identidad con vision_analyze contra el character bible. Evidencia y decisión: `planning/2026-11-aguinaldo/03-piezas/_pruebas/COMPARATIVA-MODELOS.md` del repo m-c-g.
- Resultado: `openai/gpt-image-2.5/flare/edit` (quality=high) = 8,5/10 identidad, PRIMARIO; `blackforestlabs/flux-3/edit-image` (resolution=1.5k) = 8,5/10 pero garabatea texto de marca (generó «A5GO» en vez de «A560») y desplaza detalles, RESPALDO; `alibaba/qwen-image-3/edit` = 1/10 — ignoró por completo la referencia y generó una mujer humana — DESCARTADO.
- Pitfall de content policy verificado en Flux 3: el prompt con «casino»/«slot-machine» devuelve `content_policy_violation`; describir la ESCENA («elegant festive hall») pasa sin problema. Los prompts de piezas describen la escena, nunca el negocio.
- Regla dura: CERO texto dentro de la imagen IA — ninguno de los 3 modelos renderizó texto de marca de forma fiable. Tipografía, pie legal y monogramas se montan en local con el pipeline drawtext existente.
- Regla: verificar la PRIMERA pieza de cada lote con vision_analyze contra el character bible ANTES de producir en lote; la fidelidad a la referencia varía radicalmente por modelo y el fallo puede ser total.
- Cuidado con errores de transporte del MCP fal («SSE stream ended without a response»): el job pudo quedar enviado y cobrado aunque no llegue request_id; no reintentar en automático — revisar costo/estado primero y limitar a un reintento documentado.

## Entregables de cierre
- `REVISION-*.html` autocontenida (PNG+MP3 en base64, cero llamadas externas) + `RESULTADO.md` + `audit/resultado-lote.json` con estado `generated_pending_human_review`, sha256 y `generation_submissions {fal:1, elevenlabs:1}`.
- Handover en `PROJECT_MEMORY.md` del repo (backup .bak antes del patch; solo sección nueva, nunca revertir secciones ajenas). Sin commit ni push sin autorización.
- Voz Golden fijada: Voz-Goldie `qWWAqFomnJ99VwQLREfT` (categoría professional; funcionó en tier Starter con ~12k/57.5k chars). Si la síntesis falla, PARAR y escalar, no sustituir voz ni cambiar plan.

## Montaje final (verificado 14-oct-2026, Golden Reel 1 V02)
- Código de montaje NUNCA dentro de `assets/<reel>/` (git-ignored por diseño): versionarlo en `scripts/<reel>_montaje/` del repo. Rutas: ROOT absoluto del repo + `Path(__file__).parent` para assets versionados (rótulos .txt).
- **Voz natural vs calce labial**: si el usuario exige velocidad normal, conservar `speed=1.0` y el PCM original; ajustar los tiempos del VIDEO, nunca acelerar o ralentizar la voz para ocultar asincronía. El refit `atempo>=1.0` es una receta histórica de Golden, no autorización para cambiar la velocidad en otros lotes.
- **Música ElevenLabs `/v1/music`** (endpoint ya usado en rendiciones sep-2026): exige permiso `music_generation` EN LA API KEY — sin él responde 401 missing_permissions y no cobra; el Admin lo habilita en el dashboard. Prompt descriptivo verificado: cumbia colombiana, ~106 BPM, 22 s. Sin key habilitada: montar con fallback silencioso, no sustituir por música genérica.
- **Pitfall ffmpeg crítico (2 bugs en silencio)**: (1) overlays de imagen en la MISMA filtergraph con drawtext y expresiones (`x=(W-w)/2`, `y=h*0.565`) NO se dibujan y ffmpeg no avisa → usar coordenadas FIJAS calculadas en Python; (2) overlays de imagen van en PASADA SEPARADA (paso 2b) después de los drawtext, no en la cadena combinada.
- **fade con alpha en overlays RGBA** los deja invisibles → aparecer con `enable='between(t,..)'`, sin fade alpha.
- Patrón rótulos kinetic: textos por escena en archivos .txt (s1a, s1b, …), tipografías de marca del repo `assets/fonts/` (DM Serif Display / DM Sans), entrada escalonada por drawtext con enable.
- QA de montaje antes de publicar: vision_analyze sobre frames extraídos del MP4 final (ffmpeg -ss) verificando rótulos y placa CTA visibles; ffprobe del audio final (voz + música con ducking). Receta completa de la sesión: references/montaje-golden-reel1-v02-2026-10-14.md

## Producción rápida sin bajar calidad
- Preflight único, piloto antes del lote, montaje guiado por voz, QA en dos rutas y métricas reales: [producción rápida controlada](references/produccion-rapida-controlada.md).

## Recorte de ritmo con Akari
- Flujo local sin nuevas generaciones, empaquetado de inputs, recibos, voz intacta y salida de distribución: [recorte de ritmo con Akari](references/akari-recorte-ritmo.md).

## Lotes multi-escena y multi-marca (verificado 14-oct-2026, Lucky Reel 1 «La Noche Encantada»)
- Reutilizar el MÉTODO, no el concepto creativo: misma cadena (gate humano → lote-preparado.json → 1 submit por escena → sin reintentos), pero con la identidad/estética de la marca destino. Directiva del Admin (estándar ahora, no excepción): TODAS las personas en keyframes para Seedance van 3D estilo Pixar, adultos inequívocos, sin fotorrealismo ni mezcla de estilos — lo que dispara el rechazo de ByteDance son personas realistas.
- Estructura de prompts probada: MASTER común (identity lock, paleta, exclusiones globales) + bloque por escena; SIEMPRE en inglés y con máximo detalle (identidad, encuadre, luz, referencias, exclusiones) — estándar explícito del Admin.
- Referencias congeladas por SHA-256 (máx. 3): identidad aprobada (autoridad principal), master de anatomía evergreen (solo anatomía/material) y arte de campaña (solo atmósfera) — declarar en el prompt la prioridad y qué NO copiar de cada una.
- Lote de N escenas: revalidar `gate_status` antes de CADA submit, assert de salida inexistente por escena, audit único con `expected_images`, contador de `submissions` y estado por escena; verificación final = decode PIL + dimensiones exactas + request IDs únicos == N + ZIP íntegro (`testzip`).
- QA recurrente: gpt-image-2 edit tiende a ignorar "medium shot" y devolver cuerpo completo → reportarlo tal cual sin regenerar. Escribir en el prompt que los rasgos de identidad (p. ej. el tallo marrón curvado de Lucky) son anatomía aprobada, e instruir a los revisores (vision_analyze y subagente independiente) a NO marcarlos como artefacto ni recomendar eliminarlos.
- Rasgo facial ausente en las refs de héroe (verificado 28-oct, Lucky E1 v03): los píxeles de referencia PISAN al texto — exigir en el prompt un rasgo que NO existe en las imágenes de entrada (p. ej. "CRITICAL: visible nose" en mayúsculas) es IGNORADO por gpt-image-2.5/edit, que replica la superficie plana del héroe. Vía que funciona: pasar como referencia ADICIONAL el recorte del detalle oficial del design sheet de marca (panel «Nariz» de assets/sheets/lucky/brand/lucky-design-sheet.png) y declarar en el prompt que solo ese rasgo anatómico debe tomarse de esa hoja — esto reconcilia la regla de referencias (solo anatomía/material) con el estándar oficial sin violar la exclusión del arte completo. Verificar el rasgo con vision_analyze y zoom a la región facial antes de dar por buena la imagen.
- Locación real como referencia (verificado 28-oct): fotos reales que entrega el Admin (calle/fachada del negocio) se suben a fal con upload_file (PUT binario a upload_url con Content-Type, sin Authorization) y se pasan como refs de escena; la fidelidad arquitectónica resultó alta (letrero, balcones, bolardos). Para lip-sync móvil, pedir en el prompt plano medio cintura-arriba SIN pies — el modelo obedece parcialmente (plano americano, corta en tobillos): reportarlo tal cual.
- Entregables del lote: hoja de contacto JPG + `REVISION-*.html` autocontenida con los prompts completos + ZIP (originales/prompts/audit) + handover en PROJECT_MEMORY.md con backup .bak previo. El repo puede tener cambios de sesiones/crons paralelas: tocar solo archivos nuevos, nunca revertir ni commitear trabajo ajeno.

## Ediciones sobre másteres ya entregados (verificado 26-oct-2026, Golden Tunja Terror V03)
- Cuando el Admin pide modificar una versión YA entregada (quitar subtítulos quemados, quitar logo, ajuste quirúrgico acotado), NO regenerar el reel desde cero: partir del máster entregado + la placa limpia existente (la variante sin subtítulos ya renderizada). Receta completa: [postproducción sobre máster entregado](references/postproduccion-sobre-master-entregado.md).
- Regla dura de ubicaciones: toda versión entregada al Admin (Telegram/Drive) DEBE quedar respaldada en ruta durable conocida (`/opt/data/campaigns/<campana>/corte/<version>/` + copia en repo cuando aplique) con SHA-256 registrado. JAMÁS pedirle al Admin que reenvíe un archivo que la flota produjo — buscarlo primero en el registro y en disco.
- Regla dura de herramientas: antes de declarar «herramientas no disponibles / no puedo ejecutar», ejecutar una sonda real (ls/git status/echo) y citar su salida. El Admin corrige con firmeza un falso bloqueo; «no puedo» sin evidencia de ejecución es una falla grave.
- Preservar el audio: extraer el stream AAC del máster fuente y copiarlo con `-c:a copy` (sin recodificar); demostrar integridad comparando el SHA-256 del stream extraído fuente vs. entregado. Los MP4/WAV quedan git-ignored: al repo solo van manifiestos y docs.
- Manifestar discrepancias de QA, no resolverlas en silencio: si dos informes previos contradicen un dato del material (ej. afiche físico «viernes» vs. «jueves» verificado por calendario), registrarlo en el manifiesto de entrega como pendiente de verificación antes de publicar.
- Git bajo worktree compartido: si `git add` falla por `index.lock`, diagnosticar antes de tocar (tamaño 0, antigüedad >1h, sin descriptores abiertos en /proc/*/fd) y PRESERVARLO como `.git/index.lock.backup-<ts>` en vez de borrarlo. Para no mezclar trabajo ajeno del worktree, stagear con `git add <rutas exactas>` y commitear con `git commit --only -m '...' <rutas exactas>`; nunca `git add -A`.

## Banners estáticos sobre fotos reales de sede (composición local Pillow — verificada 03-nov-2026, Aguinaldo 12 sedes + 8 generales)
- Cuando el defecto dominante es el FONDO (letreros del local borrados por el modelo, clientes/peatones reales visibles, desorden), NO regenerar con IA: componer en local con foto ORIGINAL intacta (solo encuadre/extensión) + mascota recortada como capa. La generación IA borra letreros de negocio al «recrear» la foto; la composición local los conserva garantizado.
- Selección de placa base: auditar TODAS las fotos originales del cliente por hojas de contacto con vision_analyze ANTES de elegir (descartar clientes sentados, peatones, monitores con escritorio, artículos de limpieza). Exigir al Admin la foto en horizontal 16:9 (1920×1080); una foto vertical (738×1600) pegada al borde derecho con relleno desenfocado produce una costura vertical dura que el Admin detecta de inmediato. Recortar personas con crop quirúrgico en vez de descartar la foto si el resto sirve.
- Degradado lateral SIN costuras: construir la máscara como una fila de 1px (L) con rampa suave smoothstep (`1 - (z*z*(3-2z))` entre u=0.28 y u=1.0, plateado hasta 242) y luego `resize((W,H), NEAREST)` — un degradado continuo de borde a borde reemplaza la caja rectangular (`rounded_rectangle` + blur) detrás del texto, que marca un borde vertical duro visible. Los 3 problemas del Admin (imagen mal configurada, costura, solapamiento texto/mascota) se resolvieron con: placas horizontales + degradado fila + `side` fijo en el spec por sede.
- Placa de respaldo del logo SEGÚN MARCA: logo oscuro/bordeado (Golden) va sobre placa oscura translúcida (alpha ~175, blur 10); logo de trazos finos rojo/dorado (Grand Paradise) PIERDE contraste sobre placa oscura — usar placa crema/marfil `(252,245,225)` alpha ~215. Verificar contraste del logo con vision_analyze en la hoja de contacto final; fue el único defecto residual de la v10 y la placa clara lo resolvió.
- Recorte chroma de mascota: magenta `(255,0,255)` con tolerancia por distancia + castigo extra cuando `g<120 and r>140 and b>140`, MinFilter+GaussianBlur para feather y despill (limitar r/b a g+offset en bordes). CACHear el resultado (`_CHROMA_CACHE[path]` + `.copy()` al devolver): sin caché el pipeline de 12 piezas re-cromakeyed la misma mascota en cada render.
- QA final en DOS pasos: (1) vision_analyze sobre hoja de contacto de las piezas preguntando por los defectos concretos de la sesión previa (costuras, personas, solapamientos, contraste de logo); (2) dimensiones exactas (1920×1080) con PIL al copiar a la ruta de entrega. Publicar en el portal con rsync --checksum y verificar md5 local == prod de al menos 3 archivos antes de declarar sincronizado. Entregar siempre la hoja de contacto de auditoría junto con la galería.
