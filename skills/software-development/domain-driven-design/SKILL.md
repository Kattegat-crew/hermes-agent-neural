---
name: domain-driven-design
description: >-
  Use when modeling complex domain logic with DDD Value Objects, and Ubiquitous Language.'
tags: [ddd, domain-driven-design, bounded-context, aggregates, value-objects, arquitectura, modelado]
license: MIT
compatibility: opencode---


# Domain-Driven Design (DDD)

Guidelines for tackling complex domain logic using strategic and tactical DDD.

## Tactical Patterns
1. **Entities vs Value Objects**: Entities have unique IDs and lifecycles. Value Objects are immutable, defined only by their attributes.
2. **Aggregates & Aggregate Roots**: Enforce business invariants within transactional boundaries. Only the Aggregate Root is referenced externally.
3. **Domain Events**: Capture significant occurrences in the domain (`OrderPlaced`, `UserRegistered`) to enable asynchronous side effects.
4. **Repositories**: Return complete Aggregates and abstract away storage mechanisms.


<!-- absorbido de software-development/clean-architecture-patterns (censo 2026-09-24) -->
## Layers & Dependency Inversion

1. **Domain Layer (Core)**: Entities, Value Objects, Domain Services, and Domain Events. ZERO external dependencies.
2. **Application Layer (Use Cases)**: Coordinates workflow execution, commands, and queries (CQRS). Defines interfaces (Ports).
3. **Adapters / Infrastructure**: Implements Ports for DBs, external APIs, message brokers, and UI frameworks.
4. **Dependency Rule**: Dependencies always point inward toward the Domain. The core never imports frameworks or databases.
