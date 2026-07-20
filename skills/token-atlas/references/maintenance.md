# Incremental Maintenance

## Purpose

Detect repository changes and determine the smallest PKF/OKF knowledge set that must be updated.

Do not directly edit application code.

For routine mutation-triggered closeout, use `closeout.md` first. Continue
with this full workflow only when that gate identifies an exceptional
maintenance case.

## Change Detection

Prefer this order:

1. `git diff --cached --name-status`
2. `git diff --name-status`
3. Full repository scan fallback when Git data is unavailable or inconclusive.

Report staged and unstaged changes separately when both exist. Prefer staged changes for CI-oriented maintenance.

During adaptive closeout, compare against the session's last acknowledged
change set and inspect only new changes. Do not persist that acknowledgement in
the repository.

## Runtime Migration

The current runtime contract is `pkf.runtime_version: 4`. When an existing
`.ai/PKF.md` has no runtime version or an older version, migrate it in the same
maintenance cycle. For version 3, install the dependency-free helpers under
`.ai/tools/`, add `pkf.ownership_roots` to module indexes, refresh only the
managed bootstrap and embedded protocol blocks, and reconcile focused test
evidence in materialized public-behavior leaves. For older versions, preserve
the mutation gate, replace mandatory every-task retrieval with the adaptive
local-probe gate, add `pkf.retrieval: adaptive`, and add the knowledge-impact closeout gate. Mark
unextracted skeleton leaves `pkf.materialization: pending`; treat existing
source-backed leaves as complete. Preserve an explicit closeout `off` value and
validate before acknowledgment. Never downgrade an unknown newer runtime.

## Impact Mapping

Map changed paths through `ARCHITECTURE.md`, `knowledge/INDEX.md`, and module `INDEX.md` files.

| Change | Affected docs |
|--------|---------------|
| API route | module `api.md`, module `INDEX.md` |
| Schema/model | module `schema.md`, module `INDEX.md` |
| Business logic | module `business_rules.md`, module `INDEX.md` |
| UI behavior | module `ui.md`, module `INDEX.md` |
| Config/tooling | `dependencies.md`, `ARCHITECTURE.md`, affected module index |
| New source root or module | `ARCHITECTURE.md`, `knowledge/INDEX.md`, new module skeleton |
| Deleted or renamed file | every canonical doc citing the old path |
| Tests | relevant module doc and validation notes |

## Module Boundary Audit

Audit the current module map against the Module Boundary Contract in
`initialize.md`. When a module contains at least two independently routable,
source-backed capabilities and ownership is unambiguous, include an automatic
repartition in the maintenance impact:

1. Inventory every durable fact, manual note, evidence path, and routing edge in
   the coarse module.
2. Map each item to a capability and knowledge type.
3. List the new flat module skeletons, rewritten routes, and superseded module
   directories.
4. Defer deletion until extraction has moved every item and validation proves
   all references resolve.

If any fact has ambiguous ownership, retain the current module boundary and
report the ambiguity. Do not infer modules from placeholders or names alone.

## Leaf Contract Migration

During routine semantic closeout, migrate only an affected legacy leaf that
lacks `source_symbols` or a valid Edit Map. A repository-wide leaf-contract
migration requires an explicit migration request or CI profile; the existence
of one legacy leaf must not expand an ordinary task into a whole-knowledge scan.
Verify every migrated symbol from source and validate the affected slice before
returning to incremental updates.

## Stale References

For deleted or renamed evidence:

- Search canonical `.ai/**/*.md` for removed paths, old paths, symbols, routes, schemas, commands, config keys, and tests.
- Replace evidence only when the new path or symbol is certain.
- Remove current facts when implementation no longer exists.
- Mark facts `TODO` only when source may still exist but cannot be verified.

Stale references to removed files or symbols are validation defects.

## Report Format

```text
Maintenance Impact
Change source: <git diff --cached, git diff, or full scan>
Changed paths:
- <status> <path>
Affected modules:
- <module or unknown>
Affected docs:
- <canonical .ai path>
Invalidated facts:
- <fact or none>
Stale references:
- <reference or none>
Duplicate facts:
- <fact or none>
Module boundary changes:
- <automatic repartition, retained boundary, or none>
Retrieval exports:
- <disabled, affected records, or regenerate required>
Leaf contract migration:
- <complete, required, or not needed>
Closeout migration:
- <complete, required, disabled, or not needed>
Recommended workflows:
- <extract, optimize, validate, export when enabled>
Warnings:
- <warning or none>
Errors:
- <error or none>
```

## Rules

- Prefer incremental maintenance over full scans.
- Treat retrieval exports as generated artifacts, never source truth.
- Do not inspect or regenerate `.ai/retrieval/` when retrieval exports are off.
- Report ambiguous ownership instead of guessing.
- Automatically repartition a coarse module only when every moved fact has an unambiguous source-backed owner.
- Never recursively run adaptive closeout because maintenance changed `.ai/`.
