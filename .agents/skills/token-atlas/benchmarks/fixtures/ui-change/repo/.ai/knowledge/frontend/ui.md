---
type: ui
title: Frontend UI
description: Frontend UI facts for the ui-change fixture.
resource: .ai/knowledge/frontend/ui.md
tags: [ui-change, frontend, ui]
timestamp: 2026-07-08
source_symbols:
  src/frontend/CartSummary.tsx:
    - renderCartSummary
  src/frontend/CartSummary.test.ts:
    - cartSummaryLabel
pkf:
  loads: []
  related: []
---

## Edit Map

| Behavior | Source symbols | Tests | Styles/tokens | Locator |
|---|---|---|---|---|
| Cart summary label and totals | `src/frontend/CartSummary.tsx:renderCartSummary` | `src/frontend/CartSummary.test.ts:cartSummaryLabel` | `src/frontend/cart.css:--cart-summary-gap` | `rg -n -F -- 'renderCartSummary' 'src/frontend/CartSummary.tsx'` |
