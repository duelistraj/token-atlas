---
name: token-atlas
description: Generate and maintain repository-specific PKF runtime and OKF knowledge bases in target repositories. Use when Codex is explicitly asked to initialize `.ai/` knowledge, extract source-backed repository facts, maintain stale PKF/OKF docs after code changes, optimize minimal context retrieval, validate PKF integrity, simulate retrieval for a task, or generate optional RAG/GraphRAG exports.
---

# Token Atlas

## Purpose

Use Token Atlas to create and maintain `.ai/` Project Knowledge Framework (PKF) runtime files and an Open Knowledge Format (OKF) knowledge base for a target repository.

This skill is activation-light and workflow-deep. Run it only when explicitly invoked by the user or when the target repository's own instructions opt into PKF startup. Do not install watchers, daemons, global hooks, background jobs, or persistent runtime services.

## Workflow Selection

Start by reading the target repository's `.ai/PKF.md` when it exists.

If `.ai/PKF.md` is missing, read `references/initialize.md` before repository analysis. If `.ai/PKF.md` exists, read `references/maintenance.md` before extraction when the repository has changes.

Use the smallest needed reference set:

| Need | Read |
|------|------|
| Create missing PKF runtime and OKF skeleton | `references/initialize.md` |
| Detect changed, renamed, deleted, stale, or duplicate knowledge | `references/maintenance.md` |
| Populate source-backed facts | `references/extract.md` |
| Tighten routing, deduplicate facts, and reduce context cost | `references/optimize.md` |
| Validate structure, sync, routing, token budget, and exports | `references/validation.md` |
| Predict retrieval context for a task intent or changed paths | `references/simulate.md` |
| Generate optional retrieval JSONL artifacts | `references/export.md` |
| Understand optional local command wrappers | `references/tooling.md` |

## Profiles

Default options:

```yaml
profile: core
retrieval_exports: off
simulation: changed
token_budget: summary
validation_strictness: advisory
```

Use `ci` for strict validation, required simulations, and full token budget reporting. Use `retrieval` or `full` only when retrieval exports are explicitly requested.

## Rules

- Treat source code, tests, configuration, and existing docs as source truth.
- Never invent implementation details.
- Never modify application code.
- Generate or update only PKF/OKF knowledge unless the user explicitly asks for tooling changes.
- Store each durable fact in one narrow authoritative document.
- Keep `pkf.loads` minimal and put optional context in `pkf.related`.
- Do not load or generate `.ai/retrieval/` unless retrieval exports are enabled.
- Report stale, unsupported, duplicate, or broad-loading knowledge as validation defects.

## Output Expectations

Every run should report:

- Workflow references used.
- Files read or changed.
- Source evidence for durable facts.
- Validation warnings or errors.
- Token budget status when optimization or validation runs.
- Follow-up workflows needed, if any.
