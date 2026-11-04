# Caso validado: Bingo Millonario × Amor y Amistad (sept-oct 2026)

Manual de cajeras entregado como NLC-0004 (DOCX + PDF, 25/08/2026). Estructura aprobada por el Admin sin cambios. Cliente: Golden Game S.A.S. + Lucky Brothers SAS (dos T&C: NLC-0002 y NLC-0003, misma mecánica, sedes distintas).

## Datos base extraídos de los T&C

- **Golden Game S.A.S.** — NIT 830.115.955-4 · goldengameltda@gmail.com · Tel 601 384 3934 · WhatsApp 316 691 0728
- **Lucky Brothers SAS** — NIT 900.177.204-0 · contacto «por confirmar» (quedó pendiente en el DOCX)
- Vigencia: viernes 04, 11, 18, 25 sep + gran final 02 oct 2026, desde 5:00 p.m.
- Mecánica: 2 bingos por jornada por sede; 1 cartón por persona; +18 con documento físico; mínimo $50.000 COP en máquina; registro obligatorio de datos; bingo escalonado 15-20 balotas/hora; empleados NO participan, parientes 2.º grado SÍ; Funza excluida en ambas empresas.
- Evidencia obligatoria en cada entrega de premio (constancia firmada: fecha, sede, balotas, ganador, documento, valor, medio de pago, firma + copia del cartón).

## Sedes (tabla del manual)

Golden Game (7): Agua de Dios (Calle del Comercio), Anolaima (Cra 5 No. 2-33), Cachipay (Cra 3 No. 2-37), El Carmen de Apicalá (Calle 4 No. 6-23/6-25, Gran Casino Club), Pacho (Cra 15 No. 7-3), San Francisco (Calle 3 No. 8-32), Tunja (Cra 6 No. 47 A-40 Local 3).
Lucky Brothers (4): Chiquinquirá S1 (Cra 10), Chiquinquirá S2 (Plaza de la Libertad), La Calera («por confirmar»), Tunja (Grand Paradise).

## Escalera del acumulado (independiente por local)

| Jornada | Fecha | Acumulado |
|---|---|---|
| 1 | Vie 04 sep | $400.000 |
| 2 | Vie 11 sep | $800.000 |
| 3 | Vie 18 sep | $1.200.000 |
| 4 | Vie 25 sep | $1.600.000 |
| 5 GRAN FINAL | Vie 02 oct | Hasta $1.600.000 |

Reglas: jornadas 1-4 → bingo ≤53 balotas paga el acumulado del local; >53 balotas paga $100.000 por bingo; si ningún bingo cae en ≤53, acumulado rueda +$400.000 a la siguiente jornada; si se gana, reinicia en $400.000. Gran final: acumulado sin regla de 53; el premio de $100.000 no aplica. Empate = dividir en partes iguales.

## Decisiones de pre-work confirmadas por el Admin (clarify batch)

1. Manual genérico multi-empresa con campos por local (no uno por empresa).
2. Sedes «confirmadas» — pero en la práctica el T&C de Lucky traía direcciones incompletas → marcarlas «por confirmar» y pedirlas sin bloquear la entrega.
3. La cajera ejecuta: registro obligatorio + verificación de $50.000 + entrega de cartón.
4. Redes sociales: envío por WhatsApp interno/Drive; publica el Admin (nadie publica directo).
5. Entrega en DOCX editable + PDF imprimible.

## Entregables generados (reutilizables como plantilla)

- `/opt/data/workspace/gen_manual_cajeras_bingo.py` — generador DOCX (python-docx, patrón membrete).
- `/opt/data/workspace/gen_manual_cajeras_pdf.py` — generador PDF (fpdf2, tablas con cell border).
- Salidas: `Manual_Cajeras_Bingo_Millonario_Amor_Amistad.docx/.pdf`.

## Notas de generación

- fpdf2: no existe DejaVuSans-Oblique.ttf → `pdf.add_font("sans","I",FONT)` con la fuente regular (el error FileNotFoundError aparece al registrar la oblique).
- DOCX: cuidar sintaxis — coma colgante en llamadas y `enumerate([...])` sin `], start=1):` rompen el script (lint los detecta).
- Verificación: `read_file` extrae texto de .docx y .pdf — usarlo antes de entregar con MEDIA:.
