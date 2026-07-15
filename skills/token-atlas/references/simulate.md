# Simulate Retrieval

## Purpose

Predict the smallest OKF context set needed for a natural-language task intent and optional changed file paths.

Do not modify files.

## Inputs

- Natural-language task intent.
- Optional changed paths.
- Optional known module or task type.
- Simulation mode: `off`, `changed`, `required`, or `all`.

## Task Types

Classify intent as one or more:

- API route change.
- Schema or model change.
- Business logic change.
- UI behavior change.
- Architecture understanding.
- Dependency or tooling update.
- Unknown or mixed task.

## Selection Order

1. Changed paths matched by `ARCHITECTURE.md` or `knowledge/INDEX.md`.
2. Module names and keywords in `knowledge/INDEX.md`.
3. Module `INDEX.md` routing tables.
4. `pkf.related` only as optional context.

Do not automatically load unrelated modules.

For a normal task, select one module index and one or two leaves, then return the
exact `source_symbols` and Edit Map locator commands. A cross-cutting task may use
more slices only with an explicit budget exception.

## Required Docs By Task

| Task type | Required OKF document |
|-----------|-----------------------|
| API route change | `api.md` |
| Schema or model change | `schema.md` |
| Business logic change | `business_rules.md` |
| UI behavior change | `ui.md` |
| Architecture understanding | `ARCHITECTURE.md` plus relevant module `INDEX.md` |
| Dependency or tooling update | `dependencies.md` plus affected module `INDEX.md` when applicable |

## Report Format

```text
Retrieval Simulation
Intent: <task>
Changed paths: <paths or none>
Task type: <classified type>
Simulation mode: <off, changed, required, or all>
Selected modules: <modules>
Required docs: <docs loaded automatically>
Optional related docs: <docs not automatically loaded>
Estimated tokens: <count>
Estimator: <exact or approximate>
Threshold status: <passed, warning, or error>
Source targets: <path:symbol entries>
Targeted commands: <sg when verified as ast-grep, otherwise exact rg commands>
Fallback search: <yes or no>
Fallback reason: <reason or none>
Budget usage: <module indexes, leaves, tokens, and exception reason if any>
Routing evidence:
- <evidence>
Warnings:
- <warning or none>
Errors:
- <error or none>
```

## Errors

Report errors when:

- Required docs are missing.
- Routing references missing documents.
- The selected module cannot be reached from `knowledge/INDEX.md`.
- `pkf.loads` automatically loads an unrelated module.
- A task-specific route must load unrelated capability facts because the selected module mixes independently routable capabilities.
- A leaf lacks valid source symbols or a targeted Edit Map.
- A normal route exceeds one module index, two leaves, or 4,000 tokens without a
  justified cross-cutting exception.

Report an ambiguous module-boundary warning when the evidence suggests a split
but does not satisfy the Module Boundary Contract. Simulation never invents or
renames modules.
