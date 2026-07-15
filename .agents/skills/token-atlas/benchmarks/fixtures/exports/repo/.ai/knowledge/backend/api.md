---
type: api
title: Backend API
description: Backend API facts for the exports fixture.
resource: .ai/knowledge/backend/api.md
tags: [exports, backend, api]
timestamp: 2026-07-08
source_symbols:
  src/backend/routes/products.ts:
    - listProductsRoute
pkf:
  loads: []
  related:
    - .ai/knowledge/backend/schema.md
---

## Edit Map

| Behavior | Source symbols | Tests | Styles/tokens | Locator |
|---|---|---|---|---|
| Api | `src/backend/routes/products.ts:listProductsRoute` | Not documented | N/A | `rg -n -F -- 'listProductsRoute' 'src/backend/routes/products.ts'` |
