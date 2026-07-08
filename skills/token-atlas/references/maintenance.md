# Incremental Maintenance

## Purpose

Detect repository changes and determine the smallest PKF/OKF knowledge set that must be updated.

Do not directly edit application code.

## Change Detection

Prefer this order:

1. `git diff --cached --name-status`
2. `git diff --name-status`
3. Full repository scan fallback when Git data is unavailable or inconclusive.

Report staged and unstaged changes separately when both exist. Prefer staged changes for CI-oriented maintenance.

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
Retrieval exports:
- <disabled, affected records, or regenerate required>
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
