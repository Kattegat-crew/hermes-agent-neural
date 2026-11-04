---
name: spec-driven-development
description: "Use when writing an OpenSpec spec before coding."
tags: [sdd, openspec, spec, gates, multiagente, roster, gentle-ai]
version: 1.0.0
author: Ragnar
triggers:
  - sdd: spec-driven / SDD / OpenSpec / especificación primero
  - gates: verificación de claims / gate pass / claims / verificación
  - multi-agente: varios agentes / especialistas / roster / módulos en paralelo
  - gentle-ai: conductor / opencode / antigravity / engram / gga
  - propuesta: proposal / propuesta de cambio / change / requerimientos / escenarios
---

# Spec-Driven Development (SDD) — multi-agente

## Qué es

SDD = escribir la especificación ANTES de tocar código, y hacer que el código se escriba contra esa spec — no contra una idea vaga. En sistemas multi-agente es "ultra necesario" (tip @barckcode, 19/08/2026): sin una spec compartida como fuente única de verdad, N agentes en paralelo divergen, se pisan archivos y el trabajo deja de ser auditable.

### Ciclo de un change (OpenSpec)

```
1. PROPOSE   → escribes spec: Expected Behavior + Scenarios + Constraints
2. VERIFY    → los claims del agente se comprueban contra el repo REAL antes de escribir (Gate PASS/FAIL)
3. IMPLEMENT → solo cuando el gate pasó se escribe código
4. REVIEW    → auditoría (lens: riesgo/resiliencia/legibilidad/confiabilidad) + evidencia
```

**El gate es el corazón:** un agente no puede afirmar "asumo que X llama a Y" y escribir 200 líneas sobre una premisa falsa — tiene que verificar el claim en el codebase y que el gate pase antes de codear. Eso elimina el fallo más caro de los agentes: código correcto construido sobre suposiciones equivocadas.

## Harness: gentle-ai v2.3.0 (instalado y verificado en vivo)

`/usr/local/bin/gentle-ai` trae el pipeline SDD/OpenSpec completo. Verificado el 19/08/2026 sobre `/opt/repos/golden-game-landing`:

| Comando | Función |
|---------|---------|
| `gentle-ai sdd-status [change]` | Fase actual, `planning_home` (raíz `openspec/`), `next:` (paso de bootstrap `sdd-new` cuando no hay changes) |
| `gentle-ai sdd-continue [change]` | Routing del dispatcher: qué debe ejecutar el orquestador |
| `gentle-ai sdd-attempt <status\|begin\|finish\|reset> --cwd <repo> --change <change>` | Orquestación acotada del runtime-attempt (también admite `acquire`/`settle`) |
| `gentle-ai sdd-verify-validate --input <path> --requirements <n> --scenarios <n>` | Valida reportes de verificación (gates) sin persistencia |
| `gentle-ai review start\|status\|finalize\|validate\|repair\|mode ...` | Pipeline de auditoría, inventario de gates `authoritative` |

**Bootstrap:** `sdd-status` reporta `store: openspec`, `planning_home: <repo>/openspec`, `next: sdd-new`. Antes de usarlo, crear la raíz `openspec/specs/` + `openspec/changes/` en cada repo activo. Salidas reales y paths en `references/gentle-ai-sdd-cli-verified.md`.

## Diseño de rosters multi-agente on-demand (no un contenedor por módulo)

En un VPS de ~16GB el stack core ya consume ~15.7G. NO crees un contenedor Hermes por módulo de servicio. En su lugar (patrón @mr_r0b0t, 19/08/2026):

- El **orquestador disena el roster de especialistas según la petición**: cada especialista con su soul.md completo, invocado como subagente (delegate) en el momento.
- Solo viven perpetuos: agentes de cliente (front-line) y bots internos del equipo (p. ej. bot del CTO). Los especialistas se activan bajo demanda.
- Los soul.md de los especialistas se guardan como plantillas reutilizables (p. ej. `brain/agent-roster/`), listos para activarse por petición — no como contenedores durmiendo.
- Cada bot = un perfil Hermes (`/opt/data/profiles/<nombre>/`) con config limpia (~15 skills), token de gateway propio (BotFather), acceso según `ACCESS.md`.

## Cómo aplicar en una petición multi-módulo

```
Petición → Ragnar (orquestador) diseña roster
        → agente EXPLORA el repo (claims contra realidad)
        → escribe PROPUESTA (spec) en openspec/changes/<modulo>-v1/
        → GATE PASS (verificado, no inventado)
        → IMPLEMENTA
        → REVIEW (gentle-ai review + GGA)
        → orquestador reporta
```

Incluso para módulos no-code (Content, Social, Ads) se escribe la propuesta: qué se publica, contra qué datos. Para el pipeline "vibecoder" (no-programador con Hermes) el mismo principio con skills: /grill-with-docs (interroga) → /to-spec (transforma) → /to-tickets (divide) → label `agent-ready`.

## Pitfalls

- **Git "dubious ownership" bloquea gentle-ai:** `gentle-ai review status` / `sdd-*` falla sobre repos montados con `fatal: detected dubious ownership`. Fix: `git config --global --add safe.directory /opt/repos/<repo>` (por repo). NO es que el harness esté roto.
- **No existe el comando `sdd-new` en la CLI de gentle-ai (v2.3.0).** `sdd-status` lo cita como `next:` porque es el paso de bootstrap de OpenSpec — se crea la raíz `openspec/` a mano.
- **safe.directory no se hereda entre entornos.** Aplicar de nuevo en nuevos contenedores/VPS.
- **En repos read-only** el SDD no puede escribir `openspec/`; asegurar escritura antes de exigir gates.
- **Los claims se verifican contra el repo, no contra la memoria.** Un claim sin Gate PASS no es una spec — es una alucinación a punto de hacerse código.