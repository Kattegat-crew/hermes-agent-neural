# Promociones y Juegos de Azar en Colombia — Investigación verificada (2026-08-18)

Caso base: landing Golden Game / Paradise Club Casinos, promoción "Ruleta" (bonos $10k/$20k/$30k COP, 7 sedes Cundinamarca/Boyacá/Tolima, redención en caja con cédula física, regla de "duplicar el bono" para retirar dinero).

## Normativa verificada en fuentes oficiales

### Ley 643 de 2001 (régimen de juegos de suerte y azar)
- Monopolio rentístico del Estado (Coljuegos administra).
- **Art. 4**: prohíbe ofrecer/operar juegos a menores de edad y a personas con enfermedad mental declaradas interdictas; prohíbe operar sin autorización.
- **Art. 5 (exclusiones)**: juegos realizados por comerciantes con finalidad publicitaria y sin ánimo de lucro NO entran al régimen, PERO debe gestionarse ante Coljuegos el reconocimiento de la exclusión. Sin ese reconocimiento, la autoridad puede tratarlo como juego gravado.
- **Art. 31**: impuesto del 14% sobre juegos con azar y lucro (escenario 2). Autorización + impuesto son concurrentes, no alternativos.
- Tres escenarios (según MS Legal, artículo de referencia):
  1. Juego por mérito (sin azar) → excluido, sin trámite.
  2. Azar + ánimo de lucro → autorización Coljuegos + impuesto 14%.
  3. Comerciante, sorteo publicitario sin lucro → reconocimiento de exclusión (art. 5) ante Coljuegos.
- Competencia territorial: campaña digital = alcance nacional por definición → interlocutor es Coljuegos (no entidad territorial).
- Lo que Coljuegos evalúa antes de aprobar: estructura y reglas del juego (acceso, alcance geográfico, vigencia, beneficios), respaldo jurídico del plan de premios (valor, condiciones de entrega), documentación de procesos de selección/entrega y conservación de soportes por varios años.

### Resolución Coljuegos 20244000022654 de 2024 (juego responsable) — VIGENTE
- Diario Oficial 52.912, 17-oct-2024. **Deroga** la Resolución 20214000036784 de 2021 (que había sido modificada por la 20224000032324).
- ⚠️ El reporte de compliance del cliente citaba "20244000021144" — número NO operativo/incorrecto. Verificar siempre el número vigente.
- Puntos operativos para promociones:
  - Publicidad debe: advertir riesgos de adicción al juego, incluir mensaje de juego responsable y mencionar que la actividad es solo para mayores de 18 años (remite al Acuerdo 08 de 2020 de la Junta Directiva, cap. 7).
  - Programa de Juego Responsable obligatorio para operadores (etapas: implementación y seguimiento).
  - Herramientas: test de identificación de factores de riesgo (basado en SOGS/BPGS), formato de autoexclusión, registro de autoexcluidos.
  - Incumplimiento → sanciones contractuales (multas).
- Fuentes: normograma.supersalud.gov.co/compilacion/docs/resolucion_coljuegos_22654_2024.htm ; coljuegos.gov.co/publicaciones/307018

### Ley 1581 de 2012 (protección de datos personales) + Decreto 1377 de 2013
- Autorización previa, expresa e informada; prueba de la autorización a cargo del responsable.
- **Art. 8** derechos: conocer/actualizar/rectificar, solicitar prueba de autorización, ser informado del uso, presentar quejas ante SIC, revocar autorización/suprimir, acceso gratuito.
- **Art. 14** (consultas): respuesta en 10 días hábiles, ampliable 5.
- **Art. 15** (reclamos): respuesta en 15 días hábiles, ampliable 15.
- Consentimiento: el silencio, casillas premarcadas o inacción NO constituyen consentimiento (criterio SIC — sedeelectronica.sic.gov.co, boletín jurídico).

### Ley 1480 de 2011, art. 33 (promociones y ofertas)
- Informar tiempo, modo, lugar y requisitos; los términos obligan al anunciante.

### Ley 2300 de 2023 (comunicaciones comerciales)
- Autorización previa, expresa e informada para SMS, correo, WhatsApp y llamadas; separada del consentimiento principal.
- Mecanismo de cancelación/revocación en cada comunicación.
- Crea el Registro de Números Excluidos (RNE); restricciones de horario para llamadas comerciales.
- Redactar sin fijar rangos horarios exactos salvo verificación puntual de la norma.

## Estructura del T&C de promoción (18 numerales, caso ruleta)

1. Organizador (razón social, NIT, domicilio, correo, teléfono) — [PLACEHOLDERS]
2. Autorización de la promoción (nº resolución/certificación Coljuegos o entidad territorial) — [PLACEHOLDER]
3. Vigencia (fecha/hora inicio-fin o agotamiento de N bonos)
4. Ámbito territorial y sedes participantes (solo Colombia; listar sedes)
5. Participantes (mayores de 18; prohibido menores art. 4 Ley 643; exclusión de empleados/agencias/familiares)
6. Mecánica (acceso → giro único → premio aleatorio → formulario → código único → redención en caja)
7. Participación única (por cédula/correo/celular; anti-duplicidad)
8. Naturaleza del bono (crédito promocional de juego, NO efectivo, no transferible, no acumulable)
9. Regla de conversión a dinero ("duplicar el bono") — fórmula matemática exacta, [CONFIRMAR CON EL OPERADOR]
10. Vigencia del bono y plazo de redención
11. Restricciones (horarios, juegos excluidos, no canje salvo regla 9, prevalece lo autorizado)
12. Procedimiento de reclamación y validación (documento físico en caja)
13. Prevención de fraude y duplicidad (bots, suplantación, cuentas múltiples → anulación)
14. Tratamiento de datos (Ley 1581 + enlace a política; marketing opcional Ley 2300)
15. Juego responsable (Res. 22654/2024; micrositio coljuegos.gov.co)
16. Reclamos y PQR (canales, plazos; SIC)
17. Modificaciones (causas justificadas, derechos adquiridos)
18. Legislación aplicable y jurisdicción

## Guion del generador python-docx (reutilizable)

- Script de referencia: `/opt/data/scripts/gen_legal_docs_ruleta.py` (ejecutado y verificado 2026-08-18).
- Recetas clave python-docx: estilos Normal/Heading 1-2-3 (fuente Calibri, dorado RGB(0xC9,0xA2,0x27) para H1), función `set_cell_bg` (w:shd OxmlElement) para encabezados de tabla oscuros, tabla con estilo "Light Grid Accent 1", portada centrada, bullets/numeración con List Bullet/List Number.
- Salida: `/opt/data/entregables/<Cliente>_<Tipo>_<fecha>.docx`; verificar con read_file (extracción automática) antes de entregar vía `MEDIA:`.
- El usuario prefiere: tabla para datos estructurados (bloqueadores: dato | responsable | estado), campos no confirmados entre [ ], nota final de que el documento no sustituye concepto jurídico.
