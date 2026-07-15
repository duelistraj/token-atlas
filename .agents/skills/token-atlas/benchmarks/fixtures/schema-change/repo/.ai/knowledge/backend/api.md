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
pkf:
  loads: []
  related: []
---

## Edit Map

| Behavior | Source symbols | Tests | Styles/tokens | Locator |
|---|---|---|---|---|
| Api | `src/backend/routes/customers.ts:listCustomersRoute` | Not documented | N/A | `rg -n -F -- 'listCustomersRoute' 'src/backend/routes/customers.ts'` |
