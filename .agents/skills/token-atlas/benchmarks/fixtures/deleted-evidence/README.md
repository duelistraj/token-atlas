# deleted-evidence

## Goal

Verify stale references to deleted source evidence are detected and treated as validation defects.

## Source Shape

- Existing `.ai/` Markdown cites a source file, symbol, command, or route.
- The cited source evidence is deleted in the benchmark Git state.

## Benchmark Flow

- Run `maintenance.md`.
- Run `validation.md` with CI strictness.

## Expected Selected Modules

- The module that owned the deleted evidence path.

## Expected Required Docs

- Startup path.
- Root knowledge index.
- Affected module `INDEX.md`.
- Every canonical Markdown doc citing the deleted evidence.

## Forbidden Automatic Loads

- Unaffected module leaf docs.
- Retrieval exports when `retrieval_exports: off`.

## Expected Warnings

- Duplicate facts may warn if they do not affect source truth or routing.

## Expected Errors

- Stale reference to the deleted evidence path.
- Removed symbol, route, schema, command, config key, or test still cited as current if present.

## Token Measurements

- Token budget must still be reported when validation fails.

## Exit Behavior

- Advisory validation reports blocking recommendations and exits successfully.
- CI validation exits nonzero.
