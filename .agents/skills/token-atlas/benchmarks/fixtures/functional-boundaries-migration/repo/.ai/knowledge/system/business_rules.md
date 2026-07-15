---
type: business-rules
title: Mixed Workflows
description: Workflows for multiple capabilities.
resource: src/layer-one
tags: [system, workflows]
timestamp: 2026-07-12
source_symbols:
  src/layer-one/capability-one/workflow.ts:
    - runCapabilityOne
  src/layer-one/capability-two/workflow.ts:
    - runCapabilityTwo
pkf:
  loads: []
  related: []
---

## Edit Map

| Behavior | Source symbols | Tests | Styles/tokens | Locator |
|---|---|---|---|---|
| Business Rules | `src/layer-one/capability-one/workflow.ts:runCapabilityOne` | Not documented | N/A | `rg -n -F -- 'runCapabilityOne' 'src/layer-one/capability-one/workflow.ts'` |
| Business Rules | `src/layer-one/capability-two/workflow.ts:runCapabilityTwo` | Not documented | N/A | `rg -n -F -- 'runCapabilityTwo' 'src/layer-one/capability-two/workflow.ts'` |
