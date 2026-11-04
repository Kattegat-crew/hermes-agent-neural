# Caso: gate regulatorio de copy en el calendario de campañas (16-sep-2026)

Contexto: calendario bingo-sep2026 (golden+lucky) del repo marketing-campaign-generator. Propuesta de gate con juez Jev pendiente de decisión del Admin (colocación, nº de preguntas, shadow mode).

## Qué se verificó contra el código real (read-before-design)

- `planning/calendario-sep2026/publish.py` (404 líneas): `publish()` aborta con SystemExit si el veredicto es bloquear.
- `planning/calendario-sep2026/cron_publish_due.py:69`: ventana `0 <= ahora - slot <= 2h`, tick horario → **sin catch-up**. Publicar ya lo aprueba el humano (Admin) en el chat.
- `daily_package.py:149`: ahí el copy se muestra al Admin en el paquete de las 07:30 → punto correcto para el gate.
- La fila del calendario NO tiene campo `sede` (verificado sobre las 64 filas); sedes vigentes/cerradas viven en `datos-duros.yaml`. Sin pasarlo en el `state`, la pregunta de sede es incontestable — ese fue el error real del ensayo.
- No existía ningún validador de copy en el pipeline: el gate es nuevo, no duplica nada.

## Correcciones al primer diseño (por qué)

- De 5 preguntas a 2 difusas + 1 score: 2 eran búsquedas de texto disfrazadas (sede cerrada → lookup + `'funza' in copy.lower()`; avisos legales → regex).
- De la vía de publicación al paquete 07:30: bloquear en la vía sin catch-up = pérdida silenciosa de la pieza.
- Shadow mode 2 semanas antes de dar poder de veto.

## Errores de la sesión (para no repetir)

- `type-safe-ai-gate` fue un nombre malo (sesión-artifact); renombrado a la clase `llm-judge-gates`.
- La primera propuesta de plan se formuló ANTES de leer el código y la ventana de publicación — el código la demostró floja. Orden correcto: leer código → proponer diseño.
- Presentar 3 decisiones como preguntas abiertas en bloque funcionó bien para que el Admin decidiera en una sola pasada.
