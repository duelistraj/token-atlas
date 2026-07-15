---
type: api
title: Mixed Interfaces
description: Interfaces for multiple capabilities.
resource: src/layer-one
tags: [system, api]
timestamp: 2026-07-12
source_symbols:
  src/layer-one/capability-one/interface.ts:
    - capabilityOneRoute
  src/layer-one/capability-two/interface.ts:
    - capabilityTwoRoute
pkf:
  loads: []
  related: []
---

## Edit Map

| Behavior | Source symbols | Tests | Styles/tokens | Locator |
|---|---|---|---|---|
| Api | `src/layer-one/capability-one/interface.ts:capabilityOneRoute` | Not documented | N/A | `rg -n -F -- 'capabilityOneRoute' 'src/layer-one/capability-one/interface.ts'` |
| Api | `src/layer-one/capability-two/interface.ts:capabilityTwoRoute` | Not documented | N/A | `rg -n -F -- 'capabilityTwoRoute' 'src/layer-one/capability-two/interface.ts'` |
