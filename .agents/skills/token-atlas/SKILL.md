---
name: token-atlas
description: Develop and validate Token Atlas PKF/OKF workflows and fixtures, including mutation-gated adaptive closeout behavior. Use when maintaining the token-atlas skill's public/internal packages, initialization protocols, validators, fixtures, or local benchmarks; never run Token Atlas against its own maintenance repository.
---

# Token Atlas

## Purpose

Generate and maintain a repository-specific, Open Knowledge Format (OKF) compatible knowledge base optimized for minimal-context retrieval by AI coding agents.

Token Atlas extracts verified repository knowledge on demand or incrementally, stores each fact in one authoritative location, and routes agents to the smallest useful context set for a task.

This `.agents/skills/token-atlas/` copy is the internal development and benchmarking surface for the Token Atlas project. The public user-facing package lives under `skills/token-atlas/`; keep normal target-repository usage guidance there and keep benchmark or maintenance-repo-specific guidance here.

---

## Execution

### 1. Recover PKF Startup

At the beginning of every session, detect whether `.ai/PKF.md` exists without loading its contents. The neutral bootstrap owns the adaptive retrieval decision.

If `.ai/PKF.md` is missing and Token Atlas was explicitly invoked:

- Do not continue with repository analysis yet.
- Execute `references/initialize.md` to create the PKF runtime and OKF skeleton.
- Use the bundled scaffold helper, which validates the initialized structure.
- Resume the normal execution flow only after `PKF.md` exists.
- Report the recovery as a startup action.

If `.ai/` exists but `.ai/PKF.md` is missing, treat the runtime as incomplete and run initialization before extraction.

### 2. Analyze Repository

After startup recovery, determine:

- Repository structure
- Technologies
- Functional modules
- Existing PKF runtime (`.ai/`)
- Existing OKF knowledge base
- Current change set, when available

Do not modify files during analysis.

---

### 3. Determine Execution Profile

Default profile is `core`.

Use these profiles:

- `core`: initialize, maintain incrementally, extract, optimize, and run lightweight validation.
- `ci`: `core` plus strict validation, required simulator scenarios, and token budget gates.
- `retrieval`: `core` plus retrieval export generation when explicitly requested.
- `full`: all workflows, including full simulator scenarios and retrieval exports.

Profile options:

- `retrieval_exports`: `off | rag | graph | all`, default `off`.
- `simulation`: `off | changed | required | all`, default `changed`.
- `token_budget`: `summary | full`, default `summary`.
- `validation_strictness`: `advisory | ci`, default `advisory`.

Do not generate or load retrieval exports unless `retrieval_exports` is not `off`. Retrieval exports are generated artifacts, never the source of truth, and must not be part of the PKF startup path.

### 4. Determine Execution Mode

If `.ai/` does **not** exist or `.ai/PKF.md` is missing:

- Execute `references/initialize.md`
- Execute `references/extract.md` using **Hybrid Extraction** for shared knowledge, routing, and public entry points
- Mark deferred leaves `pkf.materialization: pending`
- Validate once after hybrid extraction
- Execute `references/optimize.md` only when validation reports a routing,
  duplication, or token-budget defect; revalidate only the affected slice if it
  changes knowledge
- Execute `references/simulate.md` during initialization only when `simulation`
  is explicitly `required` or `all`
- Execute `references/export.md` only when `retrieval_exports` is not `off`

Otherwise, after an intentional mutation with durable knowledge impact:

- Apply the embedded closeout gate first and stop on a no-op
- Route turn-owned paths with bundled `pkf_route.py`; do not replay startup for
  a mapped route
- Read `references/closeout.md` only for a partial, unmapped, or exceptional route
- Execute `references/maintenance.md` to detect changed paths, stale references, duplicate facts, and affected docs when closeout identifies an exceptional case
- Execute `references/extract.md` using **Incremental Extraction**
- Validate the affected slice once
- Execute `references/optimize.md` only for a reported affected-route defect and
  revalidate only if it changes knowledge
- Execute `references/simulate.md` only according to the selected `simulation` option
- Execute `references/export.md` only when `retrieval_exports` is not `off`

Stop immediately on validation failures only when `validation_strictness: ci` is selected. In advisory mode, report blocking recommendations without treating the default workflow as a CI gate.

---

## Retrieval Contract

Every generated knowledge base must support this loading path:

```text
PKF.md
  -> MEMORY.md
  -> ARCHITECTURE.md
  -> knowledge/INDEX.md
  -> knowledge/<module>/INDEX.md
  -> only the task-required OKF documents
```

Use each layer for a different job:

- `PKF.md`: startup sequence, operating rules, and validation gates.
- `MEMORY.md`: stable repository facts that apply across most tasks.
- `ARCHITECTURE.md`: repository structure and module ownership.
- `knowledge/INDEX.md`: root routing by task, keyword, module, and file path.
- Module `INDEX.md`: module-level routing by task and document.
- Leaf OKF documents: concise source-backed facts for one knowledge type.

Each module leaf must expose `source_symbols` as a repository-relative
path-to-symbol-list mapping and use a compact Edit Map to connect behavior to
symbols, tests, styles/tokens, and targeted locator commands.

`pkf.loads` means "load automatically for this task." Keep it minimal.

`pkf.related` means "useful if the task expands." Do not treat related documents as automatic context.

During initialization, set `pkf.runtime_version: 3`, `pkf.retrieval: adaptive`, and `pkf.closeout: adaptive`, embed the Retrieval and Closeout Protocols in `.ai/PKF.md`, and add a neutral bootstrap in a root `AGENTS.md` or the repository's existing agent-instruction entry point. Initialize architecture, routing, dependencies, and public entry-point facts, and mark deferred leaves `pkf.materialization: pending`. The bootstrap allows a cheap local probe without loading PKF, activates PKF for cross-capability or broad-discovery work, and knowledge-impact-gates closeout. Generated guidance must not name a specific vendor, agent, or model.

---

## Incremental Maintenance

Use `references/maintenance.md` in the default `core` profile when closeout identifies exceptional drift, migration, or module-boundary work. Routine semantic closeout routes directly from turn-owned changed paths to affected leaves.

Maintenance determines changed paths, affected modules, affected canonical docs, stale references, duplicate facts, and optional retrieval export invalidation.

Change detection order:

1. `git diff --cached --name-status`
2. `git diff --name-status`
3. Full repository scan fallback

Deleted or renamed source evidence must invalidate affected facts. Retrieval exports are regenerated only when `retrieval_exports` is not `off`.

### Module Boundary Maintenance

Derive flat module names from the target repository's source-backed functional
capabilities; never prescribe a module vocabulary. When an existing module
contains at least two independently routable capabilities that satisfy the
Module Boundary Contract in `references/initialize.md`, automatically
repartition it during maintenance and extraction. Preserve the existing
structure and report ambiguity when ownership is not provable. Never create a
module from placeholder or roadmap-only evidence.

---
## Retrieval Simulator

Use `references/simulate.md` to predict the smallest useful context set for a natural-language task intent and optional changed file paths.

Run the simulator:

- In `changed` mode to test only changed paths or the current task intent.
- In `required` mode to prove representative tasks load only expected documents.
- In `all` mode to test changed-path, required, and broad-load scenarios.
- During optimization to identify broad, ambiguous, or unrelated automatic loads.
- On demand when a user asks what PKF would retrieve for a task.

A simulation report must include selected modules, required docs, source targets,
targeted commands, fallback-search status and reason, retrieval-budget usage,
routing evidence, and warnings or errors.

Treat unrelated modules loaded automatically through `pkf.loads` as blocking validation defects.

---

## Retrieval Exports

Use `references/export.md` only when `retrieval_exports` is `rag`, `graph`, or `all`.

Export modes:

- `off`: generate no retrieval artifacts and do not validate `.ai/retrieval/`.
- `rag`: generate `documents.jsonl` and `claims.jsonl`.
- `graph`: generate `entities.jsonl`, `relationships.jsonl`, and `claims.jsonl`.
- `all`: generate all retrieval export files.

Exports are backend-neutral generated artifacts under `.ai/retrieval/`. They may feed vector RAG, GraphRAG, or custom tooling, but they must never become source truth or startup context.

---

## Benchmarking

Use `references/benchmark.md` when a user or CI process requests skill benchmarking.

Benchmarking measures fixture-based skill quality, not just runtime speed. Run
normal suites against isolated fixture repositories under `benchmarks/fixtures/`.
When explicitly approved, the real-repository lifecycle eval may instead export
a pinned external target into isolated workspaces to measure PKF-versus-no-PKF
cost. Never target the token-atlas skill-maintenance repository itself.

After changing trigger or closeout semantics, run the focused activation-gate
eval documented in `references/benchmark.md` in addition to the relevant
fixture suite.

Benchmark suites:

- `quick`: startup and simple routing confidence.
- `core`: initialization, extraction, maintenance, validation, simulation, optimization, and stale-reference fixtures.
- `full`: `core` plus retrieval export fixtures.

Benchmark output modes:

- `text`: human-readable fixture and aggregate report.
- `json`: deterministic machine-readable report.

Treat invented facts, unsupported durable facts, stale evidence, broken routing, unrelated automatic loads, invalid exports, and wrapper workflow drift as benchmark failures.

---

## Knowledge Quality Standard

Each durable fact must be:

- Verified from source files, repository configuration, tests, or existing docs.
- Stored in the narrowest authoritative document.
- Written as retrieval-ready notes, not prose documentation.
- Traceable to source paths, symbols, commands, or config keys.
- Removed or marked `TODO` when no longer verifiable.

Prefer compact tables and bullets over long explanations. Do not copy large source snippets into `.ai/`.

---

## Context Budget

Optimize for small, predictable loads:

- Root and module indexes should be short routing surfaces, not knowledge dumps.
- Shared documents contain only repository-wide facts.
- Module documents contain only module-specific facts.
- Avoid repeating the same fact across indexes and leaf documents.
- Split a document only when independent tasks can load the split sections separately.
- Preserve useful manual notes, but move them to the correct authoritative location.

Optimization and validation must produce token budget output according to `token_budget`.

Use:

- `summary`: startup path, changed module paths, and threshold status.
- `full`: summary plus every module index load, representative tasks, and broad `pkf.loads` chains.

Estimate token cost for:

- Startup path: `PKF.md -> MEMORY.md -> ARCHITECTURE.md -> knowledge/INDEX.md`.
- Changed module paths in `summary` mode.
- Each module index load, representative tasks, and accidental broad `pkf.loads` chains in `full` mode.

Use an exact tokenizer when one is available locally for the target model. If no exact tokenizer is available, use a deterministic approximate estimator and label the report `approximate`; the default approximation is `ceil(character_count / 4)` for Markdown content after front matter is included.

Default budgets and thresholds:

- Read startup protocol and indexes only after adaptive retrieval activates; refresh only after changes, contradictions, or a need for an uncached section.
- Use one module index and one or two leaves for a normal task.
- Gate startup above 2,500 tokens, any leaf above 1,500 tokens, and a normal task
  route above 4,000 tokens. Warn locally and fail in CI.
- Treat unrelated modules loaded automatically through `pkf.loads` as a blocking error.

---

## Developer Tooling

Use `references/tooling.md` for command wrappers.

Commands are thin workflow selectors:

- `pkf init` -> `references/initialize.md`
- `pkf maintain` -> `references/maintenance.md`
- mutation-triggered closeout -> `references/closeout.md`
- `pkf extract` -> `references/extract.md`
- `pkf optimize` -> `references/optimize.md`
- `pkf validate` -> `references/validation.md`
- `pkf export` -> `references/export.md`
- `pkf simulate` -> `references/simulate.md`
- `pkf bench` -> `references/benchmark.md`

Tooling must keep documented workflows authoritative. Scripts may validate arguments and report CI startup failures, but must not reimplement extraction, optimization, validation, or export logic.
The public scaffold and route helpers are deterministic mechanics: they must not
decide capability boundaries, durable facts, or knowledge impact.

---
## Global Rules

- Source code is the single source of truth.
- Generate an OKF-compatible knowledge base.
- Preserve existing documentation whenever possible.
- Never invent implementation details.
- Never modify application code.
- Store each durable fact in one narrow authoritative document. This governs where a fact is written, not how many documents a task reads: a cross-cutting change may route to several leaf documents, one slice each.
- Keep capability modules flat and repository-derived; automatically migrate coarse boundaries only when evidence is unambiguous.
- Prefer incremental maintenance and affected-document updates.
- Migrate only affected legacy leaves during routine work; reserve a repository-wide leaf-contract migration for an explicit migration request or CI.
- Optimize for minimal AI context retrieval.
- Keep routing deterministic and easy to validate.
- Treat stale or unverified knowledge as a blocking issue when it could mislead an agent.

---

## Success

Execution succeeds only when:

- The scaffold mechanical check and the smallest required final or affected
  validation complete, with hard failure behavior only in `ci` strictness.
- The PKF runtime is synchronized.
- Initialization records both embedded mandatory protocols, the adaptive closeout mode, and the neutral bootstrap it created or updated.
- The OKF knowledge base reflects the repository.
- Incremental maintenance identifies stale references and duplicate facts.
- Optional retrieval exports are synchronized only when enabled.
- Developer tooling maps commands to documented workflows without duplicating PKF logic.
- AI retrieval is optimized.
