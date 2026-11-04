---
name: casino-campaign-content
description: "Use when writing casino campaign scripts or copy."
tags: [casino, bingos, guiones, copy, reels, coljuegos, voz-de-marca, campanas]
---

# Contenido para campañas de casinos Colombia (NeuralCrew)

Aplica a: reels por sede, posters, captions, stories y test de arte premium para Bingo Millonario y campañas futuras de Golden Game / Lucky Brothers.

## Voz de marca (corrección del Admin Jesús, 26/08/2026 — primera clase)
- **Tuteo con cariño de pueblo, "casi coqueto"**: "a ver si esa suerte que tiene tu pueblo, te la juegas tú", "te guardo cartón", "mijo". **Nunca ustear, nunca folleto corporativo.**
- Coquetería justa y elegante (+18 mediante) — sin pasarse de lanza, cero pasteloso.
- Frases cortas, ritmo de conversador de pueblo; cierre con **picada memorable** (doble sentido pueblo/suerte) que pueda vivir sola en la tapa del reel.
- En posters: máximo 3 líneas con jerarquía — cifra, fecha-hora, CTA. Poco texto hace que se vea caro.

## Estructura de guion validada (30s, 9:16)
| Tiempo | Beat | Regla |
|---|---|---|
| 0-3s | ① Dato curioso del pueblo | Debe ser **VERIFICABLE con fuente** (Wikipedia/AGN/Javeriana/El Espectador). Si no hay fuente, no va. Overlay con la cifra estrella desde el segundo 0 (40% del consumo es sin sonido). |
| 3-12s | ② Conexión casino | Incluir **ambiente** (comida, bebida, música, mesa con amigos), no solo máquinas. "El bingo es la excusa, la experiencia es el plan." |
| 12-20s | ③ Bingo — premio TEMPRANO | Acumulado + regla de 53 balotas + "rueda +$400K". El cliffhanger "¿CAERÁ CON 53 O MENOS? 👀" en pantalla. |
| 20-30s | ④ CTA | Hora flexible ("llegas cuando quieras", escalonado) + cartón gratis + picada de cierre. |

**Legal SIEMPRE en toda pieza:** `+18 Juego responsable | Regulado por Coljuegos`.

## Datos de la campaña (no asumir — verificar contra fuente de verdad)
- Fuente de verdad = `campaign.yaml` (contrato) y **T&C v3**, no el plan viejo. Los T&C dicen **"desde las 5:00 p.m., escalonado en tandas de 15-20 balotas/hora"** — el "viernes 7PM" del plan de agosto quedó obsoleto.
- Verificar hechos contractuales leyendo el docx directamente: `zipfile` → `word/document.xml` → regex sobre el texto plano (funciona para confirmar horarios, montos, cláusulas sin dependencias).
- ⚠️ **Heridas reales de los pueblos**: el lazareto de Agua de Dios es memoria dolorosa — tocar el agua y la música (orgullo), jamás la lepra como gancho.
- Episodicidad: la serie "Cada pueblo tiene su historia" usa **misma fórmula de apertura**, solo cambia el pueblo (plantilla de 4 tiempos, no pieza suelta).

## Referencias
- `references/fal-hero-prompt-matrix.md` — disciplina para tests de modelos de imagen (una variable por render, zonas de aire del compositor, negativos fijos, criterios de pase).

## Producción en equipo
- Reel y poster comparten idioma: overlays anclados por spec común (contador de acumulado + balota 53, esquina inferior-izquierda). Verificar que los assets entregados existen en disco antes de confirmar recepción.
- Aprobaciones con firma nominal ("Aprobado G1 —Jesús") — el chat de Desktop no distingue autores; la trazabilidad vive en doc de guiones + `04-aprobadas/` + manifest (`aprobada_por`).
- Los logos van como **capa del compositor**, nunca quemados en arte generado.
