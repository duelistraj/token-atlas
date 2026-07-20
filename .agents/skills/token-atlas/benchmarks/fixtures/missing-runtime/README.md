# missing-runtime

## Goal

Verify startup recovery when `.ai/PKF.md` is absent.

## Source Shape

- Repository has source files.
- Repository has no `.ai/PKF.md`.
- It may have no `.ai/` directory or an incomplete `.ai/` directory.

## Benchmark Flow

- Run startup recovery through `initialize.md`.
- Run `validation.md` after initialization.

## Expected Selected Modules

- Modules detected from repository structure only.

## Expected Required Docs

- `.ai/PKF.md`
- `.ai/MEMORY.md`
- `.ai/ARCHITECTURE.md`
- `.ai/knowledge/INDEX.md`
- Applicable source-backed shared docs.
- A module index and every applicable complete evidence-backed leaf.

## Forbidden Automatic Loads

- No retrieval exports in startup context.
- No unrelated module leaf docs.

## Expected Warnings

- None. Unknown or nonapplicable knowledge is omitted.

## Expected Errors

- None after initialization and validation.
- In CI validation before initialization, missing `.ai/PKF.md` is a blocking startup error.

## Token Measurements

- Startup, leaf, and task-route sizes are observed telemetry without numeric ceilings.

## Exit Behavior

- Advisory validation reports recovery without failing.
- CI validation fails before recovery and passes after successful initialization.
