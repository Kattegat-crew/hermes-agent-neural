# El Aguinaldo 2026 — Golden Game + Lucky Brothers (nov–dic 2026)

Campaña que re-validó el patrón multi-empresa con expediente documental por DAG Kanban (D01–D16). Repo: `marketing-campaign-generator/planning/2026-11-aguinaldo/` (migrado a la estructura canónica de carpetas, commit 67173e1).

## Mecánica confirmada por el operador (22-oct-2026)

- Vigencia 1-nov → 16-dic-2026. Tarjeta de constancia de 6 casillas, firmada por quien la entrega y por el cliente; si se pierde NO se repone.
- Un sello por semana, colocado **UNA VEZ TERMINADO el sorteo del miércoles** (orden: cierre de boletas → apertura de urna → sorteo → sello → desocupar urna → entregar boletas nuevas para el miércoles siguiente). Último sello 9-dic; el 16-dic no se sella.
- El sello se pone **SOLO a quien presenta la tarjeta** (Q6).
- Cada sello acumulado = 1 boleta para la final (máx. 6 por persona).
- Boleta semanal por visita; la recepción cierra el mismo miércoles antes del sorteo.
- El número de sellos puede cambiar si cambia el número de jornadas (sellos = boletas).

## Premios (verificados con python)

- Sorteo pequeño por sede/jornada: 50.000 + 100.000 + 200.000 = **$350.000** (6 jornadas = $2,1M/sede).
- Final 16-dic: 250.000 + 250.000 + 500.000 + 1.000.000 = **$2.000.000 POR SEDE** (resuelto explícito: por sede, no evento central).
- Excepción Agua de Dios y San Francisco (solo Golden): 500.000 + 300.000 + 100.000 + 100.000 = **$1.000.000 por sede**.
- Agregado con 12 sedes: 10 × $2M + 2 × $1M = $22M finales. Los agregados son verificación aritmética, NO presupuesto autorizado (spend_gate vigente).

## Estado FINAL del paquete documental (23-oct-2026, v1.0)

A1 (corrección de documentos) aprobada por el Admin con sus respuestas literales registradas. Cerrados: Q5/Q6/Q8 (cuarta ronda), C1 (final por sede), C2 (tipo de final). Entregables aprobados y publicados con membrete oficial NeuralCrew Labs en `01-docs/finales/` con nombre `NN-tipo_v1.0_2026-10-22.ext` (DOCX editable + PDF, Drive Golden y Lucky):

1. `01-tyc-golden-game_v1.0` — TyC Golden con privacidad integrada como anexo.
2. `02-tyc-lucky-brothers_v1.0` — TyC Lucky, documento autónomo (cero contaminación cruzada, verificada).
3. `03-manual-operativo-sede_v1.0` — manual común por audiencia (patrón Halloween: prosa profesional, secciones numeradas, tablas de control; NO folleto, NO condescendiente).
4. `04-reglas-participacion-golden_v1.0` — volante de reglas (interna del manual).
5. `00-indice-paquete_v1.0` — índice del paquete.
6. `MANIFIESTO.md` — hashes del paquete D16.

Impresión en sede: registro de tarjetas, control de canje, acta de sorteo. Resto digital.

## Lecciones de formato para la próxima campaña

- El Admin exige el formato Halloween para manuales de sede: extenso y formal pero claro; el extremo «folleto de 15 págs» y el extremo «ultra-corto» fueron ambos rechazados.
- Regenerar SIEMPRE desde las fuentes del repo (no parchear los DOCX antiguos) y actualizar MANIFIESTO con hashes recalculados.
- Publicar a Drive con conteo exacto por carpeta (los reintentos duplican; ver regla 12 del SKILL.md).

## Deuda estructural restante

C3 roster de sedes participantes · C4 logística antes del 1-nov (el deadline histórico 25-nov NO sirve de lanzamiento) · C5 horario por sede · C6 pie legal · C7 firma/organizador en piezas · C8 tiraje/presupuesto de impresión · C9 responsable PQR · C10 protocolo de urna/acta heredado de octubre por validar.
