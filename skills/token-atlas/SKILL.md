---
name: token-atlas
description: Generate and maintain repository-specific PKF runtime and OKF knowledge bases on demand or incrementally in target repositories. Use when explicitly asked to initialize, extract, maintain, optimize, validate, simulate, or export PKF/OKF knowledge, or when an initialized repository reports a partial, unmapped, pending, migration, or otherwise exceptional closeout route. Do not trigger for routine mapped closeout, read-only turns, knowledge-neutral mutations, or unrelated repositories.
---

# Token Atlas

## Purpose

Use Token Atlas to create and maintain `.ai/` Project Knowledge Framework (PKF) runtime files and an Open Knowledge Format (OKF) knowledge base for a target repository.

Initialize only when explicitly invoked. After initialization, run semantic
closeout when the target repository's own instructions require it. Do not install
watchers, daemons, global hooks, background jobs, or persistent runtime services.

## Workflow Selection

Start by detecting whether `.ai/PKF.md` exists. Read it only when an explicit Token Atlas workflow or the repository's adaptive retrieval gate activates PKF.

If `.ai/PKF.md` is missing, read `references/initialize.md` before repository analysis. If `.ai/PKF.md` exists, read `references/maintenance.md` before extraction only for exceptional drift, migration, or module-boundary work. Routine semantic closeout uses the embedded protocol, turn-owned changed paths, and repository-local route helper; read `references/closeout.md` only when the route is partial, unmapped, or exceptional.

Use the smallest needed reference set:

| Need | Read |
|------|------|
| Create missing PKF runtime and OKF skeleton | `references/initialize.md` |
| Detect changed, renamed, deleted, stale, or duplicate knowledge | `references/maintenance.md` |
| Resolve a partial, unmapped, pending, or exceptional closeout | `references/closeout.md` |
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
- During `initialize`, embed the adaptive Retrieval Protocol into `.ai/PKF.md`, and ensure a neutral bootstrap can decide whether to use PKF without loading it first.
- Default the runtime to `pkf.runtime_version: 4`, `pkf.retrieval: adaptive`, and `pkf.closeout: adaptive`. Permit `pkf.retrieval: mandatory` for compatibility and the quoted YAML value `pkf.closeout: "off"` as an explicit opt-out.
- Initialize in hybrid mode: materialize runtime, architecture, dependencies,
  public behavior, and source-backed cross-capability contracts needed for
  direct routing; mark unrelated or genuinely deferred leaves
  `pkf.materialization: pending`.
- Use the bundled scaffold helper for fresh runtime mechanics. Review capability
  boundaries before creation; never let directory heuristics become durable
  ownership without source evidence.
- Allow a cheap local source probe for a single-capability task. Activate PKF for explicit cross-capability, architecture, ownership, or repository-wide work, or when the probe cannot resolve the target without broad search.
- Bypass closeout silently on read-only turns. Use implementation context to reject knowledge-neutral mutations before loading PKF or inspecting Git. For a durable knowledge-impacting mutation, capture a deterministic session baseline, synchronize only affected knowledge, acknowledge only successfully validated snapshots, and never recursively close out a closeout.
- Keep all generated guidance vendor, agent, and model agnostic. Reference no specific assistant, tool, or model.
- Keep `pkf.loads` minimal and put optional context in `pkf.related`.
- Require every module leaf to expose machine-readable `source_symbols`; use a compact Edit Map to connect behaviors to symbols, tests, styles, and targeted locator commands.
- Require materialized public-behavior leaves to include their focused test evidence in `source_symbols`, and require module indexes to expose machine-readable `pkf.ownership_roots`.
- Cache PKF protocol and index acknowledgements after activation. Do not load the startup path for a bypassed local task or routine semantic closeout.
- Keep a normal task within one module index, one or two leaves, and the exact named symbols. Require an explicit reason for cross-cutting exceptions.
- Do not load or generate `.ai/retrieval/` unless retrieval exports are enabled.
- Report stale, unsupported, duplicate, or broad-loading knowledge as validation defects.
- Prefer the bundled dependency-light validator for mechanical checks; keep source-truth and duplicate-authority judgments in the semantic validation workflow.
- During routine closeout, run the validator with affected scope and summary detail. Reserve full, verbose validation for runtime/routing changes, exceptional maintenance, explicit validation, or CI.
- Route durable turn-owned changes with the repository-local changed-path helper before
  reading indexes or leaves. A mapped route reads only returned complete leaves,
  performs one affected validation, and must not replay PKF startup or load
  Token Atlas workflow instructions.
- During fresh initialization, rely on the scaffold helper's mechanical check,
  run `simulation=changed` over newly materialized routes, and run one final
  post-extraction validation. Optimize only reported defects and revalidate only
  an affected slice when optimization changes knowledge.

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
