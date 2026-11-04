---
name: spec-best-practices
description: "Use when writing RFC or technical specs"
tags: [rfc, spec, especificacion, arquitectura, diseno, requirements, planning]
license: MIT
compatibility: hermes, opencode
metadata:
  hermes:
    tags: [rfc, spec, architecture, requirements, design-doc, planning, engineering]
    category: software-development
---

# Technical Specification & RFC Best Practices

Architectural standards for designing, evaluating, and writing actionable Requests for Comments (RFCs) and technical design documents before writing implementation code.

## 1. Core Architectural Axiom: CONCEPTS > CODE

Writing code before agreeing on system boundaries, failure modes, and data contracts is the primary source of technical debt. A specification is not bureaucracy; it is the blueprint that prevents catastrophic rewrites.

---

## 2. Standard RFC Structure

Every technical specification must contain these sections:

### 1. Problem Context & Motivation
- What concrete pain point or user requirement triggers this change?
- Why can current system primitives or existing architectures not solve it?
- What is the cost of doing nothing?

### 2. Goals & Explicit Non-Goals
- **Goals**: Quantifiable outcomes (e.g., "Reduce API turn latency under 2s", "Centralize skills into single Git repo").
- **Non-Goals (CRITICAL)**: Explicitly scope out features, edge cases, or optimizations that this design will NOT address to prevent scope creep.

### 3. Proposed Architecture & System Design
- **High-Level Diagram**: Component interactions, network boundaries, and message flows.
- **Data Models / Schema**: Precise database schemas, protobuf/JSON contracts, or state machine definitions.
- **Invariants**: Guarantees the system promises to uphold (e.g., "Zero unencrypted secrets on disk", "Idempotent event processing").

### 4. Trade-Off Analysis & Rejected Alternatives
- Document at least 2 alternative solutions that were evaluated.
- Detail why each alternative was rejected (e.g., operational complexity, license incompatibilities, latency costs).

### 5. Failure Modes & Mitigation
- What happens when downstream services timeout?
- How does the system handle split-brain or partial network partitions?
- Data recovery and rollback plan if migration fails midway.

### 6. Observability, Security & Rollout
- Key metrics (RED: Rate, Errors, Duration).
- Authorization, encryption in transit/rest, audit logging.
- Phase-by-phase rollout (Feature flag -> Canary 5% -> 100% production).
