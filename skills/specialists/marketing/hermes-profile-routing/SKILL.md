---
name: hermes-profile-routing
description: "Use when routing several Hermes profiles on one channel."
tags: [perfiles, profiles, routing, gateway, whatsapp, telegram, bots, canal]
version: 1.0.0
author: Ragnar
triggers:
  - perfiles: perfil / profiles / varios bots / un bot por cliente / mismo canal varios agentes
  - bot mode: bot mode / bots tab / new agent / duplicate bot / agent inbox
  - routing: enrutar mensajes / un número para varios / puente orquestador / línea por bot
  - whatsapp multi: un solo whatsapp / un número / varios perfiles whatsapp
---

# Hermes Profile Routing — Bots, perfiles y un canal para varios agentes

Cómo funciona la relación bot↔perfil y cómo atender a varios agentes desde UN solo canal (WhatsApp, Telegram, etc.) sin líneas/bridges por bot. Verificado 19/08/2026 sobre Hermes v0.20.0 (2026.8.3) y los artículos de Bot Mode de @IBuzovskyi y @shannholmberg (18–19/08/2026).

## Semántica núcleo (lo que hay que explicar al Admin)

- **Un bot ES un perfil Hermes.** Bot Mode (Hermes Desktop, ~18/08/2026) no añade un core nuevo: es una vista de los perfiles que ya existen bajo `~/.hermes/profiles/<nombre>/` (config, memoria, skills, credenciales, historial aislados). "New Agent" crea un perfil; "Duplicate" clona TODO (config + SOUL.md + skills + memoria) — el patrón oficial es empezar cada bot nuevo duplicando el mejor existente y cambiando el SOUL.md (30 segundos).
- **Un perfil puede existir sin ser "bot"** (CLI / dashboard / API): bot es presentación en Desktop, no un tipo distinto.
- **Perfiles separados = agentes distintos.** Cada perfil tiene su propia soul/memoria/skills. No es "el mismo Ragnar con dos caras": si se crea un perfil por persona, son agentes con almas potencialmente distintas. Un solo perfil compartido por varias personas = el mismo agente, con conversaciones separadas por sesión (`group_sessions_per_user`).
- **Otras piezas de Bot Mode:** Advanced Create con Skill Hub (skills por bot, no instalación global), per-bot model pin, Manage Groups (agrupar bots por proyecto), Agent Inbox (protocolo en SOUL.md para que los bots se mensajeen y hagan handoff), "company brain" (contexto compartido legible por todos los bots).

## Un solo canal sirviendo a varios perfiles: gateway.profile_routes

El gateway de Hermes enruta por perfil a nivel de chat. Config en `config.yaml`:

```yaml
gateway:
  profile_routes:
    - name: jonathan-wa
      platform: whatsapp
      chat_id: "43001262956766@lid"
      profile: ragnar
    - name: chucho-wa
      platform: whatsapp
      chat_id: "573166910728@s.whatsapp.net"
      profile: chucho-cto
    - name: cliente-golden
      platform: whatsapp
      chat_id: "<número-de-cliente>@s.whatsapp.net"
      profile: golden-game
```

- Implementación: `gateway/profile_routing.py` (matcheo jerárquico: thread > chat_id > guild > default) + `_resolve_profile_home_for_source` / `_resolve_profile_for_key` en `gateway/run.py` y `gateway/session.py`. El motor es **agnóstico de plataforma** aunque el docstring del archivo solo mencione Discord — aplica a WhatsApp con `chat_id` (`@s.whatsapp.net`, `@lid`).
- Clarificación de latencia: `profile_routes` = UN salto LLM (el del perfil destino). Un "orquestador-puente" custom = DOS saltos (puente decide + bot responde) — desaconsejado salvo necesidad real.
- Sin conflicto de sesión: a diferencia de dos bridges sobre el mismo número (Baileys → `440 conflict loop`), el routing es lógico dentro del mismo gateway.

## Limitaciones honestas (verificar antes de prometer)

- La allowlist del bridge (`WHATSAPP_ALLOWED_USERS`) sigue siendo global al número; el routing decide perfil, no autorización.
- Conversaciones de distintos perfiles se procesan por turno (secuencial), no en paralelo.
- El matcheo WhatsApp de `profile_routes` NO está documentado oficialmente (la docstring cita Discord/guilds) — hacer una prueba real en sandbox antes de producción (crear perfil de prueba + ruta para un chat y ver qué perfil responde).

## Pitfalls

- No prometer "un número por bot" ni "bridge por perfil" sin haber evaluado `profile_routes` primero — es la respuesta con evidencia a esa pregunta frecuente.
- Al buscar recursos del equipo sobre este tema, distinguir lo creado internamente (repos Kattegat-crew, scripts onboard-agent) de lo compartido externamente (canales "Links de X" / "Repos Git", Notion) — el Admin distingue ambos y espera precisión.

## Referencias

- Brain canon: `/opt/data/brain/concepts/equipo-de-bots.md` (roster 13 bots, 19/08) · `vps-brain/HISTORIAL_Y_CONTEXTO_VPS.md` (ruteo de modelos/contexto).
- Skills hermanas (user-owned; recomendar `hermes curator adopt` para poder actualizarlas desde sesiones cura):
  - `bot-team-architecture` — diseño de rosters multi-bot (4 capas, capas 19/08).
  - `whatsapp-bridge-operations` — bridge Baileys, allowlist, grupos, 440 conflicts, s6 restart.