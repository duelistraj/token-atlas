# zephyr-pkf
Zephyr PKF is an AI context optimization framework that continuously extracts verified repository knowledge and generates an OKF-compatible knowledge base optimized for minimal-context retrieval by AI coding agents.

## PKF Lifecycle

Zephyr PKF treats `.ai/` Markdown as the canonical source of repository knowledge. Generated indexes and retrieval exports are derived artifacts, not the source of truth.

1. Initialize: create `.ai/PKF.md`, runtime docs, the root knowledge index, shared docs, and module skeletons.
2. Extract: populate only source-backed facts from the repository into the narrowest authoritative OKF documents.
3. Optimize: reduce duplicate knowledge, tighten routing, and keep `pkf.loads` minimal.
4. Simulate retrieval when enabled: predict selected modules, required docs, optional related docs, token cost, and routing evidence.
5. Validate: check structure, metadata, stale evidence, broken references, duplicate facts, routing integrity, enabled simulations, and token impact.
6. Generate retrieval exports only when requested; derived JSONL and graph artifacts are never the source of truth.

## Execution Profiles

Default profile is `core`: initialize, extract, optimize, and run lightweight validation.

Options:

| Option | Values | Default |
|--------|--------|---------|
| `retrieval_exports` | `off`, `rag`, `graph`, `all` | `off` |
| `simulation` | `off`, `changed`, `required`, `all` | `changed` |
| `token_budget` | `summary`, `full` | `summary` |
| `validation_strictness` | `advisory`, `ci` | `advisory` |

Use `ci` or `full` for required simulator scenarios and full token budget gates. Use `retrieval` or explicit retrieval export options for RAG/GraphRAG artifacts. Repos that do not use RAG should keep `retrieval_exports: off`.

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

Optimization and validation generate token budget output according to `token_budget`. Default `summary` mode covers the startup path, changed module paths, and threshold status. `full` mode adds every module index load, representative task loads, and broad `pkf.loads` chains.

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

Default simulation mode is `changed`, which only simulates the current task intent or changed paths. Required scenarios cover API routes, schemas/models, business logic, UI behavior, architecture understanding, and dependencies/tooling in `ci`, `full`, `required`, or `all` mode. Validation treats unrelated automatic module loads as defects.

## Optional Retrieval Exports

`export.md` defines optional backend-neutral retrieval exports under `.ai/retrieval/`.

| `retrieval_exports` | Generated files |
|---------------------|-----------------|
| `off` | none |
| `rag` | `documents.jsonl`, `claims.jsonl` |
| `graph` | `entities.jsonl`, `relationships.jsonl`, `claims.jsonl` |
| `all` | all export files |

Exports are generated from canonical `.ai/` Markdown and cited source evidence. They can feed vector RAG, GraphRAG, or custom retrieval tooling, but they are never loaded in the PKF startup path and never become source truth.
