---
type: rules
title: Catalog Business Rules
description: Source-backed catalog filtering behavior.
resource: src/backend/routes/catalog.ts
tags: [missing-runtime, backend, rules]
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
| Return only active catalog items | `src/backend/routes/catalog.ts:listCatalogItems` | Not documented | N/A | `rg -n -F -- 'listCatalogItems' 'src/backend/routes/catalog.ts'` |
