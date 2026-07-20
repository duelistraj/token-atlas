# Optimize Retrieval

## Purpose

Reduce context cost, remove duplicate knowledge, and make PKF routing deterministic.

Do not extract new facts in this workflow.

During adaptive closeout, optimize only affected routes that exceeded a budget,
duplicated a fact, loaded unrelated context, or required fallback search.

## Optimize Indexes

Root `knowledge/INDEX.md` should:

- List every available module.
- Route by task, keyword, and file path.
- Avoid copying leaf knowledge.
- Keep automatic startup context separate from optional discovery context.

Module `INDEX.md` files should:

- Describe module purpose.
- Route common tasks to the minimum required leaf docs.
- Keep optional context in `pkf.related`.
- Include path and keyword routing for the module.

## Optimize Documents

Each OKF document should be concise and source-backed.

Preferred shape:

```text
Purpose
When to load
Edit Map
Current verified facts or durable rules
Open TODOs
Related knowledge
```

Keep Edit Maps compact and behavior-oriented. Associate each behavior with exact
source symbols, tests, styles/tokens, and a targeted locator. Remove chronological
feature summaries; retain history only when a still-relevant decision belongs in
`decision_log.md`.

Split oversized documents only when independent tasks can load the split sections separately.

## Optimize Module Boundaries

Apply the Module Boundary Contract from `initialize.md`. A module whose leaves
mix at least two independently routable, source-backed capabilities is a coarse
boundary defect. When ownership is unambiguous, automatically finish the
maintenance/extraction repartition by tightening root routing, module indexes,
and keyed cross-capability `pkf.routes` entries. Do not split on document size,
naming, or placeholders alone. Do not create nested modules.

## Token Budget

Estimate automatic context cost for:

- Startup path: `PKF.md -> MEMORY.md -> ARCHITECTURE.md -> knowledge/INDEX.md`.
- Changed module paths in summary mode.
- Each module index load, representative task, and broad load chain in full mode.

Use an exact tokenizer when locally available. Otherwise use `ceil(character_count / 4)` and label estimates `approximate`.

Default budgets and thresholds:

- Normal retrieval: one module index and one or two leaf docs.
- Startup path above 2,500 tokens: warning locally, error in CI.
- Any leaf above 1,500 tokens: warning locally, error in CI.
- Representative normal task route above 4,000 tokens: warning locally, error in CI.
- Any unrelated module loaded automatically: blocking error.

Treat a cross-cutting task as several minimal capability slices. It may exceed the
normal document count only when the retrieval trace records the reason.

## Rules

- Keep `pkf.loads` to required context only.
- Move useful but nonessential docs to `pkf.related`.
- Remove duplicate facts from broader docs when a narrower authoritative doc owns them.
- Keep shared docs repository-wide, not module-specific.
- Treat stale or broad automatic loads as optimization defects.
- Report unresolved capability ownership instead of forcing a split.
