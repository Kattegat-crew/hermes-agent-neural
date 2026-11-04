<!-- Caso absorbido por F6 lote 4 el 2026-09-23 desde `specialists/hermes-internal/client-agent-soul-survey`.
     Contenido íntegro; original en
     `data/archive/F6_lote4_20260923-161107/absorbidas/`. -->

---
name: client-agent-soul-survey
description: "Encuesta /soul para perfilar clientes y armar su SOUL.md."
version: 1.0.0
author: Ragnar
tags: [soul, encuesta, onboarding, clientes, whatsapp, perfiles, agente]
---

# Client Agent Soul Survey — Perfilar clientes → SOUL.md + skills

Encuesta interactiva de 28 preguntas (6 bloques) que se aplica al DUEÑO del negocio
(cliente de NeuralCrew) por WhatsApp para generar/reemplazar el `SOUL.md` del agente
que atenderá a sus clientes finales, y recomendar skills. Aprobado por Jonathan el
20/08/2026 (versión v3 con bloque de personalidad + técnico-operativo).

## Cuándo usar

- El usuario pide "encuesta para perfilarme", "quiero mi soul", "configurar mi agente"
  (chat con el dueño del negocio, NO con clientes finales).
- Onboarding de un cliente nuevo (Golden Game, Paradise, Lucky Bros, etc.): antes de
  escribir el SOUL del agente del cliente, aplicar esta encuesta.

## Reglas de diseño (correcciones del Admin — respetar SIEMPRE)

1. **NO preguntar lo que ya conocemos** (giro del negocio, sedes, país, compliance).
   Ir directo a lo que el agente NO sabe.
2. **Enfoque técnico-operativo**: documentos y formatos que manejan, dónde los guardan,
   qué aplicaciones usan/quieren conectar, qué automatizaciones requieren, permisos.
3. **Empezar con PERSONALIDAD y TRATO** (bloque 0): cómo quiere que le llamen, tono,
   tratamiento tú/usted, ritmo, emojis, palabras prohibidas. La voz del agente es
   lo primero que el dueño valora.
4. **Formato WhatsApp**: una pregunta a la vez (nunca varias), opciones A-D (selección
   múltiple) o ✏️ para respuesta libre. 1 paso por respuesta.
5. **Validación antes de escribir**: al final mostrar "Esto es lo que entendí de ti"
   y pedir confirmación. NUNCA sobrescribir SOUL.md sin el "sí" del dueño.

## Procedimiento

1. Comando `/soul` (o variante) → presentar inicio y pedir confirmación breve.
2. Recorrer `references/cuestionario.md` bloque por bloque, pregunta por pregunta.
3. Llevar el estado en la sesión (bloque/pregunta/ans); si se interrumpe, retomar donde
   iba, no reiniciar todo.
4. Al final: resumen de validación (ver `references/mapeo-skills.md` para el formato).
5. Con confirmación → escribir `SOUL.md` del perfil (backup antes, `SOUL.md.bak-<ts>`)
   y ofrecer la lista de skills recomendadas.

## Desplegar la skill y el comando /soul en un perfil (gateway)

- Los skills de un perfil viven en `/opt/data/profiles/<perfil>/skills/<cat>/<skill>/`.
  Un skill con `name: soul` en frontmatter genera el comando `/soul` automáticamente.
- Para que el *gateway* lo reconozca como comando y aparezca en `/help`:
  1. Copiar el skill a `/opt/data/skills/<cat>/<name>/` (SKILL.md + references/)
  2. Borrar los snapshots de skills: `/opt/data/.skills_prompt_snapshot.json` y
     `/opt/data/profiles/<perfil>/.skills_prompt_snapshot.json`
  3. Reiniciar el gateway (ver pitfalls) para que re-escanee `get_skill_commands()`.
- Si el agente del perfil responde con el flujo de config de Hermes ("configurar
  modelo/proveedor") en vez de la encuesta: deshabilitar los skills admin en el
  `config.yaml` del perfil con `skills.disabled` (al menos `hermes-agent`) y borrar el
  snapshot. Los perfiles de clientes NO deben llevar skills de configuración.

## Pitfalls

- Perfil creado desde Desktop: puede quedar SIN el bloque `providers:` en su config →
  error "Unknown provider". Copiar `providers` + `custom_providers` + base_url del
  config principal al config del perfil (ver devops/hermes-desktop-remote-backend).
- Si el perfil responde con el flujo de config de Hermes al invocar `/solo`, el skill
  `hermes-agent` está activo — deshabilitar esos skills admin en el perfil.
- NO hacer la encuesta a un cliente final; es para el dueño/operador.

## Verificación

- [ ] Las 28 respuestas completas registradas.
- [ ] Resumen mostrado y confirmado por el dueño.
- [ ] `SOUL.md` escrito solo tras confirmación.
- [ ] Skills recomendadas entregadas al final.

## Referencias

- `references/cuestionario.md` — las 28 preguntas aprobadas (6 bloques).
- `references/mapeo-skills.md` — respuesta → sección SOUL → sugeridas + formato de validación.