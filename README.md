# zephyr-pkf
Zephyr PKF is an AI context optimization framework that continuously extracts verified repository knowledge and generates an OKF-compatible knowledge base optimized for minimal-context retrieval by AI coding agents.

## PKF Lifecycle

Zephyr PKF treats `.ai/` Markdown as the canonical source of repository knowledge. Generated indexes and retrieval exports are derived artifacts, not the source of truth.

1. Initialize: create `.ai/PKF.md`, runtime docs, the root knowledge index, shared docs, and module skeletons.
2. Extract: populate only source-backed facts from the repository into the narrowest authoritative OKF documents.
3. Optimize: reduce duplicate knowledge, tighten routing, and keep `pkf.loads` minimal.
4. Validate: check structure, metadata, stale evidence, broken references, duplicate facts, routing integrity, and token impact.
5. Generate retrieval exports: build backend-neutral JSONL or graph artifacts from the canonical Markdown knowledge base.

## Startup Recovery

At the beginning of a PKF session, read `.ai/PKF.md`. If it is missing, run initialization before repository analysis. This creates the runtime contract that tells agents how to load `MEMORY.md`, `ARCHITECTURE.md`, and `knowledge/INDEX.md`.

## Validation Report

Validation reports use four sections:

- Passed: checks that succeeded.
- Warnings: non-blocking issues with recommendations and retrieval impact.
- Errors: blocking issues with evidence and recommended fixes.
- Token Impact: estimated startup and task retrieval costs, including broad `pkf.loads` chains.

Token counts should use an exact tokenizer when available. Otherwise, reports must label estimates as approximate.
