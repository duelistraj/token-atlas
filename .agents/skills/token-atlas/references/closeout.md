# Adaptive PKF Closeout

## Purpose

Keep an initialized PKF synchronized automatically at the end of each user turn
without paying the cost of a full maintenance cycle when nothing relevant
changed.

## Gate

Run exactly once before the final response when `.ai/PKF.md` sets
`pkf.closeout: adaptive`.

1. Reuse the session's last acknowledged repository change set. Include staged,
   unstaged, and untracked paths plus enough diff identity to detect another edit
   to the same path. When Git is unavailable, use the files changed during the
   turn.
2. Compare the end-of-turn state with that acknowledgement.
3. Return `no-op` when no repository content changed, the change set is already
   acknowledged and synchronized, or only `.ai/` changed because of closeout.
4. Otherwise, route only the new or changed paths through the cached knowledge
   and module indexes. Do not reread cached startup documents unless they changed
   or contradict source truth.

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

Update the session acknowledgement only after the closeout result is known.
