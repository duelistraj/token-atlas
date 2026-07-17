---
type: runtime
title: Synthetic PKF
description: Runtime entry point.
resource: .
tags: [pkf]
timestamp: 2026-07-12
pkf:
  runtime_version: 2
  loads: [.ai/MEMORY.md, .ai/ARCHITECTURE.md, .ai/knowledge/INDEX.md]
  related: []
  closeout: adaptive
---
# Synthetic PKF

## Retrieval Protocol (MANDATORY)

Route through the root index, a flat module index, and only required leaves.
Cache this protocol and indexes for the session. A normal route loads one module
index, one or two leaves, and only their `source_symbols`; report targeted
commands, budget usage, and whether fallback search was required.

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
