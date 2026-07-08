# Validate PKF And OKF

## Purpose

Validate PKF runtime integrity, OKF structure, repository synchronization, routing, token budget, and optional retrieval exports.

Only report findings unless the user asks for fixes.

## Profiles

- `advisory`: report warnings and errors without treating default local workflows as failed.
- `ci`: fail on blocking errors, missing required simulations, unrelated automatic loads, stale source truth, and token budget gates.

## Checks

Validate:

- `PKF.md`, `MEMORY.md`, `ARCHITECTURE.md`, and `knowledge/INDEX.md` exist.
- Every detected module has `INDEX.md`, `api.md`, `schema.md`, `business_rules.md`, and `ui.md`.
- Shared docs exist: `glossary.md`, `dependencies.md`, `decision_log.md`.
- Every participating `.ai/**/*.md` document has valid OKF front matter.
- `pkf.loads` and `pkf.related` are lists and resolve to existing docs.
- `resource` paths resolve or are marked `TODO`.
- APIs, schemas, business rules, UI facts, commands, dependencies, and architecture match source truth.
- Deleted or renamed evidence is not cited as current.
- No duplicate authoritative facts exist.
- Routing starts from `PKF.md -> MEMORY.md -> ARCHITECTURE.md -> knowledge/INDEX.md`.
- Simulation output is present when enabled.
- Token budget output is present at the selected detail level.

## Required Simulation Scenarios

Run only in `ci`, `full`, `simulation: required`, or `simulation: all`:

| Scenario | Expected routing |
|----------|------------------|
| API route change | root index -> module index -> `api.md` |
| Schema/model change | root index -> module index -> `schema.md` |
| Business logic change | root index -> module index -> `business_rules.md` |
| UI behavior change | root index -> module index -> `ui.md` |
| Architecture understanding | root index -> `ARCHITECTURE.md` and relevant module index |
| Dependency/tooling update | root index -> `dependencies.md` and affected module index |

## Retrieval Exports

Validate exports only when `retrieval_exports` is `rag`, `graph`, or `all`.

If exports are off, skip `.ai/retrieval/` checks.

## Report Format

Use:

- Passed
- Warnings
- Errors
- Token Impact

Errors should include file, issue, recommended fix, source evidence or missing evidence, retrieval impact, and token impact when relevant.

## CI Exit Meaning

- `0`: valid advisory request, help output, or no CI blocking errors.
- `1`: CI blocking validation error.
- `2`: invalid command or option usage when a wrapper is involved.
