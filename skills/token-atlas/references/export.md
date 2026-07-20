# Retrieval Exports

## Purpose

Generate optional backend-neutral RAG and GraphRAG JSONL artifacts from canonical PKF Markdown.

Exports are derived artifacts. They are never source truth and must not be loaded in the PKF startup path.

## Modes

| `retrieval_exports` | Generated files |
|---------------------|-----------------|
| `off` | none |
| `rag` | `documents.jsonl`, `claims.jsonl` |
| `graph` | `entities.jsonl`, `relationships.jsonl`, `claims.jsonl` |
| `all` | `documents.jsonl`, `entities.jsonl`, `relationships.jsonl`, `claims.jsonl` |

If `retrieval_exports: off`, do nothing and report that exports are disabled.

## Source Inputs

Read canonical Markdown and cited evidence only:

- `.ai/PKF.md`
- `.ai/MEMORY.md`
- `.ai/ARCHITECTURE.md`
- `.ai/knowledge/**/*.md`

Exclude `.ai/retrieval/**` from source collection.

## Shared Fields

Every record must include:

- `id`
- `type`
- `source_path`
- `evidence`
- `timestamp`
- `confidence`

Use repository-relative paths with forward slashes.

## Record Types

- `documents.jsonl`: section chunks from canonical Markdown.
- `entities.jsonl`: modules, files, symbols, routes, schemas, commands, and docs named in canonical knowledge.
- `relationships.jsonl`: edges such as doc loads, doc related, module owns file, and fact supported by source.
- `claims.jsonl`: atomic source-backed facts.

## Validation

Before success, verify:

- Every line is valid JSON.
- Required fields are present.
- IDs are stable and unique per file.
- Source paths resolve to canonical Markdown or cited repository evidence.
- Relationship endpoints resolve.
- Claims are source-backed; omit unresolved claims.
- Export files match the selected mode.

## Rules

- Do not generate exports when disabled.
- Do not use exports as source truth.
- Do not copy large source snippets.
- Preserve deterministic ordering by source path, type, and id.
