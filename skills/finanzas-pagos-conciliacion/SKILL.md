---
name: finanzas-pagos-conciliacion
description: Use when operating/auditing la conciliación diaria de pagos.
tags: [finanzas, golden-game, paradise, pagos, conciliacion, prod, whatsapp]
version: 1.0.0
author: Ragnar
license: internal
metadata:
  hermes:
    tags: [finanzas, golden-game, paradise, pagos, conciliacion, prod, whatsapp]
    related_skills: [hermes-cron-health, fleet-profile-forensics, hermes-config-integrity]
---

# Conciliación de pagos de casinos (Golden Game / Paradise)

## Cuándo usarlo
- "¿Cómo va la conciliación de pagos?", "¿le mandaron los mensajes a Nancy/Yulieth?", "¿por qué no se registró la respuesta?", o cualquier auditoría del flujo pregunta→respuesta→golden.db.
- Antes de modificar `preguntas.py`, `respuestas.py`, `respuestas_marca.py` o los crons `pregunta_pagos*`.

Flujo diario: los crons preguntan por WhatsApp qué es cada pago sin clasificar; los perfiles de las recepcionistas aplican la respuesta al DB. Cualquier auditoría ("¿cómo va la conciliación?", "¿por qué no se registró X?") sigue el recipe de diagnóstico de abajo, en orden.

## Mapa de terreno
- Código SSOT en DEV: `/opt/golden-game-landing/finanzas/` (git). Copia desplegada en PROD: `/opt/data/scripts/finanzas/`. PUEDEN DIFIERIR: leer el archivo vivo de PROD antes de diagnosticar desde el repo — el deployed puede estar más adelantado que HEAD.
- DB única para ambas marcas: `/opt/data/finanzas-casinos/golden.db` (`marca` = 'Golden Game' | 'The Grand Paradise Club'). Mapa de tablas: `references/golden-db-map.md`.
- Preguntas: crons `pregunta_pagos.sh` (Golden → Nancy, 16:00) y `pregunta_pagos_lucky.sh` (Paradise → Yulieth, 16:01) → `preguntas.py --db golden.db --marca X`. Corren en modo mes (`--desde` = primer día del mes): la pregunta acumula TODO lo pendiente del mes, no solo el día.
- Desfase estructural: la ingesta de pagos corre ~20:00/20:01 — la pregunta de las 16:00 solo ve pagos CERRADOS del día anterior; los del día en curso no existen todavía. Sin un segundo toque vespertino, la pregunta va siempre 1 día atrás.
- Respuestas: el perfil del receptor ejecuta el gate `respuestas_marca.py --db golden.db --marca <Golden|Paradise> --texto "<respuesta literal>"`.
- Circuito automático: plugin `pagos-gate` (hook `pre_llm_call`) en los perfiles de las recepcionistas, que registra la respuesta ANTES del LLM. Estado: desplegado pero sin disparar jamás — arquitectura, pruebas y diagnóstico en `references/pagos-gate-plugin.md`.
- OJO: los `AGENTS.md` de ambos perfiles aún ordenan usar `respuestas.py` (sin marca, legacy) — corregirlos antes de confiar en que el perfil aplique solo; la pieza correcta existe (`respuestas_marca.py`) y nadie la llama.

## Regla dura — pin por marca
- `pregunta_dia` está indexada SOLO por día: la corrida de las 06:01 (Paradise) pisa la de las 06:00 (Golden). `pregunta_dia_marca` (día+marca) es la fuente autoritativa del mapeo número→pago.
- PROHIBIDO apuntar un perfil a `respuestas.py` (legacy, ciego a marca): aplica la respuesta contra la ÚLTIMA lista escrita del día, así una respuesta de Golden termina clasificando un pago de Paradise. Solo `respuestas_marca.py`.
- Síntoma del pin roto: el `clasificacion_journal` registra un pago cuya marca no corresponde al pagador — verificar siempre el cruce marca↔perfil.

## Recipe de diagnóstico (en este orden)
1. ¿Salió la pregunta? `executions.db` del perfil: fila del job con `delivery_outcome='delivered'` para la fecha (esquema real: skill hermes-cron-health).
2. ¿Llegó respuesta? `state.db` del perfil: `messages` con `role='user'`, filtrando los literales de cron y delegación para aislar mensajes humanos (patrones: skill fleet-profile-forensics).
3. ¿Se registró? `clasificacion_journal` en golden.db: última fila por `pago_id`, cruzada contra la marca del pagador. `despues='respuesta manual'` (sin "gate") = pasó por el script legacy. Journal sin NINGUNA fila del gate pese a respuestas registradas = el plugin `pagos-gate` no está disparando (ver `references/pagos-gate-plugin.md`).
4. Pendientes actuales: `SELECT marca, COUNT(*), ROUND(SUM(monto)/1e6,1) FROM pagos WHERE categoria IS NULL AND duplicado_de IS NULL AND substr(fecha,1,7)='<YYYY-MM>' GROUP BY marca`.

## Backlog y límites
- El modo mes solo cubre el mes en curso: los meses anteriores quedan fuera del ciclo diario y hay que preguntarlos explícitamente en lotes (~15 pagos por mensaje, no uno gigante).
- Las filas con `fecha IS NULL` (~1.100) son del libro histórico (`fuente='libro'`): excluirlas de TODO conteo de conciliación.
- El gate no adivina: categoría 'otros' o desconocida queda como dudoso para que la resuelva el agente — no forzar la escritura de una categoría sin confirmación humana.
