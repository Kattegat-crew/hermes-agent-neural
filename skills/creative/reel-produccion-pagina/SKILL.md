---
name: reel-produccion-pagina
description: "Use when producing a campaign reel and its page."
tags: [reels, campanas, produccion, pagina, portal, keyframes, cliente]
---

Pipeline validado en Chiquinquirá (Lucky) y Goldie (Golden): guion → keyframes →
clips Seedance → voces fit_voice → página de producción en el portal.

## Estructura canónica de la página (aprobada por Jonathan 05/09)
Secciones EN ESTE ORDEN, copiar exactamente del ejemplo:
`https://reels.neuralcrewlabs.com/lucky-brothers/campañas/septiembre-2026/reels/reel2-chiquinquira/`

1. **Header**: título (Reel N · sede), marca × campaña, tomas/duración/formato, estado.
2. **📜 Guion detallado**: tabla Toma|Tiempo|Personajes|Lugar|Qué pasa|Diálogo + link .md.
3. **🖼️ Keyframes aprobados**: composición bloqueada; Seedance anima, no rediseña.
4. **🧭 Hero + Referencia de dirección**: sección PROPIA — el hero/referencia de personaje
   NO va dentro de keyframes (corrección explícita de Jonathan).
5. **🎬 Clips animados Seedance** (voz nativa).
6. **🎙️ Clips con voz de marca cuadrada** (fit_voice) con botón ⬇ Descargar.
7. **🎵 Audios ElevenLabs por escena** (crudos, descargables WAV, voz por personaje).
8. **🏷️ Assets de campaña** (overlays + logos: se componen en edición, NO se generan).
9. **📄 Documentos producción** (guion .docx, reporte, .md).

## Reglas de layout (no negociables, Jonathan revisa en móvil)
- Filas lado a lado: 6 (desktop) / 3 / 2 columnas.
- Keyframes PEQUEÑOS (max-height 280px) con `object-fit:CONTAIN` — imagen completa, nunca recortada.
- Videos 9:16 height ~340px con `object-fit:contain`; clips seedance y clips con voz lado a lado.
- Assets pequeños (max-height 110px) lado a lado completos.
- TODO audio con reproductor + botón ⬇; TODO video descargable.
- Verificar layout con getBoundingClientRect en navegador real antes de entregar.

## Guion oficial = fuente de verdad (lección 07/09, reel Pacho)
Cuando Jonathan comparte el DOCX de guiones oficial (ej. NLC-BINGO-GG-002-FINAL, G4 "Padre bueno"),
sus narraciones DEROGAN cualquier locución derivada del guion maestro. Verificar escena-por-escena
contra el DOCX ANTES de generar voces o clips. Leer DOCX sin python-docx: zipfile + regex sobre
word/document.xml (<w:p> = párrafo, <w:t> = texto). En el reel Pacho la estructura 4 escenas
coincidió 1:1 con el DOCX (S1 Padre Bueno, S2 Naranja, 3A/3B/3C Fuego/Paciencia/Punto Exacto,
S4 CTA) pero la locución que había publicado era la del maestro (equivocada).

## Sección "Guion oficial" en la página (aprobada por Jonathan 07/09)
La página debe mostrar TODOS los diálogos completos + descripciones visuales por escena (no resúmenes):
bloque `.esc` por escena con tag tiempo (① 0–12 s · NOMBRE), visual 🎥, diálogo 🎙️ completo,
en pantalla 🖥️ + notas de recorte 60s/30s + contexto del pueblo con fuentes + reglas de voz.
Reemplaza/complementa la tabla de guion detallado cuando existe DOCX oficial.
QA obligatorio: render en navegador real (desktop + móvil emulado 390px, check overflow
horizontal y grid columns) y curl prod para confirmar publicada.

## Flujo de producción (pipeline validado)
1. Guion detallado con tomas y diálogos literales (frases intocables marcadas por el cliente).
2. Keyframes: Jonathan los genera (GPT/flux) con prompts míos en inglés; yo hago QA visual
   (vision_analyze) y refino por escena. Ajustar la DURACIÓN del clip Seedance a la locución
   real (~+1s margen, límite 15s/toma → dividir en a/b si excede).
3. Clips: Seedance 2.0 Mini, SOLO first_frame (no mezclar con reference_image, error 400);
   consistencia por bloque CHARACTER en el prompt. Mostrar prompt completo ANTES de lanzar
   (regla de aprobación de runs pagados).
4. Voz: ElevenLabs por escena (Voz_Lucky U9tZtg3uJtVgXPkvosWR; Goldie 'Kate' qWWAqFomnJ99VwQLREfT)
   → fit_voice (atempo≈0.9) → clips voz-cuadrada. Jonathan RECHAZA fal sync-lipsync ('muy fea');
   método = fit_voice SIEMPRE.
5. Publicar página en `reels.neuralcrewlabs.com/<cliente>/campañas/septiembre-2026/reels/reelN-<sede>/`
   (staging /opt/reels/_staging/ en prod .222; tarjetas por proyecto).
6. Edición final: silenciar audio nativo, montar WAVs, overlays (logo, balota, contador),
   entrega CapCut/Akari a Jonathan.

## Fuentes de material (Drive por campaña)
Cada campaña vive en Drive con estructura 00-contrato / 01-docs / 02-guiones / 03-piezas.
- Golden Bingo sep2026: carpeta 1yjMyLNPD_YTDuk5Vi2WOD4bCOxklvFIi
  (03-piezas/Reels/Reel N con Scenes/, Assets/, Voces eleven labs/, Voces arregladas/,
  Videos seedance/, Final/; 02-guiones con guion maestro + guion cinematográfico por sede).
- Listar/descargar Drive vía secrets `/opt/data/secrets/jonathan-drive.json` (skill
  google-drive-access), corriendo Python DENTRO del contenedor.

## Checklist de readiness (informe a Jonathan antes de empezar)
- [ ] Guion(es) en 02-guiones — ¿cuál versión corre si hay 2 (maestro vs cinematográfico por sede)?
- [ ] Keyframes completos (todas las escenas + hero). Escena de cierre pendiente = bloqueante.
- [ ] Assets overlays listos (balota, contador, escalera premios, fechas, logo).
- [ ] Voz de marca cargada.
- [ ] Contrato (campaign.yaml + estado.json) vigente.
- [ ] Decisión de Jonathan: versión del guion + aprobación de prompts y presupuesto Monid.
