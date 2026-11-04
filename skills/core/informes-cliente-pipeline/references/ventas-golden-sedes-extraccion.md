# Extracción de ventas octubre+ Golden Game por sede (verificado 3-nov-2026)

Fuente: Drive de Golden, carpetas de sede → un .xlsx por sede (AGUA_DE_DIOS, ANOLAIMA, CACHIPAY, EL_CARMEN, PACHO, SAN_FRANCISCO, TUNJA). Descargar con drive API (mime xlsx), leer con openpyxl `data_only=True`.

## Estructura real de las hojas (semanas tipo `01-10 OCT`, `21-31 OCT`, etc.)
- Cada día es un bloque: fila `CASINO GOLDEN GAME` con la fecha en columnas **D/E/F = día/mes/año**; unas filas abajo, fila `VENTA TOTAL` con el valor diario en **columna B**.
- Las hojas MIXTAN años: 2023, 2025 y 2026 conviven en el mismo archivo. Filtrar SIEMPRE por el bloque (mes==10, año==2026), no por el nombre de la hoja.
- `VENTA NETA` ≠ `VENTA TOTAL`: en sedes antiguas la NETA puede ser negativa y no es la cifra de reporte. Usar `VENTA TOTAL`.
- Deduplicar por fecha tomando el **máx** por día (duplicados entre hojas de semanas solapadas).

## Gate de calidad obligatorio antes de publicar cifras
Calcular ratio vs venta consolidada del mes anterior (hoja `METAS` de `VENTAS MENSUALES GOLDEN`, columnas F= sede, H= meta mensual, I= venta a la fecha, K= % cumplido):
- ratio aceptado ≈ **×0,7–×1,5**. Fuera de rango → NO publicar.
- Oct-2026: 5/7 sedes pasaron (Agua de Dios 19,2M ×1,05; Anolaima 33,7M ×1,25; Cachipay 35,1M ×1,00; San Francisco 24,0M ×0,93; Tunja 59,2M ×1,44). **PACHO ×2,19 y EL CARMEN ×1,61 no reconciliaron** — patrón: hojas nuevas con 2 bloques por día (dos turnos/salas) que un max-por-día no detecta. Reconciliar bloque por bloque contra el subtotal semanal de la hoja antes de usarlas.
- El consolidado de la hoja METAS va un mes atrasado (a 3-nov seguía en sept: 202.954.727 / meta 297.000.000 / 68,3%). El mes en curso SIEMPRE se consolida desde las 7 hojas de sede, no desde METAS.

Scripts de referencia (corrida 3-nov): `informes/ventas_golden_oct.json`, `extract_ventas.py`, `extract2.py` en scratch de sesión.

## Consolidado oficial: usar primero la hoja `MM-YY ventas {brand}` del Drive del cliente
- Golden tiene un workbook consolidado propio (`10-26 ventas golden`) con tabs **MATRIZ / DATOS / RESUMEN**: RESUMEN ya trae venta neta por sala, metas, % cumplido, mejor/peor día y **cobertura de reportes** (oct-2026: 282.707.505 vs meta 297M = 95,2%; 213/217 reportes = 98,16%). Si existe este consolidado, es la fuente canónica; la extracción por sede sirve para auditarlo, no para reemplazarlo. Este patrón (`MM-YY ventas X`) es el lugar a revisar primero cada mes.
- En `DATOS`, un día en `0` NO es venta cero: es **día sin reporte**. Identificar días faltantes por sala antes de publicar (Zeus oct-2026: 7, 11, 17 y 23 → ~2,5M faltantes a 633k/día promedio). Reportar siempre cobertura (N/N reportes).

## Trampa: salas renombradas — verificar identidad antes de sumar
- **Zeus = Agua de Dios (misma sala)**: los correos diarios llegan como "Zeus" (renombrada en el pipeline) pero la hoja `METAS` sigue rotulada "Agua de Dios". Verificado comparando día a día (valores coinciden ±1.000). NO sumar ambas como sedes distintas (doble conteo). En entregables usar "Zeus (Agua de Dios)" o corregir el rótulo.
- Regla general: si `DATOS` tiene N sedes y `METAS` lista N sedes con nombres distintos, comparar series diarias de las sospechosas antes de sumar.

## Bre-B mensual (Golden y Lucky) — estructura y receta verificada
- Fuentes en Drive: `Bre-B Golden — Pagos` y `Bre-B Lucky — Pagos` (Google Sheets exportables a xlsx). Cada uno tiene tabs: pagos crudos (`Fecha y hora | Valor | Envía | Cuenta destino | Código`) + **`Informe Septiembre` / `Informe Octubre`** con TOTAL RECAUDADO, PAGOS, TICKET PROMEDIO, PAGO MÁS ALTO y tabla POR DÍA.
- Receta de extracción: secret `/opt/hermes-agent-data/secrets/{brand}-drive.json` (refresh_token) → `google.oauth2.credentials.Credentials` + `Request().refresh()` → Drive `files().export(mime=xlsx)` → `openpyxl(data_only=True)`. Sheets se exporta con `files().export`, NO `get_media`.
- SIEMPRE recompute el mes desde el tab crudo (filtrar fechas `YYYY-MM-*`, parsear `"$ 70.000,00"` con regex strip) y contrastar contra el `Informe` del propio workbook: los informes los arma una persona y pueden quedar desactualizados.
- Lucky NO tiene consolidado de ventas por sede en Drive: sus ventas salen de workbooks por sede (TUNJA, LA CALERA, CHIQUI 1, CHIQUI 2, LA CALERA GARDENS) + `BASE 2026`; el BRE-B sí está consolidado en su propia hoja.
- Cifras Bre-B oct-2026 verificadas (para comparación o gates de ratio): Golden 50.429.800 / 426 pagos / ticket 118.380 (+30,1% vs sept); Lucky 114.503.708 / 861 / 132.989 (−9,7% vs sept).