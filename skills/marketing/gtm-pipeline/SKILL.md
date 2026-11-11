---
name: gtm-pipeline
description: "Use when running outbound prospecting end to end."
version: 1.0.0
author: Ragnar (NeuralCrew Labs)
license: proprietary
metadata:
  hermes:
    tags: [gtm, outbound, prospeccion, twenty, leads]
    related_skills: [review-multi-experto, seo-geo-launch]
---

# GTM Pipeline — outbound como sistema, no como inspiración

## When to Use

Cargar esta skill cuando la tarea sea conseguir clientes nuevos de punta a punta: definir ICP,
armar lista de cuentas, escribir outreach, o preparar el scorecard semanal. NO usar para un solo
email suelto ni para responder a un cliente existente (eso es soporte, no GTM).

Pipeline de 12 pasos para conseguir clientes nuevos. Cada paso deja un archivo en disco y el
siguiente lo lee: si un paso no produjo archivo, no ocurrió. Dueño operativo: **Ullr**
(leads/Twenty/ActivePieces). El Admin es el operador: define ICP, precio, tono y aprueba envíos.

## Regla de oro

**Un revisor que nunca vio la conversación** juzga cada pieza contra reglas escritas. Sin ese
revisor, ningún copy sale. Y ningún mensaje sale a un tercero sin aprobación explícita del Admin.

## Estructura de trabajo

```
/opt/data/gtm/
  data/            closed-won.csv, closed-lost.csv, customers.csv, open-deals.csv, clients.txt
  outputs/         01_icp.md, 02_voc.md, 03_mercado.md, 04_cuentas.csv, 05_calificadas.csv,
                   06_tiers.csv, 07_personas.csv, 08_emails.csv, 09_review.md, 12_scorecard.md
  reglas.md        ICP, lo que NUNCA diremos, límites de tono y montos
```

`reglas.md` es el equivalente a CLAUDE.md: se carga al inicio de cada corrida, <200 líneas, y se
actualiza cuando el aprendizaje cambia el ICP o el tono.

## Los 12 pasos

1. **ICP desde deals** — comparar ganadas vs perdidas y conservar SOLO los rasgos que separan los
grupos (un rasgo igual de común en perdidas no dice nada). Con pocas deals: tratarlos como
hipótesis y corregir con las primeras 10-20 cuentas. Salida: `01_icp.md`.
2. **Voz del comprador** — minar llamadas/emails reales para extraer las palabras exactas y las
objeciones. Salida: `02_voc.md` con citas verificables.
3. **Tamaño de mercado con fuente** — cada segmento con conteo y fuente citable; empezar por donde
sacar nombres es más fácil. Sin fuente, el número se descarta.
4. **Lista de cuentas** — scraping propio (Playwright/PageSpeed ya en la flota) o fuentes públicas;
EXCLUIR clientes actuales y deals abiertos. Salida: `04_cuentas.csv`.
5. **Calificar con razón escrita** — una razón por fila que explique qué supuesto la puso ahí.
Probar 50 primero, leerlas todas, corregir reglas, recién entonces escalar.
6. **Señales de necesidad** — ofertas de empleo, cambios en la web, expansiones: encontrar LA tarea
que podemos resolver. Ordena en tiers (T1 = mejores). Salida: `06_tiers.csv`.
7. **Personas por cuenta** — 3-5 por cuenta (firma, usa, opina) con línea "por qué es él/ella".
Verificar que el cargo siga vigente antes de escribir. Salida: `07_personas.csv`.
8. **Primer email desde la situación** — la señal decide a quién; el email habla de la situación
detrás de la señal y ofrece algo útil gratis (3 ideas armadas para ESA empresa pueden ser el email
completo). Nunca insultar, nunca superlativos sin dato, nunca adjuntos en el primer contacto.
9. **Revisión adversarial** — subagente fresco que NO vio la conversación, con `reglas.md` como
vara. Si el revisor no puede explicar la oferta en una frase, el email no está claro. Salida:
`09_review.md` con veredicto por pieza.
10. **Respuestas** — clasificar (interesado / no ahora / no / rebote), quitar bajas de inmediato,
borrar respuestas y esperar aprobación del Admin antes de enviar.
11. **Hoja de preparación** — una página antes de cada llamada; cada "no encontrado" es una
pregunta para la llamada.
12. **Scorecard de los lunes** — interested rate = respuestas interesadas / contactados, partido por
segmento y cargo. **Un solo cambio por semana** para saber qué movió el número. Salida:
`12_scorecard.md`.

## Stack propio (adaptación obligatoria)

| Del playbook original | Nuestro equivalente |
|---|---|
| Instantly / lemlist | Twenty CRM + ActivePieces para secuencias |
| ColdIQ (40+ proveedores) | Solo con spend_gate y OK explícito; por defecto, fuentes públicas |
| Apify / Firecrawl | Playwright/PageSpeed/curl propios en DEV |
| folk CRM | Twenty |
| CLAUDE.md | `reglas.md` + skills |

## Límites y trampas

- **De pago:** cualquier proveedor de datos (ColdIQ, Apify de pago, teléfonos) pasa por spend_gate
  con aprobación previa. Un teléfono cuesta ~10x un email: pedirlo solo cuando la cuenta es T1.
- **Volumen de envío:** 2-3 buzones por dominio, 20-30 emails por buzón/día, warmup de 2 semanas
  antes del primer envío. Sin esto, el dominio se quema y no hay segunda oportunidad.
- **Mantenimiento:** el ICP cambia; `reglas.md` y la skill se actualizan o el pipeline se degrada.
- **Falso positivo de calidad:** el scorecard mide respuestas, no emails enviados. Enviar más no es
  progreso.
- **Humano en el bucle:** la lista y los emails los lee una persona antes de escalar; el agente
  prepara, no decide a quién le escribimos.

## Criterios de aceptación por corrida

1. Cada paso con su archivo en `outputs/`, con fecha.
2. Toda afirmación numérica con fuente o etiquetada como hipótesis.
3. `09_review.md` existe antes de cualquier envío.
4. Scorecard con un solo cambio propuesto por semana.
