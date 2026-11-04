# Bibliotecas externas de skills de agentes (verificado 26/08/2026)

Paisaje de fuentes de skills utilizables dentro de Hermes. Formato SKILL.md (frontmatter + markdown) es interoperable entre Hermes / Claude Code / OpenCode / OpenClaw; importar = copiar a `/opt/data/skills/<name>/` y validar (skill-auditor / skill-security-auditor: revisar comandos destructivos antes de importar de fuentes no oficiales).

## Hermes (fuente primaria)
- Local: 412 skills activas en `/opt/data/skills/` (índice `SKILLS_INDEX.md`); catálogo total 649 (hermes-skills-hub). Nativas con toolsets/MCP/cron.

## Claude Code / Anthropic
- Oficial Anthropic: ~927 skills (mcpservers.org/agent-skills/author/anthropic). Destacadas: frontend-design (producción-grade, evita estética genérica de IA), artifacts-builder, canvas-design, webapp-testing, brand-guidelines, pdf, docx.
- `travisvn/awesome-claude-skills` — lista curada.
- `alirezarezvani/claude-skills` — 386 skills, 24.9k★, compatible EXPLÍCITAMENTE con Hermes Agent (+Codex, Gemini CLI, OpenClaw, Cursor). Tier POWERFUL: agent-designer, rag-architect, ci-cd-pipeline-builder, mcp-server-builder, pr-review-expert, env-secrets-manager, incident-commander. Categorías: engineering, marketing, product, compliance, research, business ops, finance, productivity.
- `hesreallyhim/awesome-claude-code` — 53k★, directorio general.
- `ComposioHQ/awesome-claude-skills` — integraciones SaaS (Google, Slack, Notion, GitHub).
- `Digidai/product-manager-skills` — 6 dominios, 30+ frameworks PM.
- `nowork-studio/toprank` — 9 skills SEO + Google Ads (Search Console, PageSpeed Insights, Google Ads API), 107★, MIT. Relevante para Web/Ads.
- `sergebulaev/linkedin-skills` — 11 skills LinkedIn (post writer 16 hooks, humanizer, audit), MIT. Relevante para Social/Content.

## OpenCode (SST)
- Docs: opencode.ai/docs/skills — `skill({ name })`, permisos por skill (`permission.skill`), override por agente.
- Plugins NO corren en Hermes; sus skills en markdown SÍ son importables. Relevantes: opencode-agent-skills (loader dinámico, compatible Claude Code + Superpowers), opencode-handoff (handoff entre sesiones), opencode-agent-memory.
- awesome-opencode: directorio de plugins/agentes.

## OpenClaw (VoltAgent)
- Docs: docs.openclaw.ai/tools/skills — Skill Workshop (`list/inspect/evaluate/apply`) = modelo de gobierno de skills (evaluar antes de aplicar) que adoptamos en curadurías.
- ClawHub/ClawSkills: 500+ skills (clawskills.sh); `VoltAgent/awesome-openclaw-skills` en GitHub.

## Agregadoras multi-agente
- `VoltAgent/awesome-agent-skills` — 32k★, 1000+ skills (Claude Code, Codex, Gemini CLI, Cursor…).
- `mcpservers.org/agent-skills` — índice por autor: Anthropic 927 · OpenAI 746 · GitHub 567 · Microsoft 1577 · Vercel 396 · Cloudflare 140 · Google Workspace 99 · Figma 21 · Stripe 18 · Notion 27.
- `JimLiu/baoyu-skills` — 25.3k★: infografías (21×21), cómics de conocimiento, ilustraciones de artículos (Producer/Content).
- `obra/superpowers` — brainstorming / planning / writing-plans / executing-plans (parcialmente ya en catálogo local).

## Criterios de evaluación usados (curar 100+ skills)
| Criterio | Peso |
|---|---|
| Compatibilidad Hermes (SKILL.md importable) | 30% |
| Relevancia módulo/bot | 30% |
| Estructura (frontmatter + pasos + pitfalls + verificación) | 15% |
| Estrellas/adopción | 15% |
| Seguridad (sin comandos destructivos) | 10% |