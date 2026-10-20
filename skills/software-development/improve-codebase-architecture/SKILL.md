---
name: improve-codebase-architecture
description: "Scan a codebase for deepening opportunities, present them as a visual HTML report with Mermaid and Tailwind, and propose architectural refactors."
tags: [architecture, design, refactoring, deep-modules, report, quality]
version: 1.0.0
author: NeuralCrew Labs (adapted from Matt Pocock / John Ousterhout)
license: MIT
platforms: [linux, macos, windows]
---

# Improve Codebase Architecture

Surface architectural friction and propose **deepening opportunities**: refactors that turn shallow modules into deep ones. The aim is testability and AI-navigability.

This command is informed by the project's domain model, SDD specs, and built on a shared design vocabulary:

- Refer to the `codebase-design` skill for the architecture vocabulary (**module**, **interface**, **depth**, **seam**, **adapter**, **leverage**, **locality**) and its principles (the deletion test, "the interface is the test surface", "one adapter = hypothetical seam, two = real"). Use these terms exactly in every suggestion, and don't drift into "component," "service," "API," or "boundary."
- Use Engram (`/opt/engram/`) and `PROJECT_MEMORY.md` to avoid re-proposing previously rejected architectural changes.

## Process

### 1. Explore

**Scope before you scan: YAGNI.** Deepening a module pays off by making future changes to it easier, so put extra weight on the parts of the codebase that have recently changed. Decide *where* to look before you look:

- If the user named a direction (a module, a subsystem, a pain point), take it, and skip the inference below.
- Otherwise, walk back a good stretch of the commit history (`git log --oneline -30`) to find the codebase's hot spots, the files and areas that keep coming up, and let those paths pull your attention first.

Look for areas where:
- Understanding one concept requires bouncing between many small, pass-through modules.
- Modules are **shallow**, with an interface nearly as complex as the implementation.
- Pure functions have been extracted just for testability, but the real bugs hide in how they're called (no **locality**).
- Tightly-coupled modules leak across their seams.
- Parts of the codebase are untested, or hard to test through their current interface.

Apply the **deletion test** to anything suspected as shallow: would deleting it concentrate complexity, or just move it? A "yes, concentrates" is the signal you want.

### 2. Present Candidates as an HTML Report

Write a self-contained HTML file to `/tmp/architecture-review-<timestamp>.html` so nothing lands in the git repository. Open it or notify the user of the path.

The report uses **Tailwind via CDN** for layout and styling, and **Mermaid via CDN** for diagrams where a graph/flow/sequence reliably communicates the structure.

For each candidate, render a card with:
- **Files**: Which files/modules are involved.
- **Problem**: Why the current architecture is causing friction.
- **Solution**: Plain English description of what would change.
- **Benefits**: Explained in terms of locality and leverage, and how tests would improve.
- **Before / After diagram**: Side-by-side, custom-drawn, illustrating the shallowness and the deepening.
- **Recommendation strength**: One of `Strong`, `Worth exploring`, `Speculative`.

End the report with a **Top recommendation** section: which candidate to tackle first and why.
See [`HTML-REPORT.md`](HTML-REPORT.md) for full scaffolding and styling patterns.

### 3. Review Loop

Once the user selects a candidate:
1. Walk the decision tree: constraints, dependencies, the shape of the deepened module, what sits behind the seam, what tests survive.
2. If approved for implementation in an SDD repository, formulate the proposal into Phase 1 (`01-spec.md`) and Phase 2 (`02-design.md`) under `.specs/<feature-name>/`.
3. Record the architectural decision in Engram (`engram save --type architecture`).
