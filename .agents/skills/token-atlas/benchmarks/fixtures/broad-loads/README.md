# broad-loads

## Goal

Verify broad or unrelated `pkf.loads` chains are detected as retrieval defects.

## Source Shape

- Existing `.ai/` Markdown has at least two modules.
- One module or root index automatically loads another unrelated module.

## Benchmark Flow

- Run `simulate.md` with a task that should select only one module.
- Run `optimize.md` in `token_budget: full` mode.
- Run `validation.md` in CI strictness.

## Expected Selected Modules

- Only the module matched by the task intent or changed path.

## Expected Required Docs

- Startup path.
- Root knowledge index.
- Selected module `INDEX.md`.
- One task-specific leaf doc.

## Forbidden Automatic Loads

- Any unrelated module directory.
- Optional context through `pkf.loads`.

## Expected Warnings

- Token budget warning if a load path crosses a threshold.

## Expected Errors

- Unrelated module loaded automatically through `pkf.loads`.

## Token Thresholds

- Broad-load chain must be listed with threshold status.

## Exit Behavior

- CI validation exits nonzero until unrelated automatic loads are removed or moved to `pkf.related`.

