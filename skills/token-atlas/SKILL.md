---
name: token-atlas
description: Generate and maintain repository-specific PKF runtime and OKF knowledge bases on demand or incrementally in target repositories. Use when explicitly asked to initialize, extract, maintain, optimize, validate, simulate, or export PKF/OKF knowledge, and when an initialized repository's `.ai/PKF.md` or agent instructions require the automatic adaptive Token Atlas closeout after a user turn. Do not implicitly initialize unrelated repositories.
---

# Token Atlas

## Purpose

Use Token Atlas to create and maintain `.ai/` Project Knowledge Framework (PKF) runtime files and an Open Knowledge Format (OKF) knowledge base for a target repository.

Initialize only when explicitly invoked. After initialization, run the adaptive
closeout when the target repository's own instructions require it. Do not install
watchers, daemons, global hooks, background jobs, or persistent runtime services.

## Workflow Selection

Start by reading the target repository's `.ai/PKF.md` when it exists.

If `.ai/PKF.md` is missing, read `references/initialize.md` before repository analysis. If `.ai/PKF.md` exists, read `references/maintenance.md` before extraction when the repository has changes.

Use the smallest needed reference set:

| Need | Read |
|------|------|
| Create missing PKF runtime and OKF skeleton | `references/initialize.md` |
| Detect changed, renamed, deleted, stale, or duplicate knowledge | `references/maintenance.md` |
| Run the automatic end-of-turn adaptive gate | `references/closeout.md` |
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
- Store each durable fact in one narrow authoritative document. This governs where a fact is written, not how many docs a task reads: a cross-cutting change legitimately routes to several leaf docs, one slice each.
- Derive flat module names from source-backed functional capabilities. Prefer capability boundaries over technical layers only when the repository proves at least two independently routable capabilities; never prescribe module names or create speculative modules.
- During maintenance, automatically repartition coarse modules when capability ownership is unambiguous. Preserve the current structure and report ambiguity instead of guessing.
- During `initialize`, embed the Retrieval Protocol into the generated `.ai/PKF.md`, and ensure a neutral bootstrap (a root `AGENTS.md`, or the repository's existing agent-instruction entry point) routes every task to `.ai/PKF.md`.
- Default the runtime to `pkf.closeout: adaptive`. Permit the quoted YAML value `pkf.closeout: "off"` as an explicit opt-out.
- Run closeout exactly once before the final response to each user turn. Treat an unchanged acknowledged change set or an `.ai/`-only change as a no-op, and never recursively close out a closeout.
- Keep all generated guidance vendor, agent, and model agnostic. Reference no specific assistant, tool, or model.
- Keep `pkf.loads` minimal and put optional context in `pkf.related`.
- Require every module leaf to expose machine-readable `source_symbols`; use a compact Edit Map to connect behaviors to symbols, tests, styles, and targeted locator commands.
- Cache startup protocol and index acknowledgements for the session. Re-read them only when they changed, contradict source truth, or the task needs an uncached section.
- Keep a normal task within one module index, one or two leaves, and the exact named symbols. Require an explicit reason for cross-cutting exceptions.
- Do not load or generate `.ai/retrieval/` unless retrieval exports are enabled.
- Report stale, unsupported, duplicate, or broad-loading knowledge as validation defects.

## Output Expectations

Every run should report:

- Workflow references used.
- Files read or changed.
- Enforcement artifacts written during `initialize` (embedded Retrieval Protocol in `.ai/PKF.md`, neutral bootstrap).
- Source evidence for durable facts.
- Validation warnings or errors.
- Token budget status when optimization or validation runs.
- Targeted locator commands, retrieval-budget usage, and whether fallback search was required (with a reason when it was).
- Follow-up workflows needed, if any.
- Closeout status (`no-op`, `updated`, `stale`, `disabled`, or `blocked`) when the closeout protocol applies.
