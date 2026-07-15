# ui-change

## Goal

Verify UI behavior changes route to UI knowledge without pulling backend-only docs automatically.

## Source Shape

- One frontend module.
- One multi-symbol UI source file where only one declaration is relevant, plus a
  test symbol and CSS token associated through the Edit Map.
- The benchmark Git state includes a UI-related changed path.

## Benchmark Flow

- Run `maintenance.md`.
- Run `extract.md`.
- Run `simulate.md` with intent `Change UI behavior` and the changed UI path.
- Run `validation.md`.

## Expected Selected Modules

- The frontend module that owns the changed UI path.

## Expected Required Docs

- Startup path.
- Root knowledge index.
- Frontend module `INDEX.md`.
- Frontend module `ui.md`.
- Exact target `src/frontend/CartSummary.tsx:renderCartSummary`, its test symbol,
  CSS token, and a targeted locator command.

## Forbidden Automatic Loads

- Backend module docs.
- `api.md`, `schema.md`, and `business_rules.md` unless source evidence makes them required.
- Retrieval exports.

## Expected Warnings

- None when UI ownership is unambiguous.

## Expected Errors

- None.

## Token Thresholds

- Each leaf should stay at or below 1,500 tokens and the normal task route at or below 4,000 tokens.

## Exit Behavior

- Advisory and CI validation pass when routing and source evidence are complete.
