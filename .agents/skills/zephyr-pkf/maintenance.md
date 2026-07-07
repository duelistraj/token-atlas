# Incremental Maintenance Workflow

## Purpose

Maintain the PKF runtime and OKF knowledge base incrementally after repository changes.

Maintenance determines what changed, which canonical Markdown documents are affected, which facts must be invalidated, and whether optional retrieval exports need regeneration.

Markdown under `.ai/` remains canonical. Retrieval exports are regenerated only when `retrieval_exports` is enabled.

---

## Inputs

- Repository working tree.
- Existing PKF runtime and OKF knowledge base.
- Selected execution profile and options.
- Git change information, when available.

---

## Outputs

Produce a maintenance impact report.

Update only through the documented workflows:

- Use `extract.md` to update affected canonical Markdown docs.
- Use `optimize.md` to repair routing, duplication, and load paths.
- Use `export.md` to regenerate derived retrieval exports only when `retrieval_exports` is not `off`.

Do not directly edit application code.

---

## Change Detection

Use this priority order:

1. `git diff --cached --name-status`
2. `git diff --name-status`
3. Full repository scan fallback when Git data is unavailable or inconclusive

Detect:

- Added files.
- Modified files.
- Deleted files.
- Renamed files.
- Type changes when Git reports them.
- Changed symbols, routes, schemas, commands, config keys, and tests when detectable from changed files.

When both staged and unstaged changes exist, report both sets and prefer staged changes for CI-oriented maintenance.

---

## Impact Mapping

Map each changed path to affected knowledge using `ARCHITECTURE.md`, `knowledge/INDEX.md`, and module `INDEX.md` routing.

Typical impact mapping:

| Change | Affected docs |
|--------|---------------|
| API route | module `api.md`, module `INDEX.md` |
| Schema/model | module `schema.md`, module `INDEX.md` |
| Business logic | module `business_rules.md`, module `INDEX.md` |
| UI behavior | module `ui.md`, module `INDEX.md` |
| Config/tooling | `dependencies.md`, `ARCHITECTURE.md`, affected module index |
| New source root or module | `ARCHITECTURE.md`, `knowledge/INDEX.md`, new module skeleton |
| Deleted or renamed file | every doc citing the old path |
| Tests | relevant module doc and validation notes |

If ownership is ambiguous, report a warning and route through `knowledge/INDEX.md` before updating leaf docs.

---

## Stale Reference Handling

For deleted or renamed files, search canonical Markdown for references to removed paths, old paths, symbols, routes, schemas, commands, config keys, and tests.

For each stale reference:

- Replace it with the new path or evidence when a rename is certain.
- Remove the current fact when the implementation no longer exists.
- Mark the fact `TODO` only when the source may still exist but cannot be verified.
- Record stale references in the maintenance report.

Stale references to removed files or symbols are validation defects. In `ci` strictness they are blocking errors.

---

## Duplicate Fact Handling

Detect duplicate facts across authoritative documents.

Warn when the same fact appears in multiple places.

Treat duplicates as blocking in `ci` when they affect:

- Source-of-truth evidence.
- Task routing.
- `pkf.loads` behavior.
- Module ownership.

Resolve duplicates by keeping the fact in the narrowest authoritative document and replacing other copies with routing references or `pkf.related` links.

---

## Retrieval Export Invalidation

If `retrieval_exports: off`, do not inspect or regenerate `.ai/retrieval/`.

If retrieval exports are enabled:

- Mark exports affected by changed canonical Markdown documents as stale.
- Regenerate only the affected export records when deterministic incremental generation is available.
- Fall back to full export regeneration when affected records cannot be isolated safely.
- Never use `.ai/retrieval/` to decide canonical truth.

---

## Maintenance Report

Produce:

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
- <disabled, affected records, or regenerated files>
Recommended workflows:
- <extract, optimize, validate, export when enabled>
Warnings:
- <warning or none>
Errors:
- <error or none>
```

---

## Rules

- Prefer incremental maintenance over full scans.
- Use full scan fallback when Git data is unavailable or ambiguous.
- Update only affected canonical Markdown docs.
- Do not modify application code.
- Do not invent facts or relationships.
- Do not use retrieval exports as source truth.
- Treat removed-file and removed-symbol references as stale until proven current.
- Keep report output deterministic and evidence-backed.

---

## Completion Criteria

Maintenance succeeds when:

- Changed paths are detected or a full scan fallback is reported.
- Affected modules and docs are identified or ambiguity is reported.
- Deleted and renamed references are invalidated or marked for validation.
- Duplicate authoritative facts are reported with severity.
- Optional retrieval exports are ignored when disabled and marked/regenerated when enabled.
- Follow-up workflows are listed with the smallest affected context set.