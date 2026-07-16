# Phase 3 - Optimize OKF Knowledge Base

## Purpose

Optimize the OKF knowledge base for efficient AI retrieval.

Improve routing, reduce context size, eliminate duplication, and ensure AI agents can load only the minimum knowledge required for any task.

Do not extract new repository knowledge.

During adaptive closeout, optimize only affected routes that exceeded a budget,
duplicated a fact, loaded unrelated context, or required fallback search.

---

## Inputs

- Existing PKF runtime
- Existing OKF knowledge base

---

## Outputs

A concise, consistent, and retrieval-optimized OKF knowledge base, plus token budget output according to the selected profile.

---

## Execution

### 1. Optimize Root Knowledge Index

Review `knowledge/INDEX.md`.

Ensure it:

- Lists every available module.
- Contains accurate module summaries.
- Uses meaningful routing keywords.
- Routes correctly to every module `INDEX.md`.
- Maps source paths and common task intents to modules.
- Separates automatic startup context from optional discovery context.
- Avoids embedding module details that belong in module documents.

---

### 2. Optimize Module Indexes

Review every module `INDEX.md`.

Ensure each module:

- Clearly describes its purpose.
- Routes common development tasks.
- Loads the minimum required documents.
- Avoids unnecessary context.
- Distinguishes task-specific loads from optional related documents.
- Provides file-path and keyword routing for the module.

---

### 3. Optimize Knowledge Documents

Review every OKF document.

Ensure:

- Information is concise.
- Facts are implementation-backed.
- Duplicate knowledge is removed.
- Each concept has one authoritative location.
- Evidence is compact and points to source paths or symbols.
- Sections are task-oriented and skimmable.

Split oversized documents when necessary.

Prefer this document shape:

```text
Purpose
When to load
Edit Map
Current verified facts or durable rules
Open TODOs
Related knowledge
```

Associate each behavior with exact source symbols, tests, styles/tokens, and a
targeted locator. Remove chronological feature summaries; retain history only
when a still-relevant decision belongs in `decision_log.md`.

### 3a. Optimize Module Boundaries

Apply the Module Boundary Contract in `initialize.md`. Treat a module as a
coarse boundary defect when its leaves mix at least two independently routable,
source-backed capabilities. When ownership is unambiguous, automatically finish
the maintenance/extraction repartition by tightening root routing, module
indexes, and cross-capability `pkf.related` edges.

Do not split because of size, a name, a placeholder, or a roadmap entry alone.
Do not create nested modules. Preserve and report the current boundary when the
evidence cannot assign every moved fact safely.

---

### 4. Optimize Metadata

Review every document's OKF metadata.

Ensure:

- Required fields are present.
- `resource` references are valid.
- `tags` remain accurate.
- `pkf.loads` loads only the minimum required documents.
- `pkf.related` references only meaningful related knowledge.
- Automatic load paths stay within token budget thresholds.

Remove obsolete metadata.

Reject broad load chains that pull unrelated modules into context.

---

### 5. Optimize Shared Knowledge

Review:

- `glossary.md`
- `dependencies.md`
- `decision_log.md`
- `MEMORY.md`
- `ARCHITECTURE.md`

Ensure they contain only repository-wide knowledge.

Move module-specific information into the appropriate module.

Repository-wide knowledge should help route work or avoid repeated rediscovery. It should not describe local implementation details that only matter after a module is selected.

---

### 6. Remove Stale Knowledge

Identify knowledge that no longer reflects the repository.

Update or remove:

- Deprecated APIs
- Removed schemas
- Obsolete business rules
- Invalid routing
- Broken references

---

### 7. Verify Retrieval Efficiency

Run `simulate.md` while optimizing retrieval only when the selected `simulation` option requires it.

The expected retrieval flow is:

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
Required OKF documents
```

The knowledge base should support minimal-context retrieval without unnecessary repository exploration.

In `required` or `all` simulation mode, test these retrieval scenarios:

- "Change an API route."
- "Change a schema or data model."
- "Change business logic."
- "Change UI behavior."
- "Understand repository architecture."
- "Update dependencies or tooling."

For each simulated scenario, record selected modules, required documents, optional related documents, token cost, routing evidence, warnings, and errors. In default `changed` mode, simulate only the current task intent or changed paths.

Remove unnecessary automatic loads, move optional context to `pkf.related`, and fix ambiguous routing evidence.

---

### 8. Generate Token Budget Report

Generate token budget output during optimization according to `token_budget`.

Track:

- Startup path: `PKF.md -> MEMORY.md -> ARCHITECTURE.md -> knowledge/INDEX.md`.
- Changed module paths in `summary` mode.
- Each leaf, representative one-index/two-leaf task load, and broad `pkf.loads` chain in `full` mode.

For each reported entry include:

- Route name.
- Documents loaded automatically.
- Estimated token cost.
- Estimator type: `exact` or `approximate`.
- Threshold status: `passed`, `warning`, or `error`.
- Retrieval impact.

Use an exact tokenizer when available locally for the target model. Otherwise use the deterministic approximate estimator `ceil(character_count / 4)` and label the report as approximate.

Default budgets and thresholds:

- Normal retrieval: one module index and one or two leaves.
- Startup path above 2,500 tokens: warning locally, error in CI.
- Any leaf above 1,500 tokens: warning locally, error in CI.
- Representative normal task route above 4,000 tokens: warning locally, error in CI.
- Any unrelated module loaded automatically: blocking error.

If a route exceeds a threshold, tighten indexes, split oversized documents, or move optional documents from `pkf.loads` to `pkf.related`.

---

## Rules

- Do not modify application code.
- Do not invent information.
- Do not duplicate knowledge.
- Prefer references over repetition.
- Keep documents concise.
- Optimize for minimal AI context loading.
- Preserve existing manual documentation whenever possible.
- Maintain valid OKF documents.
- Keep root and module indexes as routing surfaces.
- Treat excessive `pkf.loads` entries as optimization defects.
- Generate summary token budget output by default; generate full token budget reports only in `ci`, `full`, or explicit `token_budget: full` mode.
- Treat unrelated automatic module loads as blocking optimization defects.
- Treat unresolved capability ownership as a reported ambiguity, not permission to guess.

---

## Completion Criteria

Phase 3 succeeds when:

- The OKF knowledge base is fully navigable.
- Root and module routing are accurate.
- Duplicate knowledge has been removed.
- Metadata is consistent.
- Shared knowledge contains only repository-wide information.
- All cross references are valid.
- AI retrieval requires only the minimum necessary context.
- Token budget output is generated at the selected summary or full level and threshold status is recorded.
- Startup context is at or below warning threshold, or warnings are reported with recommendations.
- Retrieval simulations produce evidence-backed reports when enabled; required scenarios run in `ci`, `full`, or `simulation: required|all` mode.
- No unrelated modules are loaded automatically.
- The knowledge base is optimized for long-term maintenance.
