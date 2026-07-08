# schema-change

## Goal

Verify schema or data-model changes route to schema knowledge only.

## Source Shape

- One module has a model, schema, migration, or type definition.
- The benchmark Git state includes a schema-related changed path.

## Benchmark Flow

- Run `maintenance.md`.
- Run `extract.md`.
- Run `simulate.md` with intent `Change a schema or data model` and the changed schema path.
- Run `validation.md`.

## Expected Selected Modules

- The module that owns the changed schema path.

## Expected Required Docs

- Startup path.
- Root knowledge index.
- Owning module `INDEX.md`.
- Owning module `schema.md`.

## Forbidden Automatic Loads

- `api.md`, `business_rules.md`, and `ui.md` unless source evidence makes them required.
- Unrelated module docs.

## Expected Warnings

- Ambiguous ownership warning only if the fixture intentionally contains overlapping path rules.

## Expected Errors

- None for the default fixture.

## Token Thresholds

- Schema-change task should be at or below the 8,000 token module-task warning threshold.

## Exit Behavior

- CI validation passes when changed-path routing is source-backed.

