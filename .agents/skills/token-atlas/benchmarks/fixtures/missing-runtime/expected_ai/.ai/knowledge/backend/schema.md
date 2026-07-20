---
type: schema
title: Backend Schema
description: Backend schema facts for the missing-runtime fixture.
resource: src/backend/models/catalogItem.ts
tags: [missing-runtime, backend, schema]
timestamp: 2026-07-08
source_symbols:
  src/backend/models/catalogItem.ts:
    - CatalogItem
pkf:
  materialization: complete
  loads: []
  related: []
---

## Edit Map

| Behavior | Source symbols | Tests | Styles/tokens | Locator |
|---|---|---|---|---|
| Schema | `src/backend/models/catalogItem.ts:CatalogItem` | Not documented | N/A | `rg -n -F -- 'CatalogItem' 'src/backend/models/catalogItem.ts'` |
