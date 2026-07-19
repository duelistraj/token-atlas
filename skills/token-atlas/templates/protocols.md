## Retrieval Protocol (MANDATORY)

The `.ai/` knowledge base is an adaptive accelerator for tasks where routing can
replace broad repository discovery. Source remains authoritative.

### Adaptive retrieval gate

Do not read PKF merely to decide whether PKF is useful.

- For a likely single-capability task, use a cheap local probe of at most two
  targeted `rg`/`sg` searches and three source files. If it resolves a known
  path or symbol without broad search, bypass PKF.
- Activate PKF retrieval immediately for explicit cross-capability,
  architecture, ownership, or repository-wide tasks.
- Activate PKF retrieval when the probe reveals multiple capabilities,
  ambiguous ownership, or the need for codebase-wide search.
- With `pkf.retrieval: mandatory`, activate PKF for every analysis task.

### PKF activation

After activation:

1. Read `.ai/PKF.md`, `MEMORY.md`, `ARCHITECTURE.md`, and
   `.ai/knowledge/INDEX.md` once and cache them for the session.
2. Select the owning module and read one module `INDEX.md` plus one or two
   task-specific leaves. Follow `pkf.related` only when the task expands.
3. Materialize a selected pending leaf from source before relying on it.
4. Open only the paths and symbols in `source_symbols` and use targeted
   locators before reading a large file.

Do not run broad search after activation until the route proves absent,
incomplete, or inconsistent with source truth. Record the route, targets,
commands, fallback status and reason, and context budget in the task report.

### Fallback and verification

- Fall back to codebase-wide search only when routed knowledge is absent,
  incomplete, or contradicted by source; state why first.
- Prefer verified ast-grep, otherwise use `rg -n -F -- '<symbol>' '<path>'`.
- Verify knowledge against cited source before editing and report drift.
- Keep each durable fact in one authoritative leaf. Cross-cutting work may load
  several leaves, one narrow slice each.

### Keep the knowledge base in sync

After changing code, update each leaf that owns a changed fact. Add
`pkf.related` links instead of duplicating facts. If synchronization cannot
finish, name the stale leaves. A normal route uses one module index and one or
two leaves; explain legitimate cross-capability exceptions.

## Closeout Protocol (MANDATORY)

Apply this gate before loading Token Atlas or PKF:

- If the current turn made no intentional repository content mutation, stop
  silently without Git inspection, validation, or status output.
- After an intentional mutation, apply the knowledge-impact gate exactly once.

Ignored caches and temporary outputs do not trigger closeout. Explicit Token
Atlas workflows own their validation and do not recursively invoke closeout.

### Adaptive gate

1. Before the first task mutation, capture a session-only baseline with paths,
   rename endpoints, staged/unstaged identity, and untracked content identity.
2. Compare the end state with the last successfully acknowledged snapshot.
3. Return `no-op` for reverted or already synchronized changes and closeout-only
   `.ai/` changes. Keep the acknowledgement in session context.
4. Route only turn-owned changed paths; do not replay the startup chain.

When no baseline exists, synchronize only paths known to have changed during
the turn and report ambiguous pre-existing changes as `stale`.

### Knowledge-impact gate

- Return `no-op` without loading PKF, Token Atlas, Git, or validation when no
  durable facts, evidence, or routing changed.
- Durable impact includes behavior, API/schema, dependencies, architecture,
  ownership/routes, and supporting symbols, tests, styles, tokens, or locators.
- Reuse implementation context and turn-owned changed paths.
- Report `stale` for uncertain impact or ownership rather than guessing.

### Incremental synchronization

- Route mapped paths with the bundled `pkf_route.py` helper and read only
  returned complete leaves. Do not load Token Atlas, startup documents, or an
  index for this routine mapped path. Preserve the compact route result.
- Treat pending, partial, and unmapped results as exceptional maintenance;
  materialize affected pending leaves and repair deletes or renames there.
- Update indexes only when ownership or routing changed.
- Optimize only defective affected routes.
- Run exactly one affected-slice advisory validation with summary detail after
  changing knowledge. Use full maintenance only for boundary changes, migrations,
  unresolved drift, broad-load repair, or CI.

### Safety and recursion

- Never modify application code during closeout or overwrite unrelated changes.
- Never invoke closeout again because closeout changed `.ai/`.
- Name stale leaves when synchronization cannot finish.

Emit nothing for a read-only bypass. Otherwise report one compact line:

`PKF closeout: <no-op|updated|stale|disabled|blocked> — <docs or reason>`

Acknowledge the snapshot only after successful synchronization and validation.
