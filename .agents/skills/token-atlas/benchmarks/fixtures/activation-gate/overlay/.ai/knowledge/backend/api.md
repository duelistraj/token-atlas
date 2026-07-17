---
type: api
title: Backend API
description: Backend API facts for the schema-change fixture.
resource: .ai/knowledge/backend/api.md
tags: [schema-change, backend, api]
timestamp: 2026-07-08
source_symbols:
  src/backend/routes/customers.ts:
    - listCustomersRoute
  src/backend/routes/customers.test.ts:
    - listCustomersRoutePathTest
pkf:
  loads: []
  related: []
---

## Edit Map

| Behavior | Source symbols | Tests | Styles/tokens | Locator |
|---|---|---|---|---|
| Customer list path is `/customers` | `src/backend/routes/customers.ts:listCustomersRoute`, `src/backend/routes/customers.test.ts:listCustomersRoutePathTest` | `src/backend/routes/customers.test.ts:listCustomersRoutePathTest` | N/A | `rg -n -F -- 'listCustomersRoute' 'src/backend/routes/customers.ts' 'src/backend/routes/customers.test.ts'` |

- `listCustomersRoute` exposes the `/customers` path.
