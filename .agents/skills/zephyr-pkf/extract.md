# Phase 2 — Extract Repository Knowledge

## Purpose

Populate and maintain the OKF knowledge base using verified repository information.

Prefer incremental updates whenever possible to minimize repository analysis and AI context usage.

Do not optimize or reorganize knowledge in this phase.

---

## Inputs

- Repository source code
- Existing PKF runtime
- Existing OKF knowledge base (if available)

---

## Outputs

Update only the affected OKF documents so they accurately reflect the current repository.

---

## Execution

### 1. Determine Extraction Mode

If `.ai/` does **not** exist:

- Perform a **Full Repository Extraction**.

Otherwise:

- Perform an **Incremental Extraction**.

---

### 2. Detect Repository Changes

For Incremental Extraction:

Determine changes using the following priority:

1. `git diff --cached`
2. `git diff`
3. Repository history comparison (if explicitly requested)
4. Full repository scan (fallback)

Identify:

- Added files
- Modified files
- Deleted files
- Renamed files

For Full Repository Extraction:

Analyze the entire repository.

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
| New Module | Root `INDEX.md` + Module Skeleton |
| Repository Structure | `ARCHITECTURE.md` |
| Stable Project Knowledge | `MEMORY.md` |

Update only affected documents.

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

Never infer missing implementation.

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
- Never invent information.
- Never duplicate knowledge.
- Never modify application code.
- Preserve existing manual documentation whenever possible.
- Generate valid OKF documents.

---

## Completion Criteria

Phase 2 succeeds when:

- Every affected OKF document reflects the repository.
- Runtime documents are synchronized when necessary.
- Root and module `INDEX.md` files route correctly.
- OKF metadata is valid and current.
- Unknown information is marked as `TODO`.
- No duplicate knowledge exists.
- The repository is ready for Phase 3.