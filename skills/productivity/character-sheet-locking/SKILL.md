---
name: character-sheet-locking
description: "Use when locking canonical mascot model sheets for video."
tags: [personaje, mascota, sheets, imagen, video, referencia, lock]
metadata:
  hermes:
    tags: [imagen, personaje, mascot, referencia, video]
    category: creative
---

# Character Sheet Locking (hojas canónicas de mascota)

Antes de generar video long-form/story-ads, cada personaje necesita un SET lockeado
(front/side/back + grid de expresiones) que se adjunta SIEMPRE como reference_images.
Un solo hero no basta: el modelo de video deriva sin vistas consistentes (fallo #1 =
drift de identidad). Verificado 09/09/2026 con Goldie (Golden Game) y Lucky (Lucky
Brothers) tras 3 iteraciones de rechazo.

## Cuándo usar

- Un registry de sheets (ej. marketing-campaign-generator `assets/sheets/registry.json`)
  tiene character sheets en `seed`/`missing` y hay que llevarlos a `locked`.
- Se va a generar la primera campana de video con un personaje recurrente.

## Cómo (receta verificada, imagen local sin costo de fal.ai)

1. **Imagen de partida**: image-to-image (`/images/edits` multipart, `model=flux-2-klein`,
   ver skill `nan-builders-api`) sobre el hero/seed aprobado — NUNCA text-to-image desde cero.
2. **UNA FIGURA POR IMAGEN** — 4+ llamadas separadas: frontal, perfil estricto, dorsal,
   y un grid 2x2 de expresiones (multi-celda solo OK para caras de la MISMA cabeza).
3. Anclas de prompt que funcionaron (repetir el bloque de identidad IDÉNTICO en todas):
   - `full body single character, centered, ... neutral A-pose, hands EMPTY`
   - perfil: `STRICT SIDE PROFILE, 90 degrees from camera, ONLY ONE eye and ONE arm and ONE leg visible`
   - dorsal: `BACK view seen from directly behind: plain back panel, no face visible`
   - fondo: `flat light-gray studio background, even soft lighting, full body visible head to feet`
   - resolución: 1024x1024 por vista (grid: 1536x1024)
4. **Texto quemado**: cualquier marquee/letrero del personaje sale como texto IA ilegible
   ('GOUDE GAME') → anclar `the marquee band is solid black with NO letters and NO text`.
5. **QA visual por imagen** con `vision_analyze` exigiendo veredicto **LOCK o REJECT con
   motivo** (vistas correctas? escala igual? manos vacías? incoherencias graves?). Iterar
   el prompt hasta aprobar el set. Nota: el QA tiende a REJECTar por exceso (p.ej. botánica
   real vs personaje estilizado) — juzcar contra el hero de la marca, no contra la realidad.
6. Al lockear: registry → `status: locked`, `gaps: []`, y `provenance` documentando
   rechazos y semillas conservadas como referencia de estilo (NO canon).

## Pitfalls

- **NO generar turnarounds multi-figura en una imagen**: flux-2-klein produce deriva
  2.5D entre vistas (palancas/orejas fantasma que solo existen por detrás, corona de
  4 hojas que se ve de 2, cara donde no debe haber). REJECT sistemático: dos rondas
  completas se perdieron así antes del enfoque de una-figura-por-imagen.
- 400 intermitente en /images/edits → retry 2-3 veces con espera de ~5s (transitorio).
- El modelo default de clientes antiguos puede estar roto: `flux` ya no existe en NaN
  (400/404) → `flux-2-klein`; y el CDN de descarga migró a `*.r2.cloudflarestorage.com`
  (allowlists de hosts hay que ampliarlas).
- No borrar el seed del repo al lockear (git lo conserva); solo retirarlo de las rutas canon.
- **Refrescar la hoja canónica cuando se aprueba un key art de campaña** (verificado 29-oct-2026): cuando el Admin aprueba la imagen de campaña con correcciones de personaje (p. ej. Lucky v2 sin tallo, nariz de botón, mejillas planas), actualizar la hoja master en `assets/sheets/` y propagarla al registry — las campañas siguientes deben heredar el diseño corregido, no el seed viejo. Dejar el recordatorio en la hoja de diseño de la campaña como paso explícito post-aprobación.
- **Propagar la versión nueva a TODAS las capas del ecosistema, sin borrar la anterior** (verificado 29-oct-2026, Lucky v2): regenerar el PNG no basta — si solo cambia la imagen, cada capa sigue sirviendo la vieja. Checklist de propagación: (1) `assets/sheets/registry.json`: entrada nueva `locked` con la vista regenerada y la anterior marcada `deprecated` (NUNCA borrar ni sobreescribir la entrada vieja — es la «versión anterior» exigida por el Admin), (2) doc canónico de identidad en el repo (`docs/marketing-factory/IDENTIDAD-PERSONAJES.md`) con vigente vs anterior y referencias prohibidas, (3) `AGENTS.md` del repo: obligatorio leer la identidad antes de generar arte y prohibido adjuntar hojas `deprecated`, (4) espejo en `/opt/data/brain/IDENTIDAD-PERSONAJES.md` + fila en `brain/AGENTS.md` para agentes que arrancan de cero sin contexto del repo, (5) skills que adjuntan sheets (p. ej. `print-asset`): regla de leer el registro y adjuntar solo la `locked`. Si el refresh solo regenera el frontal, marcar side/back como «no adjuntar» en registry y manifiesto hasta regenerarlas.

## Relacionado / solape

- `scene-consistency-qa` (user-owned, candidata a absorber este skill tras
  `hermes curator adopt scene-consistency-qa`): esa cubre QA de stills de escenas; esta,
  el lockeo del set de referencia PRE-producción.
- Generación de clips a partir de las hojas: `monid-seedance-clips`, `reel-pipeline`.

## Verificación

- `sheets_registry.py --check` sin hojas rotas; `require_locked(brand)` devuelve rutas
  existentes para cada marca del set.
- Cada archivo del set tiene su QA LOCK registrado (provenance del registry).
