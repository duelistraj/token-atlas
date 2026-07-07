---
name: zephyr-pkf
description: Generate and maintain this repository's PKF runtime and OKF-compatible knowledge base. Use when Codex needs to initialize, extract, validate, or optimize `.ai/` knowledge files for the zephyr-pkf repository while preserving source-code truth and avoiding application-code changes.
---

# Zephyr PKF

## Purpose

Generate and maintain a repository-specific, Open Knowledge Format (OKF) compatible knowledge base optimized for minimal-context retrieval by AI coding agents.

Zephyr PKF continuously extracts verified repository knowledge, stores each fact in one authoritative location, and routes agents to the smallest useful context set for a task.

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

### 3. Determine Execution Mode

If `.ai/` does **not** exist or `.ai/PKF.md` is missing:

- Execute `initialize.md`
- Validate
- Execute `extract.md` using **Full Extraction**
- Validate
- Execute `optimize.md`
- Execute `simulate.md` for representative retrieval scenarios
- Validate

Otherwise:

- Execute `extract.md` using **Incremental Extraction**
- Validate
- Execute `optimize.md`
- Execute `simulate.md` for representative retrieval scenarios
- Validate

Stop immediately if validation fails.

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

## Retrieval Simulator

Use `simulate.md` to predict the smallest useful context set for a natural-language task intent and optional changed file paths.

Run the simulator:

- During validation to prove representative tasks load only expected documents.
- During optimization to identify broad, ambiguous, or unrelated automatic loads.
- On demand when a user asks what PKF would retrieve for a task.

A simulation report must include selected module or modules, required OKF docs, optional related docs, estimated token cost, routing evidence, and warnings or errors.

Treat unrelated modules loaded automatically through `pkf.loads` as blocking validation defects.

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

Every optimization and validation run must produce a token budget report.

Estimate token cost for:

- Startup path: `PKF.md -> MEMORY.md -> ARCHITECTURE.md -> knowledge/INDEX.md`.
- Each module index load: `knowledge/INDEX.md -> knowledge/<module>/INDEX.md`.
- Representative tasks: API, schema, business logic, UI, architecture, and dependency/tooling work.
- Accidental broad `pkf.loads` chains, especially chains that cross into unrelated modules.

Use an exact tokenizer when one is available locally for the target model. If no exact tokenizer is available, use a deterministic approximate estimator and label the report `approximate`; the default approximation is `ceil(character_count / 4)` for Markdown content after front matter is included.

Default thresholds:

- Warn when startup context is above 4,000 estimated tokens.
- Warn when any module task is above 8,000 estimated tokens.
- Treat unrelated modules loaded automatically through `pkf.loads` as a blocking error.

---

## Global Rules

- Source code is the single source of truth.
- Generate an OKF-compatible knowledge base.
- Preserve existing documentation whenever possible.
- Never invent implementation details.
- Never modify application code.
- Prefer incremental updates.
- Optimize for minimal AI context retrieval.
- Keep routing deterministic and easy to validate.
- Treat stale or unverified knowledge as a blocking issue when it could mislead an agent.

---

## Success

Execution succeeds only when:

- Validation passes after every phase.
- The PKF runtime is synchronized.
- The OKF knowledge base reflects the repository.
- AI retrieval is optimized.
