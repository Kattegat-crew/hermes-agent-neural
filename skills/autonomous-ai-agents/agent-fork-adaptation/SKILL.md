---
name: agent-fork-adaptation
description: >-
  Use when forking an AI agent for a new company. Proceso completo para hacer fork de un agente IA existente (Hermes, Codex, Claude Code) y adaptarlo a las necesidades de una empresa. Incluye: análisis de arquitectura, documentación técnica (PRD, TRD), diseño multi-tenant, sistema de módulos/subagentes, y plan de implementación.
tags: [fork, agente, prd, trd, multi-tenant, arquitectura, ragnar]
---

# Agent Fork Adaptation

## Cuándo usarlo

Cuando necesitás hacer fork de un agente IA existente y adaptarlo para un cliente o producto propio.

## Pasos

### 1. Análisis de Arquitectura

1. Clonar el repositorio del agente base
2. Ejecutar `tree` para mapear la estructura completa
3. Leer los archivos clave (entry point, core loop, config, tools, platforms)
4. Generar documento de arquitectura con:
   - Mapa de directorios
   - Clase central (AIAgent)
   - Bucle de conversación
   - Sistema de herramientas (registry, toolsets)
   - Integración de canales (gateway, platforms)
   - Configuración de modelos (providers, fallback)
   - Sistema de memoria (providers, persistence)
   - Sistema de skills (discovery, loading, injection)

**Comandos útiles:**
```bash
git clone <repo> /tmp/<name>-repo
cd /tmp/<name>-repo
tree -L 3
find . -name "*.py" | wc -l  # tamaño del proyecto
```

**Archivos clave a leer:**
- Entry point (`run_agent.py`, `main.py`, `__main__.py`)
- Core loop (`conversation_loop.py`, `agent.py`)
- System prompt (`system_prompt.py`, `prompt_builder.py`)
- Tool registry (`tools/registry.py`, `model_tools.py`)
- Platform adapters (`gateway/platforms/`, `plugins/platforms/`)
- Config loader (`config.py`, `config.yaml`)
- Memory manager (`agent/memory_manager.py`)
- State persistence (`hermes_state.py`, database files)

### 2. Documentación de Marca del Cliente

1. Leer todos los documentos de marca disponibles (Google Drive, Notion, files)
2. Extraer: identidad, misión, visión, valores, paleta, módulos de negocio
3. Crear resumen ejecutivo con la info clave

**Comando para Google Drive:**
```bash
python3 /opt/data/skills/productivity/google-workspace/scripts/google_api.py drive search "<keyword>" --max 20
python3 /opt/data/skills/productivity/google-workspace/scripts/google_api.py docs get <DOC_ID>
```

### 3. PRD (Product Requirements Document)

Crear `/opt/data/<project>/01-PRD.md` con:
- Qué es el producto
- Problema que resuelve
- Módulos del agente (subagentes especializados)
- Planes de suscripción y acceso por plan
- Casos de uso principales
- Requerimientos no-funcionales
- Métricas de éxito

### 4. TRD (Technical Requirements Document)

Crear `/opt/data/<project>/02-TRD.md` con:
- Arquitectura general (monorepo recomendado)
- Adaptación del core (qué se mantiene, qué se cambia)
- Sistema de módulos (subagentes)
- Multi-tenant (DB, aislamiento, billing)
- Canales soportados
- Configuración de modelos
- Sistema de skills (compartidas + específicas)
- Logging y observabilidad
- Seguridad (auth, guardrails, aislamiento)
- Despliegue (Docker compose)
- Roadmap técnico

### 5. Documentos Complementarios

- `03-Flujo-App.md` — Flujo de usuario
- `04-UI-UX-Design-Brief.md` — Especificaciones visuales
- `05-Backend-Schema.md` — Esquema de BD y APIs
- `06-Implementation-Plan.md` — Plan detallado
- `07-Master-Prompt.md` — Prompt para agente IDE

### 6. Prompt Maestro para Generación de Código

Crear `07-Master-Prompt.md` que incluya:
- Todo el contexto del TRD
- Estructura del repositorio objetivo
- Instrucciones paso a paso para el agente IDE
- Reglas de seguridad y calidad
- Criterios de aceptación

## Archivos de Salida

Todos los documentos van en `/opt/data/<project>/` con prefijo numérico para orden.

## Pitfalls

- **Los archivos temporales de subagentes van a `/tmp/`**, no al home del VPS. Siempre verificar dónde se crearon.
- **Permisos**: El VPS corre como usuario `hermes`. Carpetas creadas pueden no ser visibles si no tienen permisos `777`.
- **Google Drive scope**: El script `google_api.py` usa `drive.readonly` por defecto. Para archivos no-editables (markdown, docx), usar `alt=media` download directo.
- **No usar "Nexa"** — el nombre fue cambiado a "NeuralCrew" por conflicto de marca.
- **Monorepo vs Multi-repo**: Para un agente con módulos, el monorepo es preferible (orquestador centralizado, skills compartidas, actualizaciones sincronizadas).

## Verificación

- [ ] Todos los archivos de docs existen en `/opt/data/<project>/`
- [ ] El PRD tiene los 7 módulos definidos
- [ ] El TRD tiene la arquitectura multi-tenant
- [ ] Se identificaron los archivos clave del agente base
- [ ] El roadmap técnico tiene fases con duración estimada
