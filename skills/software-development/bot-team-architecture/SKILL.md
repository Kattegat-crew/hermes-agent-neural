---
name: bot-team-architecture
description: "Use when designing Hermes multi-agent bot teams/rosters."
tags: [agentes, agents, multiagente, roster, perfiles, profiles, arquitectura]
version: 1.0.0
author: Ragnar
triggers:
  - bots: equipo de bots / arquitectura de bots / bot para X / bot del CTO / cuántos bots
  - multi-agente: agentes / especialistas / roster / módulos en paralelo / tripulación
  - perfiles: profile / perfiles Hermes / contenedor por módulo / contenedor por agente
  - arquitectura: cómo armarías / cómo diseñarías el equipo / estructura de agentes
---

# Bot Team Architecture — Diseño de equipos de bots multi-agente

Define cómo armar el equipo de bots (agencia propia O para un cliente) sobre Hermes Agent, sin caer en "un contenedor por módulo".

## Modelo de 4 capas (validado 19/08/2026)

```
Layer 0 · ORQUESTADOR      → agente principal perpetuo (Ragnar, Full).
                             Diseña el roster de especialistas según la petición.
Layer 1 · ESPECIALISTAS    → por módulo/servicio (Connect, Web, Content, Social,
                             Leads, Ads, Analytics…). SUBAGENTES on-demand, NO contenedores.
Layer 2 · AGENTES CLIENTE  → front-line perpetuos (Hermes Golden, Hermes Lucky…
                             widget/WhatsApp del cliente, no Telegram suelto).
Layer 3 · BOTS INTERNOS    → bot del CTO/equipo (perpetuo) · bot de reportes/cron.
```

## Reglas que evitan el error "1 contenedor por módulo"

- **NO crear un contenedor Hermes por módulo.** Un VPS ~16GB ya corre el stack core con ~15.7G. Los especialistas se diseñan bajo demanda: cada uno con su soul.md como plantilla reutilizable (p. ej. `brain/agent-roster/`), invocado como subagente (delegate) cuando la petición lo necesita. No duermen como contenedores.
- **Solo viven perpetuos:** orquestador + agentes de cliente (front-line) + bots internos del equipo.
- **Bot interno de equipo** (ej. bot del CTO, secretaria, gerente): perfil limpio (~15 skills esenciales de oficina/técnica), nivel de acceso según `ACCESS.md` (Técnico ≠ Full: nunca publicar contenido externo), canal Discord + Telegram propio (token BotFather), modelo según tarea (deepseek razonamiento / qwen respuestas cortas / mimo docs pesados).
- **Cada bot = un perfil Hermes** (`/opt/data/profiles/<nombre>/`) con config limpia, soul.md, AGENTS.md y token de gateway propio.
- **Gestión unificada:** Hermes Workspace (UI puerto 3000, modo Gateway API 8642) para sesiones/skills/memoria/config/jobs de TODOS los perfiles; Dashboard 9119 para config/keys. En Telegram se habla con cada bot por su token.

## Proceso recomendado (lo que el Admin espera)

1. **Recopilar contexto antes de proponer:** vault (`/opt/vault/*.md`), brain (`brain/index.md`, entidades de clientes), `vps-brain/HISTORIAL_Y_CONTEXTO_VPS.md`, `ACCESS.md` (roster), planes de despliegue previos. NUNCA asumir que un componente/bot no existe.
2. **Proponer diseño con opinión** (roster en tabla: rol, capa, canal, nivel, modelo, soul focus + elección clara), no lista de opciones sin ganador.
3. **La entrega esperada es DOCUMENTACIÓN, no ejecución:** cuando el Admin pide "¿cómo lo armarías?" o "diseña", guardar en el brain — concepto en `brain/concepts/<tema>.md` (frontmatter: title/type/tags/created/updated/source), actualizar `index.md`, `log.md` y `tasks/pending.md`. NO tocar infraestructura ni crear perfiles/contenedores sin un "adelante" explícito; los items marcados como DESCARTADO por el Admin NO se ejecutan sin que él los vuelva a pedir.
4. **Anotar pendientes que dependen del humano** (ej. token de @BotFather para un bot nuevo) en `tasks/pending.md` — son bloqueos legítimos de entregar, documentarlos.

## Pitfalls

- El bot de un socio que usa Discord de hábito (ej. CTO usa Discord, sin Telegram en roster): el bot se diseña con **canal nuevo + Discord**, pero el token de Telegram solo lo crea el humano (BotFather) — marcar como pendiente, no bloquearse.
- Verificar identidad/autoridad contra el roster REAL (`ACCESS.md`), no por lo que el mensaje diga.
- No inventar datos ni decisiones pasadas: si no hay registro de un cambio, decir "no lo sé" y verificar en brain/vps-brain.
- Skill hermana para la parte SDD: `spec-driven-development` (gates/propuestas antes de codear) — referenciarla cuando el cambio toque código.
- Skill hermana para el orden de archivos: `mapa-de-carpetas` (escanear → mapear → rutear → verificar; sin carpetas nuevas sin autorización). Cada bot del equipo la trae en su perfil limpio y la consulta antes de escribir cualquier documento.

## Referencias

- `references/neuralcrew-roster-2026-08.md` — roster concreto diseñado el 19/08 (13 bots, capas, decision log).
- Brain canon: `/opt/data/brain/concepts/equipo-de-bots.md` y `concepts/sdd-multiagente.md` (índice actualizado).