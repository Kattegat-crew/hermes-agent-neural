---
name: pipeline-informes-ventas-multimarca
description: "Use when onboarding a new brand into sales reports."
tags: [ventas, informes, multimarca, runbook, kassiuss, sheet, pdf]
version: 1.0.0
author: Ragnar
metadata:
  hermes:
    category: devops
    tags: [ventas, informes, multimarca, runbook, cron]
---

# Pipeline Informes de Ventas Multimarca Skill

Runbook para dar de alta una marca nueva en el sistema de informes de ventas (diario + mensual) reutilizando el motor probado de Golden. Caso ejecutado de punta a punta: **Lucky Brothers** (16-sep-2026, F1-F5 corridas; F0 descartada por el Admin al existir ya evidencia del canal). Estado vivo en `brain/ops/informe-mensual-ventas-lucky.md`.

## Motor tal como quedo (multi-marca)

Todo vive en `/opt/data/scripts/ventas/` y la marca se elige con `--marca <k>` o `VENTAS_MARCA=<k>`:

| Script | Hace |
|---|---|
| `cfg.py` + `marcas.json` | Config por marca: buzones/senders, sedes, prefijo, paleta, Drive, chats |
| `captura.py` | Correos KASSIUSS -> `historico.jsonl` + `crudo/` + aviso diario |
| `archivo.py` | Backfill por dia (ventana 4 dias, reintentos, no toca el dedup) |
| `libro.py` | XLSX multi-mes, 4 pestanas/mes, mes vivo delante |
| `publicar.py` | `files.update`/`create` sobre el Sheet (id en `sheet_state.json`) |
| `pdf.py` | HTML + Chrome headless -> PDF membreteado |
| `informe.py` | Cierre mensual (libro + publicar + pdf + linea `MEDIA:`) |
| `aviso.py` | Aviso diario para un destinatario que NO captura, con dedup propio |
| `verif_sheet.py` / `verif_crons_lucky.py` | Verificacion del Sheet real y de los crons |

Datos por marca en `/opt/data/workspace/ventas/<marca>/`.

## When to Use
- Alta de una marca nueva que usa KASSIUSS (o correo de ventas con layout tabular).
- Replicar el sistema Golden (captura, Sheet, PDF mensual) para otro cliente.

## Arquitectura de referencia (Golden, operada)
- Captura - `kassiuss_diaria.py` (529 l.) corre en el perfil dueño de la marca, cada 5 min en ventana manana, escribe `historico.jsonl` + `crudo/<fecha>/`.
- Archivo + libro - `backfill_ventas.py` (ventana 4 dias, 4 reintentos, no toca dedup) + `sheet_build.py` (449 l., XLSX multi-mes, 4 pestanas/mes, mes vivo delante) + `sheet_publish.py` (files.update sobre el MISMO file_id).
- Cierre mensual - `informe_pdf.py` (HTML + Chrome headless + PDF membreteado A4 horizontal) corre en perfil `default` y entrega al Admin.
- Evidencia Golden - 7 sedes, septiembre $124.672.453, Sheet id 1My1fr2fahAWUpcWQuJhgSGCvm69QktFvmYxIad4vfrI, crons 42f099428220 (archivo+Sheet) y 06f7fa1b2ef6 (PDF).

## Fases de alta de marca (orden obligatorio)
- F0 - Prueba de canal - job temporal que manda UN mensaje real a cada chat destino, con OK previo del Admin. Exit 0 NO es evidencia - confirmar llegada en el chat. **Se puede saltar si el canal ya tiene evidencia** (p.ej. el mismo tipo de job ya entrega a diario); entonces el estreno se observa en la primera corrida real y se declara como pendiente de observar.
- F1 - Parametrizar el motor - `marcas.json` (buzones/senders, sedes exactas, prefijo de sede, paleta, secrets gmail/drive, sheet_folder, chats) + los scripts de `/opt/data/scripts/ventas/`. La marca vieja queda INTACTA; validar por paridad contra su salida actual.
- F3 - Crear el Sheet en Drive de la marca (verificar ANTES que no exista - precedente de duplicados 'Fotos Locales' x2). El `drive_secret` debe ser de la cuenta **duena de la carpeta**: el token del cliente suele ser de solo lectura y da `403 insufficientParentPermissions` despues de que el GET pasa.
- F4 - Informe diario (consolidado 07:10 + faltantes cada 5 min) - cada entrega desde el perfil DUEÑO del chat (ver hermes-cron-delivery-routing).
- F5 - PDF mensual membreteado - perfil `default`, entrega al Admin.
- F6 - Cierre - brain + Engram + memoria + ledger + skills.

## Pitfalls
- NO tocar la marca vieja al parametrizar - paridad primero, cutover despues.
- Sedes con prefijo compartido - match exacto (LA CALERA vs LA CALERA GARDENS).
- Sedes irregulares (FUNZA) - el diario tolera faltantes y lista pendientes.
- Backfill grande - pausas por rate limit.
- Contrato del correo - ver kassiuss-informe-parser. Reglas de entrega - ver hermes-cron-delivery-routing. Detalle del sondeo Lucky - references/sondeo-lucky-fases.md.

## Verification
- Cada fase cierra con evidencia observada (mensaje recibido, fila en JSONL, Sheet con datos, PDF generado) - nunca con exit 0.