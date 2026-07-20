---
type: api
title: Backend API
description: Backend API facts for the missing-runtime fixture.
resource: src/backend/routes/catalog.ts
tags: [missing-runtime, backend, api]
timestamp: 2026-07-08
source_symbols:
  src/backend/routes/catalog.ts:
    - listCatalogItems
pkf:
  materialization: complete
  loads: []
  related: []
---

## Edit Map

| Behavior | Source symbols | Tests | Styles/tokens | Locator |
|---|---|---|---|---|
| Api | `src/backend/routes/catalog.ts:listCatalogItems` | Not documented | N/A | `rg -n -F -- 'listCatalogItems' 'src/backend/routes/catalog.ts'` |
