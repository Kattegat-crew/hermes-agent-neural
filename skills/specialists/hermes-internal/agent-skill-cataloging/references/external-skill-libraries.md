# Bibliotecas de skills de otros agentes — importables a Hermes

Condensado de la investigación del 26/08/2026, al construir un catálogo de 800 skills (100 por bot) para los 8 especialistas de NeuralCrew (Connect, Web, Content, Social, Leads, Ads, Analytics, Producer). Todas las fuentes verificadas vía búsqueda web en esa sesión.

## Fuentes verificadas

| Biblioteca | Repo / fuente | Adopción | Alcance | Compatibilidad Hermes |
|---|---|---|---|---|
| **Corey Haines marketingskills** | `coreyhaines31/marketingskills` | 45.7k★ · 281.9K installs en skills.sh (líder mundial) | 32 skills de marketing: seo-audit, copywriting, ads, ad-creative, cold-email, analytics, attribution, social, video, image, cro, ab-testing | Sí — Agent Skills spec (agentskills.io), agnóstico de agente |
| **VoltAgent awesome-agent-skills** | `VoltAgent/awesome-agent-skills` | 32k★ | 1000+ skills oficiales y comunitarias: marketing (Corey Haines), advertising (Kim Barrett), Baoyu, Typefully, Postiz, SuperCMO, Remotion, fal.ai, WordPress, Figma, Google Workspace | Índice/benchmark; skills individuales importables |
| **alirezarezvani claude-skills** | `alirezarezvani/claude-skills` | 24.9k★ | 386 skills, 116 agents, 7 personas; tier POWERFUL (agent-designer, rag-architect, ci-cd-pipeline-builder, mcp-server-builder, pr-review-expert, env-secrets-manager) | **Lista explícitamente Hermes Agent** entre los agentes soportados |
| **ComposioHQ awesome-claude-skills** | `ComposioHQ/awesome-claude-skills` | — | Integraciones SaaS: HubSpot, Close, Zoho CRM, TikTok, YouTube, brand-guidelines, competitive-ads-extractor, lead-research-assistant, theme-factory | SKILL.md importable; apps vía MCP/API |
| **Baoyu skills** | `JimLiu/baoyu-skills` | 25.3k★ | Infografías (21 layouts × 21 estilos), cómics educativos, ilustraciones de artículos | Importable (varias ya locales: baoyu-infographic, baoyu-comic, baoyu-article-illustrator) |
| **OpenClaw / ClawHub** | `docs.openclaw.ai/tools/skills` · `clawskills.sh` · `VoltAgent/awesome-openclaw-skills` | ~500 skills | Skills comunitarias; **Skill Workshop** (list/inspect/evaluate/apply) como modelo de gobierno de skills | Importable; el Workshop es buen precedente de curaduría |
| **Anthropic oficial** | vía `mcpservers.org/agent-skills/author/anthropic` | 927 skills | frontend-design, accessibility, best-practices, canvas-design, webapp-testing, brand-guidelines, pdf, docx | Importable |
| **Otros autores grandes** | `mcpservers.org/agent-skills` | OpenAI 746 · GitHub 567 · Microsoft 1577 · Vercel 396 · Cloudflare 140 · Google Workspace 99 · Stripe 18 · Notion 27 | Paquetes por vendor | Importable |
| **toprank** | `nowork-studio/toprank` | 107★ | 9 skills SEO + Google Ads (Search Console, PageSpeed Insights, Google Ads API, meta tags, schema, keyword bids) | Web/Ads |
| **LinkedIn skills** | `sergebulaev/linkedin-skills` | MIT | 11 skills de LinkedIn: post writer (16 hooks), humanizer, pre-publish audit, comment/reply, content planner, profile optimizer | Social/Content |
| **OpenCode (SST)** | `opencode.ai/docs/skills` | — | Sistema `skill({name})`, permisos por skill, override por agente | Los **plugins** NO son importables; las skills markdown sí |

## Criterios de evaluación para filas de catálogo

| Criterio | Peso |
|---|---|
| Compatibilidad Hermes | 30% |
| Relevancia módulo | 30% |
| Estructura (frontmatter + pasos + pitfalls + verificación) | 15% |
| Estrellas/adopción | 15% |
| Seguridad | 10% |

## Flujo para construir catálogo de skills por perfil (p. ej. 100 por bot)

1. **Interpretar el requisito:** "100 skills por cada bot" = **POR CADA bot** (8 bots → 800 filas). No agregar a 100 en total. (Corrección recibida del Admin el 26/08/2026.)
2. **Inventariar local primero ([H]):** `ls /opt/data/skills/` y contar `SKILL.md` reales; marcar como [H] solo lo verificado en disco.
3. **Mapear bibliotecas externas por módulo** usando la tabla de fuentes (★ reales + compatibilidad conocida + repos de origen).
4. **Emitir filas** como `| # | Skill | Fuente | ★ | Por qué |` en markdown. Fuentes: [H] local, [CH] Corey Haines, [CP] Composio, [AZ] alirezarezvani, [V] VoltAgent, [OW] OpenClaw, [AN] Anthropic, [B] Baoyu.
5. **Dividir la escritura en trozos < ~8K tokens** (2 archivos por bot: `catalogo-<bot>-1.md` / `-2.md`) para evitar stream timeouts en write_file grande.
6. **Ensamblar** → INFORME.md; convertir a .docx (python-docx; renderizar tablas markdown + membrete) porque **el Admin prefiere Word para informes/planes** (ver `hermes-production-deployment`).
7. **Gobernar:** toda skill externa pasa por `skill-security-auditor` / lectura manual del SKILL.md antes de importar (el ecosistema de skills de terceros es vector de ataque: 1Password "From magic to malware").

## Pitfalls

- No rellenar catálogos con filas "excluida / no aplica" — solo skills reales y útiles.
- Las skills transversales de herramienta (email, web research, testing, deploy, compliance) son parte legítima del set de cada bot: 100/bot exige amplitud más allá del núcleo de 12–16.
- Tensión con la guía "clean profile ~15 skills" (19/08): esa regla aplica a perfiles de oficina/secretaria/gerente; los perfiles de especialista de producción pueden llevar catálogos completos (100).
- Filas de fuentes externas = skills documentadas en esos repos, no instaladas; distinguir "documentada/existe" de "verificada localmente" en el informe (honestidad de evidencia).
- Nomenclatura de archivos `catalogo-<bot>-1/2.md` por bot para ensamblado y trazabilidad limpios.