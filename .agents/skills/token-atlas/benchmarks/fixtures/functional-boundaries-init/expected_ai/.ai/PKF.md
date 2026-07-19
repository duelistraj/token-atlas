---
type: runtime
title: Synthetic PKF
description: Runtime entry point.
resource: .
tags: [pkf]
timestamp: 2026-07-12
pkf:
  runtime_version: 3
  retrieval: adaptive
  loads: [.ai/MEMORY.md, .ai/ARCHITECTURE.md, .ai/knowledge/INDEX.md]
  related: []
  closeout: adaptive
---

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
