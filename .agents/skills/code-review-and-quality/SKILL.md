---
name: code-review-and-quality
description: "Use when reviewing a diff before merge across all axes."
tags: [code-review, quality, security, testing, performance, merge]
phase: review
domains:
  - review
  - security
  - testing
  - performance
stacks:
  - any
allowed_agents:
  - reviewer
  - lead
  - developer
surfaces:
  - diff-review
  - quality-gates
skill_source: built-in
origin: null
status: active
---

# Code Review And Quality

## Purpose

Route every code review through one canonical policy and only the profiles that
match the changed surface and declared architecture. This file is an entrypoint,
not a second source of review rules.

## Required Loading Sequence

1. Read [`references/review-policy.md`](references/review-policy.md) completely.
2. Always activate the `core` policy.
3. Activate the generic backend and/or frontend profile from the changed
   surface.
4. Activate a strict architecture profile only from an explicit declaration in
   the task, applicable repository instructions, an ADR, a specification, or
   architecture documentation.
5. Treat file names and folders only as corroborating evidence; layout alone
   does not activate a strict profile.
6. Report `profile_resolution`: selected profiles, omitted profiles, evidence
   for selection, and fallback used when architecture is not declared.
7. Apply the findings and final-output contracts from the canonical policy.

## Profile Routing

### Generic backend

Read
[`references/profiles/backend.md`](references/profiles/backend.md) for server,
worker, consumer, persistence, backend API, or server-side integration changes.

### Declared Clean/DDD/hexagonal/CQRS backend

Read
[`references/profiles/backend-clean-ddd-cqrs.md`](references/profiles/backend-clean-ddd-cqrs.md)
only for the parts of Clean Architecture, DDD, hexagonal architecture, or CQRS
that the repository or task explicitly declares.

### Generic frontend

Read
[`references/profiles/frontend.md`](references/profiles/frontend.md) for web,
mobile, desktop, UI, client state, navigation, local storage, or client network
changes.

### Declared Clean/layered frontend

Read
[`references/profiles/frontend-clean-layered.md`](references/profiles/frontend-clean-layered.md)
only when a layered/Clean client architecture is explicitly declared.

## Contextual Adaptation

When no strict profile is declared:

- preserve correctness, dependency direction, boundary clarity, testability,
  replaceability, and explicit contracts;
- translate those principles into the project's actual modules, services,
  stores, hooks, components, controllers, adapters, or other boundaries;
- follow applicable local instructions, ADRs, and canonical examples;
- do not require DDD building blocks, Clean layers, CQRS, repositories, value
  objects, use-case classes, or specific folder/naming conventions;
- do not treat personal preference as architecture evidence.

## Optional Supporting Skills

Load `security-and-hardening`, `performance-optimization`,
`test-driven-development`, or `debugging-and-error-recovery` only when the diff
or evidence activates that risk. Supporting skills may deepen an axis but may
not redefine the canonical policy's causality, stage, verdict, or blocking
rules.

## Modo de Revisión Paralela en Dos Ejes (Estándares vs. Especificación)

Al realizar revisiones exhaustivas de diffs, ramas o pull requests, dispara dos subagentes de revisión en paralelo con contextos aislados para evitar sesgos de confirmación:

### Eje 1: Subagente de Estándares (Standards Sub-agent)
Evalúa el cumplimiento de las normas del repositorio y la línea base de los 12 olores de código (*code smells*) de Martin Fowler:
- **Nombre Misterioso (Mysterious Name)**: Funciones, variables o tipos cuyos nombres no revelan su intención ni contenido.
- **Código Duplicado (Duplicated Code)**: La misma forma lógica repetida en más de un bloque o archivo.
- **Envidia de Características (Feature Envy)**: Métodos que acceden a los datos de otro objeto más que a los propios.
- **Grupo de Datos (Data Clumps)**: Conjuntos de parámetros o campos que viajan juntos y deberían formar un tipo/modelo propio.
- **Obsesión Primitiva (Primitive Obsession)**: Uso de strings o enteros genéricos para representar conceptos clave del dominio.
- **Switches Repetidos (Repeated Switches)**: Cascadas condicionales recurrentes sobre el mismo tipo que deberían usar polimorfismo o mapas compartidos.
- **Cirugía con Perdigones (Shotgun Surgery)**: Un cambio lógico que obliga a realizar modificaciones dispersas en múltiples archivos.
- **Cambio Divergente (Divergent Change)**: Un archivo o módulo que se edita por múltiples razones no relacionadas.
- **Generalidad Especulativa (Speculative Generality)**: Parámetros, hooks o capas agregadas para necesidades no solicitadas en la especificación.
- **Cadenas de Mensajes (Message Chains)**: Navegaciones profundas del tipo `a.b().c().d()` que violan la ley de Deméter.
- **Hombre del Medio (Middle Man)**: Clases o funciones que solo delegan hacia otro componente sin añadir valor.
- **Legado Rechazado (Refused Bequest)**: Subclases que ignoran o anulan la mayor parte del comportamiento heredado (preferir composición).

### Eje 2: Subagente de Especificación (Spec Sub-agent)
Evalúa la fidelidad frente a la especificación SDD de origen (`01-spec.md` / `02-design.md`):
- **Requerimientos Faltantes**: Capacidades o criterios de aceptación exigidos por la especificación que están incompletos o ausentes.
- **Ampliación de Alcance (Scope Creep)**: Comportamientos o APIs en el diff que no fueron solicitados.
- **Inversión de Contratos**: Lógica que aparenta estar implementada pero viola los contratos o esquemas definidos en el diseño técnico.

Los resultados se presentan en paralelo: el código que sigue todos los estándares pero resuelve el problema equivocado reprueba en el eje de Especificación; el código que cumple la especificación pero rompe la arquitectura reprueba en el eje de Estándares. Presentar ambos ejes por separado evita que la discusión de estilo opaque la falta de requerimientos de negocio.

## Completion Check

Before returning:

- the canonical policy was read;
- selected profiles and activation evidence are explicit;
- the real diff and primary evidence were inspected;
- relevant deterministic validation was independently repeated or listed as
  `not_run` with impact;
- every finding follows the common schema and causal blocking rules;
- pre-existing debt remains non-blocking;
- only the general reviewer emits `review_stage: final` and a final verdict.
