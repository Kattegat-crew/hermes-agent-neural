---
name: guiones-campana-por-canal
description: "Use when writing or auditing casino ad scripts."
tags: [guiones, campanas, casino, meta-ads, cumplimiento, coljuegos, reels]
version: 1.0.0
metadata:
  hermes:
    tags: [guiones, campanas, casino, meta-ads, cumplimiento, reels]
    related_skills: [guion-video-campana, meta-ads-operations]
---

# Guiones de campaña por canal (clientes regulados: casino / juego)

Clase de trabajo: escribir, auditar o refinar los guiones de una campaña de reels para un cliente
regulado (Golden Game, The Grand Paradise / Lucky Brothers), donde **el mismo mensaje necesita copy
distinto según dónde se emita** y donde la duración no se opina: se mide.

Complementa a `guion-video-campana` (producción, prompts Seedance, despliegue) y a
`meta-ads-operations` (pauta, pixel, campañas). Aquí vive **el guion y su gate**, no la producción.

---

## 1. Regla madre: dos piezas, no una

Mezclar el copy del anuncio con el de la pieza de sala es el error que quema plata y hace que Meta
baje el anuncio.

| | **Pieza de Meta (objetivo: CLICS)** | **Pieza de salón / TV / mostrador** |
|---|---|---|
| Cifras del acumulado | ✗ fuera | ✓ dichas y en pantalla |
| Mecánica (cartón, balota, un bingo por jornada, hora según aforo) | ✗ fuera | ✓ completa |
| Fechas exactas, dirección, pie legal | ✗ fuera | ✓ obligatorios |
| Cuerpo del guion | experiencia: el lugar, la gente, la música, el plan del viernes | dato del pueblo + mecánica + CTA |
| Destino de la mecánica | copy del post + **página de destino** (ahí se ve y se registra) | el propio reel |
| Lo que sí puede decir del acumulado | solo su **existencia** ("el acumulado crece cada viernes") | cifra concreta |

- Se escriben como **archivos separados** (`GUION-<ID>-meta.md` y `GUION-<ID>.md`) y se marcan por
  canal, para que nadie produzca la pieza equivocada ni le exija al ad lo que solo el salón puede decir.
- **No forzar 60s en el ad.** Si al sacar cifras y mecánica la locución queda en 30-40s, esa ES la
  duración de la pieza de Meta: se ajusta la ventana a la voz medida, no al revés. Un anuncio de
  clics con una idea limpia rinde más corto que 60s rellenados.
- Evidencia de qué copy aprueba Meta en nuestro propio `kb/ad.jsonl` (13 anuncios verdes corriendo
  48-85 días): `references/copy-casino-que-pasa-meta-review.md`.

### Léxico vigilado en el ad
"premio", "gana / gánate", cifras de dinero, "cae / se reparten", balotas, "apuesta", "azar" y
"suerte" **como promesa** levantan el flag de Meta. Los verdes del `kb` dicen lugar y experiencia
(`game, dine, and relax` · `Come for the show. Stay for the fun.`), nunca cuánto se gana.

---

## 2. Protocolo medido: nunca opinar sobre un guion sin correrlo

Antes de decir si un guion "está bien", **transcribirlo literal** a la tabla de
`templates/guion-reel.md` del repo del generador y medirlo con `scripts/guion_lint.py` (sintetiza la
locución con edge-tts: **gratis**, sin tocar el gate de gasto).

```bash
cd <repo marketing-campaign-generator>          # verificar la ruta viva: git status + git pull
setpriv --reuid=hermes --regid=10000 --clear-groups \
  env HOME=/tmp/hermes-home TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python scripts/guion_lint.py <guion.md> [--json --out informe.json]
```

Correrlo como el usuario del repo evita dejar `__pycache__` de root dentro del árbol de trabajo.

**Los "Voz medida" escritos a mano en un guion o en un CSV del cliente son estimaciones viejas.**
En cuanto alguien cambia una línea, el número impreso al lado deja de valer. Medir siempre.

### Los dos defectos que hay que reportar (y el segundo se olvida)

1. **La narración no cabe** en su ventana → el linter da el exceso exacto en segundos.
2. **Aire muerto** → la voz usa mucho menos que la ventana ("usa solo X% de su ventana"). Aparece
   justo cuando alguien recortó texto para cumplir un límite.

> **Regla de relleno:** el hueco **no se rellena con mecánica ni con T&C, se rellena con experiencia**
> (lugar, gente, ambiente). Si con experiencia tampoco alcanza, la pieza **baja de duración**.

Ojo con el ritmo: un registro corto y exclamativo habla **más lento** (≈2,3 pal/s) que el narrativo
(≈2,7 pal/s). Si el cliente cambia el registro, hay que **recalcular todas las ventanas**, no solo el
texto. Cifras: dichas en palabras en la voz y mostradas en cifras en pantalla.

---

## 3. Método del injerto (cuando el cliente manda su propia edición)

El patrón que funciona con el Admin no es reescribir: es **injertar**.

1. Transcribir su edición **literal** (sin "mejorar" su redacción) y medirla.
2. Contrastarla con las constantes obligatorias de la serie y marcar **qué se cayó**. En casino las que
   no son estilo sino obligación: fechas explícitas · mecánica corregida por el cliente · cifras ·
   balota · **"cartón gratis *mientras estés jugando*"** (el calificador es lo que hace legal el
   "gratis") · dirección confirmada · pie legal `+18 Juego responsable | Regulado por Coljuegos`.
3. **Conservar su registro** y meter lo obligatorio en los segundos de aire que la medición revela.
4. Reportar aparte, siempre y en este orden:
   - **Errores factuales** de su texto (p.ej. una frase que invierte quién hizo qué).
   - **Promesas nuevas que los T&C no autorizan.** Esa frase **no se escribe** hasta que el cliente la
     apruebe; se deja el hueco medido y listo para cuando responda.

Al entregar: tabla de trabajo con **cámara · diálogo · rótulo**, el veredicto con los segundos reales,
lo que sale y lo que se queda, y la decisión concreta que le toca al cliente. Nada se publica externo
sin aprobación Full.

---

## 4. El gate y sus choques conocidos

- **El linter exige el pie legal (`+18` + `Coljuegos`) en el texto EN PANTALLA** y da ERROR si falta.
  Un guion de Meta lintado con este gate queda **en rojo por diseño**: eso es esperado, no un defecto
  del guion. Se reporta como tal para que nadie "arregle" el ad metiéndole el pie legal.
- **`scene_plan.py`** convierte el guion en el `brief.json` del motor y sale con
  `approved_to_spend=false` + `max_cost_usd=0` (gate cerrado). El brief trae además el **estimado del
  run completo** — hay que dárselo al Admin y esperar su OK explícito antes de producir nada pagado.
- **Nada pago sin firma.** Imágenes, clips y audio se pagan por llamada; el guion se cierra **antes**
  de gastar, porque regenerar sobre un guion que aún cambia es quemar saldo.
- Los dos defectos del linter que hoy bloquean a quien escribe (valor crudo de `**Pieza:**` que rompe
  `spine_id`; `|` sin escapar dentro de una celda que bloquea `scene_plan`), con su workaround y repro,
  están en `references/guion-lint-protocolo-medido.md`.

---

## 5. Traer el guion desde Drive

Los guiones llegan como **Word subido a Drive** (link con `rtpof=true`), no como Google Doc nativo.

- `files().export()` falla con **403 «Export only supports Docs Editors files»** en archivos subidos
  → bajar el binario con `files().get_media()` + `MediaIoBaseDownload` y leerlo con `read_file`
  (extrae el texto del docx sin convertir nada).
- Si el token OAuth local da `invalid_grant`, la salida es la **credencial materializada de
  ActivePieces** `secrets/<tenant>-drive.json` (mismo patrón que en `guion-video-campana`).
- Antes de bajar: leer metadatos (`name`, `mimeType`, `owners`, `modifiedTime`) — la fecha de
  modificación suele revelar que el cliente editó el doc esa misma mañana.

---

## Referencias

- `references/guion-lint-protocolo-medido.md` — medidas reales de la serie, cómo se corre el linter,
  los dos defectos conocidos con repro, la tensión del modo `--perfil meta-ad` y el método del injerto.
- `references/copy-casino-que-pasa-meta-review.md` — los anuncios de casino que Meta aprueba (evidencia
  del `kb`), qué se dice y qué no, y el reparto por canal.
