---
type: schema
title: Backend Schema
description: Backend schema facts for the schema-change fixture.
resource: .ai/knowledge/backend/schema.md
tags: [schema-change, backend, schema]
timestamp: 2026-07-08
source_symbols:
  src/backend/models/customer.ts:
    - CustomerRecord
pkf:
  loads: []
  related: []
---

## Edit Map

| Behavior | Source symbols | Tests | Styles/tokens | Locator |
|---|---|---|---|---|
| Schema | `src/backend/models/customer.ts:CustomerRecord` | Not documented | N/A | `rg -n -F -- 'CustomerRecord' 'src/backend/models/customer.ts'` |
