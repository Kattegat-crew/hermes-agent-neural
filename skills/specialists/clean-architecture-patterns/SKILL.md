---
name: clean-architecture-patterns
description: Clean, Hexagonal, and Screaming Architecture patterns for decoupled, testable, and maintainable software.
license: MIT
compatibility: opencode
---

# Clean Architecture & Hexagonal Patterns

Architectural blueprint for building domain-centric, framework-agnostic systems.

## Layers & Dependency Inversion
1. **Domain Layer (Core)**: Entities, Value Objects, Domain Services, and Domain Events. ZERO external dependencies.
2. **Application Layer (Use Cases)**: Coordinates workflow execution, commands, and queries (CQRS). Defines interfaces (Ports).
3. **Adapters / Infrastructure**: Implements Ports for DBs, external APIs, message brokers, and UI frameworks.
4. **Dependency Rule**: Dependencies always point inward toward the Domain. The core never imports frameworks or databases.
