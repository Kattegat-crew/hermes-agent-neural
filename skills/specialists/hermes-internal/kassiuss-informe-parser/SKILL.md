---
name: kassiuss-informe-parser
description: "Use when parsing KASSIUSS daily sales emails."
tags: [kassiuss, parser, ventas, email, multicliente, casino]
version: 1.0.0
author: Ragnar
metadata:
  hermes:
    category: devops
    tags: [parser, kassiuss, ventas, email, multicliente]
---

# KASSIUSS Informe Parser Skill

Contrato del correo diario de ventas KASSIUSS y su compatibilidad entre marcas (Golden Game, Lucky Brothers). Verificado con sondeos read-only sobre correos reales el 16-sep-2026.

## When to Use
- Escribir o reparar parsers de correos KASSIUSS (kassiuss_diaria.py y sucesores multimarca).
- Dar de alta una marca nueva que recibe reportes del sistema KASSIUSS.

## Contract
- Sistema compartido - Golden y Lucky reciben reportes del mismo proveedor KASSIUSS. Sender verificado de Lucky - luckybrothers@kassiuss.me.
- HTML IDENTICO entre marcas (sondeo de layout GOLDEN vs LUCKY) - el parser de Golden sirve tal cual para Lucky. Probado con correo real de LA CALERA del 15-sep - fila `023 Maquinas`, Neto $2.841.315 extraído sin cambios.
- Fila `Maquinas` - 13 celdas; los valores de venta salen de los índices [3][4][5][6][7]. Sanidad mínima de fila - >=8 celdas.
- Sanidad aritmética por fila - Neto = Bruto - Pagos - Jackpot. Rechazar la fila si no cuadra.
- El asunto trae el prefijo de marca pegado - normalizar antes de rutear por marca.

## Pitfalls
- Sedes con prefijo compartido - LA CALERA es prefijo de LA CALERA GARDENS. Match EXACTO por nombre de sede, NUNCA por prefijo.
- Sedes Lucky verificadas - LA CALERA, LA CALERA GARDENS, TUNJA ONCE, CHIQUIQUIRA 1, CHIQUIQUIRA 2, FUNZA.
- FUNZA llega irregular (15-sep 10:29, 16-sep no llegó) - el informe diario debe tolerar faltantes y listar pendientes, no asumir cero ventas.
- Backfill de histórico grande (~201 informes en el buzón de Lucky) - tocar rate limit de Gmail, pausar entre lotes.
- Sondeos de buzón - nunca preservar credenciales ni tokens, enmascarar con [REDACTED].

## Verification
- Antes de escribir un parser nuevo, correr el sondeo de layout (read-only) contra un correo real de la marca y confirmar que la fila `Maquinas` cuadra con este contrato. Detalle del sondeo en references/layout-comparativa-golden-lucky.md.