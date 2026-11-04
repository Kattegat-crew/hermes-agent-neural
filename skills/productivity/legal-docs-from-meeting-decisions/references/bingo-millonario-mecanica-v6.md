# Bingo Millonario 2026 (Golden + Lucky) — mecánica VIGENTE (v6) y rastro de decisiones

**VIGENTE: v6 (31/08/2026, tras la reunión de las 11:21 am).** La mecánica cambió 3 veces en una
semana (v2 → v5 → v6). NUNCA reutilizar versiones viejas ni copys derivados de ellas sin confirmar
vigencia: todo el contenido (copys, pósters, reels, páginas web) se genera a partir de estos T&C.

## Mecánica v6 (definitiva, confirmada con Jonathan 31/08)
- Participación: créditos activos en máquina (SIN mínimo de $50.000 — propuesto y rechazado 2 veces) + registro obligatorio (nombre, correo, celular, cédula y local) al recibir la tabla.
- Cartones: tablas plásticas reutilizables — UNA por persona por TODA la jornada (sirve para los 3 bingos). Número de tabla anotado en el registro. Propiedad del local, se devuelven al final. Sin fichas de redención ni reservas (eliminadas definitivamente).
- TRES bingos por noche, en este orden: corto de $50.000 (completar UNA letra anunciada) → corto de $100.000 (una letra) → ACUMULADO cartón completo entre 7:30 y 8:00 pm en DOS tandas (~30 balotas + intermedio + resto). Los cortos no tienen límite de balotas.
- Regla de la balota 53: SOLO el acumulado. Cae en ≤53 → paga el acumulado del local y REINICIA en $400.000. No cae → NADA se paga (SIN premio de consolación) y rueda +$400.000.
- Escalera por local: 400K → 800K → 1.2M → 1.6M. Acumulado independiente por local y por empresa.
- GRAN FINAL 02/10: el acumulado se paga SÍ O SÍ, sin regla de 53 (decisión verbal final del Administrador en la transcripción 00:39; el resumen automático de Gemini dice lo contrario — ver rastro). Los 3 bingos también se juegan esa noche. Después se evalúa si la campaña CONTINÚA en nov-dic (continuidad, no el pago).
- Desempate: NO se divide el premio. Rifa con la balotera: cada afectado extrae una balota y la MÁS ALTA gana TODO. Aplica a los 3 bingos.
- Llegadas tardías: participan únicamente en el bingo EN CURSO al llegar; los finalizados no se juegan.
- Evidencia: constancia firmada (fecha, sede, tipo de bingo, balotas del acumulado, N° de tabla ganadora, ganador, valor, medio de pago, firma) + digitalización al equipo central. La copia del cartón YA NO APLICA (son tablas plásticas).
- Premio en efectivo libre de retenciones; empleados del organizador y personal de la promoción excluidos; parientes SÍ participan; Funza EXCLUIDA en ambas empresas.
- Hora de inicio: 5:00 pm (la v2 decía 7:00 pm).

## Sedes
- Golden (7): Agua de Dios (Calle del Comercio — confirmada por operador), Anolaima (Cra 5 #2-33), Cachipay (Cra 3 #2-37), El Carmen de Apicalá (Calle 4 #6-23/25, Gran Casino Club), Pacho (Cra 15 #7-3), San Francisco (Calle 3 #8-32), Tunja (Cra 6 #47 A-40 L3).
- Lucky (5): Chiqui 1 (Cra 9 — corregida en reunión 31/08, antes se decía Cra 10), Chiqui 2 (Cra 8, Plaza de la Libertad), La Calera S1 (frente a la plaza), La Calera S2 (CC Calera Gardens — añadida 31/08), Tunja (Grand Paradise). Funza excluida por cierre.

## Rastro de reversiones (por qué existe el protocolo de confirmar)
- **v2 (24/08):** 2 bingos por jornada; $100.000 por bingo como consolación si no cae en 53; empate divide en partes iguales; 7 pm; evidencia con copia del cartón.
- **v5 (31/08 madrugada):** UN bingo por jornada; $100.000 consolación única si no cae en 53; seguía la división de empate.
- **v6 (31/08, reunión 11:21 am) — VIGENTE:** estructura real de 3 bingos ($50K letra + $100K letra + acumulado en 2 tandas); consolación ELIMINADA; desempate por rifa de balota más alta; UNA tabla plástica por persona por jornada; gran final se paga sí o sí.
- Lección clave 31/08: las notas automáticas de Gemini («Decisiones») resumieron LO CONTRARIO de lo acordado en el pago del acumulado del 02/10 («continuará acumulándose» vs «se paga sí o sí»). Evidencia fuerte: transcripción 00:39 + qué frases quedaron INTACTAS cuando el operador revisó la cláusula. Verificar SIEMPRE contra transcripción y preguntar al Admin antes de generar.

## Entregables y scripts (v6)
- Local: /opt/data/entregables/TC_BINGO_MILLONARIO_GOLDEN_GAME_v6.docx · TC_BINGO_MILLONARIO_LUCKY_BROTHERS_v6.docx
- Drive: Golden id 1OFdfqWWmvgY5iUCnLqVggny-oVKIL9XX (carpeta 03-piezas Golden 1EOqKqoPAz4h68O4OgUOl1S-DUU4Arkrk); Lucky id 1AZtVTyjyFrVhHbxSjyIgmvJL_XzcX-8y (03-piezas Lucky 1FY-8Gyvcr5SxfPqDaQs1libTPhTYNbvG). v5 en papelera (1l9UjKuAKoqiZIOL7X8j7Q6VI4jd3ALJW, 1k-hc48R7d59ji2Rncw7sgQnbEVNPwm-m).
- Build v6: /opt/data/scripts/build_bingo_tc_v7_tres_bingos.py (emite archivos _v6.docx; backup v5 = build_bingo_tc_v6_un_bingo.py).
- Carpeta AGY: /opt/data/agy-docs/ — LEEME.md (mecánica v6 + frases oficiales para piezas), TC-golden-v6.md, TC-lucky-v6.md, DOCX v6, Políticas de datos v1.
- Políticas de datos: siguen v1, sin cambios en v6.
- Páginas a actualizar: golden-game-landing src/pages/TerminosBingo.jsx (dice «Versión 4.0», «2 bingos» — líneas ~48 y ~199) y src/data/eventsData.js (~140); repo paradisclub (Lucky) igual.
- Nota ambiente: /opt/data/brain/folder-maps/bingo-millonario-campanas.md es propiedad de root y NO escribible desde sesiones hermes; el registro de vigencia vive en agy-docs/LEEME.md y este archivo.
