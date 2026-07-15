---
type: api
title: Backend API
description: Backend API facts for the deleted-evidence fixture.
resource: .ai/knowledge/backend/api.md
tags: [deleted-evidence, backend, api]
timestamp: 2026-07-08
source_symbols:
  src/backend/routes/legacyOrders.ts:
    - getLegacyOrderRoute
  src/backend/routes/orders.ts:
    - getOrderRoute
pkf:
  loads: []
  related: []
---

## Edit Map

| Behavior | Source symbols | Tests | Styles/tokens | Locator |
|---|---|---|---|---|
| Api | `src/backend/routes/legacyOrders.ts:getLegacyOrderRoute` | Not documented | N/A | `rg -n -F -- 'getLegacyOrderRoute' 'src/backend/routes/legacyOrders.ts'` |
| Api | `src/backend/routes/orders.ts:getOrderRoute` | Not documented | N/A | `rg -n -F -- 'getOrderRoute' 'src/backend/routes/orders.ts'` |
