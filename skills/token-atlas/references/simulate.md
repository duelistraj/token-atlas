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
2. The smallest set of matching atomic keyed `pkf.routes` entries for a cross-capability intent.
3. Module names and keywords in `knowledge/INDEX.md`.
4. Module `INDEX.md` routing tables.
5. Leaf-level `pkf.related` only as optional context.

Do not automatically load unrelated modules.

For every task, select the smallest context packet that completely covers its requirements, then return the exact `source_symbols` and Edit Map locator commands.
For a cross-capability task, compose the smallest matching atomic route set, deduplicate its leaves, and remove any leaf without unique requirement coverage.
When equally complete alternatives use the same leaf count, prefer the lower estimated token cost.
Do not load adjacent indexes or leaf-level `pkf.related` entries unless routed evidence is contradictory.

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
Coverage status: <complete, incomplete, or unknown>
Minimality status: <minimal, redundant, or unknown>
Source targets: <path:symbol entries>
Targeted commands: <sg when verified as ast-grep, otherwise exact rg commands>
Fallback search: <yes or no>
Fallback reason: <reason or none>
Route telemetry: <atomic route IDs, requirements covered, unique leaves, and estimated tokens>
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
- A selected route does not completely cover the task requirements.
- A selected leaf contributes no requirement that the other selected leaves do not already cover.
- An atomic cross-capability route is absent, names pending leaves, lacks requirement coverage metadata, or contains redundant leaves.
- A composed task rereads duplicate leaves, selects a route unrelated to a task clause, or retains a route or leaf without unique requirement coverage.

Report an ambiguous module-boundary warning when the evidence suggests a split
but does not satisfy the Module Boundary Contract. Simulation never invents or
renames modules.
