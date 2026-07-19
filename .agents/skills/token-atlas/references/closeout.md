# Adaptive PKF Closeout

## Purpose

Keep an initialized PKF synchronized after knowledge-impacting repository
mutations without loading PKF for read-only or knowledge-neutral turns.

## Gate

When `.ai/PKF.md` sets `pkf.closeout: adaptive`, first apply the mutation
gate:

- If the current turn made no intentional repository content mutation, stop
  silently. Do not load this reference, capture a baseline, inspect Git, run
  validation, or emit a closeout status.
- If the turn intentionally changed a tracked file or created a non-ignored
  repository file as task output, apply the knowledge-impact gate exactly once
  before the final response.

Ignored caches, build outputs, and temporary files do not trigger closeout.
Explicit Token Atlas workflows remain explicit invocations and own their
validation without recursively invoking closeout.

1. Before the first task mutation in a session, capture a baseline snapshot. Use
   normalized repository-relative paths, staged and unstaged diff identity,
   both endpoints of renames, and content identity for untracked files. The
   identity must change when the same path is edited again. Keep this snapshot
   only in session context.
2. Reuse the last successfully acknowledged snapshot, or the baseline when no
   closeout has completed, and compare it with the end-of-turn state. When Git
   is unavailable, use the files changed during the turn with equivalent content
   identity.
3. Return `no-op` when the applicable mutation was reverted, the change set is
   already acknowledged and synchronized, or only `.ai/` changed because of
   closeout.
4. Otherwise, route only the new or changed paths through the cached knowledge
   and module indexes. Do not reread cached startup documents unless they changed
   or contradict source truth.

If no baseline was captured, synchronize only paths known to have changed during
the current turn. Do not claim ambiguous pre-existing dirty paths; report the
affected knowledge as `stale` when their synchronization cannot be established.

Do not persist a change-set ledger in the repository. Keep the acknowledgement
in session context.

## Knowledge-Impact Gate

Use the implementation context and turn-owned changed paths to decide whether
the mutation changed durable facts, evidence, or routing.

- Return `no-op` without reading PKF, loading Token Atlas, inspecting Git, or
  validating when the change is knowledge-neutral. Examples include formatting,
  internal refactors with unchanged symbols and behavior, or generated output.
- Synchronize immediately when externally relevant behavior, API/schema,
  dependencies, architecture, ownership, or routes changed.
- Also synchronize when an existing fact's source symbols, tests, styles/tokens,
  or targeted locator changed, even if runtime behavior did not.
- Treat ambiguous impact or an unmapped new path as exceptional maintenance.
  Report `stale` when ownership cannot be proved.

## Incremental Sync

- Route turn-owned changed paths directly to existing leaves. Read a root or
  module index only for a new or unmapped path; never replay the startup chain.
- Update only leaves whose durable facts changed. Keep `source_symbols`, Edit
  Maps, tests, styles/tokens, and locator commands exact.
- Materialize an affected `pkf.materialization: pending` leaf and mark it
  `complete` after source-backed extraction succeeds.
- Remove or repair evidence made stale by deletes and renames.
- Update an index only when ownership or routing changed.
- Optimize only an affected route that exceeds a token budget, duplicates a
  fact, loads unrelated context, or required fallback search.
- Run affected-slice advisory validation with summary detail after changing PKF
  knowledge. The bundled validator invocation is:

  `python <token-atlas-skill>/scripts/pkf_validate.py --path . --strictness advisory --scope affected --detail summary --changed-path <path>`

  Repeat `--changed-path` for each turn-owned source or knowledge path. Do not
  emit inventories of successful checks during routine closeout.
- Read the full maintenance, extraction, optimization, or validation reference
  only for an exceptional case: a module-boundary change, legacy leaf migration,
  unresolved drift, broad-load repair, or CI execution.

## Safety

- Never modify application code during closeout.
- Preserve pre-existing user changes and do not claim unrelated dirty paths as
  work performed in the current turn.
- Do not inspect or generate retrieval exports unless they are enabled.
- Do not invoke closeout again because closeout changed `.ai/`.
- If synchronization cannot finish, name the stale leaves instead of guessing.

## Report

When the mutation gate runs, emit one compact line before the final response
summary. Emit nothing for a read-only bypass. Emit the `no-op` line directly
from the knowledge-impact gate without loading other Token Atlas references.

```text
PKF closeout: <no-op|updated|stale|disabled|blocked> — <affected docs or reason>
```

Update the session acknowledgement only after synchronization and affected-slice
validation finish and the closeout result is known. Never acknowledge a failed or
ambiguous snapshot as synchronized.
