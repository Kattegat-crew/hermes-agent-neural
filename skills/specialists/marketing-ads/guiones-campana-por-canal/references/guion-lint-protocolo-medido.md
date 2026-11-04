# Guion → lint → brief: el protocolo medido (marketing-campaign-generator)

Levantado el 11-sep-2026 sobre los guiones vivos de la campaña Bingo Millonario (Golden + Lucky).

## Dónde vive

- Repo: `marketing-campaign-generator` (rama `main`). **Verificar la ruta viva antes de usarla**
  (`git status` + `git pull` en el árbol físico): el repo se movió durante esta campaña.
- Piezas del protocolo: `templates/guion-reel.md` (forma canónica del guion),
  `contracts/guion.schema.json`, `scripts/guion_lint.py`, `scripts/scene_plan.py`,
  `scripts/sales_spine.py` (test producto-necesario), `contracts/brief.schema.json`.
- Guiones maestros de la serie en `plans/` (`GUION-G1..G4`, `GUION-L0/L1`).

## Cómo se corre

```bash
cd <repo>
setpriv --reuid=hermes --regid=10000 --clear-groups \
  env HOME=/tmp/hermes-home TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python scripts/guion_lint.py <guion.md>          # informe legible
# añadir --json --out informe.json para leer las medidas campo por campo
```

Salida esperada: bloques `GUION / ESCENAS / VOZ / SPINE`, la lista de `[ERROR]` y `[aviso]`, y
`RESULTADO`. En `VOZ medido real` está la verdad: segundos reales por escena.

## Medidas reales de la serie (referencia para calibrar)

| Guion | Declara | Voz real | Lectura |
|---|---|---|---|
| `GUION-G2-TUNJA.md` (maestro) | 60,0s | **105,17s** | 4/4 escenas se pasan; scene-03 sola usa 56,09s de una ventana de 26s |
| `GUION-G4-PACHO.md` | 60,0s | **100,73s** | mismo patrón de sobrepaso |
| `GUION-L1-CHIQUINQUIRA.md` | 38,0s | 39,96s | casi cuadra; **ERROR de cumplimiento**: sin pie legal en el texto en pantalla |
| edición del Admin sobre Tunja (CSV) | 60,0s | **36,48s** | el opuesto: scene-03 con 10,4s en ventana de 25s → **42% de aire muerto** |

**Lección de calibración:** una serie escrita "a 60s de montaje" puede llevar 100-105s de locución
real y resolver el recorte con una **instrucción en prosa** en vez de con un guion de 60s. Mientras eso
no se decida, todo lo que se produzca encima (locución, montaje, slots) se produce sobre una ficción.
El linter lo dice en segundos, no en opiniones.

## Los dos defectos del linter que bloquean a quien escribe (reportados 11-sep-2026)

1. **Con `## Spine (7 beats)` declarado, `spine_id` se arma con el valor crudo de `**Pieza:**`** y
   `sales-spine` lo rechaza por patrón. Una ficha tipo `Reel 9:16 · 60s · voz del local` **no pasa
   lint** (2 errores, exit 1); un slug tipo `g2-tunja-centro-60s-reel-9-16` sí.
   *Workaround:* poner el slug en `**Pieza:**` y mover la ficha a `**Formato:**`.
2. **Un `|` sin escapar dentro de una celda de la tabla cuenta como celdas de más**
   (`parse_scenes` parte por todo `|`) → aviso «celdas con '|' sin escapar», y ese aviso **bloquea
   `scene_plan.py`** salvo que se pase `--allow-warn`.
   *Workaround:* usar `·` como separador en el pie legal en pantalla (contenido legal idéntico).
   El arreglo real es en el parser (partir solo por pipes no escapados) y **no se toca sin OK del
   Admin**, porque el protocolo es suyo.

## Tensión abierta: modo `--perfil meta-ad`

El linter **exige** el pie legal en pantalla y las constantes de T&C (cifras, balota, mecánica, fechas
explícitas). Un anuncio de Meta necesita exactamente lo contrario. Propuesta presentada al Admin el
11-sep-2026, **aún sin autorizar**: un perfil `--perfil meta-ad` que invierta el gate — (a) deja de
exigir el pie legal en pantalla, (b) **veta** cifras / azar / balota, (c) exige CTA de clic. Hasta que
exista, la pieza de Meta se lintéa como pieza de salón y **queda en rojo por diseño**.

## Método del injerto (cuando el cliente manda su propia edición)

1. Transcribir su edición **literal** a la tabla de `templates/guion-reel.md` (sin "mejorar" nada) y
   medirla.
2. Comparar contra las constantes obligatorias de la serie y marcar qué se cayó: fechas explícitas,
   mecánica corregida por el cliente, cifras, balota, `cartón gratis **mientras estés jugando**`,
   dirección confirmada, pie legal.
3. **No reescribir su registro:** se conservan sus frases y lo obligatorio entra en los segundos de
   aire que la propia medición revela. Caso Tunja: el hueco de 14,6s de scene-03 es exactamente donde
   caben mecánica + cifras + balota sin tocar una coma del resto.
4. Reportar aparte **(a)** los errores factuales del texto del cliente y **(b)** cualquier **promesa
   nueva que los T&C no autorizan** — esa no se escribe hasta que el cliente la apruebe, y se deja el
   hueco medido para cuando responda.

## Presupuesto y gate

El `brief.json` que emite `scene_plan.py` sale con `approved_to_spend=false` y `max_cost_usd=0`, y trae
el estimado del run completo (para un reel de 4 escenas con keyframes + clips + audio, del orden de
~5,8 USD al 11-sep-2026; verificar precio real, no citarlo de memoria). Ese estimado se le presenta al
Admin y se espera su OK explícito.
