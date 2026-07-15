---
type: schema
title: Backend Schema
description: Backend schema facts for the exports fixture.
resource: .ai/knowledge/backend/schema.md
tags: [exports, backend, schema]
timestamp: 2026-07-08
source_symbols:
  src/backend/models/product.ts:
    - ProductRecord
pkf:
  loads: []
  related:
    - .ai/knowledge/backend/api.md
---

## Edit Map

| Behavior | Source symbols | Tests | Styles/tokens | Locator |
|---|---|---|---|---|
| Schema | `src/backend/models/product.ts:ProductRecord` | Not documented | N/A | `rg -n -F -- 'ProductRecord' 'src/backend/models/product.ts'` |
