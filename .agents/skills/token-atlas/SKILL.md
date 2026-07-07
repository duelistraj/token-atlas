---
name: token-atlas
description: Generate and maintain this repository's PKF runtime and OKF-compatible knowledge base. Use when Codex needs to initialize, extract, validate, or optimize `.ai/` knowledge files for the token-atlas repository while preserving source-code truth and avoiding application-code changes.
---

# Token Atlas

## Purpose

Generate and maintain a repository-specific, Open Knowledge Format (OKF) compatible knowledge base optimized for minimal-context retrieval by AI coding agents.

Token Atlas continuously extracts verified repository knowledge, stores each fact in one authoritative location, and routes agents to the smallest useful context set for a task.

---

## Execution

### 1. Recover PKF Startup

At the beginning of every session, attempt to read `.ai/PKF.md`.

If `.ai/PKF.md` is missing:

- Do not continue with repository analysis yet.
- Execute `initialize.md` to create the PKF runtime and OKF skeleton.
- Validate the initialized structure.
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

- Execute `initialize.md`
- Validate
- Execute `extract.md` using **Full Extraction**
- Validate
- Execute `optimize.md`
- Execute `simulate.md` only according to the selected `simulation` option
- Execute `export.md` only when `retrieval_exports` is not `off`
- Validate

Otherwise:

- Execute `maintenance.md` to detect changed paths, stale references, duplicate facts, and affected docs
- Execute `extract.md` using **Incremental Extraction**
- Validate
- Execute `optimize.md`
- Execute `simulate.md` only according to the selected `simulation` option
- Execute `export.md` only when `retrieval_exports` is not `off`
- Validate

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

`pkf.loads` means "load automatically for this task." Keep it minimal.

`pkf.related` means "useful if the task expands." Do not treat related documents as automatic context.

---

## Incremental Maintenance

Use `maintenance.md` in the default `core` profile whenever an existing PKF runtime is present.

Maintenance determines changed paths, affected modules, affected canonical docs, stale references, duplicate facts, and optional retrieval export invalidation.

Change detection order:

1. `git diff --cached --name-status`
2. `git diff --name-status`
3. Full repository scan fallback

Deleted or renamed source evidence must invalidate affected facts. Retrieval exports are regenerated only when `retrieval_exports` is not `off`.

---
## Retrieval Simulator

Use `simulate.md` to predict the smallest useful context set for a natural-language task intent and optional changed file paths.

Run the simulator:

- In `changed` mode to test only changed paths or the current task intent.
- In `required` mode to prove representative tasks load only expected documents.
- In `all` mode to test changed-path, required, and broad-load scenarios.
- During optimization to identify broad, ambiguous, or unrelated automatic loads.
- On demand when a user asks what PKF would retrieve for a task.

A simulation report must include selected module or modules, required OKF docs, optional related docs, estimated token cost, routing evidence, and warnings or errors.

Treat unrelated modules loaded automatically through `pkf.loads` as blocking validation defects.

---

## Retrieval Exports

Use `export.md` only when `retrieval_exports` is `rag`, `graph`, or `all`.

Export modes:

- `off`: generate no retrieval artifacts and do not validate `.ai/retrieval/`.
- `rag`: generate `documents.jsonl` and `claims.jsonl`.
- `graph`: generate `entities.jsonl`, `relationships.jsonl`, and `claims.jsonl`.
- `all`: generate all retrieval export files.

Exports are backend-neutral generated artifacts under `.ai/retrieval/`. They may feed vector RAG, GraphRAG, or custom tooling, but they must never become source truth or startup context.

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

Default thresholds:

- Warn when startup context is above 4,000 estimated tokens.
- Warn when any module task is above 8,000 estimated tokens.
- Treat unrelated modules loaded automatically through `pkf.loads` as a blocking error.

---

## Developer Tooling

Use `tooling.md` for command wrappers.

Commands are thin workflow selectors:

- `pkf init` -> `initialize.md`
- `pkf maintain` -> `maintenance.md`
- `pkf extract` -> `extract.md`
- `pkf optimize` -> `optimize.md`
- `pkf validate` -> `validation.md`
- `pkf export` -> `export.md`
- `pkf simulate` -> `simulate.md`

Tooling must keep documented workflows authoritative. Scripts may validate arguments and report CI startup failures, but must not reimplement extraction, optimization, validation, or export logic.

---
## Global Rules

- Source code is the single source of truth.
- Generate an OKF-compatible knowledge base.
- Preserve existing documentation whenever possible.
- Never invent implementation details.
- Never modify application code.
- Prefer incremental maintenance and affected-document updates.
- Optimize for minimal AI context retrieval.
- Keep routing deterministic and easy to validate.
- Treat stale or unverified knowledge as a blocking issue when it could mislead an agent.

---

## Success

Execution succeeds only when:

- Validation completes after every phase, with hard failure behavior only in `ci` strictness.
- The PKF runtime is synchronized.
- The OKF knowledge base reflects the repository.
- Incremental maintenance identifies stale references and duplicate facts.
- Optional retrieval exports are synchronized only when enabled.
- Developer tooling maps commands to documented workflows without duplicating PKF logic.
- AI retrieval is optimized.
