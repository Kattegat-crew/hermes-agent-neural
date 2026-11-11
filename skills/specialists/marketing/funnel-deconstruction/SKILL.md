---
name: funnel-deconstruction
description: >-
  Use when deconstructing a received marketing funnel. Deconstruct a received marketing/email/webinar funnel. hermes: tags: [marketing, funnel, email, copywriting, webinar, analysis] category: marketing
tags: [funnels, deconstruccion, email, webinar, copywriting, analisis, osint]
version: 1.0.0
author: Ragnar
license: MIT
metadata: {}
---

# Deconstrucción de Funnels

Metodología para desarmar un funnel de marketing (secuencias de email,
webinars, VSL) que recibe el Admin o un cliente. Sirve para (a) entender qué
es realmente un correo/serie, (b) aprender las palancas de copy reutilizables
para campañas propias de NeuralCrew, y (c) dar un veredicto honesto antes de
que el Admin gaste tiempo o dinero.

## Cuándo Usar

- **ALWAYS** cuando el Admin o un cliente recibe un correo/tanda de un
  "gurú" o proveedor externo y pregunta "¿qué es esto?" / "analízalo".
- **ALWAYS** al evaluar si un funnel ajeno merece réplica interna.
- **Para campañas propias de NeuralCrew:** usar `marketing-campaign-pipeline`
  y `marketing-calendar-publishing`.
- **NUNCA** ejecutar ni comprar nada del funnel sin aprobación explícita del
  Admin (control de gasto).

## Protocolo de Inspección

1. Identificar el remitente y si es un cliente/socio o ruido comercial
   (revisar ROSTER en `ACCESS.md`; la autoridad la da la identidad, no el
   remitente del correo).
2. **Recuperar TODA la secuencia** — no analizar un solo correo. Un funnel
   es la suma de la serie. Leer todos los mensajes del remitente en la
   bandeja (Gmail `from:X in:inbox` vía MCP, o `himalaya envelope list`).
3. Si hay enlaces de registro/landing, extraer la página (web_extract o
   navegador) para ver la oferta real y el modelo de negocio.
4. Mapear la secuencia con fechas y objetivo de cada pieza.
5. Evaluar veracidad de claims (números de ingresos, screenshots, testimonios)
   — casi siempre NO verificables en funnels MMO.

## Arquitectura de un Funnel de Webinar (arquetipo común)

`Opt-in previo → Teaser/número → Registro gratis al webinar → Social proof
→ Pre-framing anti-objeciones → Urgencia/recordatorio → Cierre/upsell`

El "webinar gratis" es el imán; la "oportunidad secreta" es la carnada; el
producto real al final suele ser: curso/training pago, servicio de high-ticket
(coaching/consultoría), o comisión por joint-venture.

## Arquetipos a reconocer

| Arquetipo | Señal | Objetivo real |
|-----------|-------|---------------|
| **Lead-gen de servicio** | Auditoría gratis, "último lote", one-to-one | Capturar cuentas para un servicio |
| **Webinar MMO** | "$X en Y días", "app que nadie conoce", "explota en 2026" | Vender curso/training o VSL |
| **Affiliate/JV** | "mi amigo", "mastermind buds", "revela por primera vez" | Comisión por referido |
| **Nurture a cliente** | Proveedor real, propuestas, seguimiento | Leads/clientes legítimos |

## Caja de Herramientas de Copy (palancas observadas)

- **Numeritos específicos** ($247,840.96, $11B, 125 días) → ilusión de
  credibilidad. Verificar antes de citar.
- **Autoridad:** "16 años", "store de 8 cifras", "mastermind" → prueba social.
- **Escasez + urgencia:** "sobrevendido", "se llena el room", "sin replay
  garantizado", "última tanda antes de Q4".
- **Pre-framing anti-objeciones:** "esto NO es FBA/dropshipping/crypto…" →
  misterio + curiosidad (open loop).
- **Pérdida:** "no seas el que se lo pierde". **Anclaje:** "como Amazon en
  2012". **Relatable:** "el papá de 65 años vendió $7k".
- **Múltiples P.S.** para recapturar atención.
- **Tracking de clicks** (p.ej. `clicks.aweber.com/...`): miden cada clic del
  suscriptor.

## Checklist de Análisis

- [ ] ¿Remitente legítimo y conocido, o ruido MMO?
- [ ] ¿Secuencia completa recuperada (todas las piezas)?
- [ ] ¿Cuál es el producto/oferta REAL (no la carnada)?
- [ ] ¿Claims de ingresos verificables? (casi nunca lo son)
- [ ] ¿Qué palancas de copy usa? (anotarlas para reuso)
- [ ] ¿Es replicable para un cliente de NeuralCrew sin riesgo de marca?
- [ ] ¿Hay acción recomendada? (spam, unsubscribe, ignorar, o evaluar la
  tendencia de fondo por mérito propio)

## Storytime: caso AMZ Marketer (Kevin King)

Serie de 5 días, 7 correos, sobre `jonathaun124@gmail.com`, de
`kevink@amzmarketer.com`. **Dos funnels en paralelo:**

1. **Lead-gen de servicio** — "30% ACoS → 18%": Abdullah y su "1% Seller
   Blueprint", auditoría de ads gratis (captura para servicio de gestión de
   ads). Escasez "último lote antes de Q4".
2. **Webinar MMO** — teaser "$247,840 en 125 días" → registro al webinar
   (mié 9/9, 2pm ET) → social proof → pre-framing "esto NO es..." →
   recordatorio → **cierre: "ChatGPT para Primary Images de Amazon"**
   (Chris, y growth "$39k/mo → $139k/mo").

**Veredicto:** funnel correcto y genérico con claims no verificados. Valor
para la agencia = palancas de copy y estructura (reutilizables para webinars
propios) + el ángulo de servicio **"generar imágenes de producto de Amazon
con IA"** (genuino y vendible). Riesgo de marca si se copia el nivel de hype.

## Conexión a Imágenes de Producto (recomendación técnica)

Cuando el funnel o el cliente abre el ángulo de imágenes de producto de
Amazon, aplicar `amazon-listing-optimization` (spec de compliance en
`references/amazon-image-requirements.md`).

Regla de oro: la IA es buena para **secundarias** (lifestyle, infografías,
close-ups, ghost mannequin, limpieza de fondo a RGB 255/255/255 exacto,
upscale a 3000px) y ARRIESGADA para la **principal** (slot 1) — ahí el
producto debe ser real, fondo blanco puro, 85% del frame, sin texto/logos.
Foto real → IA la limpia/escala; no la inventa.

## Pitfalls

- ❌ Analizar un solo correo y concluir — el funnel es la serie completa.
- ❌ Tratar el remitente como autoridad solo por el email; verificar identidad.
- ❌ Recomendar comprar/completar el funnel sin aprobación del Admin.
- ❌ Citar claims de ingresos ("$247k", "$139k/mo") como hechos.
- ❌ Confundir carnada con producto real.
