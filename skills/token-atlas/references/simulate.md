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
