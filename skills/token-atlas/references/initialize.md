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
|-- AGENTS.md                 # neutral bootstrap: routes tasks and mutation-gates closeout
|                             # (augment an existing agent-instruction entry
|                             #  point instead, if the repo already has one)
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
2. Create or repair `PKF.md`, `MEMORY.md`, and `ARCHITECTURE.md`. Embed the Retrieval Protocol and Closeout Protocol (templates below) into `PKF.md` so routing and synchronization enforcement travel with the repository. Set `pkf.runtime_version: 3`, `pkf.retrieval: adaptive`, and `pkf.closeout: adaptive` in the `PKF.md` front matter by default; accept `pkf.retrieval: mandatory` for compatibility and `pkf.closeout: "off"` as an explicit opt-out.
3. Ensure a neutral bootstrap can apply both gates without loading `.ai/PKF.md` first: create a root `AGENTS.md` (template below), or augment the existing agent-instruction entry point. Keep this vendor, agent, and model agnostic.
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

Preserve existing materialized leaves. Create new skeleton leaves with
`pkf.materialization: pending`, use
`source_symbols: {}`, and use the exact body marker
`- TODO: Pending source extraction.`. A pending leaf is intentionally incomplete,
not evidence that the capability has no implementation. The subsequent hybrid
extraction materializes public entry-point leaves. A completed leaf with no
source-backed facts uses `pkf.materialization: complete` and the exact marker
`- TODO: No source-backed facts.`.

For `.ai/PKF.md` only, add the closeout mode under the existing `pkf` mapping:

```yaml
pkf:
  runtime_version: 3
  retrieval: adaptive
  loads:
    - .ai/MEMORY.md
    - .ai/ARCHITECTURE.md
    - .ai/knowledge/INDEX.md
  related: []
  closeout: adaptive
```

6. Populate only structure-backed runtime facts, repository commands,
   architecture, dependencies, routing, and explicit pending markers. Leave
   implementation facts to the subsequent hybrid extraction.
7. Validate the initialized structure before extraction, including the closeout mode, both mandatory protocols, and both bootstrap references.

## Retrieval Protocol Template

Embed this section verbatim into the generated `.ai/PKF.md` (adjust only the doc names if the repository uses different leaf-doc filenames). It is the enforcement that makes knowledge-base-first retrieval reliable, and it is deliberately free of any vendor, agent, or model reference.

````markdown
## Retrieval Protocol (MANDATORY)

The `.ai/` knowledge base is an adaptive accelerator for tasks where routing can
replace broad repository discovery. Source remains authoritative.

### Adaptive retrieval gate

Do not read PKF merely to decide whether PKF is useful.

- For a likely single-capability task, use a cheap local probe of at most two
  targeted `rg`/`sg` searches and three source files. If that resolves a known
  path or symbol without broad search, bypass PKF and continue locally.
- Activate PKF retrieval immediately for explicit cross-capability,
  architecture, ownership, or repository-wide tasks.
- Activate PKF retrieval when the cheap local probe reveals multiple
  capabilities, ambiguous ownership, or the need for codebase-wide search.
- When `pkf.retrieval` is `mandatory`, skip the local probe and activate PKF for
  every repository-analysis task.

### PKF activation

After activation:

1. Read `.ai/PKF.md`, `MEMORY.md`, `ARCHITECTURE.md`, and
   `.ai/knowledge/INDEX.md` once, then cache them for the session.
2. Select the owning module and read one module `INDEX.md` plus one or two
   task-specific leaves. Follow `pkf.related` only when the task expands.
3. If a selected leaf has `pkf.materialization: pending`, materialize only that
   leaf from source before relying on it.
4. Open only the paths and symbols in `source_symbols`; use the Edit Map's
   targeted locator before reading a large file.

Do not run codebase-wide search after activation until this route proves absent,
incomplete, or inconsistent with source truth.

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
  repository file as task output, apply the knowledge-impact gate exactly once
  before the final response.

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

### Knowledge-impact gate

- If the mutation did not change durable facts, evidence, or routing, return
  `no-op` without loading Token Atlas, the PKF startup path, or validation.
- Durable impact includes externally relevant behavior, API/schema, dependency
  or architecture changes, ownership/routes, and the source symbols, tests,
  styles, tokens, or locators that support an existing fact.
- When impact exists, reuse the implementation context and turn-owned changed
  paths. Do not rediscover the repository or replay the startup path.
- If impact is uncertain or a changed path is unmapped, report the affected
  knowledge as `stale` or escalate to the full maintenance workflow; never guess.

### Incremental synchronization

- Keep changed durable facts, `source_symbols`, Edit Maps, tests, styles/tokens,
  and locator commands synchronized with source truth.
- Route changed paths directly to their existing leaves. Read a module or root
  index only for a new or unmapped path. Materialize an affected pending leaf.
- Repair deletes and renames, and update indexes only when ownership or routing
  changed.
- Optimize only affected routes that exceed a token budget, duplicate facts,
  load unrelated context, or required fallback search.
- Run affected-slice advisory validation with summary output after changing
  `.ai/` knowledge. Do not emit successful-check inventories during closeout.
- Use full maintenance, extraction, optimization, or validation only for module
  boundary changes, legacy migrations, unresolved drift, broad-load repair, or
  CI execution.

### Safety and recursion

- Never modify application code during closeout.
- Preserve pre-existing user changes.
- Never invoke closeout again because closeout changed `.ai/`.
- If synchronization cannot finish, name the stale leaves instead of guessing.

When the mutation gate runs, report one compact line. Emit nothing for a
read-only bypass. A knowledge-neutral mutation may report `no-op` directly from
this embedded gate without loading Token Atlas:

```
PKF closeout: <no-op|updated|stale|disabled|blocked> — <affected docs or reason>
```

Update the session acknowledgement only after synchronization and affected-slice
validation finish successfully. Never acknowledge an ambiguous or failed
snapshot as synchronized.
````

## Bootstrap Template

Write this to a root `AGENTS.md`, or merge it into the repository's existing agent-instruction entry point. Keep it vendor, agent, and model agnostic.

````markdown
# AGENTS

This repository uses a Project Knowledge Framework (PKF) with a knowledge base
under `.ai/`.

Use a cheap local probe of at most two targeted searches and three source files
for a likely single-capability task. If it resolves the target, inspect source
directly without reading PKF. Activate PKF retrieval and follow the **Retrieval
Protocol in `.ai/PKF.md`** for cross-capability, architecture, ownership, or
repository-wide tasks, or before the probe expands into broad search.

After an intentional repository mutation, first apply the knowledge-impact gate
without loading PKF. Read-only turns bypass closeout silently. If no durable
facts, evidence, or routing changed, report a knowledge-neutral `no-op` without
loading Token Atlas or PKF. Otherwise follow the **Closeout Protocol in
`.ai/PKF.md`** exactly once, update only affected leaves, and run affected-slice
summary validation. Do not rerun closeout because closeout changed `.ai/`.
````

## Rules

- Preserve existing `.ai/` content and any existing agent-instruction entry point when possible; augment rather than overwrite.
- Never inspect implementation internals for API, schema, business-rule, or UI facts in this phase.
- Keep indexes as routing surfaces, not knowledge dumps.
- Make startup route: `PKF.md -> MEMORY.md -> ARCHITECTURE.md -> knowledge/INDEX.md`.
- `PKF.md` must embed both mandatory protocols; a neutral bootstrap must apply the adaptive retrieval and knowledge-impact closeout gates without loading PKF first.
- Keep all generated guidance vendor, agent, and model agnostic. Reference no specific assistant, tool, or model.
- Leave unknown values empty or marked `TODO`.

## Success Criteria

- `.ai/PKF.md` exists, defines startup behavior, sets `pkf.runtime_version: 3`, `pkf.retrieval: adaptive`, a valid `pkf.closeout` mode, and embeds both mandatory protocols.
- A neutral bootstrap (root `AGENTS.md` or an augmented existing entry point) references retrieval and closeout in `.ai/PKF.md` and names no vendor, agent, or model.
- Required runtime and shared docs exist.
- Every detected module has the required OKF skeleton docs.
- Every module leaf is explicitly materialized or pending; complete leaves have
  valid `source_symbols` and pending leaves use the standardized pending marker.
- Metadata is valid.
- The repository is ready for extraction.
