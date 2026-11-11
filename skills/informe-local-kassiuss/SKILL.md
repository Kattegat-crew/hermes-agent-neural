---
name: informe-local-kassiuss
description: Use when reporting Kassiuss sales by local.
version: 0.3.0
author: Jonathan Parra, Ragnar
platforms: [linux]
metadata:
  hermes:
    tags: [ventas, kassiuss, maquinas, informes, xlsx, drive]
---

# Informe detallado Kassiuss por local

Generar informes por máquina de cualquier sede que use el formato Kassiuss validado. El código vive en Git, no en memoria ni copiado a la skill. Para otros sistemas POS, inspeccionar el formato y crear un adaptador antes de prometer compatibilidad.

## Cuándo usar
- Ventas de un local, rankings de máquinas, pagos diarios, fluctuaciones y registros Jackpot.
- XLSX de seis hojas y, con autorización independiente, Google Sheet nativo.
- No reemplaza los crons de ventas ni configura publicación automática.

## Prerrequisitos
- Localizar repo vivo marketing-campaign-generator. Ubicación verificada DEV `/root/marketing-campaign-generator`; consultar `git status`, rama/HEAD y origen antes de editar; no clonar ni tocar cambios ajenos.
- Código `modules/kassiuss_report/{dataset,build_xlsx,verify_xlsx,publish_drive}.py`.
- Python con openpyxl existente. En PROD contenedor hermes-agent, intérprete `/opt/data/venvs/ventas/bin/python3` (no usar python default sin verificar).
- Crudos y histórico de ventas ya capturados. PROD `/opt/data/profiles/helmer/scripts/ventas/{crudo,historico.jsonl}`. Acceso solo lectura por SSH; no leer nuevos buzones de clientes sin pedido expreso.
- Pedir sede EXACTA del histórico, prefijo EXACTO del archivo, inicio y fin. No confundir GOLDEN_GAME con GOLDEN_GAME_PACHO.

## Procedimiento
1. Inspeccionar esquema y fuentes; resolver fechas ausentes y correos duplicados, sin elegir silenciosamente el último correo.
2. Con `terminal`, ejecutar desde repo:
   `python modules/kassiuss_report/dataset.py --crudo <dir> --historico <jsonl> --sede '<sede exacta>' --file-prefix <prefijo exacto> --inicio YYYY-MM-DD --fin YYYY-MM-DD --out <dataset.json>`.
   Debe terminar V1/V2 OK para TODOS los días; V1 compara siete campos y V2 cinco. Datos inválidos no se convierten en cero. `--allow-missing-days` solo tras confirmar cobertura parcial; faltantes deben informarse.
3. Reviewer independiente con `delegate_task` al cierre de fase de datos; exigir comparación crudos/dataset, no solo exit 0 del autor.
4. Generar `python modules/kassiuss_report/build_xlsx.py --dataset <dataset.json> --out <informe.xlsx>`; opcional `--config <json>` para paleta. Verificar `python modules/kassiuss_report/verify_xlsx.py --dataset <dataset.json> --xlsx <informe.xlsx>`. Reviewer independiente de celdas, rankings y etiquetas antes de entregar.
5. Entregar archivo real con `MEDIA:/ruta/absoluta/informe.xlsx`. Las seis hojas son RESUMEN, MAQUINAS, JACKPOTS, FLUCTUACIONES, DATOS y GRAFICAS.
6. Drive es OPCIONAL y exige autorización explícita. En PROD el Python del sistema tiene google-auth y el venv ventas tiene openpyxl, pero NO google-auth. Ejecutar publicador con `python3` del sistema y añadir `--verify-python /opt/data/venvs/ventas/bin/python3`; no instalar paquetes para resolverlo. Usar secret materializado vía ActivePieces de la cuenta DUEÑA de la carpeta; refresh OAuth del secret, jamás google_token.json. Nunca imprimir credenciales.
   `python modules/kassiuss_report/publish_drive.py --dataset <dataset.json> --xlsx <informe.xlsx> --secret <secret-drive.json> --folder <id> --name '<nombre>' --create --confirm-write`.
   Para actualizar: sustituir `--create` por `--sheet-id <id> --backup-dir <dir>`; respalda el Sheet anterior antes de sobrescribir. El comando exporta el Sheet y vuelve a verificar su contenido. Reviewer de read-back antes de afirmar publicado.

## Límites y errores conocidos
- La fila Maquinas viene sin Id Mqna: las columnas de total están desplazadas. El subtotal .N/A. no es el total real.
- Pagos corresponde a acumulado diario por máquina, NO a un premio individual; pagos/games NO es ticket de compra.
- Jackpot es registro agregado máquina-día; no inferir premios individuales ni aportes sin verificar significado del campo.
- Una máquina ausente debe figurar vacía, no como cero. Nunca afirmar mes completo si el período termina antes de fin de mes.
- `--overwrite` exige respaldo; no sobrescribir entregables existentes por defecto.
- El glob de crudo `PREFIX__*.html` es EXACTO: GOLDEN_GAME no captura GOLDEN_GAME_PACHO__* ni GOLDEN_GAME_SAN_FRANCISCO__* (verificado 29-sep-2026, 28/28 días con un único match). La ambigüedad solo dispara error con 2+ coincidencias exactas el mismo día; cada HTML identifica su sede en el título interno.
- Si la red falla después de escribir Drive, consultar REMOTE_WRITTEN y el objeto antes de repetir: riesgo de duplicados.
- No cron, push, nuevas dependencias ni generación paga implícitos.
- Etiqueta JACKPOTS A2 debe ser neutra («reportado», no «acumulado aportado»). verify_xlsx.py rechaza el label viejo con exit 1.

## Verificación
- Regresiones `python -m unittest discover -s modules/kassiuss_report -p 'test_dataset.py' -v`.
- Genericidad requiere dos sedes reales distintas y fechas explícitas, sin modificar fuentes.
- Toda fase debe tener reviewer APROBADO; documentar evidencia en el repo, no en memoria global.
- Los hallazgos del reviewer también se revalidan con evidencia directa antes de tratarlos como bloqueantes: el 29-sep-2026 un veredicto APROBADO incluía un falso positivo de mezcla de sedes con prefijo GOLDEN_GAME que se desprobó replicando el generate y comparando fuentes, título del HTML y rosters (ver references/revalidacion-golden-game-2026-09-29.md).
- Estado de aprobación (29-sep-2026): Fase 1 APROBADO, Fase 2 APROBADO (fix A2 neutral aplicado), Fase 3 APROBADO (×2). Suite 19/19 OK. Genericidad demostrada: Pacho 28d/17m/16j, Cachipay 28d/16m/0j, Cachipay 6d/16m/0j, Synthetic-Absence 6d/16m/0j con 1 vacía.
- Referencia `references/operacion.md` para ubicaciones y ejemplo confirmado.