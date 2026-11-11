# Operación y referencias

Código canónico DEV: `/root/marketing-campaign-generator/modules/kassiuss_report/`.
Inspeccionar Git antes de modificarlo. No tocar DOCX de campaña ni otros cambios ajenos.

## Fuentes reales (PROD)
- SSH `root@100.73.30.29`.
- Contenedor `hermes-agent`, usuario `hermes` uid 10000.
- Crudos `/opt/data/profiles/helmer/scripts/ventas/crudo/YYYY-MM-DD/<prefijo>__<correo_id>.html`.
- Histórico `/opt/data/profiles/helmer/scripts/ventas/historico.jsonl`.
- Python `/opt/data/venvs/ventas/bin/python3`.
- Consultar rutas en vivo: estos paths de contenedor NO son el runtime nativo de DEV.

## Ejemplos
- Pacho: sede `GOLDEN GAME PACHO`, prefijo `GOLDEN_GAME_PACHO`.
- Cachipay: sede `CACHIPAY`, prefijo `CACHIPAY`.
- Prueba de datos 01–28 septiembre 2026: V1/V2 OK, 28 días Pacho (17 máquinas) y Cachipay (16 máquinas).

## Informe Pacho ya publicado
Nombre `Ventas Pacho (Golden Game)`.
Sheet `1n4-nTNP1qxAuZLnmV5octmmWtgnym_ATYRFaG2iKmHA`.
Carpeta `1Y6mPNThkUavCcdwgng-68AGaW5yXrgl7`, Informacion-estadisticas.
Secret materializado de cuenta dueña `/opt/data/secrets/jonathan-drive.json`.
Es una referencia histórica, NO el destino por defecto de otras sedes; solicitar carpeta/cuenta al publicar.
Nunca guardar tokens ni valores del secret en esta skill.

## Seguridad de operación
- Probar datos e informe sin red; publicación exige autorización adicional.
- Si se copia código DEV a PROD para ejecutar, usar carpeta aislada y restaurar uid 10000; nunca pisar scripts de Golden/Lucky existentes.
- Instalar paquetes, activar crons y push a GitHub no están incluidos.
- Si hay un cambio de código, leer archivo justo antes de parchear, pruebas + diff + reviewer.
- Revisar fechas omitidas, máquinas ausentes y alcance del período en la entrega.
