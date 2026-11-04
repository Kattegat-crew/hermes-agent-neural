---
name: reel-stills-production
description: Stills pagados de reels via fal con gate de gasto y costos.
version: 1.0.0
author: Ragnar
metadata:
  hermes:
    category: specialists
    tags: [reels, stills, fal, gate, marketing-campaign-generator]
---

# Reel Stills Production Skill

Producción de stills (imágenes clave) para reels de campañas vía API paga de fal (GPT Image) con el flujo físico obligatorio del repo: dry-run gratis → gate de gasto firmado por humano → llamada live. Cubre la fase de imagen; el video Seedance y la validación pre-gasto viven en otras skills (ver When NOT to Use).

## When to Use
- Producir los stills de una escena/pieza de reel ya aprobada para gasto (después de la preproducción).
- Estimar el costo de un lote de stills antes de pedir autorización.
- Diagnosticar un live que falla aunque el gate ya esté firmado.

## When NOT to Use
- Preproducción gratuita (lint, brief, draft three.js) — skill `reel-preproduccion`.
- Generación de video/animación — Seedance vía monid, no imágenes.
- Logos de marca — NUNCA se generan con IA, se componen en post.

## Prerequisites
- Repo marketing-campaign-generator en DEV — resolver la ruta en vivo (candidatos /host/root primero), `git status`/`pull` pre-flight.
- `.env` del repo cargado con `set -a; . .env; set +a` (FAL_KEY — nunca imprimir el valor).
- Gate `.spend-gate.json` vigente para live (ver Procedure paso 2).

## Procedure
1. **Dry-run SIEMPRE primero** — `scripts/fal_image_client.py` sin `--live` cuesta $0 y devuelve el presupuesto real del still (tamaño, calidad, precio). Validar ahí el prompt antes de gastar.
2. **Gate con firma humana** — el agente NO puede crear ni recrear `.spend-gate.json` por sí mismo; lo escribe el humano. Exige `approved_by` (validado por `is_human_approver`, rechaza agent/bot), `purpose` no vacío, `expires_at` ISO CON offset de zona horaria y ventana ≤ 24 h.
3. **Live** — `--model gpt-image-2 --size 9:16 --quality medium --format png --report-cost`.
4. **Verificación** — abrir/analizar la imagen con visión (no confiar en el exit 0) y registrar el costo real.

## Costos (medidos, sep-2026)
| Config | Costo/still |
|---|---|
| gpt-image-2 · 9:16 (720x1280) · medium · png | $0.0434 (presupuesto dry-run; live aún sin cobrar por falta de saldo) |

## Pitfalls
- Dry-run con prompt de prueba genérico puede fallar o colgar; el presupuesto correcto sale con el prompt real de escena.
- `expires_at` del gate sin offset de zona horaria o con ventana > 24 h → gate rechazado en seco.
- HTTP 403 "Exhausted balance" de fal = cuenta sin saldo, NO problema de gate ni de credencial — bloquea el live aunque todo lo demás esté bien; no reintentar en bucle.
- Prompt de still contract mínimo — incluir siempre "No text, no letters, no logos, no watermarks" y "character locked to reference design".

## Verification
- Imagen descargada y analizada con visión — personaje/geometría/fondo presentes, sin texto ni logos.
- Costo reportado por `--report-cost` registrado.
- Gate expirado o consumido según reglas del repo (no reutilizarlo para un lote no autorizado).

## References
- `references/stills-gpt-image-gate.md` — receta completa CLI + campos del gate + caso del 22-sep-2026.


---

## Procedencia

Absorbido por F3 el 20260923-055337 desde la autoskill `data/skills/specialists/reel-stills-production` (sin versión en git hasta hoy).
El procedimiento se conserva íntegro; el paraguas `video-reel-pipeline` es su punto de entrada.

