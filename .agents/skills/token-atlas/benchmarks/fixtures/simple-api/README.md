# simple-api

## Goal

Verify source-backed API extraction and route-change retrieval.

## Source Shape

- One backend module.
- One API route implemented by source code.
- No frontend or export requirement.

## Benchmark Flow

- Run `initialize.md` if needed.
- Run `extract.md`.
- Run `simulate.md` with intent `Change an API route`.
- Run `validation.md`.

## Expected Selected Modules

- The backend module that owns the route source path.

## Expected Required Docs

- Startup path.
- Root knowledge index.
- Backend module `INDEX.md`.
- Backend module `api.md`.

## Forbidden Automatic Loads

- `schema.md`, `business_rules.md`, and `ui.md` unless the route evidence explicitly requires them.
- Other module directories.
- `.ai/retrieval/`.

## Expected Warnings

- None when route ownership is unambiguous.

## Expected Errors

- None.

## Token Thresholds

- Route-change task should be at or below the 8,000 token module-task warning threshold.

## Exit Behavior

- Advisory and CI validation pass when source evidence and routing are complete.

