# zephyr-pkf
Zephyr PKF is an AI context optimization framework that continuously extracts verified repository knowledge and generates an OKF-compatible knowledge base optimized for minimal-context retrieval by AI coding agents.

## PKF Lifecycle

Zephyr PKF treats `.ai/` Markdown as the canonical source of repository knowledge. Generated indexes and retrieval exports are derived artifacts, not the source of truth.

1. Initialize: create `.ai/PKF.md`, runtime docs, the root knowledge index, shared docs, and module skeletons.
2. Extract: populate only source-backed facts from the repository into the narrowest authoritative OKF documents.
3. Optimize: reduce duplicate knowledge, tighten routing, and keep `pkf.loads` minimal.
4. Simulate retrieval: predict selected modules, required docs, optional related docs, token cost, and routing evidence for representative tasks.
5. Validate: check structure, metadata, stale evidence, broken references, duplicate facts, routing integrity, simulations, and token impact.
6. Generate retrieval exports: build backend-neutral JSONL or graph artifacts from the canonical Markdown knowledge base.

## Startup Recovery

At the beginning of a PKF session, read `.ai/PKF.md`. If it is missing, run initialization before repository analysis. This creates the runtime contract that tells agents how to load `MEMORY.md`, `ARCHITECTURE.md`, and `knowledge/INDEX.md`.

## Validation Report

Validation reports use four sections:

- Passed: checks that succeeded.
- Warnings: non-blocking issues with recommendations and retrieval impact.
- Errors: blocking issues with evidence and recommended fixes.
- Token Impact: estimated startup and task retrieval costs, including broad `pkf.loads` chains.

Token counts should use an exact tokenizer when available. Otherwise, reports must label estimates as approximate.

## Token Budgeting

Optimization and validation generate a token budget report for the startup path, each module index load, representative task loads, and broad `pkf.loads` chains.

Default thresholds:

| Route | Threshold | Result |
|------|-----------|--------|
| Startup path | Above 4,000 estimated tokens | Warning |
| Module task | Above 8,000 estimated tokens | Warning |
| Unrelated automatic module load | Any occurrence | Error |

Use an exact tokenizer when available. Otherwise use `ceil(character_count / 4)` and mark the report approximate.

Example report shape:

```text
Token Impact
Estimator: approximate, ceil(character_count / 4)
Startup path: 3,420 tokens, passed
Module task: auth API change, 5,880 tokens, passed
Module task: sales UI change, 8,450 tokens, warning, split UI notes or move optional docs to pkf.related
Broad loads: none, passed
```

## Retrieval Simulation

`simulate.md` defines the deterministic retrieval simulator workflow. Input is a natural-language task intent plus optional changed file paths.

Simulation reports include:

- Selected module or modules.
- Required OKF documents.
- Optional related documents.
- Estimated token cost and estimator type.
- Source and routing evidence.
- Warnings for ambiguous or broad retrieval.
- Errors for unrelated automatic loads.

Required scenarios cover API routes, schemas/models, business logic, UI behavior, architecture understanding, and dependencies/tooling. Validation treats unrelated automatic module loads as defects.
