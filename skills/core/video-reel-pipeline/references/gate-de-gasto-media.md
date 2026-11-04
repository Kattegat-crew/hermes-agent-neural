---
name: paid-media-generation
description: Use when launching any paid generation. Auth, gate, verify.
version: 1.0.0
author: Ragnar
metadata:
  hermes:
    category: devops
    tags: [gasto, autorizacion, fal, monid, elevenlabs, spend-gate, seedance]
---

# Paid Media Generation Skill

Protocolo obligatorio para lanzar CUALQUIER generación que consuma saldo: fal.ai, monid, elevenlabs, gpt-image, seedance, cualquier API de crédito. Nace del incidente del 22-sep-2026 (Engram #840) — se lanzó una prueba sin pedir autorización y se firmó el gate a nombre del Admin; él dejó la cuenta fal sin saldo a propósito para probar si se pedía permiso.

## When to Use
- Antes de lanzar cualquier request pago, aunque sea 1 imagen de prueba a $0.04.
- Antes de escribir o firmar el gate físico del repo (scripts/spend_gate.py).
- Al reportar resultados de generaciones pagas (qué se verificó y cómo).

## Prerequisites
- Repo marketing-campaign-generator en DEV (resolver la ruta viva, no hardcodearla).
- Cliente real del repo con --dry-run disponible.
- Saldo del proveedor verificado. Cuenta sin saldo NO es error de permisos.

## The Hard Rule (orden literal del Admin, 22-sep-2026)
1. Pedir autorización SIEMPRE antes de lanzar cualquier generación paga. Sin excepciones por monto.
2. "¿correcto?", "¿va?", preguntas retóricas = NO son autorización, son consultas.
3. Autorización válida = "Dale" / "Sí" / "Procede" textual del humano en el chat.
4. Al pedir, declarar modelo + nº de piezas + dimensiones + costo estimado.
5. PROHIBIDO firmar el spend_gate a nombre del Admin. La firma la pone el humano real (is_human_approver rechaza agent/ragnar/assistant/bot). Firmar por él = falsificar una autorización.
6. Registrar la autorización con las palabras LITERALES del humano + fecha y canal.

## Procedure
1. Pre-vuelo GRATIS --dry-run del cliente. Confirma modelo, tamaño y costo exacto sin tocar el gate.
2. Verificar los flags del CLI leyendo su ayuda real (el cliente usa --size, no --width/--height; no asumir flags).
3. Pedir autorización en el chat con el desglose del paso 1.
4. Con el "dale" textual, escribir el gate con la frase literal del Admin y ventana ≤24 h (MAX_WINDOW_S = 24*3600 en spend_gate.py).
5. Lanzar la llamada live.
6. Verificar el ARTEFACTO en disco: ls -la + dimensiones reales (file/ffprobe/PIL). Exit 0 + Request ID NO prueban éxito.
7. Verificación visual (vision_analyze) contra el sheet lockeado del personaje — contenido correcto, cero texto/logos/números si el diseño los prohíbe (van en post).
8. Entregar MEDIA: en chat (el Admin preguntó "¿dónde me lo muestras apenas lo tengas?" — la respuesta es aquí y al portal) + copia a PROD (/opt/reels/<marca>/campañas/<año-mm-slug>/reels/<slug>/) + portal, verificando por URL directa del asset.

## Pitfalls
- No reutilizar la hora de un turno anterior — correr date fresco. (Error real: corregir el vencimiento de un gate citando "01:15" cuando eran 18:12.)
- "Exhausted balance" en fal — el request pasa (exit 0, Request ID) y la generación falla. Es bloqueo de facturación, no de permisos. Tras recarga, la misma llamada sale sin re-aprobar si el gate sigue vigente.
- Un gate legacy expirado (.fal-gate.json) puede convivir con .spend-gate.json — verificar estado antes de escribir y avisar si se pisa una autorización viva.
- Verificación en disco ≠ verificación externa — el portal v2 tiene SSO (oauth2-proxy) — curl externo recibe un redirect de 354 bytes a auth.neuralcrewlabs.com y un grep 0 en ese HTML NO prueba que la edición falte. Verificar en el disco del origen (PROD) y por URL directa del asset.

## Verification
- PNG en disco con las dimensiones exactas pedidas (ej. 720x1280) y peso real.
- Visión valida contra el sheet lockeado del personaje (GOLDIE/LUCKY).
- URL del asset en PROD responde 200 con el peso del archivo.

## Reference
- references/fal-quirks-y-casos.md — quirks de fal/monid, precios de referencia, caso completo del incidente y cadena canónica de reels.


---

## Procedencia

Absorbido por F3 el 20260923-055337 desde la autoskill `data/skills/devops/paid-media-generation` (sin versión en git hasta hoy).
El procedimiento se conserva íntegro; el paraguas `video-reel-pipeline` es su punto de entrada.

