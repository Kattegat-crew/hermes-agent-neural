---
name: guion-video-campana
description: "Use when producing campaign reels and Seedance prompts."
tags: [reels, video, seedance, guion, lip-sync, campana]
---

# Producción de reels de campaña (página de producción + prompts Seedance)

Workflow probado (Reel 2 Chiquinquirá Lucky y Reel 2 Pacho Golden, sept 2026).

## Página de producción
- Estructura espejo entre clientes: Guion por escena → Keyframes → Hero/referencia (sección PROPIA, no dentro de keyframes) → Clips Seedance → Clips con voz → Audios ElevenLabs descargables → Assets/overlays → Documentos.
- Todos los diálogos COMPLETOS + descripción visual por escena (bloques `.esc`); el usuario revisa la página para aprobar.
- QA SIEMPRE con navegador real desktop (1366px) + móvil (390px): 0 overflow de texto, 0 imágenes rotas, sin scroll horizontal, hover rules verificadas. Publicar vía scp a root@100.73.30.29:/opt/reels/.
- Pitfall móvil: palabras largas sin espacios (nombres de archivos DOCX) desbordan 6px dentro de su caja → `word-break:break-word` en el pie legal.

## Diálogos: el usuario manda
- El diálogo FINAL es el que el usuario pega literalmente en el chat, NO el del DOCX ni el propuesto por el agente. Cuando el usuario dice "que quede así" o "que ese diálogo solo quede X", usar su texto EXACTO palabra por palabra (puntuación incluida si la marca él); no «mejorar» ni re-expander.
- Si pide condensar («vuelvela dos líneas, explicando muy sencillamente»), condensar SIN cambiar los datos de cumplimiento (horario, balota, premios).
- Tras cada corrección: patch + scp + verificación con curl/grep + QA de render antes de reportar.

## Escena larga = varias tomas del MISMO keyframe
- El usuario puede tener solo 1 keyframe por escena. NO pedir keyframes extra: partir la escena en tomas de cámara (push-in / órbita / rack focus) que TODAS animan el mismo keyframe con `first_frame`. Cortes de cámara crean continuidad sin re-diseño. Límite Monid 15s por clip obliga a partir escenas >15s.
- Cada toma lleva su fragmento del diálogo de la escena (el diálogo completo se reparte entre las tomas en orden).

## Prompt Seedance 2.0 Mini (plantilla)
- Solo `first_frame` (NO mezclar con reference_image) + bloque CHARACTER.
- Estructura: línea de apertura («Animate the provided approved Scene N keyframe…») → DIALOGUE (voz, tono, números escritos en letras) → «Treat the provided image as a LOCKED visual composition» → GOLDIE CONTINUITY (anatomía intacta) → SCENE → CAMERA (timeline de segundos) → ACTION → ENVIRONMENT → LIGHTING → MOOD → IMPORTANT (comercial cinematográfico, no cartoon) → lista de prohibiciones (no text/logos/numbers/morph/shake). Los rótulos, balota 53, cifras y contadores van en OVERLAY EN POST — el clip los deja en blanco.
- **LIP-SYNC: línea crítica.** Si el guion dice «the character's mouth does NOT need to be visibly speaking… treat the dialogue as voice-over narration», Seedance genera la voz PERO NO ANIMA LA BOCA → labial congelado/desincronizado (queja real del Admin, sept 2026). El patrón correcto (lote Goldie agosto, aprobado) es el INVERSO: `DIALOGUE (spoken by Goldie OUT LOUD… looking at camera)` + `Goldie's screen-face CLEARLY animates his mouth and eyes IN SYNC with the spoken line. His lips and jaw move naturally word by word… never frozen, never stiff, exactly like a real 3D animated character` + bloque `AUDIO` (voz nativa, empieza en el 0:00, no música/subtítulos). Siempre re-escribir la línea del guion que desactiva el labial.
- Cada toma lleva su bloque CHARACTER FIJO, idéntico entre escenas (un solo `GOLDIE_CHAR`, sin rewrites por scene).
- Flujo de aprobación: mostrar el prompt COMPLETO en el chat ANTES de lanzar; costo estimado por clip; gate Monid firmado por Jonathan antes de cualquier pago; primer clip confirma tarifa real antes de escalar.

## Pitfalls de despliegue en prod (costaron un run y un reclamo, sept 2026)
- **Cache-buster OBLIGATORIO en la URL del keyframe.** Si reemplazas un keyframe en prod (`/opt/reels/.../scene-N.png` vía scp) pero el clip usa esa URL, Cloudflare puede seguir sirviendo el archivo VIEJO → ByteDance descarga el keyframe anterior y dispara el filtro. Sintoma: el run da `InputImageSensitiveContentDetected.PrivacyInformation` AUNQUE subiste la versión buena. Diagnóstico: `curl -sL -o /dev/null -w '%{size_download}B' <url>` — si el tamaño difiere del archivo nuevo, hay cache. Fix: añadir `?v=2` (bump al cambiar el keyframe) a la URL del `first_frame`. Verificar con `curl` SIN y CON el buster (solo el buster debe traer el nuevo).
- **Filtro de personas reales (ByteDance).** Keyframes con humanos FOTORREALISTAS → `InputImageSensitiveContentDetected.PrivacyInformation` (400, $0). Los humanos deben ser CLARAMENTE cartoon 3D (Pixar). Como el usuario edita las imágenes (GPT/DALL·E), pedirle que cartoonee SOLO a los humanos (cripta editable, deja el robot y composición intactos). Puede convivir con el bug de cache: subir cartoon OK pero Cloudflare sirviendo el fotorrealista viejo.
- **Verificar el run real vs el .run.json.** Tras un fallo y un re-lanzamiento, `clips/<S>.run.json` queda con el run_id del ÚLTIMO submit — no asumir que un proceso terminado es el bueno. Comprobar con `ps aux | grep run_pacho` y leer el run_id actual antes de reportar.

## Google Drive (credencial ActivePieces cuando el token directo expira)
- El `google_token.json` (drive_download.py / drive_list.py) expira ~7 días y da `invalid_grant`. FIX sin re-auth del usuario: usar la credencial materializada de ActivePieces `secrets/<tenant>-drive.json` (refresh_token + client_id + client_secret) y construir el client Drive con `Credentials(token=None, refresh_token=…, client_id=…, client_secret=…, token_uri='https://oauth2.googleapis.com/token', scopes=...).split(','))` + `.refresh(...)`. Detalle en `references/keyframe-despliegue-y-oauth.md`.

## Voz
- Clips con voz nativa Seedance (generate_audio + DIALOGUE) para que el usuario monte los WAVs ElevenLabs en CapCut (método aprobado). fal sync-lipsync RECHAZADO por el usuario («muy fea») → fit_voice SIEMPRE.

## Versionado post-aprobación (el Admin cambia duración/literal en chat, oct 2026)
- Si el Admin cambia duración o locución DESPUÉS de aprobar un guion (ej. 30 s → 20 s), NO editar el lote aprobado: crear carpeta nueva `reel2-<tema>-v0X/` (cp -r), editar `guion-cerrado.md` A MANO (el generador nunca la sobreescribe), regenerar los 10 prompts (imagen+video) con un script propio en `scripts/` que reutilice MASTER/REFS/`video_prompt` del preparador v2 del repo m-c-g (sin duplicar lógica), y mover el lote viejo a `assets/campanas/<campana>/_archive/<motivo>-<fecha>/`. Registrar el cambio en `.specs/<tarea>/01-spec.md` con costo recalculado.
- El video se cobra por SEGUNDO GENERADO, no por el target: objetivo 20 s → 23–25 s generados (se recorta la cartela en post). Presupuestar con los totales reales de `lote-preparado.json` (imágenes+video), nunca con el target.
- Literal canónico en PROD (`GUIONES-V2-APROBADOS-LITERAL.md`): no editar la tabla original; hacer `cp -p` a `.bak-<fecha>` y APPEND de una sección «AJUSTES VIGENTES DEL ADMINISTRADOR» que prevalece sobre la tabla.
- Handoff con Bob vía `agent_exchange.py` (PROD `/opt/data/scripts`): `send --from ragnar --tarea "<cuerpo>"` — ojo, `--deliver` es un CANAL de entrega (default `bot-chat:ragnar`), no el mensaje; el cuerpo va en `--tarea`. Tickets solo-informativos se marcan «INFORMATIVO (no ejecutar):» para que Bob no actúe.
- Marcadores `guion-cerrado.md.drive-conflicto` del sync XLSX↔Drive: son notas de texto del detector (ruta canónica vs. ruta alternativa), NO datos. Si el repo es la verdad, borrar el marcador y dejar que el próximo sync suba la versión del repo.

## Referencias
- `references/keyframe-despliegue-y-oauth.md` — receta completa: diagnóstico del cache-buster en prod, subida de keyframes vía ssh/scp, y credencial de Drive por ActivePieces cuando google_token.json expira.
