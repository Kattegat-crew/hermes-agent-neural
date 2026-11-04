---
name: client-agent-onboarding
description: Perfilar clientes y generar SOUL.md vía /soul por WhatsApp.
version: 1.0.0
author: Ragnar
triggers:
  - soul: /soul / encuesta / perfilame / configurar mi agente / get-to-know-me
  - onboarding: dar agente a cliente / perfil nuevo de cliente / questionário
metadata:
  hermes:
    tags: [soul, onboarding, cliente, whatsapp, encuesta, agente]
    category: communications
---

# Client Agent Onboarding — Cuestionario /soul y generación de SOUL.md

Clase de trabajo: cuando un cliente (Golden, Paradise, Lucky, Guaya…) recibe un
agente Hermes y hay que perfilarlo para generar su `SOUL.md`. El mecanismo es
una entrevista interactiva **por WhatsApp** (comando `/soul`) con 28 preguntas
en 6 bloques; al final se valida un resumen y SOLO tras confirmación se
reescribe el SOUL y se recomiendan skills. Adaptación (no copia) del skill
comunitario `get-to-know-me` de @mathieuhq (30 preguntas; el original no tiene
repo público — ver brain/raw/2026-08-08-twitter-mathieuhq-get-to-know-me-skill.md).

## Reglas de diseño del cuestionario (aprobadas por Admin 20/08/2026)

1. **NO preguntar datos que ya conocemos** (tipo de negocio, NIT, sedes,
   promociones genéricas). Prestar solo lo técnico-operativo que el agente
   NO sabe: con qué documentos trabaja, dónde los guarda, qué integraciones
   quiere, qué automatizaciones requiere, nivel de acceso, canales.
2. **Primero personalidad y trato** (bloque 0): cómo quiere que lo llamen,
   tono (formal/cercano/ejecutivo), tú/usted, ritmo (directo/conversacional),
   emojis, frases prohibidas. El usuario lo pidió explícitamente al inicio.
3. **Formato WhatsApp**: una pregunta a la vez; opciones A-D (el dueño responde
   la letra) o ✏️ (respuesta libre). Aprovechar encuestas/opciones del bridge.
4. Al final: resumen "Esto entendí de ti" → el dueño confirma o corrige →
   recién ahí escribir SOUL.md. **Nunca sobrescribir SOUL sin confirmación.**

## Implementar el comando /soul en un perfil

El comando se auto-registra con una **skill cuyo `name:` coincida** (no es
`quick_commands`, que solo hace aliases de comandos existentes):

- Crear `profiles/<cliente>/skills/communications/soul/SKILL.md` con
  `name: soul` en el frontmatter → `scan_skill_commands()` genera `/soul`.
- SKILL.md del perfil → flujo de la encuesta (una pregunta por mensaje, estado
  por sesión, resumen, validación).
- `references/cuestionario.md` → el cuestionario completo, copiado desde
  `templates/cuestionario-soul.md` (base de este skill).
- `references/mapeo-skills.md` → mapa respuesta → sección SOUL → skills.
- Se dispara por el comando y por variantes en texto ("quiero configurar mi
  agente", "comienza la encuesta").
- La skill del perfil debe quedar legible por el usuario del gateway
  (uid hermes: `chown -R 10000:10000` tras crearla desde el serve).

## Flujo (para el agente)

1. Detectar `/soul`/variante en el chat del **dueño**, no con clientes finales.
2. Presentar inicio y arrancar bloque 0..5 pregunta a pregunta.
3. Guardar respuestas; bloque interrumpido → retomar donde quedó (no reiniciar).
4. Resumen de validación con la recomendación de skills (según mapa).
5. Con "sí": escribir SOUL.md y entregar lista de skills a habilitar.

## Verificación

- [[ ]] 28 respuestas recopiladas (6 bloques completos).
- [[ ]] Resumen mostrado y confirmado por el dueño.
- [[ ]] SOUL.md escrito SOLO tras confirmación.
- [[ ]] Skills recomendadas listadas y opción de habilitación ofrecida.