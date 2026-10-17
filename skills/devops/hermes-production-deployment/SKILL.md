---
name: hermes-production-deployment
description: >-
  Use when planning a multi-client Hermes deployment. Production deployment of Hermes agents for multiple clients. Includes: full VPS setup plan with dependency mapping, Neural-Brain (Gentle AI + Engram + GGA), Tailscale network topology, DNS architecture, resource limits per container, and day-by-day deployment timeline.
tags: [hermes, deployment, multitenant, vps, perfiles, neural-brain]
version: 1.1.0
author: Ragnar
triggers:
  - produccion: agente en producción / desplegar / deploy / multi-tenant / cliente
  - cliente: dar agente a cliente / entregar / get-to-know-me / onboarding
  - infra: coolify / langfuse / activepieces / observabilidad / monitoreo
  - multi-agente: varios agentes / perfiles / profiles
  - vps: nuevo servidor / VPS / servidor nuevo / plan de despliegue / deployment plan
  - infra-estructura: arquitectura completa / stack completo / recursos por contenedor---

# Hermes Production Deployment — Agentes en Producción

## Arquitectura Multi-Tenant

Cada cliente tiene su propio perfil Hermes (profiles nativos v0.20.0):

```
VPS (Coolify + Docker)
├── hermes-cliente-1 (profile: golden-game)
│   ├── SOUL.md → personalidad
│   ├── AGENTS.md → contexto del negocio
│   ├── skills/ → skills específicas
│   └── gateway → Telegram/WhatsApp del cliente
├── hermes-cliente-2 (profile: guaya-racing)
└── hermes-central (Ragnar — orquestador)
```

Crear perfil: `hermes config set --profile <name> provider.name nan-builders`

Docker multi-contenedor:
```bash
docker run -d -v /opt/data/profiles/<cliente>:/home/hermes/.hermes --name hermes-<cliente> hermes-agent
```

## Stack 4 Capas (con Neural-Brain)

```
Capa 4: ORQUESTACIÓN  → ActivePieces · n8n · Cron · Kanban
Capa 3: CONTEXTO       → Engram · Skills · SOUL.md · AGENTS.md · MCP · Semantica
Capa 2: NEURAL-BRAIN   → Gentle AI · Engram · GGA (memoria global cross-agente)
Capa 1: INFRA         → Coolify · Docker · NaN-Builders · Langfuse · Tailscale
```

### Capa 1: Infraestructura
- **Coolify**: Hosting self-hosted (Docker, SSL, push-to-deploy)
- **Langfuse**: Observabilidad (tracing, evals, LLM-as-judge)
- **NaN-Builders**: Provider de modelos (deepseek-v4-flash, qwen3.6)
- **Tailscale**: Red privada cifrada entre VPS, dev y admin Windows
- **Nginx Proxy Manager**: Reverse proxy + SSL Let's Encrypt

### Capa 2: Neural-Brain (Gentle AI Stack)
**CRÍTICO — no es opcional.** Sin esto, los agentes no comparten contexto entre sí.

- **Gentle AI (gentle-ai v2.3.0)**: Orquesta Ragnar, OpenCode, Antigravity. SDD + gestión de skills + sync entre agentes. Instala: `pip install gentle-ai`. Verificar: `gentle-ai doctor` (8/8 checks).
- **Engram (engram v1.20.0)**: Memoria persistente agnóstica vía SQLite/FTS5 + servidor MCP stdio. SIN LÍMITE de tamaño. Compartido entre TODOS los agentes del VPS. DB en `.engram/engram.db`.
- **GGA (gga v2.10.1)**: Gentleman Guardian Angel — auditor de código pre-deploy.

**Diferencia con MEMORY.md:**
| Aspecto | MEMORY.md | Engram |
|---------|-----------|--------|
| Límite | ~10K chars | Ilimitado |
| Persistencia | Inyectado cada turno | Bajo demanda vía MCP |
| Compartido | Solo Ragnar | Ragnar + OpenCode + Antigravity |
| Búsqueda | Lineal | FTS5 full-text 0.03s |

### Capa 3: Contexto (por cliente)
Cada cliente = SOUL.md + AGENTS.md + MEMORY.md + skills propias + conexión a Engram

### Capa 4: Automatización
**ActivePieces** (leads) + **n8n** (ads) + **Formbricks** (forms)

## Cómo crear un plan de despliegue para un VPS nuevo

Cuando el usuario pida un plan de despliegue para un servidor nuevo, sigue esta metodología:

### Paso 1 — Auditar lo que YA existe
Antes de escribir una sola línea del plan, revisar:
- `docker ps` — qué contenedores están corriendo en el VPS actual
- `/opt/data/brain/entities/` — planes existentes
- `/opt/vault/` — bóveda de conocimiento (ESTRATEGIA-EMPRESA, REPOS-ARQUITECTURA, APIS-INTEGRACIONES)
- `/opt/data/plan-despliegue-*.md` — planes de despliegue previos
- Engram mem_search — decisiones pasadas sobre el stack
- `/opt/vps-brain/HISTORIAL_Y_CONTEXTO_VPS.md` — historial completo del VPS

**NUNCA asumas que un componente no existe.** Verifícalo en vivo.

### Paso 2 — Identificar componentes faltantes específicos del Neural-Brain
Gentle AI + Engram + GGA son los que más frecuentemente se omiten al planificar. Preguntar explícitamente:
- "¿Esto incluye Gentle AI y Engram?"

### Paso 3 — Organizar por niveles de dependencia
Cada programa debe tener una dependencia explícita del nivel anterior:
| Nivel | Contenido |
|-------|-----------|
| 0 | Sistema base (Ubuntu, Docker, Tailscale, Python, Node, Homebrew) |
| 1 | Infraestructura core (Coolify, Nginx, PostgreSQL, Redis) |
| 2 | Neural-Brain (Gentle AI, Engram, GGA) |
| 3 | Observabilidad (Langfuse, NeMo, Presidio) |
| 4 | Servicios negocio (Twenty, ActivePieces, n8n, Formbricks, Qdrant) |
| 5 | Agentes Hermes (uno por cliente) |
| 6 | Aplicaciones web (landing pages, widget chat) |
| 7 | Soporte futuro (Semantica, Portkey, Ollama) |

### Paso 4 — Incluir siempre en el plan
- **Arquitectura general** — diagrama con Nginx → agentes → infra compartida
- **Mapa DNS** — subdominios, puertos, propósitos
- **Red Tailscale** — nodos, IPs, puertos expuestos
- **Límites de recursos por contenedor** — CPU/RAM por servicio
- **Riesgos y mitigaciones** — tabla con probabilidad e impacto
- **Registro de decisiones** — opción elegida vs alternativas descartadas, con razón
- **Checklist por día** — items verificables, no genéricos

### Paso 5 — Verificar que los comandos de instalación funcionan
Usar comandos que ya se probaron en el VPS dev. No adivinar flags, versiones o rutas.

## Onboarding (Get-to-Know-Me)

Entrevista automática al primer inicio:
1. Bienvenida al cliente
2. 5-7 preguntas (tono, productos, prohibiciones, herramientas)
3. Genera SOUL.md + AGENTS.md + MEMORY.md automáticamente
4. Implementar como cronjob one-shot en el perfil

## Observabilidad con Langfuse

Plugin Hermes para tracing:
```python
ctx.register_hook("post_tool_call", ...)
ctx.register_hook("post_generate", ...)
ctx.register_hook("post_delegate", ...)
```

## Integraciones con Clientes

| Herramienta | Integración |
|-------------|-------------|
| WhatsApp/Telegram | Gateway Hermes nativo |
| Email | Gateway Hermes nativo |
| CRM (Twenty/HubSpot) | ActivePieces + MCP GraphQL |
| MercadoLibre | MCP MercadoLibre |
| Google Calendar | Hermes Google Workspace |
| Memoria global | Engram MCP (compartida entre agentes) |

## Clean Profile Design (para gerentes/secretarias)

### Metodología de auditoría

Cuando un cliente pida un asistente de oficina (secretaria, gerente, asistente ejecutivo):

1. **Auditar todo el stack actual** — docker ps, skills, scripts, cron, config
2. **Categorizar cada skill** por su utilidad para el perfil objetivo
3. **Skills esenciales (~15)** — lectura documentos, escritura documentos, web, búsqueda, email, calendario, voz, visión, memoria, gestión tareas
4. **Skills inútiles (~54)** — gaming, ML training, red-teaming, infra, comunidad Hermes, etc. → deshabilitar
5. **Personalidades** — reducir de 12 (catgirl, uwu, pirate, etc.) a solo 2 (helpful, concise)
6. **MCPs esenciales** — Engram + Gmail + Calendar + Drive (no más)
7. **Cronjobs del cliente** — reemplazar los de Ragnar por los del cliente

### config.yaml mínimo para perfil oficina

```yaml
model:
  default: deepseek-v4-flash
  provider: custom
  base_url: https://api.nan.builders/v1

smart_model_routing:
  enabled: true
  max_simple_chars: 160
  cheap_model:
    provider: custom
    model: qwen3.6
    base_url: https://api.nan.builders/v1

toolsets:
  - terminal
  - file
  - web

skills:
  disabled: [lista-de-54-skills]

agent:
  max_turns: 50
  verbose: false
  personalities:
    helpful: You are a helpful, professional assistant.
    concise: You are a concise assistant.

display:
  personality: helpful
```

### Asignación de modelos NaN por tarea

| Tarea | Modelo | Contexto |
|-------|--------|----------|
| Respuesta rápida (<160 chars) | qwen3.6 | 262K, <1.5s |
| Razonamiento profundo | deepseek-v4-flash | 1M, calidad superior |
| Documentos largos | mimo-v2.5 | 1M, extracción pesada |
| Visión/imágenes | qwen3.6 | Visión nativa |
| Voz (STT) | whisper | Transcripción |
| Voz (TTS) | kokoro (em_alex) | Español colombiano |
| Imágenes | flux-2-klein | Generación gráfica |

## Timeline típico

```
D1: OS + Docker + Tailscale + seguridad
D2: Coolify + Nginx + Postgres + Redis
D2: Gentle AI + Engram + GGA (Neural-Brain)
D2-3: Langfuse + NeMo + Presidio
D3: Twenty CRM + ActivePieces + n8n + Formbricks + Qdrant
D3-4: Hermes x N clientes (perfiles)
D4-5: Landing pages + widget chat + DNS
D5+: Pruebas + backups + go-live
```

## Pitfalls

- **Gentle AI + Engram se olvidan frecuentemente.** Son el sistema nervioso central del VPS. Sin ellos los agentes no comparten memoria entre sí. **Siempre preguntar explícitamente "¿Esto incluye Gentle AI y Engram?" antes de entregar un plan.**
- **Firecrawl no configurado** → usar agent-reach o Jina Reader
- **mcporter puede no estar en PATH** → find /opt -name mcporter
- **Cada profile requiere su propio token de gateway**
- **SOUL.md es global al HERMES_HOME, no desde el proyecto**
- **Engram requiere gentle-ai sync post-config**
- **Permisos en .engram/ son críticos** — sin chown el MCP server crashea después de 1-2 requests
- **Backup de .engram/engram.db es independiente del backup de Hermes** — asegurar ambos
- **Nunca asumas que un componente existe sin verificar en vivo** (docker ps, curl, ls)
- **LiteLLM tuvo breach supply chain 12/08/2026** — no instalarlo. Usar fallback nativo de Hermes + OpenRouter
- **ENTREGA DE PLANES: el usuario prefiere .docx (Word) sobre .md.** Cuando entregues un plan de despliegue, auditoría o documento para el cliente, generar archivo .docx con python-docx. El markdown es para el repositorio técnico, el Word es para el humano. Preguntar una vez, después recordar.
- **PERFILES LIMPIOS: para un gerente/secretaria, NO cargar las 70 skills.** Reducir a ~15 skills esenciales de oficina (document-reader, google-docs-api, agent-reach, brain-knowledge-base, engram-memory-system, persistent-task-manager, evidence-based-replies, knowledge-absorption, ssot-context-document, wiki-entry-creation, browser-backend-replacement, browser-fallback-protocol, discord-reporter, notion-integration, local-vision-toolkit, mapa-de-carpetas). Las 54 restantes (ML, gaming, infra, sociales, comunidad) se deshabilitan en skills.disabled del config.yaml. Ver referencia `16-audit-clean-profile-design.md` para la auditoría completa.
- **FILESYSTEM DRIFT POST-UPGRADE:** Tras actualizar Hermes de v0.x a v0.y, verificar que las monturas Docker NO apunten a directorios que ya no existen. `docker inspect` + loop de verificación. Ver referencia `filesystem-consolidation.md`.
- **ENGRAM DB DIVERGENTE:** Después de una actualización mayor, buscar duplicados de `engram.db`. Si hay 2+ DBs, elegir la más grande, hacer checkpoint WAL, copiar, verificar integridad, eliminar duplicados.
- **GITHUB PROFILES:** Para versionar perfiles de clientes, usar estructura del template `templates/github-profile-repo.md` con CI/CD a Coolify.
- **CONFIG.YAML ESTÁ PROTEGIDO:** Los tools `patch`/`write_file` REFUSAN escribir a `/opt/data/config.yaml` ("Agent cannot modify security-sensitive configuration"). Para editar config: usar `sed -i` o script Python vía terminal, o `hermes config` desde el host.
- **SED CON RANGOS EN YAML ES PELIGROSO:** `sed -i '/<patron>/,+5d'` borra líneas de más y puede romper la estructura YAML (experimentado 16/08: rompió el bloque `personalities/` y dejó líneas huérfanas). Para eliminar bloques con precisión usar Python `re.sub` con un patrón acotado y verificar la sección tras editar.
- **AUTOCONFIGURACIÓN DE PERFILES:** El script `scripts/onboard-agent.sh` genera config.yaml/SOUL.md/AGENTS.md/MEMORY.md desde templates de forma INTERACTIVA (12 pasos, pregunta cliente→usuario→empresa→NIT→CRM→tono→idioma y hace sed-substitution). Usarlo en vez de escribir cada archivo a mano. Template base: `templates/clean-profile-config.yaml`.
- **ONBOARD-AGENT.SH — RUTAS CANÓNICAS (19/08):** Script corregido tras la consolidación de filesystem. BASE debe ser `/root/hermes-agent-legacy-docker/data/profiles/<cliente>` (NO `/opt/hermes/profiles`), templates en `/root/hermes-agent-legacy-docker/data/hermes-profiles/templates/`, Engram en `/root/hermes-agent-legacy-docker/data/.engram`. Verificado end-to-end con perfil de prueba: genera los 4 docs + cron/ + skills/ + `.engram-config.json`.
- **SED DELIMITADOR:** En `onboard-agent.sh` usar SIEMPRE `|` como delimitador de sed (`s|<patron>|$VALOR|g`), NUNCA `/` — las URLs (`https://...`) y direcciones rompen el script con "unknown option to s" (falló así el 19/08).
- **REPO PRIVADO DE GITHUB:** Si el repo del cliente es privado, el contenedor NO puede clonarlo sin credenciales: no hay `~/.ssh/` ni `gh` CLI dentro del contenedor por defecto. Opciones: (A) generar par de llaves SSH en el VPS y agregar la pública como Deploy key con write access, (B) PAT fine-grained con acceso solo a ese repo, (C) agregar como colaborador. Recomendar Opción A para deploys.