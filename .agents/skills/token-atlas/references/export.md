# Retrieval Export Workflow

## Purpose

Generate optional backend-neutral RAG and GraphRAG exports from the canonical PKF Markdown knowledge base.

Exports are derived artifacts. They are never the source of truth and must never be loaded in the PKF startup path.

Run this workflow only when `retrieval_exports` is `rag`, `graph`, or `all`.

Do not generate exports when `retrieval_exports: off`.

---

## Inputs

- PKF runtime (`.ai/PKF.md`, `.ai/MEMORY.md`, `.ai/ARCHITECTURE.md`).
- OKF knowledge base (`.ai/knowledge/`).
- Selected `retrieval_exports` option.
- Current validation status.
- Maintenance impact report, when available.

---

## Outputs

Create or update `.ai/retrieval/` only when exports are enabled. Prefer regenerating only affected records from the maintenance impact report; fall back to full export regeneration when affected records cannot be isolated safely.

| Option | Generated files |
|--------|-----------------|
| `off` | None |
| `rag` | `documents.jsonl`, `claims.jsonl` |
| `graph` | `entities.jsonl`, `relationships.jsonl`, `claims.jsonl` |
| `all` | `documents.jsonl`, `entities.jsonl`, `relationships.jsonl`, `claims.jsonl` |

Generated files must be deterministic JSONL with one valid JSON object per line.

---

## Export Principles

- Markdown under `.ai/` is canonical.
- `.ai/retrieval/` is generated output and may be deleted and rebuilt.
- Exports must be backend-neutral and vendor-independent.
- Exports must include stable IDs, source paths, evidence labels, timestamps, and confidence status.
- Exports must not copy large source snippets.
- Exports must not introduce facts that are absent from canonical Markdown or source evidence.
- Exports must not affect default PKF token cost when `retrieval_exports: off`.

---

## Shared Fields

Every export object must include:

| Field | Meaning |
|-------|---------|
| `id` | Stable deterministic ID derived from type and canonical path or evidence key. |
| `type` | Object type, such as `document`, `entity`, `relationship`, or `claim`. |
| `source_path` | Canonical `.ai/` Markdown path or repository source path. |
| `evidence` | Compact source evidence label or `TODO` when unresolved. |
| `timestamp` | Timestamp from the source OKF document metadata when available. |
| `confidence` | `verified`, `todo`, or `derived`. |

Use repository-relative paths with forward slashes.

---

## Documents Export

Generate `.ai/retrieval/documents.jsonl` for `rag` and `all`.

Each record represents a retrieval chunk from canonical Markdown.

Required fields:

- `id`
- `type: "document"`
- `source_path`
- `title`
- `module`
- `knowledge_type`
- `text`
- `tags`
- `loads`
- `related`
- `evidence`
- `timestamp`
- `confidence`

Chunking rules:

- Prefer one chunk per OKF section when sections are small.
- Split oversized sections deterministically by heading or paragraph boundary.
- Preserve enough heading context for standalone retrieval.
- Do not include generated retrieval files as source documents.

---

## Entities Export

Generate `.ai/retrieval/entities.jsonl` for `graph` and `all`.

Entity kinds:

- `module`
- `file`
- `symbol`
- `route`
- `schema`
- `command`
- `doc`

Required fields:

- `id`
- `type: "entity"`
- `kind`
- `name`
- `source_path`
- `module`
- `evidence`
- `timestamp`
- `confidence`

Only emit entities that are named in canonical Markdown or directly supported by source evidence cited from canonical Markdown.

---

## Relationships Export

Generate `.ai/retrieval/relationships.jsonl` for `graph` and `all`.

Standard edge kinds:

- `module_owns_file`
- `doc_describes_module`
- `fact_supported_by_source`
- `doc_loads_doc`
- `doc_related_to_doc`
- `symbol_depends_on_symbol`
- `route_implemented_by_symbol`

Required fields:

- `id`
- `type: "relationship"`
- `kind`
- `from_id`
- `to_id`
- `source_path`
- `evidence`
- `timestamp`
- `confidence`

Every relationship endpoint must resolve to an exported entity, document, or claim.

---

## Claims Export

Generate `.ai/retrieval/claims.jsonl` for `rag`, `graph`, and `all`.

Each record represents one source-backed fact from canonical Markdown.

Required fields:

- `id`
- `type: "claim"`
- `claim`
- `source_path`
- `module`
- `knowledge_type`
- `supported_by`
- `evidence`
- `timestamp`
- `confidence`

Rules:

- Claims must be atomic and source-backed.
- Claims must point to source evidence or be marked `TODO`.
- Duplicate claims should reuse stable IDs or be reported as duplicate facts during validation.

---

## Execution

### 1. Check Export Mode

If `retrieval_exports: off`, do nothing and report that retrieval exports are disabled.

If exports are enabled, continue only after canonical Markdown validation has no blocking source-truth errors.

---

### 2. Collect Canonical Sources

Read only canonical PKF Markdown and its cited repository evidence:

- `.ai/PKF.md`
- `.ai/MEMORY.md`
- `.ai/ARCHITECTURE.md`
- `.ai/knowledge/**/*.md`

Exclude `.ai/retrieval/**` from source collection.

---

### 3. Determine Export Impact

When a maintenance impact report is available, map affected canonical Markdown docs to export records.

If impact is narrow and deterministic, regenerate only affected records.

If impact cannot be isolated safely, regenerate the selected export files fully.

---

### 4. Build Export Records

Generate records deterministically from OKF metadata, headings, routing fields, source maps, verified facts, and evidence labels.

Do not infer missing symbols, routes, schemas, or relationships.

---

### 5. Validate Export Records

Before writing or reporting success, verify:

- Every JSONL line is valid JSON.
- Required fields are present.
- IDs are stable and unique per file.
- Source paths resolve to canonical Markdown or cited repository evidence.
- Relationship endpoints resolve.
- Claims are supported by evidence.
- Export files match the selected `retrieval_exports` option.
- Removed source paths are absent from current export records unless marked `TODO`.

---

## Rules

- Do not modify application code.
- Do not use exports as source truth.
- Do not load exports in the PKF startup path.
- Do not require exports when `retrieval_exports: off`.
- Keep all exports backend-neutral.
- Preserve deterministic output ordering by `source_path`, `type`, and `id`.

---

## Completion Criteria

Export succeeds when:

- Only the files required by `retrieval_exports` are generated.
- Incremental export regeneration is used when maintenance impact is safely isolated.
- Every generated file is valid JSONL.
- Every record has required shared fields.
- Every graph relationship endpoint resolves.
- Every claim is source-backed or marked `TODO`.
- No generated export becomes canonical knowledge.