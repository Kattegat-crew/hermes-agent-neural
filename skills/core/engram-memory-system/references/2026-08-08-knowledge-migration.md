# Knowledge Migration Session (08/08/2026)

## Context

Migración completa del conocimiento de Ragnar (Hermes agent) a Engram MCP como capa de memoria persistente. Stack: Gentle AI 2.3.0 → Engram v1.20.0 → SQLite.

## Project Setup

Config `/opt/data/.engram/config.json`:
```json
{"project_name": "hermes"}
```

Ejecutar `gentle-ai sync` DESPUÉS de crear el config.

## Observations Saved (9 total)

| # | Type | Title | Sync ID |
|---|------|-------|---------|
| 1 | persona | Ragnar — Chief Orchestrator | obs-f68592fdb809fc1e |
| 2 | persona | Equipo NeuralCrew Labs | obs-388218f8385f4c57 |
| 3 | client | Clientes (GG, Bendabal, Guaya, LB) | obs-f7c898bb7ed01842 |
| 4 | architecture | Infraestructura y Stack | obs-2981529efe66dc60 |
| 5 | knowledge | Brain y Conocimiento Acumulado | obs-854013c86c418018 |
| 6 | architecture | NCA VPS | obs-a59d8a24a52c5987 |
| 7 | integration | Integraciones Externas | obs-870e440aeb649dde |
| 8 | config | Cronjobs y Alertas | obs-ce7890ed6a737035 |
| 9 | workflow | Skills Más Usadas por Categoría | obs-312f66da9e25e6d6 |

## Conflict Judgments (10 relations)

All resolved as `compatible` or `scoped`:
- 6 compatible (distintas categorías)
- 2 scoped (misma categoría pero distintos niveles de detalle)

## Performance

- Engram MCP responded to 15+ consecutive tool calls without crashing (after permissions fix)
- Circuit breaker fully cleared (was parked due to Permission denied, not engram bugs)
- Session ID: `20260808-brain-knowledge-migration`

## What's NOT Yet Migrated

- Brain raw files individuales (notas por cliente en /opt/data/brain/raw/)
- Brain graph entidades (1,708 nodos)
- Full MEMORY.md text (~10K chars)
- Individual skill SKILL.md files