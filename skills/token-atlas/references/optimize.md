# Optimize Retrieval

## Purpose

Reduce context cost, remove duplicate knowledge, and make PKF routing deterministic.

Do not extract new facts in this workflow.

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
Source map
Verified facts
Open TODOs
Related knowledge
```

Split oversized documents only when independent tasks can load the split sections separately.

## Token Budget

Estimate automatic context cost for:

- Startup path: `PKF.md -> MEMORY.md -> ARCHITECTURE.md -> knowledge/INDEX.md`.
- Changed module paths in summary mode.
- Each module index load, representative task, and broad load chain in full mode.

Use an exact tokenizer when locally available. Otherwise use `ceil(character_count / 4)` and label estimates `approximate`.

Default thresholds:

- Startup path above 4,000 tokens: warning.
- Module task above 8,000 tokens: warning.
- Any unrelated module loaded automatically: blocking error.

## Rules

- Keep `pkf.loads` to required context only.
- Move useful but nonessential docs to `pkf.related`.
- Remove duplicate facts from broader docs when a narrower authoritative doc owns them.
- Keep shared docs repository-wide, not module-specific.
- Treat stale or broad automatic loads as optimization defects.
