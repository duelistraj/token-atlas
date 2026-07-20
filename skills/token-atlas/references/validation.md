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
- `PKF.md` sets `pkf.runtime_version: 4` and `pkf.retrieval` to `adaptive` or
  `mandatory`; missing or older runtimes require migration, and newer versions
  are reported as unsupported rather than downgraded.
- Every detected module has `INDEX.md`, `api.md`, `schema.md`, `business_rules.md`, and `ui.md`.
- Every module is a flat directory directly under `.ai/knowledge/`; nested module indexes are invalid.
- Shared docs exist: `glossary.md`, `dependencies.md`, `decision_log.md`.
- Every participating `.ai/**/*.md` document has valid OKF front matter.
- Every module leaf has a `source_symbols` path-to-symbol-list mapping; each path
  resolves, each symbol occurs in that source, and empty leaves use the standard marker.
- Every module leaf is complete or explicitly `pkf.materialization: pending`.
  Pending leaves have no source symbols and use the pending extraction marker.
- Every implementation-bearing leaf has an Edit Map with specific behavior,
  declared source symbols, tests, styles/tokens, and a targeted locator per row;
  placeholder behavior labels and omitted declared symbols are defects.
- `pkf.loads` and `pkf.related` are lists and resolve to existing docs.
- Architecture, root-index, and module-index `pkf.related` values are empty.
- Root-index `pkf.routes`, when present, is keyed by route ID; every route has a
  non-empty intent and triggers, names at least two exact modules, loads one to
  three complete leaves, and stays within the 4,000-token task budget.
- `resource` paths resolve or are marked `TODO`.
- APIs, schemas, business rules, UI facts, commands, dependencies, and architecture match source truth.
- Deleted or renamed evidence is not cited as current.
- No duplicate authoritative facts exist.
- Module names are target-repository-derived, placeholders are not promoted to modules, and coarse boundaries are reported when they mix independently routable capabilities satisfying the Module Boundary Contract.
- Routing starts from `PKF.md -> MEMORY.md -> ARCHITECTURE.md -> knowledge/INDEX.md`.
- `PKF.md` embeds the Retrieval Protocol: the cheap local probe, adaptive PKF
  activation, ordered route, fallback/verification, and knowledge-base sync.
- `PKF.md` sets `pkf.closeout` to `adaptive` or `off` and embeds the mandatory Closeout Protocol with a silent read-only bypass, intentional-mutation gate, session acknowledgement, incremental sync, and recursion prevention.
- A neutral bootstrap applies the adaptive retrieval and knowledge-impact gates,
  references retrieval and closeout in `.ai/PKF.md`, and names no vendor, agent,
  or model.
- Simulation output is present when enabled.
- Token budget output is present at the selected detail level.
- Startup, leaf, and representative normal task routes respect the 2,500, 1,500,
  and 4,000 token gates. Advisory mode warns; CI mode fails over-budget routes.

## Required Simulation Scenarios

Run only in `ci`, `full`, `simulation: required`, or `simulation: all`:

| Scenario | Expected routing |
|----------|------------------|
| API route change | root index -> module index -> `api.md` |
| Schema/model change | root index -> module index -> `schema.md` |
| Business logic change | root index -> module index -> `business_rules.md` |
| UI behavior change | root index -> module index -> `ui.md` |
| Cross-cutting change | root-index `pkf.routes` -> one to three exact complete leaves |
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

Routine semantic closeout uses `--scope affected --detail summary` with every
turn-owned changed source or leaf path. Runtime, shared architecture, or index
changes automatically require full validation. Full detail remains the default
for explicit validation and CI. Summary output contains counts, findings, and
only token routes that violate a threshold; it omits successful token-route
inventory.

## CI Exit Meaning

- `0`: valid advisory request, help output, or no CI blocking errors.
- `1`: CI blocking validation error.
- `2`: invalid command or option usage when a wrapper is involved.

## Deterministic Validator Non-Goals

The bundled `scripts/pkf_validate.py` enforces the mechanical subset: runtime
version, required files, flat module layout, mandatory protocol clauses, a valid
closeout mode, both root bootstrap references, OKF front matter, source-symbol
presence and literal resolution, Edit Map specificity and evidence consistency,
path resolution, routing reachability, affected-slice selection, and token
impact. It cannot prove that a literal occurrence is the correct declaration or
owner. Full source-truth synchronization, capability-boundary quality, invented-
fact detection, and duplicate-authoritative-fact detection remain semantic
validation responsibilities for this workflow.
