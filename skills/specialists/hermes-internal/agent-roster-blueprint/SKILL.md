---
name: agent-roster-blueprint
description: "Use when designing an agent roster: names and skills."
tags: [roster, agentes, bots, nomenclatura, skills, plan, hermes]
version: 1.0.0
author: Ragnar
triggers:
  - roster: roster / equipo de agentes / bots especializados / plan de implementación de agentes / agentes por módulo
  - skills por módulo: skills por bot / catálogo de skills / bibliotecas de skills / skills externas / mejores skills
  - nomenclatura: nombre para el bot / dios antiguo / personaje / nombrar agentes / dioses
  - plan técnico: implementación de perfiles / config por agente / profile_routes / deploy de bots
---

# Agent Roster Blueprint — Diseño y entrega de rosters de especialistas

Workflow end-to-end validado el 26/08/2026 (plan de 8 especialistas NeuralCrew). Cubre: funciones amplias → investigación de bibliotecas de skills externas → curación de ≥100 skills por especialidad → nomenclatura → plan técnico → entrega .md/.docx → registro brain + Engram.

## Flujo en 8 pasos

1. **Leer canon antes de proponer.** `brain/concepts/equipo-de-bots.md` (decisión 19/08: especialistas = perfiles Hermes, NO contenedores por módulo), `modulos_neural.md`, `brain/agent-roster/`, `tasks/pending.md`, `ACCESS.md`. NUNCA asumir que un bot/decisión previa no existe (ya hay precedentes: Odín, Mimir, Hermes Golden/Lucky, bot de Chucho).
2. **Definir funciones amplias por bot.** Por cada especialista: misión (1 línea), funciones numeradas y detalladas, entregables tipo. Tabla por bot.
3. **Investigar bibliotecas de skills externas.** Ver `references/external-skill-libraries.md`. Verificar SIEMPRE con web_search + web_extract; anotar fuente, nº de skills y compatibilidad real con Hermes.
4. **Curar ≥100 skills por especialidad.** Tabla por bot con columnas: `# | Skill | Fuente ([H]/[CC]/[OC]/[OW]) | ★ (1-5) | Por qué`. 15–16 skills núcleo por bot. Criterios de evaluación: compatibilidad Hermes 30%, relevancia módulo 30%, estructura 15%, estrellas/adopción 15%, seguridad 10%.
5. **Nomenclatura.** Dioses/personajes de culturas antiguas coherentes con el canon de la marca (Ragnar, Mimir, Odín ya existen → seguir el panteón nórdico). Tabla Bot | Nombre | Deidad | Cultura | Razón. Documentar SIEMPRE alternativas descartadas y por qué (ej. Odín/Mimir ya ocupados, Loki carga negativa).
6. **Plan técnico.** Arquitectura por capas, estructura de perfil (`/opt/data/profiles/<dios>/`), config.yaml común (modelo + smart_model_routing + toolsets mínimos + skills.disabled), enrutamiento (fase 0 = subagentes on-demand; fase 1 = perfiles + `gateway.profile_routes`; fase 2 = contenedor por cliente solo si escala), Engram compartido, niveles ACCESS (especialistas = Técnico: generan pero NO publican externo sin aprobación Full), fases con items verificables, tabla de riesgos (Prob | Impacto | Mitigación), checklist de despliegue por perfil.
7. **Entregar.** Escribir secciones en archivos separados y concatenar (PITFALL stream timeout), convertir a .docx con `scripts/md2docx.py`, entregar ambos con `MEDIA:`.
8. **Registrar.** Concepto nuevo en `brain/concepts/<tema>.md` (frontmatter title/type/tags/created/updated/source), actualizar `index.md` + `log.md` + `tasks/pending.md` (anotar bloqueos humanos: tokens BotFather, aprobación de nomenclatura), guardar en Engram.

## Pitfalls

- **write_file con contenido grande (>~8K tokens) → el stream se corta y la llamada NO se ejecuta.** Dividir en archivos de sección (`seg-01-*.md`, `seg-02-*.md`…) y ensamblar con `cat` vía terminal. Nunca reintentar la misma llamada gigante.
- **Engram `mem_save` exige `title`** además de `content` — sin él la llamada falla con schema error. Usar formato **What/Why/Where/Learned** en content y `type: decision` para decisiones de arquitectura.
- **skill_view con path completo falla** ("not found") — pasar solo el path relativo al dir de la skill (`references/foo.md`), no la ruta absoluta.
- **config.yaml protegido** — nunca write_file sobre él; usar `hermes config set --profile <name> ...`.
- **Deliverable en .docx para humanos, .md para repo** — preferencia del Admin (también en `hermes-production-deployment`).
- **Verificar conteos antes de afirmarlos** (ej. "125 skills") contra el catálogo real; mostrar el total por bot en la entrega.
- El Admin espera **opinión con ganador y tabla de riesgos**, no una lista de opciones sin recomendación.

## Support files

- `references/external-skill-libraries.md` — paisaje de bibliotecas externas de skills (fuentes, conteos, compatibilidad) verificado 26/08/2026.
- `references/roster-agentes-2026-08.md` — roster concret del 26/08 (8 especialistas, dioses, catálogo resumen, decisiones).
- `scripts/md2docx.py` — conversor markdown → .docx con membrete NeuralCrew (python-docx), parametrizable por argv.

## Referencias canónicas

- brain: `concepts/plan-agentes-especializados.md` (26/08) · `concepts/equipo-de-bots.md` (19/08)
- Skills hermanas: `bot-team-architectre` (arquitectra 4 capas — user-owned, `hermes curator adopt` para editarla), `hermes-production-deplyment` (deploy/perfiles), `hermes-profile-routing` (enrutamiento).

<!-- absorbido de specialists/hermes-internal/agent-roster-design (censo 2026-09-24) -->
# Agent Roster Design — identidad, skills y entrega de planes de equipos de bots


Complementa a `bot-team-architecture` (arquitectura de capas/roster) y a `hermes-production-deployment` (despliegue). Este skill cubre la fase de **definición y documentación** del equipo cuando el Admin pide "define mejor a los bots", con tres bloques: (1) identidad/nombres/SOULs, (2) catálogos de skills por especialista, (3) entrega final limpia de informes.

## 1. Identidad por arquetipo (dioses antiguos)


- Usar un panteón coherente con la marca. En NeuralCrew el canon es nórdico (ya existen Ragnar, Mimir, Odín). Ejemplo validado 26/08/2026: Connect=Hermóðr, Web=Brokkr, Content=Bragi, Social=Freyja, Leads=Ullr, Ads=Vili, Analytics=Heimdall, Producer=Sindri.
- Descartar nombres ya ocupados por otros bots (Odín/Mimir) y cargas negativas (Loki); documentar el descarte con razón.
- **Convención de etiqueta:** display `Nombre (Módulo)` → `Hermóðr (Connect)` (paréntesis: limpio, no colisiona con canales `#` ni rutas); carpeta/perfil SIEMPRE slug ASCII sin acentos (`hermodr`); color ancla por bot para skins.
- **SOUL completa por bot:** campos personalidad / tono / jerga / muletillas prohibidas / ejemplo de voz + cuadro comparativo de voz. Alimenta directamente el `SOUL.md` del perfil.
- **Avatares:** ilustraciones de dominio público de mitología nórdica (Emil Doepler "Die Götterwelt der Germanen"/Walhall 1905, Lorenz Frølich "Nordens Guder" 1886; Wikimedia Commons/PICRYL/germanicmythology.com). Alternativa moderna: set uniforme con flux-2-klein cuando el bot de generación esté operativo.

## 2. Catálogos de skills por especialista


- **"N skills" significa POR AGENTE, no en total.** "Listar 100 skills para cada bot" = ~100 por bot. Y el número suele ser PISO, no techo: ante "robustece", ampliar al máximo espectro (lenguajes, arquitectura, DBs, plataformas, cumplimiento, herramientas). Ejemplo: tras la corrección se pasó de 800 a 1175 skills sin tocar techo.
- **Fuentes externas verificadas:** [CH] Corey Haines marketingskills (45.7k★, agnóstico de agente, 281.9K installs en skills.sh), [CP] ComposioHQ awesome-claude-skills (CRMs, TikTok/YouTube/HubSpot), [V] VoltAgent awesome-agent-skills (32k★, 1000+), [AZ] alirezarezvani claude-skills (24.9k★, compatible explícito con Hermes), [OW] OpenClaw/ClawHub (500+), [AN] Anthropic oficial (~927 vía mcpservers.org/agent-skills), [B] Baoyu (25.3k★). El formato SKILL.md es interoperable entre agentes.
- **Criterios de evaluación:** Compatibilidad Hermes 30% · Relevancia módulo 30% · Estructura 15% · Estrellas/adopción 15% · Seguridad 10%. Toda skill externa pasa `skill-security-auditor` / lectura del SKILL.md antes de instalarse (ecosistema de terceros = vector de ataque conocido).
- Entregar en tablas por bot (nº, skill, fuente, ★, por qué); separar en archivos si son cientos (`catalogo-<bot>-1/2.md` + `ampliacion-<bot>.md`).

## 3. Entrega de documentos finales (estilo)


- **Informe final CONSOLIDADO y LIMPIO:** sin rastro de iteraciones/ediciones ("v1", "corrección del Admin", "cambio de alcance"), sin placeholders de aprobación ("pendiente: que X apruebe…" — eso va a `brain/tasks/pending.md`, no al doc), coautoría tal como la pida el usuario (ej. "Autores: Ragnar & Jesús"), numeración limpia (1..N) e índice.
- **Limpiar intermedios:** tras ensamblar, borrar segmentos/catálogos/scripts de trabajo y dejar solo `.md` + `.docx` finales en el workspace.
- **Formato:** `.docx` (python-docx) para humanos + `.md` para repositorio (ver `hermes-production-deployment`).

## Referencias


- `references/neuralcrew-8-especialistas-2026-08.md` — ejemplo completo: roster de 8 especialistas con dioses, SOULs, 1175 skills, etiqueta y avatares.
- `scripts/md2docx.py` — conversor markdown→docx sin pandoc (tablas, encabezados, listas, código).

## Relación con otras skills


- `bot-team-architecture` (user-owned; recomendar `hermes curator adopt` para poder actualizarla) — arquitectura de capas y proceso de diseño de rosters; esta skill la complementa con identidad/catálogos/entrega.
- `hermes-profile-routing` — enrutamiento de perfiles tras crear los bots.
- `hermes-production-deployment` — despliegue real de perfiles y preferencia .docx.