# Initialize PKF Runtime

## Purpose

Create a target repository's `.ai/` PKF runtime and OKF knowledge skeleton when `.ai/PKF.md` is missing or incomplete.

Do not extract implementation details during initialization.

## Inputs

- Target repository structure.
- Existing `.ai/` content, if any.
- Existing agent-instruction entry point, if any.
- Existing README, config, source roots, test roots, and docs.

## Outputs

Create or update:

```text
<repo root>
|-- AGENTS.md                 # neutral bootstrap: routes every task to .ai/PKF.md
|                             # (augment an existing agent-instruction entry
|                             #  point instead, if the repo already has one)
`-- .ai/
    |-- PKF.md                # embeds the Retrieval Protocol (mandatory routing)
    |-- MEMORY.md
    |-- ARCHITECTURE.md
    `-- knowledge/
        |-- INDEX.md
        |-- glossary.md
        |-- dependencies.md
        |-- decision_log.md
        `-- <module>/
            |-- INDEX.md
            |-- api.md
            |-- schema.md
            |-- business_rules.md
            `-- ui.md
```

Create module directories only for modules supported by repository structure.

## Module Boundary Contract

Module names and boundaries must be derived from the target repository. Keep
modules flat: each module is one directory directly under `.ai/knowledge/`.

Prefer an independently changeable functional capability over a technical or
deployment layer when the repository supports that distinction. Split a coarse
candidate only when it contains at least two independently routable
capabilities, and each resulting capability has either:

- A dedicated implementation subtree; or
- Evidence from at least two of these categories: interfaces, data structures,
  workflows, user-facing behavior, or tests.

When the repository exposes only one capability, or ownership is ambiguous,
retain the repository's existing structural boundary and report the ambiguity.
Do not create modules from placeholders, roadmap entries, empty scaffolding, or
names without implementation evidence. Use abstract placeholders such as
`<module>` and `<capability>` in reusable guidance; never prescribe target-repo
module names.

---

## Procedure

1. Discover project name, technologies, source roots, config roots, test roots, docs, and functional capabilities. Build a capability-to-source ownership map using the Module Boundary Contract before choosing module names.
2. Create or repair `PKF.md`, `MEMORY.md`, and `ARCHITECTURE.md`. Embed the Retrieval Protocol (template below) into `PKF.md` so routing enforcement travels with the repository.
3. Ensure a neutral bootstrap points every task at `.ai/PKF.md`: create a root `AGENTS.md` (template below), or, if the repository already has an agent-instruction entry point, augment it with the same bootstrap text. Keep this vendor, agent, and model agnostic — name no specific assistant, tool, or model.
4. Create root shared knowledge docs and one module skeleton per detected module.
5. Add OKF front matter to every generated Markdown file:

```yaml
---
type:
title:
description:
resource:
tags:
timestamp:

pkf:
  loads: []
  related: []
---
```

Add `source_symbols` to every module leaf (`api.md`, `schema.md`,
`business_rules.md`, and `ui.md`). Use a mapping from repository-relative paths
to exact symbol names:

```yaml
source_symbols:
  frontend/src/pages/NotesPage.tsx:
    - NoteSectionRows
    - SortableNoteRow
```

For a leaf with no source-backed facts, use `source_symbols: {}` and the exact
body marker `- TODO: No source-backed facts.`.

6. Populate only structure-backed facts, routing placeholders, and explicit TODOs.
7. Validate the initialized structure before extraction, including that `PKF.md` contains the Retrieval Protocol and that the bootstrap references `.ai/PKF.md`.

## Retrieval Protocol Template

Embed this section verbatim into the generated `.ai/PKF.md` (adjust only the doc names if the repository uses different leaf-doc filenames). It is the enforcement that makes knowledge-base-first retrieval reliable, and it is deliberately free of any vendor, agent, or model reference.

````markdown
## Retrieval Protocol (MANDATORY)

The `.ai/` knowledge base is the primary way to locate code. Each durable fact
has one authoritative leaf doc with machine-readable `source_symbols`, so routing
is cheaper and more reliable than scanning the codebase.

### Hard precondition

Before running any code search, or opening a source file for analysis or editing,
route through `.ai/`:

1. Read `.ai/PKF.md` once per session, then reuse that acknowledgement unless the
   file changes, contradicts source truth, or an uncached section is needed.
2. Route through the cached `.ai/knowledge/INDEX.md`, refreshing it only under
   the same conditions, and pick the owning module(s).
3. Read one module `INDEX.md` and one or two task-specific leaves for a normal
   task. Follow `pkf.related` only when the task expands.
4. Open only the paths and symbols in `source_symbols`; use the leaf Edit Map's
   targeted locator command before reading a large file.

Route to the **minimal set of leaf docs** for the fact kinds your change
touches — a cross-cutting change legitimately reads several leaves, one slice
each. **Negative constraint:** do not run codebase-wide search, or open source for
analysis, until you have followed the route and the leaf docs proved missing or
insufficient. Reading this file alone does not satisfy the protocol.

### Retrieval trace

When the route leads to a search or an edit, state it on one line, citing the full
minimal set of docs and the source symbols, e.g.:

```
Route: PKF -> INDEX -> <module>/{api.md, ui.md} -> <source-file-a>, <source-file-b>
Targets: <source-file-a>:<symbol-a>, <source-file-b>:<symbol-b>
Commands: <targeted sg or rg commands>
Fallback search: no
Budget: 1 module index, 2 leaves, <estimated tokens>
```

If fallback is required, set `Fallback search: yes` and add `Fallback reason:`.
Keep this trace in the session/task report; do not create a repository log.

### Fallback and verification

- Fall back to codebase-wide search only when the routed leaf docs are absent,
  incomplete, or contradict reality; say briefly why before doing so.
- Prefer an exact ast-grep command when the installed `sg` is verified to be
  ast-grep; otherwise use `rg -n -F -- '<symbol>' '<path>'`.
- Treat source code as the source of truth. Verify a leaf doc's claim against the
  cited file before editing, and report drift as a knowledge-base defect.

### One fact, one home (multi-doc edits are normal)

Each durable fact lives in exactly one authoritative leaf doc. A cross-cutting
change updates several leaves — one slice each — which is expected. The defect to
watch for is the same fact duplicated across leaves; report it for deduplication
rather than editing the copy.

### Keep the knowledge base in sync

After changing code, update each leaf doc that owns a fact you changed (add
`pkf.related` links instead of duplicating a fact). If you cannot update the
knowledge base in the same change, state exactly which leaf docs are now stale.

### Planning and discovery

Planning and discovery also start here: begin at `.ai/knowledge/INDEX.md`.
Codebase-wide search is a fallback, not the first move.

A normal route loads at most one module index and two leaves. A legitimate
cross-cutting task may exceed the document count only when the trace explains why
and each capability slice stays minimal.
````

## Bootstrap Template

Write this to a root `AGENTS.md`, or merge it into the repository's existing agent-instruction entry point. Keep it vendor, agent, and model agnostic.

````markdown
# AGENTS

This repository uses a Project Knowledge Framework (PKF) with a knowledge base
under `.ai/`.

Before running any code search, opening a source file for analysis, or making an
edit, follow the **Retrieval Protocol in `.ai/PKF.md`**: route
`PKF -> knowledge/INDEX -> module INDEX -> the minimal set of leaf docs -> source
symbols`, and do not run codebase-wide search until that route proves
insufficient. This applies to every task, not just the first.
````

## Rules

- Preserve existing `.ai/` content and any existing agent-instruction entry point when possible; augment rather than overwrite.
- Never inspect implementation internals for API, schema, business-rule, or UI facts in this phase.
- Keep indexes as routing surfaces, not knowledge dumps.
- Make startup route: `PKF.md -> MEMORY.md -> ARCHITECTURE.md -> knowledge/INDEX.md`.
- `PKF.md` must embed the Retrieval Protocol; a neutral bootstrap must point every task at `.ai/PKF.md`.
- Keep all generated guidance vendor, agent, and model agnostic. Reference no specific assistant, tool, or model.
- Leave unknown values empty or marked `TODO`.

## Success Criteria

- `.ai/PKF.md` exists, defines startup behavior, and embeds the Retrieval Protocol (hard precondition, negative constraint, fallback/verification, and knowledge-base sync).
- A neutral bootstrap (root `AGENTS.md` or an augmented existing entry point) references `.ai/PKF.md` and names no vendor, agent, or model.
- Required runtime and shared docs exist.
- Every detected module has the required OKF skeleton docs.
- Every module leaf has a valid `source_symbols` mapping or the standardized
  empty-leaf marker.
- Metadata is valid.
- The repository is ready for extraction.
