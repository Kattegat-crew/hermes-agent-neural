# NeuralCrew Roster — diseño del equipo de bots (19/08/2026)

Detalle de sesión. Canon: `/opt/data/brain/concepts/equipo-de-bots.md` (actualizado 19/08).

## Roster diseñado (13 bots)

| # | Bot | Capa | Canal | Nivel | Modelo | Alma (soul.md focus) |
|---|-----|------|-------|-------|--------|----------------------|
| 0 | Ragnar | 0 Orquesta | Telegram+Discord+Workspace | Full | deepseek-v4-flash (1M) | Orquesta, diseña soul.md de especialistas |
| 1 | Connect | 1 Especialista | (subagent) | por-petición | qwen3.6 | WhatsApp/voice, multi-canal |
| 2 | Web | 1 Especialista | (subagent) | por-petición | deepseek | landing, SEO técnico, código |
| 3 | Content | 1 Especialista | (subagent) | por-petición | mimo-v2.5 (1M) | copy, blogs, guiones |
| 4 | Social | 1 Especialista | (subagent) | por-petición | qwen3.6 | posts, scheduling, comunidad |
| 5 | Leads | 1 Especialista | (subagent) | por-petición | deepseek | scoring, CRM |
| 6 | Ads | 1 Especialista | (subagent) | por-petición | qwen3.6+deepseek | Meta/Google, A/B |
| 7 | Analytics | 1 Especialista | (subagent) | por-petición | deepseek + visión | dashboards, ROI |
| 8 | Hermes Golden | 2 Cliente | widget + WhatsApp casino | consulta | deepseek | "asistente de Golden Game" |
| 9 | Hermes Lucky | 2 Cliente | widget + WhatsApp casino | consulta | deepseek | "Bienvenido a Lucky Club" |
| ★ | Bot de Chucho (CTO) | 3 Interno | Telegram nuevo + Discord (Jemadiar) | Técnico | deepseek-v4-flash | Explica paso a paso, sin codear |
| ops | Bot reportes/cron | 3 Interno | Telegram canal dedicado | solo-lectura | qwen3.6 | pico y placa, alertas, resúmenes |

## Decision log (19/08)

- **Tema:** Chucho = Jesús Díaz, CTO de NeuralCrew Labs (Discord: Jemadiar), no sabe programar, usa Discord, explica paso a paso, español. Sin Telegram en el roster → el bot del CTO se diseña con canal Telegram + Discord; el token de Telegram lo crea el humano vía BotFather (quedó en `tasks/pending.md`).
- **No contenedor por módulo:** 7 contenedores dedicados no caben en ~15.7G core/16G. Especialistas = subagentes on-demand con soul.md plantilla.
- **Entrega = documentación:** el Admin pidió "¿cómo armarías el equipo?" → se guardó como diseño en brain, NO se ejecutó. Bootstrap `openspec/` en golden-game-landing y ai-platform marcado **DESCARTADO por Admin** — no ejecutar sin que vuelva a pedirlo.
- Pendiente humano:`BotFather` token para el bot de Chucho (solo el humano lo crea).

## SDD conexo (verificado en vivo 19/08)

`/usr/local/bin/gentle-ai` v2.3.0 trae el pipeline SDD/OpenSpec completo. `gentle-ai sdd-status` → `store: openspec`, `planning_home: <repo>/openspec`, `next: sdd-new` (crear `openspec/specs/` + `openspec/changes/`). `gentle-ai review status` → inventario `authoritative`, `clean`. Pitfall: `git config --global --add safe.directory /opt/repos/<repo>` para "dubious ownership". Detalle completo en skill `spec-driven-development`.