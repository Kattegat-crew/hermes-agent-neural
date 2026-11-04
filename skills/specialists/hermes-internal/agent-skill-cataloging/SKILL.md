---
name: agent-skill-cataloging
description: "Use when building a per-agent skill catalog (N per bot)."
tags: [skills, catalogo, catalog, agentes, bot, roster, importacion, docx]
version: 1.0.0
triggers:
  - catálogo: catálogo de skills / lista de skills por bot / skills por especialista / cuántas skills
  - skills por perfil: skills por cada bot / skills por módulo / perfil limpio con N skills
  - rosters con skills: armar equipo de bots + sus skills / plan de agentes con skill catalogs
  - importación: importar skills de terceros / skills de Claude Code / OpenClaw / skills externas
---

# Agent Skill Cataloging — Catálogos de skills por perfil de agente

Cómo armar un catálogo numerado de skills para un agente/rol especializado, mezclando las skills locales de Hermes con las bibliotecas públicas de otros agentes (Claude Code, OpenCode, OpenClaw, API vendors), evaluarlas y entregarlas en el formato que el Admin espera.

## Regla #1 — interpretar el requisito de escala (pitfall crítico)

**"100 skills por cada bot" significa 100 POR CADA bot** (8 bots → 800 filas), NUNCA 100 sumando todos.

- Corrección real recibida del Admin (26/08/2026): se entregó un catálogo de 125 skills "en total" y la respuesta fue *"Eran 100 skills por cada uno de los bots, no en total"*.
- Antes de escribir, confirmar el multiplicador: `N_bots × skills_por_bot = filas totales`. Si el plan pide "N por cada módulo/rol/agente", el número se multiplica por el nº de actores.
- Un catálogo por bot de 100 filas exige amplitud: incluir como parte legítima del set las skills transversales de herramienta (email, web research, testing, deploy, compliance, reportes) además del núcleo de 12–16 del rol. No quedarse solo en el "core".

## Workflow

1. **Inventariar local primero.** `ls /opt/data/skills/` y contar `SKILL.md` reales (`find . -name SKILL.md | wc -l`). Marcar [H] solo lo verificado en disco. No asumir que una skill existe porque esté en la lista del system prompt.
2. **Recopilar contexto previo.** Leer el canon existente antes de proponer: `brain/concepts/equipo-de-bots.md`, `modulos_neural.md`, Vault, roster en `ACCESS.md`. No contradecir decisiones ya tomadas (p. ej. "no un contenedor por módulo", precedentes de nomenclatura).
3. **Mapear bibliotecas externas por módulo.** Usar `references/external-skill-libraries.md` (fuentes verificadas + adopción + compatibilidad). Emitir filas con fuente explícita: `[H]` local, `[CH]` Corey Haines, `[CP]` Composio, `[AZ]` alirezarezvani, `[V]` VoltAgent, `[OW]` OpenClaw/ClawHub, `[AN]` Anthropic, `[B]` Baoyu.
4. **Criterios de evaluación** (tabla en el reference): Compatibilidad Hermes 30% · Relevancia módulo 30% · Estructura 15% · Estrellas/adopción 15% · Seguridad 10%.
5. **Escribir dividido.** Un write_file grande con ~10K+ tokens revienta el stream. Partir en trozos < ~8K tokens (normalmente 2 archivos por bot: `catalogo-<bot>-1.md` y `-2.md`). Se reensambla después con `cat`.
6. **Ensamblar y convertir.** `cat seg-*.md catalogo-*-1.md ... > INFORME.md`; luego .docx con python-docx (script `md2docx.py`: membrete + render de tablas markdown), porque **el Admin prefiere Word (.docx) sobre markdown para informes y planes**. El .md es para el repo técnico; el Word para el humano.
7. **Gobernar la importación.** Toda skill externa pasa por `skill-security-auditor` / lectura manual del SKILL.md antes de entrar a un perfil. El ecosistema de skills de terceros es vector de ataque conocido (1Password: "From magic to malware"). Distinguir en el informe "documentada/existe" (fuente externa) frente a "verificada localmente" ([H]) — no inflar evidencia.

## Entregables

- Catálogo por bot en tablas `| # | Skill | Fuente | ★ | Por qué |`.
- Índice-resumen con matriz bot(skills) y distribución por fuente.
- Informe plano ensamblado (.md + .docx) con: funciones por bot, investigación de bibliotecas, catálogo completo, propuesta de nomenclatura, plan técnico, riesgos.
- Registrar en brain: concepto en `concepts/<tema>.md`, actualizar `index.md`, `log.md`, `tasks/pending.md` (pendientes humanos como tokens/probaciones).

## Pitfalls

- **No rellenar con filas "excluida / no aplica"** — solo skills reales y útiles.
- **Tensión con "clean profile ~15 skills"**: esa regla (19/08) aplica a perfiles de oficina/secretaria/gerente. Perfiles de especialista de producción pueden llevar catálogos completos de 100. No aplicar la regla de perfil limpio a catálogos de especialistas.
- **No sobreescribir `config.yaml` con write_file** (protegido); usar `hermes config set --profile <name> ...` o sed/python vía terminal.
- **Verificar el .docx** tras generar: abrir con python-docx, contar `len(d.tables)` y filas totales (`sum(len(t.rows) for t in d.tables)`), y comparar contra el nº esperado de filas del catálogo (contar `grep -c "^|"` en el .md).

## Referencias

- `references/external-skill-libraries.md` — banco de bibliotecas externas verificadas, criterios y flujo.
- Skills guardianas (user-owned, no editar sin adopt): `bot-team-architecture` (roster multi-bot), `hermes-production-deployment` (perfiles limpios).