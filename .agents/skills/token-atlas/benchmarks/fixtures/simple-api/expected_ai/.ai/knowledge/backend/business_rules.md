---
type: rules
title: Order Lookup Business Rules
description: Source-backed order lookup behavior.
resource: src/backend/routes/orders.ts
tags: [simple-api, backend, rules]
timestamp: 2026-07-08
source_symbols:
  src/backend/routes/orders.ts:
    - getOrderRoute
pkf:
  materialization: complete
  loads: []
  related: []
---

## Edit Map

| Behavior | Source symbols | Tests | Styles/tokens | Locator |
|---|---|---|---|---|
| Return 404 when an order is absent | `src/backend/routes/orders.ts:getOrderRoute` | Not documented | N/A | `rg -n -F -- 'getOrderRoute' 'src/backend/routes/orders.ts'` |
