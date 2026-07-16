---
type: runtime
title: Coarse PKF
description: Runtime entry point before migration.
resource: .
tags: [pkf]
timestamp: 2026-07-12
pkf:
  loads: [.ai/MEMORY.md, .ai/ARCHITECTURE.md, .ai/knowledge/INDEX.md]
  related: []
  closeout: adaptive
---
# Coarse PKF

## Retrieval Protocol (MANDATORY)

### Hard precondition

Before code search, read this file, `.ai/knowledge/INDEX.md`, the selected module
index, and only the required leaves. Do not search the codebase broadly until
that route proves insufficient.

### Fallback and verification

Use broader search only when routed knowledge is missing or stale, and verify
claims against source truth before changing code.

### Keep the knowledge base in sync

After source changes, update the authoritative leaf or report it as stale.

Cache this protocol and indexes for the session. A normal route loads one module
index, one or two leaves, and only their `source_symbols`; report targeted
commands, budget usage, and whether fallback search was required.

## Closeout Protocol (MANDATORY)

Run adaptive PKF closeout exactly once before every final response. Reuse the
session change-set acknowledgement, update only affected knowledge, and do not
recurse on `.ai/`-only changes.
