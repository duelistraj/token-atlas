---
type: api
title: Backend API
description: Backend API facts for the simple-api fixture.
resource: src/backend/routes/orders.ts
tags: [simple-api, backend, api]
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
| Api | `src/backend/routes/orders.ts:getOrderRoute` | Not documented | N/A | `rg -n -F -- 'getOrderRoute' 'src/backend/routes/orders.ts'` |
