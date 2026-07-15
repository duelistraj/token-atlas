---
type: ui
title: Mixed User Behavior
description: User-facing behavior for multiple capabilities.
resource: src/layer-two
tags: [system, ui]
timestamp: 2026-07-12
source_symbols:
  src/layer-two/capability-one/view.ts:
    - capabilityOneView
  src/layer-two/capability-two/view.ts:
    - capabilityTwoView
pkf:
  loads: []
  related: []
---

## Edit Map

| Behavior | Source symbols | Tests | Styles/tokens | Locator |
|---|---|---|---|---|
| Ui | `src/layer-two/capability-one/view.ts:capabilityOneView` | Not documented | N/A | `rg -n -F -- 'capabilityOneView' 'src/layer-two/capability-one/view.ts'` |
| Ui | `src/layer-two/capability-two/view.ts:capabilityTwoView` | Not documented | N/A | `rg -n -F -- 'capabilityTwoView' 'src/layer-two/capability-two/view.ts'` |
