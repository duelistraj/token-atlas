---
type: runtime
title: PKF Runtime
description: Startup contract for the broad-loads fixture.
resource: .ai/PKF.md
tags: [broad-loads, runtime]
timestamp: 2026-07-08
pkf:
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

Route every task through `.ai/knowledge/INDEX.md` before codebase-wide search.
Cache this protocol and indexes for the session. A normal route loads one module
index, one or two leaves, and only their `source_symbols`; report targeted
commands, budget usage, and whether fallback search was required.

## Closeout Protocol (MANDATORY)

Run adaptive PKF closeout exactly once before every final response. Reuse the
session change-set acknowledgement, update only affected knowledge, and do not
recurse on `.ai/`-only changes.
