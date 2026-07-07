# token-atlas
Token Atlas is an AI context optimization framework that continuously extracts verified repository knowledge and generates an OKF-compatible knowledge base optimized for minimal-context retrieval by AI coding agents.

## PKF Lifecycle

Token Atlas treats `.ai/` Markdown as the canonical source of repository knowledge. Generated indexes and retrieval exports are derived artifacts, not the source of truth.

1. Initialize: create `.ai/PKF.md`, runtime docs, the root knowledge index, shared docs, and module skeletons.
2. Maintain incrementally: detect changed, renamed, and deleted files and map them to affected knowledge.
3. Extract: populate only source-backed facts into the narrowest authoritative OKF documents.
4. Optimize: reduce duplicate knowledge, tighten routing, and keep `pkf.loads` minimal.
5. Simulate retrieval when enabled: predict selected modules, required docs, optional related docs, token cost, and routing evidence.
6. Validate: check structure, metadata, stale evidence, broken references, duplicate facts, routing integrity, enabled simulations, and token impact.
7. Generate retrieval exports only when requested; derived JSONL and graph artifacts are never the source of truth.

## Execution Profiles

Default profile is `core`: initialize, maintain incrementally, extract, optimize, and run lightweight validation.

Options:

| Option | Values | Default |
|--------|--------|---------|
| `retrieval_exports` | `off`, `rag`, `graph`, `all` | `off` |
| `simulation` | `off`, `changed`, `required`, `all` | `changed` |
| `token_budget` | `summary`, `full` | `summary` |
| `validation_strictness` | `advisory`, `ci` | `advisory` |

Use `ci` or `full` for required simulator scenarios and full token budget gates. Use `retrieval` or explicit retrieval export options for RAG/GraphRAG artifacts. Repos that do not use RAG should keep `retrieval_exports: off`.

## Incremental Maintenance

`maintenance.md` defines the default core workflow for keeping PKF synchronized after repository changes.

Maintenance uses:

1. `git diff --cached --name-status`
2. `git diff --name-status`
3. Full scan fallback

It maps changed paths to affected modules and canonical docs, invalidates facts that cite deleted or renamed evidence, reports duplicate authoritative facts, and regenerates retrieval exports only when `retrieval_exports` is enabled.

Stale references to removed files or symbols are blocking in `ci` strictness. Duplicate facts warn by default and block in `ci` when they affect routing, source truth, `pkf.loads`, or module ownership.

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

## Developer Tooling

`scripts/pkf.ps1` is a thin workflow wrapper. It selects documented PKF workflows and options; it does not implement extraction, optimization, validation, or export logic itself.

Start with help:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 --help
```

Codex skill usage and local wrapper usage are different surfaces. In Codex, ask for the `token-atlas` skill by name and state options in natural language, such as `profile=ci` or `retrieval_exports=off`. In the terminal, use `scripts\pkf.ps1` for repeatable workflow requests.

Common commands:

| Goal | Command |
|------|---------|
| Show help | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 --help` |
| Initialize PKF | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 init` |
| Maintain changed knowledge | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 maintain` |
| Validate advisory mode | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 validate` |
| Validate CI mode | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 validate -Ci` |
| Simulate retrieval | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 simulate -Intent "change an API route" -Paths src/routes.ts` |
| Export retrieval graph | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 export -RetrievalExports graph` |

The wrapper supports PowerShell parameters and common kebab-case aliases:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 export --retrieval-exports graph
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 validate --ci
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 validate --help
```

Default command options are `profile: core`, `retrieval_exports: off`, `simulation: changed`, `token_budget: summary`, and `validation_strictness: advisory`.

CI mode maps to `validation_strictness: ci`, `simulation: required`, and `token_budget: full`. Missing `.ai/PKF.md` exits nonzero in CI validation.

