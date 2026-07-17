---
type: runtime
title: PKF Runtime
description: Startup contract for the simple-api fixture.
resource: .ai/PKF.md
tags: [simple-api, runtime]
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

Route every task through `.ai/knowledge/INDEX.md` before codebase-wide search.
Cache this protocol and indexes for the session. A normal route loads one module
index, one or two leaves, and only their `source_symbols`; report targeted
commands, budget usage, and whether fallback search was required. **Negative constraint:** do not search broadly until routing is insufficient.

### Fallback and verification

Verify routed facts against source and report fallback search.

### Keep the knowledge base in sync

Update the authoritative leaf after source changes or report it as stale.

## Closeout Protocol (MANDATORY)

### Adaptive gate

If the current turn made no intentional repository content mutation, stop silently.
After an intentional repository mutation, reuse the session change-set
acknowledgement and update only affected knowledge. Keep the acknowledgement in
session context.

### Incremental synchronization

Update and validate only affected knowledge.

### Safety and recursion

Never invoke closeout again for `.ai/`-only changes.

`PKF closeout: <status> — <reason>`
