# Adaptive PKF Closeout

## Purpose

Keep an initialized PKF synchronized automatically at the end of each user turn
without paying the cost of a full maintenance cycle when nothing relevant
changed.

## Gate

Run exactly once before the final response when `.ai/PKF.md` sets
`pkf.closeout: adaptive`.

1. Before the first task mutation in a session, capture a baseline snapshot. Use
   normalized repository-relative paths, staged and unstaged diff identity,
   both endpoints of renames, and content identity for untracked files. The
   identity must change when the same path is edited again. Keep this snapshot
   only in session context.
2. Reuse the last successfully acknowledged snapshot, or the baseline when no
   closeout has completed, and compare it with the end-of-turn state. When Git
   is unavailable, use the files changed during the turn with equivalent content
   identity.
3. Return `no-op` when no repository content changed, the change set is already
   acknowledged and synchronized, or only `.ai/` changed because of closeout.
4. Otherwise, route only the new or changed paths through the cached knowledge
   and module indexes. Do not reread cached startup documents unless they changed
   or contradict source truth.

If no baseline was captured, synchronize only paths known to have changed during
the current turn. Do not claim ambiguous pre-existing dirty paths; report the
affected knowledge as `stale` when their synchronization cannot be established.

Do not persist a change-set ledger in the repository. Keep the acknowledgement
in session context.

## Incremental Sync

- Update only leaves whose durable facts changed. Keep `source_symbols`, Edit
  Maps, tests, styles/tokens, and locator commands exact.
- Remove or repair evidence made stale by deletes and renames.
- Update an index only when ownership or routing changed.
- Optimize only an affected route that exceeds a token budget, duplicates a
  fact, loads unrelated context, or required fallback search.
- Run affected-slice advisory validation after changing PKF knowledge.
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

Emit one compact line before the final response summary:

```text
PKF closeout: <no-op|updated|stale|disabled|blocked> — <affected docs or reason>
```

Update the session acknowledgement only after synchronization and affected-slice
validation finish and the closeout result is known. Never acknowledge a failed or
ambiguous snapshot as synchronized.
