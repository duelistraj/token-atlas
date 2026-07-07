# Validation - PKF & OKF Integrity

## Purpose

Validate the integrity, synchronization, and retrieval efficiency of the Project Knowledge Framework (PKF).

Validation ensures the PKF runtime and the generated OKF knowledge base accurately represent the repository and support efficient AI context retrieval.

Do not modify any files.

Only report findings.

---

## Inputs

- Repository
- PKF runtime (`.ai/`)
- OKF knowledge base (`.ai/knowledge/`)

---

## Validation

### 1. PKF Runtime

Verify:

- `PKF.md` exists.
- `MEMORY.md` exists.
- `ARCHITECTURE.md` exists.

If `.ai/PKF.md` is missing:

- Report a blocking startup error.
- Recommend running `initialize.md`.
- Do not continue into repository synchronization checks that depend on the startup contract.

Ensure the runtime startup sequence is valid:

```text
PKF.md
    ->
MEMORY.md
    ->
ARCHITECTURE.md
    ->
knowledge/INDEX.md
```

---

### 2. OKF Structure

Verify:

- `.ai/` exists.
- `.ai/knowledge/` exists.
- Root `INDEX.md` exists.
- Every detected module has a directory.

Every module must contain:

- `INDEX.md`
- `api.md`
- `schema.md`
- `business_rules.md`
- `ui.md`

Verify shared documents:

- `glossary.md`
- `dependencies.md`
- `decision_log.md`

---

### 3. OKF Compliance

Every OKF document must contain valid front matter.

Required fields:

```yaml
type
title
description
resource
tags
timestamp

pkf:
  loads
  related
```

Verify:

- Metadata is valid.
- Metadata is internally consistent.
- Referenced resources exist.
- Every `.ai/**/*.md` document that participates in PKF retrieval has the required metadata.
- Required metadata fields are present exactly once.
- `pkf.loads` and `pkf.related` are lists.
- `pkf.loads` and `pkf.related` entries resolve to existing documents.
- `resource` paths resolve to existing repository paths or are marked `TODO`.

---

### 4. Repository Synchronization

Verify the knowledge base reflects the repository.

Ensure:

- APIs match implementation.
- Schemas match models.
- Business rules match implementation.
- UI documentation matches the frontend.
- `ARCHITECTURE.md` reflects repository structure.
- `MEMORY.md` reflects stable project knowledge.
- Commands, scripts, dependencies, and configuration facts match repository files.
- Deleted or renamed source files are not referenced as current facts.
- Source evidence labels point to existing files, symbols, commands, config keys, or tests.
- Source evidence older than the current implementation is updated or marked `TODO`.

Unknown information must be marked as `TODO`.

Never fabricated.

---

### 5. Knowledge Quality

Verify:

- No duplicate knowledge exists.
- Every concept has one authoritative location.
- Duplicate facts across authoritative documents are reported.
- Module summaries remain concise.
- Shared documents contain only repository-wide knowledge.
- Indexes route to knowledge instead of duplicating leaf document content.
- Facts include enough source evidence to be rechecked.

---

### 6. Routing Integrity

Verify the routing graph.

Expected navigation:

```text
PKF.md
    ->
MEMORY.md
    ->
ARCHITECTURE.md
    ->
knowledge/INDEX.md
    ->
Module INDEX.md
    ->
Knowledge Documents
```

Ensure:

- Every referenced document exists.
- Every module is reachable.
- No broken references exist.
- No circular routing exists.
- Every graph edge implied by `pkf.loads`, `pkf.related`, source references, and module ownership resolves to valid endpoints.
- Missing, stale, or ambiguous graph endpoints are reported as validation defects.

---

### 7. Retrieval Optimization

Simulate an AI retrieval session.

Verify that:

- Every task begins at `knowledge/INDEX.md`.
- Module `INDEX.md` files route correctly.
- `pkf.loads` loads only the minimum required documents.
- `pkf.related` references only meaningful documents.
- Unrelated modules are never loaded.

The knowledge base should support minimal-context retrieval.

Simulate representative tasks:

| Task | Expected routing |
|------|------------------|
| API change | Root index -> module index -> `api.md` |
| Schema change | Root index -> module index -> `schema.md` |
| Business rule change | Root index -> module index -> `business_rules.md` |
| UI change | Root index -> module index -> `ui.md` |
| Architecture question | Root index -> `ARCHITECTURE.md` and relevant module index |
| Dependency/tooling change | Root index -> `dependencies.md` and affected module index |

Flag any route that loads unrelated module facts.

---

### 8. Token Budgeting

Generate or verify a token budget report during validation.

Track:

- Startup path: `PKF.md -> MEMORY.md -> ARCHITECTURE.md -> knowledge/INDEX.md`.
- Each module index load.
- Representative task loads for API, schema, business logic, UI, architecture, and dependency/tooling work.
- Accidental broad `pkf.loads` chains.

Estimator rules:

- Use an exact tokenizer when available locally for the target model.
- Otherwise use `ceil(character_count / 4)` and label the result `approximate`.
- Report which estimator was used.

Default thresholds:

| Check | Threshold | Severity |
|------|-----------|----------|
| Startup path | Above 4,000 estimated tokens | Warning |
| Module task | Above 8,000 estimated tokens | Warning |
| Unrelated automatic module load | Any occurrence | Error |

Validation must fail when unrelated modules are loaded automatically through `pkf.loads`.

---

## Validation Report

Produce:

### Passed

Successful validation checks.

---

### Warnings

Non-blocking issues.

Include:

- File
- Issue
- Recommendation
- Retrieval impact, when relevant
- Token Impact, when relevant

---

### Errors

Blocking issues.

Include:

- File
- Issue
- Recommended fix
- Source evidence or missing evidence
- Retrieval impact, when relevant
- Token Impact, when relevant

Stop the PKF pipeline if any blocking errors exist.

---

### Token Impact

Summarize estimated retrieval cost and load-path risk.

Include:

- Startup path estimate for `PKF.md -> MEMORY.md -> ARCHITECTURE.md -> knowledge/INDEX.md`.
- Each module index load estimate.
- Representative task estimates for API, schema, business logic, UI, architecture, and dependency/tooling work.
- Broad or accidental `pkf.loads` chains.
- Threshold status for every tracked route.
- Whether estimates are exact tokenizer counts or approximate counts.

Use this section even when the estimate is approximate. Label approximations clearly. Include warnings above the 4,000-token startup threshold and 8,000-token module task threshold. Report unrelated automatic module loads as blocking errors.

---

## Rules

- Never modify documentation.
- Never invent missing information.
- Never ignore validation failures.
- Validate against the repository only.
- Treat the repository as the single source of truth.
- Treat misleading stale knowledge as blocking.
- Treat bloated automatic load paths as blocking when they defeat minimal-context retrieval.

---

## Success Criteria

Validation succeeds when:

- PKF runtime is valid.
- OKF knowledge base is structurally complete.
- Every document is OKF compliant.
- Repository knowledge is synchronized.
- Routing is valid.
- Retrieval simulation succeeds.
- Token budget report is present and threshold status is clear.
- AI can navigate using minimal context.
- No blocking errors remain.
