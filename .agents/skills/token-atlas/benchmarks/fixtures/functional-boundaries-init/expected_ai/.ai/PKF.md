---
type: runtime
title: Synthetic PKF
description: Runtime entry point.
resource: .
tags: [pkf]
timestamp: 2026-07-12
pkf:
  loads: [.ai/MEMORY.md, .ai/ARCHITECTURE.md, .ai/knowledge/INDEX.md]
  related: []
---
# Synthetic PKF

## Retrieval Protocol (MANDATORY)

Route through the root index, a flat module index, and only required leaves.
Cache this protocol and indexes for the session. A normal route loads one module
index, one or two leaves, and only their `source_symbols`; report targeted
commands, budget usage, and whether fallback search was required.
