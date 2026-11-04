# Estructura del paquete de compliance — promoción de casino (detalle cláusula por cláusula)

Basado en el paquete entregado a Golden Game S.A.S. el 2026-08-18 (promoción «Ruleta Golden Game»).
Patrón probado: T&C → Política de Datos → Aviso de Privacidad → textos de formulario →
juego responsable → anexos (pendientes + técnico). Entrega final en .docx con python-docx.

## 1. Términos y Condiciones — 18 cláusulas

| # | Cláusula | Contenido clave |
|---|----------|-----------------|
| 1.1 | Organizador | Razón social, NIT, domicilio, correo, teléfono, WhatsApp, representante legal |
| 1.2 | Autorización | N.º de resolución/radicado Coljuegos o entidad territorial. Para promoción digital: Coljuegos (alcance nacional, Ley 643 art. 5). Si la autorización específica no existe aún, decirlo explícitamente y prohibir publicación hasta obtenerla |
| 1.3 | Vigencia | Fecha/hora inicio y fin, o hasta agotar N bonos. Prórroga/terminación con aviso |
| 1.4 | Ámbito y sedes | Solo Colombia; tabla de sedes con municipio/departamento/dirección; excluir sedes no listadas |
| 1.5 | Participantes | +18 (Ley 643 art. 4); exclusión de empleados y agencias; el botón +18 es declaración, NO verificación (la identidad se valida en caja con documento físico) |
| 1.6 | Mecánica | Pasos exactos: ingresar → girar 1 vez → formulario → código único → redención en recepción |
| 1.7 | Participación única | Por cédula/correo/celular; sin duplicados ni múltiples cuentas |
| 1.8 | Naturaleza del bono | Crédito de juego, NO dinero en efectivo al entregarse; uso solo en máquinas de las sedes; intransferible, no acumulable |
| 1.9 | Conversión «duplicar el bono» | Regla matemática exacta: saldo ≥ 2x del nominal → retiro hasta 100% del nominal ($10k/$20k/$30k). Si el operador no la definió: proponer y marcar PENDIENTE DE CONFIRMACIÓN |
| 1.10 | Vigencia del bono | Plazo de redención y de uso; caducidad sin compensación |
| 1.11 | Restricciones | Personal e intransferible; no acumulable; horarios; juegos excluidos; prevalece lo aprobado por la autoridad |
| 1.12 | Reclamación | Formulario → código → caja con documento físico → validación → bono → retiro según 1.9 |
| 1.13 | Fraude | Anulación sin compensación: duplicados, suplantación, bots, manipulación |
| 1.14 | Datos personales | Ley 1581 + política del operador; marketing separado y revocable (Ley 2300) |
| 1.15 | Juego responsable | Resolución 20244000022654 de 2024; micrositio Coljuegos; línea de apoyo |
| 1.16 | PQR | Canales reales (correo, teléfono, WhatsApp, sedes); SIC como autoridad |
| 1.17 | Modificaciones | Por causas justificadas con aviso; respetar derechos adquiridos |
| 1.18 | Legislación/jurisdicción | Ley colombiana; jurisdicción ordinaria de la ciudad del operador |

## 2. Política de Tratamiento de Datos Personales — 14 secciones

Responsable → Marco normativo (Ley 1581/2012, Dto 1377/2013, Dto 1074/2015, Ley 1480, Ley 2300) →
Definiciones → Datos recolectados (identificación, contacto, promoción, navegación/cookies, atención) →
Finalidades (promoción, cumplimiento legal, seguridad/fraude, estadísticas agregadas, marketing solo con
autorización separada) → Autorización (casillas independientes no premarcadas; conservar prueba con
fecha/hora/versión/IP) → Derechos (art. 8 Ley 1581) → Canales y plazos (consultas 10+5 días hábiles;
reclamos 15+15) → Transferencias a encargados con contrato de transmisión; sin venta de datos →
Seguridad → Conservación → Menores (prohibido) → Cookies → Vigencia y modificaciones.

## 3. Checkboxes del formulario (textos exactos, ninguno premarcado)
1. «Declaro que soy mayor de 18 años.» — OBLIGATORIO
2. «He leído y acepto los Términos y Condiciones de la promoción [ENLACE].» — OBLIGATORIO
3. «Autorizo de manera libre, previa, expresa e informada a [RAZÓN SOCIAL] el tratamiento de mis
   datos personales, de acuerdo con su Política de Tratamiento de Datos Personales [ENLACE].» — OBLIGATORIO
4. «Autorizo el envío de comunicaciones comerciales y promocionales por SMS, correo electrónico,
   WhatsApp y llamadas telefónicas. Puedo revocar esta autorización en cualquier momento.» — OPCIONAL

Guardar evidencia separada de cada consentimiento (fecha/hora, campaña, versión del documento).

## 4. Textos de Juego Responsable
- Modal +18: «Contenido exclusivo para mayores de 18 años» / «Soy mayor de 18 años» / «Salir».
  Nota técnica: es barrera/declaración, no verificación de identidad.
- Banner/pie: «Juega con moderación. El juego es entretenimiento, no una fuente de ingresos.
  Prohibido para menores de 18 años. www.coljuegos.gov.co» (Res. 20244000022654/2024).
- Correo de constancia: incluye código único, sede, fecha límite y mensaje de juego responsable.

## 5. Checklist técnico (responsabilidad de la agencia)
Código único por reclamación · resultado de la ruleta en BACKEND (no navegador) · bloqueo de segunda
participación por cédula/correo · registro de auditoría (resultado, fecha/hora, campaña, premio) ·
versionado de T&C/política · consentimientos separados con evidencia · estados de reclamación
(generado → reclamado → validado → redimido/cancelado) · anti-redención duplicada · constancia al
usuario + aviso operativo al casino · revisar cookies/analytics/Meta Pixel/WhatsApp/CRM/terceros.

## 6. Datos típicos a pedir/verificar del operador
Razón social y NIT exactos · autorización específica de la promoción (radicado/resolución) ·
fórmula del bono · sedes participantes · vigencia y n.º de bonos · plan de premios/probabilidades ·
canales PQR · URL definitiva. Fuentes: RUT, Cámara de Comercio, contrato de concesión, informe de
cliente — ver skill `google-drive-access` para obtenerlos del Drive.
