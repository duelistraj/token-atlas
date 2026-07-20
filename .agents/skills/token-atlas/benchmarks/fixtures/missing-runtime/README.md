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
- Shared docs: `glossary.md`, `dependencies.md`, `decision_log.md`
- Module skeleton docs for every detected module.

## Forbidden Automatic Loads

- No retrieval exports in startup context.
- No unrelated module leaf docs.

## Expected Warnings

- Unknown implementation details may remain `TODO`.

## Expected Errors

- None after initialization and validation.
- In CI validation before initialization, missing `.ai/PKF.md` is a blocking startup error.

## Token Thresholds

- Startup should stay at or below 2,500 tokens and each leaf at or below 1,500; task-route size is telemetry.

## Exit Behavior

- Advisory validation reports recovery without failing.
- CI validation fails before recovery and passes after successful initialization.
