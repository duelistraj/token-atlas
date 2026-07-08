# exports

## Goal

Verify retrieval export behavior and JSONL integrity.

## Source Shape

- Valid canonical `.ai/` Markdown exists.
- Source evidence paths referenced by canonical Markdown exist or are marked `TODO`.

## Benchmark Flow

- Run `validation.md` with `retrieval_exports: off` and verify exports are skipped.
- Run `export.md` with `retrieval_exports: rag`.
- Run `export.md` with `retrieval_exports: graph`.
- Run `export.md` with `retrieval_exports: all`.
- Run `validation.md` after each enabled export mode.

## Expected Selected Modules

- Modules named in canonical `.ai/knowledge/INDEX.md`.

## Expected Required Docs

- Canonical `.ai/` Markdown only.
- Enabled export files by mode:
  - `rag`: `documents.jsonl`, `claims.jsonl`
  - `graph`: `entities.jsonl`, `relationships.jsonl`, `claims.jsonl`
  - `all`: all four JSONL files

## Forbidden Automatic Loads

- `.ai/retrieval/` in startup context.
- Export files as canonical source input.

## Expected Warnings

- Approximate token estimates if exact tokenization is unavailable.

## Expected Errors

- None for valid exports.
- Invalid JSONL, missing required fields, unresolved relationship endpoints, or unsupported claims fail the fixture.

## Token Thresholds

- Exports must not change default startup token cost when `retrieval_exports: off`.

## Exit Behavior

- `retrieval_exports: off` exits successfully without requiring `.ai/retrieval/`.
- Enabled export modes pass only with valid JSONL and resolved endpoints.
