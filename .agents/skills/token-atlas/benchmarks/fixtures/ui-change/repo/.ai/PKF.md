---
type: runtime
title: PKF Runtime
description: Startup contract for the ui-change fixture.
resource: .ai/PKF.md
tags: [ui-change, runtime]
timestamp: 2026-07-08
pkf:
  runtime_version: 2
  loads:
    - .ai/MEMORY.md
    - .ai/ARCHITECTURE.md
    - .ai/knowledge/INDEX.md
  related: []
  closeout: adaptive
---

# PKF Runtime

Startup path: `PKF.md -> MEMORY.md -> ARCHITECTURE.md -> knowledge/INDEX.md`.

## Retrieval Protocol (MANDATORY)

### Hard precondition

Route through `.ai/knowledge/INDEX.md` and the minimal leaves before source
search. **Negative constraint:** do not search broadly until routing is
insufficient.

### Fallback and verification

Verify routed facts against source and report fallback search.

### Keep the knowledge base in sync

Update the authoritative leaf after source changes or report it as stale.

## Closeout Protocol (MANDATORY)

### Adaptive gate

If the current turn made no intentional repository content mutation, stop silently.
After an intentional repository mutation, compare a deterministic session baseline with the final repository state. Keep
the acknowledgement in session context.

### Incremental synchronization

Update and validate only affected knowledge.

### Safety and recursion

Never invoke closeout again for `.ai/`-only closeout changes.

`PKF closeout: <status> — <reason>`
