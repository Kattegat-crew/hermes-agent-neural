# Producción de impresos de campaña (repo m-c-g)

> Creado como reference de `mapa-de-carpetas` porque el hook `guard_autoskill_create.py`
> fallaba cerrado al crear la skill dedicada `print-production-campanas` (3 intentos).
> Promoverla a skill propia cuando el hook esté reparado.

Pipeline probado en `2026-11-aguinaldo` (boleta semanal Lucky, A6). Repo: `/opt/marketing-campaign-generator`.
Piezas en `planning/<campana>/03-piezas/impresos/`, specs en `03-piezas/specs/<marca>/` (JSON por pieza).

## Reglas duras

1. **Costo 0 por defecto:** el panel de arte de una pieza impresa se RECORTA del maestro ya
   aprobado (`03-piezas/heros/...`), nunca se genera imagen nueva para una boleta.
2. **Texto NUNCA lo dibuja el modelo de imagen:** el texto es contractual (TyC, Coljuegos);
   todo se maqueta en vectorial con un script Python (Pillow). El modelo de imagen solo produce el arte base.
3. **Personaje base declarado:** referencia obligatoria al character sheet vigente
   (p. ej. `assets/sheets/lucky/view/front-v2.png`), no a imágenes sueltas.
4. **Gates en código, no disciplina:** el generador lleva `assert`s de layout (última fila de
   campos ≥ 3 mm sobre la banda legal; pie legal dentro del marco). Si se rompe, el script aborta.
5. **Tipo de boleta en el antetítulo** (`BOLETA OFICIAL · SEMANAL`) — lo exige el TyC.
   Confirmar el día de sorteos con el TyC vigente, no con memoria (Aguinaldo = miércoles).

## Especificación estándar (boleta A6)

- 148 × 105 mm (A6 horizontal = ¼ de A4; 4 boletas por hoja), sangrado 3 mm → lienzo
  154 × 111 mm → **1819 × 1311 px a 300 ppp**. Conversión: `px = mm / 25.4 * 300`.
- Salida doble: PNG (revisión en chat) + PDF (imprenta) del mismo canvas, LANCZOS.
- Panel de arte ~58 mm + panel de formulario ~90 mm con el logo REAL compuesto
  (`assets/sheets/.../logo/`), nunca generado.
- Campos (desde TyC): N.º, SEDE, JORNADA (casillas por fecha), NOMBRE, CÉDULA, CORREO,
  F. NACIMIENTO, CELULAR. Casillas ≥ 2.8 mm; 3.6 mm entre etiqueta y línea para escribir a mano.
- Reverso: cómo participar (numerado), horarios, sedes, firma `RECIBIDA POR / FECHA`,
  pie legal, y advertencia de que la semanal no pasa al sorteo final.

## QC en 4 capas (en orden)

1. **Geometría programática (siempre):** bloques de tinta con numpy (`|px - fondo| > umbral`),
   aire entre la última tinta y la banda legal, detección de recorte del personaje
   (0 píxeles del color dominante a ≤1 mm de los bordes del panel).
2. **QC visual (vision_analyze) a ~700 px JPEG:** pedir solo defectos concretos. El servicio
   falla intermitente (400 upstream): reintentar una vez; si no, confiar en la capa 1 y decirlo.
3. **Comparación contra errores de Golden:** logo generado ilegible, campos que faltan según
   TyC, casillas diminutas, texto pisado por la banda.
4. **Read-back:** `ls -la` de los outputs (PNG + PDF) antes de declarar la pieza lista.

## Pitfalls

- **Logo casi cuadrado empuja el layout:** medir el aspect ratio real del PNG del logo antes de
  calcular posiciones (30 mm de ancho pueden ser ~28 mm de alto y desbordar la banda 2.6 mm).
- **La tinta que "llega a la banda" suele ser el filete dorado vertical:** excluir 1 mm alrededor
  de filetes/marco al medir aire o el QC da falso positivo.
- **Pendientes legales (C6 Coljuegos) se imprimen como `PENDIENTE (C6)`** y quedan en
  `bloqueos` del spec JSON; nunca inventar el número.
- **Spec JSON por pieza** (formato, paneles, campos, archivos, bloqueos, pendientes): contrato
  para regenerar o versionar sin redisparar el diseño.
- **Versionado v1/v2:** el cambio del Admin se aplica al generador y se re-renderiza; la pieza
  vieja nunca se borra (coherente con `references/versionado-identidad-marca.md`).
- **La numeración del N.º en el render no reemplaza la foliación real de imprenta:** el campo
  queda como casillas en blanco.
