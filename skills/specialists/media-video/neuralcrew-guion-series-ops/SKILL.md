---
name: neuralcrew-guion-series-ops
description: "Use when replicar o parafrasear guiones de serie Bingo."
tags: [guiones, series, bingo, reels, campanas, parafrasis, coljuegos, linter]
category: guiones
version: 1.0.0
---

# Guiones de serie multi-local (Bingo Millonario y campañas hermanas)

Clase de tarea: mantener una serie de reels pueblo-por-pueblo sobre la misma plantilla aprobada (G1 → G2 → G3...), aplicando rondas de feedback del cliente sin romper constantes de T&C ni calcarse entre piezas. Complementa a `campaign-script-revision` (ciclo general de revisión); este cubre lo específico de SERIE y de la campaña Bingo Millonario.

## Constantes inmutables (verificar con assert antes de entregar)
- Fechas SIEMPRE explícitas: viernes 4, 11, 18 y 25/09 + gran final 02/10. Nunca "todos los viernes".
- Mecánica corregida (Jemadiar 28/08): UN solo bingo por jornada, cantado a partir de las 5 p.m. según aforo. Prohibido: "uno tras otro", "dos bingos", "escalonado".
- Frases ancla aprobadas: "no pares de jugar en tu máquina" · "completas/completes tu cartón antes o en la balota 53". **Excepción (feedback Jemadiar 28/08, G3):** si la escena arranca en impersonal "uno" ("Uno llega…, se sienta…"), NO se inserta el ancla en tuteo ahí — el salto uno→tu→"no pares" suena antinatural. Forma correcta validada: "Uno llega desde las cinco, se sienta, juega en su máquina, está ganando, y las oportunidades crecen cuando recibes tu cartón para participar del Bingo Millonario." El tuteo retoma donde la casa le habla directo al cliente ("Si completas tu cartón antes o en la balota 53…").
- **Regla de tratamiento (Jemadiar 28/08, G4 Pacho — convivencia APROBADA):** el "usted" del mostrador pachuno y el "tú" del protagonista pueden convivir en un mismo guion, PERO **NUNCA dentro de una misma frase** (✗ "usted llega, se acomoda y no pares de jugar en tu máquina"). El salto se hace siempre en frontera de oración, en unión natural (✓ "Usted llega y se acomoda. Y desde ahí, no pares de jugar en tu máquina."). Chequeo antes de entregar: split por [.!?…] y assert de que ninguna oración tenga marcas de ambos tratamientos.
- **Regla de poeticidad (Jemadiar 28/08, G4):** los giros poéticos/comprimidos ("la que volvió hierro las piedras") suman musicalidad y están bien vistos, pero solo si el guion da contexto para entenderlos al oído; si no, se introduce el contexto en la misma escena o se mantiene la literalidad ("extrajo hierro de las piedras"). Forma validada: "aquí, las piedras de color ocre se volvieron hierro en la primera forja del país".
- Cifras: $400.000 acumulado · $100.000 repartidos · balota 53 · tope `$1'600.000` (formato apóstrofo pedido por el cliente). Al referirse al tope, decir "puede crecer... hasta su tope máximo: $1'600.000" — NUNCA "hasta poder tocar los $1'600.000" (vago, suena a promesa de pago; corregido Jemadiar 28/08).
- Pie legal intacto: "+18 Juego responsable | Regulado por Coljuegos".
- Vocabulario vetado: "pana(s)"→"amigos", "bote"→"acumulado". grep programático de vetos + variantes hasta cero (las menciones como nota del veto sí se permiten).

## Variación entre locales (regla clave, Jemadiar 28/08)
La escena de mecánica (típicamente 22-48s) NO se copia palabra por palabra de la pieza anterior. Se parafrasea con un recurso nuevo por local; el validado en G2 Tunja es **autopregunta-respuesta de mostrador**: "¿Cómo funciona...? Fácil. ¿Cuándo?... ¿Qué necesitas para participar?... ¿A qué hora se canta?... ¿El premio?...".
- Cada pregunta va además como rótito en pantalla que se responde solo ("¿CUÁNDO? → Viernes 4·11·18·25/09 · desde 5PM") — sirve al ~40% de consumo sin sonido y renueva el overlay sin repetir el de G1.
- Excepción a la paráfrasis: las constantes T&C y las frases ancla se mantienen textuales.
- Verificación: lista de frases literales de la pieza anterior → assert de que ninguna aparece en la nueva salvo las ancla.

## Duración: medir con el linter, nunca rotular (actualizado 11/09/2026)
La medición que manda es la herramienta, no la cuenta a mano: `scripts/guion_lint.py` sintetiza cada narración con **edge-tts (gratis, `es-CO-GonzaloNeural` +0%)** y mide la duración REAL contra la ventana de la escena. Palabras ÷ pal/s (2,4-3,0 según registro) queda solo como **control de cordura**: si un número medido no cuadra con esa cuenta, remedir antes de confiar (11-sep se vio una submedición silenciosa: una escena medida 11,04s cuando su texto mide 14,90s — confirmado 4 veces).

**El registro cambia la velocidad**: las exclamaciones de mostrador y los textos con fechas y direcciones leen lento (2,2-2,4 pal/s), la narración descriptiva corre a 2,7-3,0. Al injertar texto nuevo en un guion ajeno, medir SIEMPRE: el injerto completo puede no caber donde la aritmética decía que sí (11-sep: injerto de 59,5s pedía ventanas de 61s en una pieza de 60s → se recortaron 4 palabras).

Al parafrasear una escena, actualizar el total en las notas de producción del maestro y re-escribir qué frases caen en los recortes (fechas, cifras, balota 53 y pie legal intocables en cualquier recorte).

## Pipeline real (11/09/2026): repo, perfiles y brief
- **Repo vivo:** `/root/marketing-campaign-generator` (ya NO `data/repos/`). `git pull --ff-only` antes de tocar nada. Los guiones maestros y los briefs viven en `/root/hermes-agent-legacy-docker/data/plans/`.
- **Plantilla obligatoria:** `templates/guion-reel.md` — tabla `Tiempo | Visual | Narración | En pantalla` con ventanas contiguas desde 0, `## Estructura (serie validada)` con la línea de ①②③④, `## Spine (7 beats)` declarado (trigger, problema, descubrimiento, mecanismo, producto, payoff, cta en ese orden, con las escenas que cubre cada beat), `## NARRACIÓN COPIABLE` con `> **inicio-fin:** "texto"`, notas con el vocabulario vetado entre comillas y el pie legal.
- **Dos perfiles de pieza (mismo guion, se juzga distinto):** `--perfil serie` (parrilla/TV/salón: exige el pie legal EN PANTALLA, admite cifras y mecánica) y `--perfil meta-ad` (anuncio de pago: **veta cifras económicas incluidas las dichas en palabras**, veta vocabulario de azar (apuesta, balota, premio, sorteo, ganar…), "suerte" es aviso, exige **verbo de clic + dominio/URL** en el aire, y pone **tope 40s = error / objetivo 30s = aviso**).
- **Trampas del parser que ya costaron tiempo:** (1) `**Pieza:**` debe ser un **slug** (`g2-tunja-meta-30s-reel-9-16`) porque el linter arma `spine_id` con ese valor crudo y el contrato `sales-spine` lo rechaza por patrón — la ficha humana va en un campo aparte `**Formato:**`; (2) un `|` dentro de una celda de la tabla (aunque vaya escapado) cuenta como celdas de más y emite aviso que **bloquea `scene_plan`**: el pie legal en rótulo va con `·` como separador en `serie` y no va en `meta-ad`.
- **Cierre de la cadena:** `guion_lint` → `scene_plan.py --perfil <x>` (genera `brief.json`, siempre con `approved_to_spend=false` y `max_cost_usd=0`: el gasto lo firma un humano) → `reel_engine.py --dry-run` debe dar 4/4 escenas con `total_cost 0.0`. El brief queda atado al guion por `sha256`.
- **Reels de conversión (guía del Admin, 11/09/2026):** de ahora en adelante, cortos y a conversión — 30-40s, una idea y una acción, clic al sitio y seguir la página. Sin cifras ni promoción de azar (Meta tumba los anuncios; el patrón que sobrevive en `kb/ad.jsonl` es lugar + experiencia). **Qué sale a la voz y qué se reenvía a pantalla:** al recortar de 53s a 30s lo que baja de la locución vuelve como rótulo — nada se pierde, cambia de capa.
- **Copy del post (caption) es donde viven** cifras, días, dirección, mecánica (en la landing) y el pie legal `+18 Juego responsable | Regulado por Coljuegos`; el video solo empuja al clic. El dominio real de Golden es **goldengame.com.co** (está en el repo; no inventar dominios).

## Maestros en /opt/data/plans/
- **Serie hermana Lucky (28/08):** ~~evento GRAN BINGO PARADISE~~ → **PIVOTE Jemadiar 28/08 (tarde, v5): el evento de Lucky se llama BINGO MILLONARIO** — ya había piezas gráficas PUBLICADAS de Paradise con ese nombre/concepto, así que la serie lo adopta (#BingoMillonario). "The Grand Paradise Club"/"casinos Paradise" = identidad del local, nunca nombre de evento. Nueva arquitectura: **video general L0 + un video por municipio, máx ~30s c/u**; L0 = Lucky toma la flota e invita a conocer juntos los municipios y casinos (solo fechas + gancho, la mecánica completa va en los videos de municipio); videos de municipio = **estructura de la serie Golden** (dato del pueblo con fuente → conexión suerte/casino → evento → CTA+legal) con voz de Lucky. El "juega doble/misterio de sedes" queda retirado como columna. Direcciones Chiq: Cra 10 # 17-34 + Cra 11 # 17-44 Plaza La Libertad. NIT Lucky 900.177.204-0 en pie legal.
- **Lección general de series con personaje preexistente + nombre de evento:** antes de acuñar un nombre de campaña, preguntar por piezas ya publicadas del cliente — un nombre "diferenciador" puede chocar con publicidad viva en la calle y cae el concepto completo. Los cambios de nombre de evento se propagan: guiones → maestro de serie → sellos/hashtags → notas de compliance.
- `GUION-G1-AGUA-DE-DIOS-FINAL.md` (v5 vigente), `GUION-G2-TUNJA.md` (v2), etc. Changelog en el header de cada versión con el feedback citado y quién lo dio.
- Datos operativos que el cliente pasa sueltos en chat (direcciones de local, horarios) se anclan INMEDIATO en el maestro con sello ("✅ Dirección confirmada por Jemadiar 28/08: Calle 18 # 11-45, Centro Histórico") y se quita el ⚠️ pendiente — las sesiones de Discord se auto-resetean por horario y lo no escrito en archivo se pierde.
- Direcciones conocidas: Golden Tunja = Calle 18 # 11-45, Centro Histórico.

## Serie Lucky: feedback de forma (Jesús 28/08, v2 de L0/L1)
Aplicable a cualquier pieza con personaje + recorrido:
- **No asumir mutez del personaje del cliente.** Lucky TIENE rostro y extremidades (ya salió en videos previos). El trébol plano sin cara es solo el LOGO. Chequeo: grep de "sin cara", "hojas como", "sus hojas" (como manos) en guiones/prompts de personaje animado → cero hits.
- **El cliente dicta la DIRECCIÓN del viaje:** en L0 camina HACIA la flota y aborda al final (no baja del bus al inicio). La caminata es "lo único continuo de la animación"; los fondos cambian en pleno paso con el **nombre del pueblo en letras grandes en un lugar representativo** cada vez que lo nombra.
- **Transición entre sedes (corregido Jesús 28/08, v3):** en video corto NO se muestra el recorrido de una casa a otra — roba tiempo y distrae del mensaje. **Lucky es el presentador**: habla a cámara y el cambio de sede es un **salto de cámara** con continuidad de discurso (audio corrido, mismo encuadre/pose a ambos lados del corte). El camino caminando solo aplica al hilo del viaje de L0 (terminal→bus), nunca entre fachadas. Split-screen / "un casino frente al otro": RECHAZADO.
- **El guion es también prompt: precisión absoluta (Jesús 28/08, v3).** Prohibido en la columna visual: condicionales ("si el modelo lo trae"), "sugerencia:", situaciones abiertas o bifurcaciones. Cerrar cada decisión (p.ej. Lucky **sin sombrero ni accesorios**, lugares representativos fijos) y marcarla como decisión revocable en notas. Chequeo grep: "si el modelo", "sugerencia" → cero hits fuera del changelog.
- **Expresiones vetadas (Jesús 28/08):** "Nos veo" ✗ → usar "Los espero" / "Te esperamos" / "Nos vemos".
- **Mes de la amistad (septiembre):** FÓRMULA OFICIAL ACTUALIZADA (Jesús 28/08, dictada en L0 v7): **"mes del amor y la amistad"** — reemplaza "mes de la amistad" en toda la serie. Sembrar sutilmente una línea por pieza sin reestructurar. Día de la Amistad Colombia 2026: sábado 19/09.
- **Texto dictado por el cliente = literal:** cuando Jesús escribe la locución en chat ("--explicar evento--" = completar desde ahí), se preserva palabra por palabra (solo corrige tildación manifiesta, anotándolo en el changelog) y se continúa con el resto de constantes. Anotar en NOTAS la sección intocable y por qué.
- **Invitación multi-sede honesta:** apelar a cercanía/preferencia ("¿cuál te pilla más cerca?") + aclarar dinámicas INDEPENDIENTES con premios y acumulado propios por sede ("cada casa canta su propio bingo", "el tope de cada casa") — evita leerse como premio compartido (compliance).
- "El guion estaba bien pero puedes hacer variaciones si mejoras la escena" = se acepta parafraseo libre manteniendo constantes T&C.

## Límites de permisos (perfil bragi)
Las skills vecinas (`neuralcrew-campaign-content` en `skills/content/`, `campaign-script-revision`) no son curator-managed y el subdirectorio `content/` es root-owned: `skill_manage(patch)` y escritas ahí fallan (PermissionError / "not curator-managed"). No insistir: los aprendizajes nuevos van a este skill y al maestro .md de `plans/`. Para editar las otras, recomendar al usuario `hermes curator adopt <skill>`.

## Entrega
Archivo .md actualizado + ruta en el chat, adjunto como MEDIA. Cierre con la decisión pendiente que le toca al cliente (visto bueno, siguiente pieza de la serie). Nada se publica externo sin aprobación Full.
