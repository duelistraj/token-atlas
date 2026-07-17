# Phase 1 - Initialize OKF Knowledge Base

## Purpose

Initialize the Project Knowledge Framework (PKF) by creating a repository-specific, Open Knowledge Format (OKF) compatible knowledge base.

This phase creates the knowledge structure and retrieval contract only. Do **not** extract implementation details.

Run this workflow before repository analysis when `.ai/PKF.md` is missing. A missing `PKF.md` means the PKF startup contract is unavailable, even if other `.ai/` files exist.

---

## Inputs

- Current repository
- PKF templates
- Existing agent-instruction entry point, if any

---

## Outputs

Create or update:

```text
<repo root>
|-- AGENTS.md                 # neutral bootstrap: routes tasks and mutation-gates closeout
|                             # (or augment an existing instruction entry point)
`-- .ai/
    |-- PKF.md                # embeds mandatory retrieval and closeout protocols
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

All documents under `.ai/` must follow the Open Knowledge Format (OKF).

---

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

## Execution

### 1. Discover Repository

Detect:

- Project name
- Technologies
- Repository structure
- Functional modules
- Source roots, config roots, test roots, and documentation roots

Create knowledge only for modules that exist.

Before selecting module names, build a capability-to-source ownership map using
the Module Boundary Contract. Record the evidence categories that qualify each
module and any ambiguous candidates retained at their existing structural
boundary.

---

### 2. Initialize PKF Runtime

Create or update:

- `PKF.md`
- `MEMORY.md`
- `ARCHITECTURE.md`

These documents define the repository-specific PKF runtime and may evolve as the project evolves.

If `.ai/` already exists but `PKF.md` is absent, preserve existing `.ai/` content and create the missing runtime document before any extraction or optimization.

`PKF.md` must define:

- Runtime contract version `pkf.runtime_version: 2`.
- Startup sequence.
- Startup recovery when `.ai/PKF.md` is missing.
- Source-of-truth rules.
- Extraction, optimization, and validation gates.
- The difference between `pkf.loads` and `pkf.related`.
- Mutation-gated adaptive closeout with `pkf.closeout: adaptive` by default and
  `pkf.closeout: "off"` as an explicit opt-out. Quote `off` so YAML parsers do
  not treat it as boolean false.
- Execution profiles and defaults: `core`, `ci`, `retrieval`, `full`.
- Profile options: `retrieval_exports`, `simulation`, `token_budget`, and `validation_strictness`.

`MEMORY.md` must start with only stable repository-wide facts.

`ARCHITECTURE.md` must map repository paths to modules without describing implementation internals.

---

### 3. Create OKF Knowledge Base

Create:

- `knowledge/INDEX.md`
- `glossary.md`
- `dependencies.md`
- `decision_log.md`

Create one directory for every detected module.

---

### 4. Generate Module Skeletons

For every detected module create:

- `INDEX.md`
- `api.md`
- `schema.md`
- `business_rules.md`
- `ui.md`

Populate only:

- OKF metadata
- Document purpose
- Placeholders
- Routing slots for future tasks

Do **not** analyze implementation.

---

### 5. Initialize OKF Metadata

Every generated document must contain valid OKF front matter.

Required fields:

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

For `.ai/PKF.md` only, add the closeout mode under the existing `pkf` mapping:

```yaml
pkf:
  runtime_version: 2
  loads:
    - .ai/MEMORY.md
    - .ai/ARCHITECTURE.md
    - .ai/knowledge/INDEX.md
  related: []
  closeout: adaptive
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

Populate only values verifiable from the repository structure.

Leave unknown values empty or marked as `TODO`.

Use consistent tags:

- Project tag, such as `token-atlas`.
- Module tag.
- Knowledge type tag, such as `api`, `schema`, `rules`, `ui`, `routing`, or `architecture`.

---

### 6. Build Root Knowledge Index

Generate `knowledge/INDEX.md`.

It must contain:

- Project overview
- Technologies
- Available modules
- Module summaries
- Routing keywords
- Module entry points
- Path-to-module ownership map
- Common task routing table

This is the root entry point into the OKF knowledge base.

---

### 7. Configure PKF Runtime

Update `PKF.md` so every AI session follows this startup sequence:

```text
PKF.md
    ->
MEMORY.md
    ->
ARCHITECTURE.md
    ->
knowledge/INDEX.md
```

Also document this recovery rule:

```text
If .ai/PKF.md is missing, run initialization before repository analysis.
```

Also document default profile options:

```yaml
profile: core
retrieval_exports: off
simulation: changed
token_budget: summary
validation_strictness: advisory
```

Embed the Retrieval Protocol and Closeout Protocol templates below in `PKF.md`. Create a root
`AGENTS.md`, or augment the existing agent-instruction entry point, with the
neutral bootstrap template below. Preserve existing instruction content and
avoid naming any specific vendor, agent, or model.

## Retrieval Protocol Template

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

## Closeout Protocol Template

Embed this section verbatim after the Retrieval Protocol. It provides portable
end-of-turn enforcement even when a host cannot implicitly load Token Atlas.

````markdown
## Closeout Protocol (MANDATORY)

Apply this gate before loading Token Atlas or executing the rest of this
protocol:

- If the current turn made no intentional repository content mutation, stop
  silently. Do not capture a baseline, inspect Git, validate, or emit a closeout
  status.
- If the turn intentionally changed a tracked file or created a non-ignored
  repository file as task output, run PKF closeout exactly once before the
  final response. Use Token Atlas when available; otherwise execute this
  embedded protocol directly.

Ignored caches, build outputs, and temporary files do not trigger closeout.
Explicit Token Atlas workflows own their validation and do not recursively
invoke closeout. When `pkf.closeout` is `off` and the mutation gate applies,
report `disabled` and stop.

### Adaptive gate

1. Before the first task mutation in a session, capture a baseline snapshot with
   normalized repository-relative paths, staged and unstaged diff identity,
   both endpoints of renames, and content identity for untracked files. The
   identity must change when the same path is edited again.
2. Reuse the last successfully acknowledged snapshot, or the baseline when no
   closeout has completed, and compare it with the end-of-turn state. When Git
   is unavailable, use files changed during the turn with equivalent identity.
3. Return `no-op` when the applicable mutation was reverted, the current
   change set was already acknowledged and synchronized, or only `.ai/`
   changed during the closeout itself.
4. Otherwise route only new or changed paths through cached indexes and update
   the smallest affected PKF leaves.

Keep the acknowledgement in session context; do not create a repository log.
If no baseline exists, synchronize only paths known to have changed during the
turn and report ambiguous pre-existing dirty paths as `stale` rather than
claiming them as synchronized.

### Incremental synchronization

- Keep changed durable facts, `source_symbols`, Edit Maps, tests, styles/tokens,
  and locator commands synchronized with source truth.
- Repair deletes and renames, and update indexes only when ownership or routing
  changed.
- Optimize only affected routes that exceed a token budget, duplicate facts,
  load unrelated context, or required fallback search.
- Run affected-slice advisory validation after changing `.ai/` knowledge.
- Use full maintenance, extraction, optimization, or validation only for module
  boundary changes, legacy migrations, unresolved drift, broad-load repair, or
  CI execution.

### Safety and recursion

- Never modify application code during closeout.
- Preserve pre-existing user changes.
- Never invoke closeout again because closeout changed `.ai/`.
- If synchronization cannot finish, name the stale leaves instead of guessing.

When the mutation gate runs, report one compact line. Emit nothing for a
read-only bypass:

```
PKF closeout: <no-op|updated|stale|disabled|blocked> — <affected docs or reason>
```

Update the session acknowledgement only after synchronization and affected-slice
validation finish successfully. Never acknowledge an ambiguous or failed
snapshot as synchronized.
````

## Bootstrap Template

````markdown
# AGENTS

This repository uses a Project Knowledge Framework (PKF) with a knowledge base
under `.ai/`.

Before running any code search, opening a source file for analysis, or making an
edit, follow the **Retrieval Protocol in `.ai/PKF.md`**: route
`PKF -> knowledge/INDEX -> module INDEX -> the minimal set of leaf docs -> source
symbols`, and do not run codebase-wide search until that route proves
insufficient. This applies to every task, not just the first.

After an intentional repository mutation, follow the **Closeout Protocol in
`.ai/PKF.md`** exactly once before the final response. Read-only turns bypass
closeout silently. Use Token Atlas when available; otherwise execute the
embedded protocol directly. Do not rerun closeout because closeout changed
`.ai/`.
````

---

## Rules

- Source code is the single source of truth.
- Generate an OKF-compatible knowledge base.
- PKF runtime documents are repository-specific and may evolve.
- Never invent implementation details.
- Never inspect APIs, schemas, or business logic.
- Preserve existing documentation whenever possible.
- Preserve existing agent-instruction entry points; augment rather than overwrite them.
- Update existing files instead of recreating them.
- Keep the process idempotent.
- Keep indexes as routers, not long-form documentation.
- Keep placeholders explicit and easy to remove during extraction.
- `PKF.md` must embed both mandatory protocols; a neutral bootstrap must point every task at retrieval and closeout in `.ai/PKF.md`.

---

## Completion Criteria

Phase 1 succeeds when:

- The PKF runtime has been initialized.
- The OKF knowledge base exists.
- Every detected module has an OKF skeleton.
- Every document contains valid OKF metadata.
- `knowledge/INDEX.md` routes to every module.
- `PKF.md` routes to the knowledge base.
- `PKF.md` sets a valid closeout mode, embeds both mandatory protocols, and a neutral bootstrap references retrieval and closeout in `.ai/PKF.md`.
- No implementation knowledge has been extracted.
- The repository is ready for Phase 2.
