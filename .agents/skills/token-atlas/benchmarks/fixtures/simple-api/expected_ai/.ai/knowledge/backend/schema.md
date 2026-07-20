---
type: schema
title: Backend Schema
description: Backend schema facts for the simple-api fixture.
resource: src/backend/routes/orders.ts
tags: [simple-api, backend, schema]
timestamp: 2026-07-08
source_symbols:
  src/backend/routes/orders.ts:
    - OrderSummary
pkf:
  materialization: complete
  loads: []
  related: []
---

## Edit Map

| Behavior | Source symbols | Tests | Styles/tokens | Locator |
|---|---|---|---|---|
| Schema | `src/backend/routes/orders.ts:OrderSummary` | Not documented | N/A | `rg -n -F -- 'OrderSummary' 'src/backend/routes/orders.ts'` |
