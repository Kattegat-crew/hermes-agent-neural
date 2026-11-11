# Producción visual de campañas con fal (verificado 2026-10-27)

Procedimiento para producir el arte de una campaña (arte base de mascota,
estáticos, pendones, piezas impresas) cuando el Admin autoriza gasto.

## Decisión de proveedor

- **Imagen estática: fal.ai**. Video NO: la invariante de repo sigue viva
  (fal de-authorized para video; Monid Seedance 2.0 único proveedor de video).
- La vía GPT/Codex quedó descartada por decisión: Codex CLI corre como
  app-server y no expone generación de imágenes. No reabrir el tema sin orden.
- Endpoints: personaje → `blackforestlabs/flux-3/edit-image` (hasta 10
  referencias); fondo/ornamento/textura → texto a imagen del mismo proveedor.
  Precio de referencia: 0,048 USD/MP (flux-3 edit).
- Dejar la decisión plasmada en `PROJECT_MEMORY.md` del repo: los agentes que
  leen la invariante "fal de-authorized" se detendrían solos si no existe la
  distinción explícita imagen-sí / video-no.

## Reglas de coste (las que evitan quemar el cap)

1. **Generar el arte a ~1,5 MP, nunca al tamaño final de impresión.** Un pendón
   60×160 cm a 150 ppp son ~33 MP: 1,60 USD generados directo vs ~0,07 USD del
   arte base. Escalado y composición tipográfica SIEMPRE en local con
   `scripts/print/`.
2. **Kit de referencia = UN collage curado por marca** (turnaround + hoja de
   diseño + logo + paleta con hex), no 10 archivos sueltos: más referencias
   diluyen la identidad y el modelo mezcla estilos. Guardar en
   `03-piezas/_referencias/<marca>-kit.png` (2048×2048). Es composición local:
   coste cero, y es prerrequisito de cualquier pieza con personaje.
3. **Un prompt legible + un spec ejecutable por pieza**
   (`02-guiones/prompts/<marca>/<pieza>.md` y
   `03-piezas/specs/<marca>/<pieza>.json` con endpoint, prompt, referencias,
   seed, aspect ratio) y **un hero por pieza** del que se derivan recortes.
   Ninguna generación con prompt improvisado.
4. El prompt describe el ARTE, nunca el texto final: tipografía y pie legal se
   montan después en local.

## Gate de gasto

- Abrir solo con autorización humana que cite **cap en USD + número de
  generaciones** ("USD 6 para 40 generaciones"). Ventana ≤ 24 h.
- `python3 scripts/spend_gate.py --authorize --by "<Admin + cita literal>" \
  --purpose "..." --providers fal --hours 12` → verificar con `--status`
  que dice `[ABIERTO] fal: ok`.
- El gate es por proveedor: autorizar `fal` no abre monid/elevenlabs.
- Verificar que `.spend-gate.json` está en `.gitignore` antes de commitear.

## Desbloqueo escalonado del board de producción

Construir el board con DAG (`hermes kanban link <parent> <child>`), tarjetas
con `--idempotency-key` para reintento seguro, y pipeline anexado al body de
cada tarjeta de producción. Al abrir el gasto:

1. Desbloquear SOLO lo que el gate cubre y lo que no depende de un bloqueo
   legal (piezas impresas con pie legal pendiente NO se generan: es saldo en
   algo que se rehace).
2. Audio/video/voz NO se desbloquean con un gate de imagen: otro proveedor,
   otro gate; si se abren, el agente muere a mitad y deja basura.
3. Las tarjetas de kits y prompts corren primero (coste cero) y son padres de
   las de arte: el DAG evita que se genere a ciegas.
4. Verificar el estado agregado del board (`list --json` + Counter) tras cada
   desbloqueo; evidence viva, no afirmación.
