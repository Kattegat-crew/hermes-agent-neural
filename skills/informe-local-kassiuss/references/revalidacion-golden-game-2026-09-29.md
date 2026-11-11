# Revalidación Fase 1 — falso positivo GOLDEN_GAME (29-sep-2026)

- Veredicto reviewer Fase 1: APROBADO para Pacho (17 máquinas) y Cachipay (16), 0 errores en 924 comparaciones con parser independiente, SHA-256 de 56 fuentes sin mismatch, 11/11 tests, regeneración bit a bit idéntica.
- Observación del reviewer: usar prefijo GOLDEN_GAME generaría 23 máquinas mezclando 3 sedes sin error.
- Revalidación independiente + replicación directa: NO se reproduce.
  - Glob exacto: `GOLDEN_GAME__*.html` no matchea `GOLDEN_GAME_PACHO__*` ni `GOLDEN_GAME_SAN_FRANCISCO__*`; 28/28 días con exactamente 1 match.
  - Título interno del HTML: `GOLDEN GAME <span>01-Sep-2026</span>`; cero apariciones de PACHO o SAN FRANCISCO en los 28 HTML.
  - Rosters de máquinas disjuntos entre sedes; solo el id 0211 se comparte con San Francisco pero con marca y valores distintos (máquina física distinta, no contaminación).
  - Scratch de evidencia: /opt/hermes-agent-data/drafts/kassiuss-review-prefix/golden-game-dataset.json.
- Lección: un veredicto APROBADO puede contener hallazgos incorrectos; revalidar con evidencia directa antes de bloquear el cierre.
- Pendiente al cierre de la sesión: veredicto independiente de Fase 2 (build/verify XLSX) y verificación del acoplamiento publicador-verificador sobre la copia Drive, que exige nueva autorización explícita.