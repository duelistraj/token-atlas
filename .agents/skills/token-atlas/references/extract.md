# Phase 2 - Extract Repository Knowledge

## Purpose

Populate and maintain the OKF knowledge base using verified repository information.

Prefer incremental updates whenever possible to minimize repository analysis and AI context usage.

Do not reorganize knowledge in this phase except where needed to keep one authoritative location for a newly extracted fact.

---

## Inputs

- Repository source code
- Existing PKF runtime
- Existing OKF knowledge base, if available
- Maintenance impact report, when available

---

## Outputs

Update only the affected OKF documents so they accurately reflect the current repository. Retrieval exports are not updated in extraction unless an explicit retrieval profile or export workflow requests derived artifacts.

---

## Execution

### 1. Determine Extraction Mode

If `.ai/` was just initialized:

- Perform a **Hybrid Extraction**: materialize shared knowledge and leaves that
  own public package, service, CLI, API, or primary UI entry points. Leave other
  skeleton leaves pending.

Otherwise:

- Perform an **On-Demand Extraction** for a selected pending leaf, or an
  **Incremental Extraction** for turn-owned source changes.

Perform a **Full Repository Extraction** only when explicitly requested or
required by CI.

---

### 2. Detect Repository Changes

For Incremental Extraction:

Prefer the maintenance impact report from `maintenance.md`. If it is unavailable, determine changes using the following priority:

1. `git diff --cached`
2. `git diff`
3. Repository history comparison, if explicitly requested
4. Full repository scan fallback

Identify:

- Added files
- Modified files
- Deleted files
- Renamed files
- Stale references caused by deleted or renamed evidence
- Changed symbols, routes, schemas, commands, configuration keys, and tests when detectable

For Full Repository Extraction:

Analyze the entire repository.

For Hybrid Extraction, inspect repository structure and public entry points but
do not scan unrelated implementation solely to materialize every leaf.

---

### 3. Determine Knowledge Impact

Map changed files to their owning modules.

Determine which OKF documents require updates.

Typical mappings:

| Repository Change | Update |
|-------------------|--------|
| Routes | `api.md` |
| Models | `schema.md` |
| Services | `business_rules.md` |
| UI | `ui.md` |
| New Module | Root `INDEX.md` + module skeleton |
| Repository Structure | `ARCHITECTURE.md` |
| Stable Project Knowledge | `MEMORY.md` |
| Config or Tooling | `dependencies.md` or `ARCHITECTURE.md` |
| Tests | Relevant module document + validation notes |
| Documentation | Preserve or reconcile with source-backed facts |

Update only affected documents. For deleted or renamed files, update every canonical Markdown document that cites the removed or old path.

When the maintenance report contains an unambiguous module repartition, create
the new flat module skeletons before updating facts. Inventory every fact and
manual note in the superseded module, then assign each item to exactly one
capability and knowledge type. Retain the existing boundary if any ownership is
ambiguous.

---

### 4. Extract Repository Knowledge

Populate affected OKF documents using verified repository information.

Extract only factual knowledge:

- APIs
- Schemas
- Business rules
- UI structure
- Module summaries
- Repository architecture
- Stable project knowledge
- Commands, scripts, dependencies, and configuration behavior
- Source ownership and task routing signals

Never infer missing implementation.

Every non-placeholder fact should include compact evidence:

- Source path.
- Exact symbol, route, command, config key, or test name when applicable.
- Status: `verified` or `TODO`.

For every implementation-bearing leaf:

- Set `pkf.materialization: complete` after source-backed extraction succeeds.
- Populate `source_symbols` as a repository-relative path-to-symbol-list mapping.
- Use `## Edit Map` as the primary retrieval index with columns `Behavior`,
  `Source symbols`, `Tests`, `Styles/tokens`, and `Locator`.
- Emit ast-grep locators only when `sg` is verified as ast-grep; otherwise emit
  `rg -n -F -- '<symbol>' '<path>'`.
- Keep current implementation facts, not chronological feature summaries. Put
  durable policies in `business_rules.md` and still-relevant history in
  `decision_log.md`.
- Use `source_symbols: {}` and `- TODO: No source-backed facts.` for an empty
  complete leaf. Deferred leaves retain `pkf.materialization: pending`,
  `source_symbols: {}`, and `- TODO: Pending source extraction.`.

Do not paste large code blocks. Summarize behavior and point to source.

When a fact can no longer be verified because source evidence was removed, remove the fact or mark it `TODO` with stale evidence noted.

---

### 5. Update OKF Metadata

Refresh affected documents.

Update:

- `resource`
- `tags`
- `timestamp`
- `pkf.loads`
- `pkf.related`

Ensure metadata reflects the current repository.

Keep `pkf.loads` limited to documents that are normally required for the specific document's task.
Keep architecture and index `pkf.related` empty; leaf-level related paths remain optional.
Store verified cross-capability intents as narrow atomic root-index `pkf.routes` entries with explicit requirements, exact complete leaves, and per-leaf requirement coverage.
Broad tasks compose matching routes, deduplicate the combined leaves, and remove leaves without unique coverage.

For a capability spanning multiple source paths, use the narrowest common
existing path for `resource`. Fall back to repository root (`.`) when there is
no narrower common path, and retain exact source paths and symbols in the body.

---

### 6. Refresh Routing

Update:

- Root `knowledge/INDEX.md`
- Affected module `INDEX.md`

Ensure routing reflects:

- Available modules
- Document additions
- Document removals
- Updated loading paths
- Keywords, file paths, commands, and task intents that should lead to the module

Rewrite every affected `pkf.loads` and `pkf.related` edge. Remove a superseded
module directory only after every durable fact and manual note has moved and no
route or metadata reference targets it.

---

### 7. Synchronize PKF Runtime

Update only when required:

- `MEMORY.md` for long-term repository changes.
- `ARCHITECTURE.md` for architectural changes.
- `PKF.md` only if the PKF startup workflow changes.

---

## Rules

- Source code is the single source of truth.
- Prefer incremental extraction.
- Fall back to a full repository scan when Git information is unavailable.
- Update only affected documents whenever possible.
- Use maintenance impact reports to avoid broad repository scans.
- Invalidate stale facts from deleted or renamed files before adding new facts.
- Never invent information.
- Never duplicate knowledge.
- Never modify application code.
- Preserve existing manual documentation whenever possible.
- Generate valid OKF documents.
- Prefer evidence-linked bullets and tables.
- Keep indexes concise and route-focused.
- Treat `.ai/retrieval/` as generated output only; do not use it as extraction source truth.
- Mark unverifiable documentation conflicts as validation warnings or errors.
- Keep modules flat and derive their names from the target repository; reusable workflow text must not prescribe capability names.

---

## Completion Criteria

Phase 2 succeeds when:

- Every affected OKF document reflects the repository.
- Runtime documents are synchronized when necessary.
- Root and module `INDEX.md` files route correctly.
- OKF metadata is valid and current.
- Unknown information is marked as `TODO`.
- No duplicate knowledge exists.
- Stale references from deleted or renamed evidence are removed, replaced, or marked `TODO`.
- The repository is ready for Phase 3.
