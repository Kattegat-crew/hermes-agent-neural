# Auditoría + Clean Profile Design — 16 Agosto 2026

## Contexto
El usuario pidió un asistente de oficina para múltiples clientes (Golden Game, Lucky Brothers, Bendabal, Guaya Racing). Se auditó todo el sistema y se diseñó un perfil Hermes limpio.

## Metodología de auditoría

### Paso 1: Inventario completo
- `docker ps` — lista contenedores activos en el VPS
- `ls -d /opt/data/skills/*/` — skills locales (70 total)
- `/opt/data/cron/jobs.json` — cronjobs activos (3)
- `ls /opt/data/scripts/` — scripts (34, mayoría obsoletos)
- `ls /opt/data/tools/` — herramientas (2)
- `ls /opt/data/plugins/` — plugins (2)
- `cat /opt/data/config.yaml` — configuración completa

### Paso 2: Categorización de skills
Skills con contenido real: 42. Vacías (0 bytes placeholder): 28.

**Clasificación manual por lectura de descripciones y tamaño:**
- ✅ OFICINA (~15): document-reader, google-docs-api, agent-reach, brain-knowledge-base, engram-memory-system, persistent-task-manager, evidence-based-replies, knowledge-absorption, ssot-context-document, wiki-entry-creation, browser-backend-replacement, browser-fallback-protocol, discord-reporter, notion-integration, local-vision-toolkit
- ❌ INFRA (~15): context-monitoring, context-recovery, loop-detection, loop-protection, pip-install-broken-env, docker-service-tailscale, hermes-workspace-setup, hermes-production-deployment, hermes-ecosystem-tools, hermes-skills-hub, ecosystem-setup, system-onboarding, vscode-ai-extension-configuration, decision-autonomy, hermes-bible, hermes-bible-study
- ❌ TÉCNICO (~8): application-security-review, skill-auditor, external-model-review, graphify-codebase-graph, agent-fork-adaptation, amazon-fba-profitability, amazon-listing-optimization, identity-cleanup
- ❌ BASURA (~12): yuanbao, x-tweet-scrape, colombia-contratos-empresa, red-teaming (vacio), gaming (vacio), leisure (vacio), smart-home (vacio), y las 28 skills vacías

### Paso 3: Diseño del config.yaml mínimo
Ver skill `hermes-production-deployment` → Clean Profile Design section.

### Paso 4: Modelos NaN por tarea
| Tarea | Modelo | Contexto |
|-------|--------|----------|
| Default razonamiento | deepseek-v4-flash | 1M tokens |
| Smart routing | qwen3.6 | 262K, <1.5s |
| Documentos pesados | mimo-v2.5 | 1M tokens |
| Visión | qwen3.6 | Visión nativa |
| STT | whisper | Transcripción voz |
| TTS | kokoro (em_alex) | Voz colombiana |
| Imágenes | flux-2-klein | Generación gráfica |

## Lecciones aprendidas
1. **Gentle AI + Engram no son opcionales** — preguntar explícitamente al planificar
2. **Entrega en .docx** — el usuario prefiere Word sobre markdown para documentos finales
3. **Reducir personalidades** — de 12 absurdas a solo 2 profesionales
4. **MCPs mínimos** — Engram + Gmail + Calendar + Drive, nada más
5. **Skills.disabled es más limpio que no tener skills** — deshabilitar 54 skills técnicamente en lugar de no cargar skills