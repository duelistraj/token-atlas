# ui-change

## Goal

Verify UI behavior changes route to UI knowledge without pulling backend-only docs automatically.

## Source Shape

- One frontend module.
- One UI component or screen source path.
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

## Forbidden Automatic Loads

- Backend module docs.
- `api.md`, `schema.md`, and `business_rules.md` unless source evidence makes them required.
- Retrieval exports.

## Expected Warnings

- None when UI ownership is unambiguous.

## Expected Errors

- None.

## Token Thresholds

- UI-change task should be at or below the 8,000 token module-task warning threshold.

## Exit Behavior

- Advisory and CI validation pass when routing and source evidence are complete.

