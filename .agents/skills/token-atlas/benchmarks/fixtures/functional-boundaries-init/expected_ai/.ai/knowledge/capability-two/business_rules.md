---
type: business-rules
title: Capability Two Workflows
description: Source-backed workflows.
resource: src/layer-one/capability-two
tags: [capability-two, workflows]
timestamp: 2026-07-12
source_symbols:
  src/layer-one/capability-two/workflow.ts:
    - runCapabilityTwo
pkf:
  loads: []
  related: []
---

## Edit Map

| Behavior | Source symbols | Tests | Styles/tokens | Locator |
|---|---|---|---|---|
| Business Rules | `src/layer-one/capability-two/workflow.ts:runCapabilityTwo` | Not documented | N/A | `rg -n -F -- 'runCapabilityTwo' 'src/layer-one/capability-two/workflow.ts'` |
