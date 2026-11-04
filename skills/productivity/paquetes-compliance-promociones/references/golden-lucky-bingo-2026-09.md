# Bingo Millonario Sept 2026 — Golden Game + Lucky Brothers (confirmaciones del operador, 24/08)

Campaña conjunta de marca con **documentos legales SEPARADOS por empresa** (decisión del cliente:
«no pueden compartir documentos»). Esta referencia es la plantilla de datos para futuras
promociones conjuntas de estos clientes.

## Entregables generados
- `/opt/data/entregables/TC_BINGO_MILLONARIO_GOLDEN_GAME_v2.docx`
- `/opt/data/entregables/TC_BINGO_MILLONARIO_LUCKY_BROTHERS_v2.docx`
- Script reutilizable: `/opt/data/scripts/build_bingo_tc_v3.py` (dict `*_CFG` por empresa → `build_tc()`).

## Mecánica confirmada por el operador (24/08/2026)
- 5 jornadas: vie 04/09, 11/09, 18/09, 25/09 + gran final 02/10, 7:00 pm. Todos los locales; Funza excluida (cierre).
- 2 bingos por local por jornada; premio $100.000 c/u cuando el bingo supera 53 balotas.
- Bingo con **≤53 balotas → paga el ACUMULADO del local**.
- **Acumulado INDEPENDIENTE POR LOCAL**: cada local tiene su propio acumulado y sus propios juegos; no se mezcla entre sedes ni entre empresas. Escalera por local: 400K → 800K → 1.2M → 1.6M; si no se gana, rueda +400K; si se gana, reinicia en 400K.
- Premio en **efectivo, libre de impuestos** para el ganador (manejo tributario interno del operador).
- Cartón: **1 por persona que esté jugando en el local** en ese momento, hasta agotar disponibilidad.
- Empate (2 cartones válidos): el premio se divide en partes iguales.
- Empleados del operador + equipo de la promoción: excluidos (parientes 2.º grado: pendiente confirmar).
- **Evidencia obligatoria** en cada entrega: constancia escrita (fecha, sede, nº balotas, nombre/documento del ganador, valor, medio de pago, firma) + copia del cartón. Cláusula 8 + Anexo C.
- **Régimen**: el operador NO tramita autorización de Coljuegos (posición: promoción publicitaria/marketing). Cláusula de régimen redactada conforme a su decisión; advertencia jurídica de rastreo en «Estado del documento» (Ley 643 art. 5 puede encuadrar en juegos promocionales con reconocimiento de exclusión). No bloquear la entrega por esto.

## Sedes por empresa
- Golden: Agua de Dios, Anolaima, Cachipay, El Carmen de Apicalá, Pacho, San Francisco, Tunja (direcciones oficiales SIICOL C2005).
- Lucky: Chiquinquirá S1 (Cra 10), Chiquinquirá S2 (Plaza de la Libertad), La Calera, Tunja (Grand Paradise). Direcciones y contactos oficiales de Lucky pendientes de verificar (Cámara Comercio / SIICOL).

## Puntos abiertos (Anexo B de cada doc)
1. Dirección oficial exacta de Agua de Dios (consta solo «Calle del Comercio» en anexos SIICOL).
2. Aforo / nº máximo de cartones por local por jornada.
3. Gran final 02/10: si en un local nadie gana el acumulado, ¿se pierde, se juega doble o se sortea?
4. Contactos oficiales de Lucky (correo/teléfono/WhatsApp).
5. Parientes de empleados (2.º grado): ¿también excluidos?

## Verificación de aislamiento aplicada
Al escanear cada docx con python-docx: el de Golden NO contiene NIT/sedes/contactos de Lucky y
viceversa; todas las claves propias presentes; 0 tokens `[CORCHETE]`/`DEFINIR`/`REVISAR`.
Lección de tooling: la regex de huecos debe usar límites de palabra (`\bPENDIENTE\b`) porque
`PENDIENTE` sin `\b` da falso positivo dentro de `INDEPENDIENTE`.