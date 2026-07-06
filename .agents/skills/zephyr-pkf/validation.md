# Validation — PKF & OKF Integrity

## Purpose

Validate the integrity, synchronization, and retrieval efficiency of the Project Knowledge Framework (PKF).

Validation ensures the PKF runtime and the generated OKF knowledge base accurately represent the repository and support efficient AI context retrieval.

Do not modify any files.

Only report findings.

---

## Inputs

- Repository
- PKF Runtime (`.ai/`)
- OKF Knowledge Base (`.ai/knowledge/`)

---

## Validation

### 1. PKF Runtime

Verify:

- `PKF.md` exists.
- `MEMORY.md` exists.
- `ARCHITECTURE.md` exists.

Ensure the runtime startup sequence is valid:

```text
PKF.md
    ↓
MEMORY.md
    ↓
ARCHITECTURE.md
    ↓
knowledge/INDEX.md
```

---

### 2. OKF Structure

Verify:

- `.ai/knowledge/` exists.
- Root `INDEX.md` exists.
- Every detected module has a directory.

Every module must contain:

- `INDEX.md`
- `api.md`
- `schema.md`
- `business_rules.md`
- `ui.md`

Verify shared documents:

- `glossary.md`
- `dependencies.md`
- `decision_log.md`

---

### 3. OKF Compliance

Every OKF document must contain valid front matter.

Required fields:

```yaml
type
title
description
resource
tags
timestamp

pkf:
  loads
  related
```

Verify:

- Metadata is valid.
- Metadata is internally consistent.
- Referenced resources exist.

---

### 4. Repository Synchronization

Verify the knowledge base reflects the repository.

Ensure:

- APIs match implementation.
- Schemas match models.
- Business rules match implementation.
- UI documentation matches the frontend.
- `ARCHITECTURE.md` reflects repository structure.
- `MEMORY.md` reflects stable project knowledge.

Unknown information must be marked as `TODO`.

Never fabricated.

---

### 5. Knowledge Quality

Verify:

- No duplicate knowledge exists.
- Every concept has one authoritative location.
- Module summaries remain concise.
- Shared documents contain only repository-wide knowledge.

---

### 6. Routing Integrity

Verify the routing graph.

Expected navigation:

```text
PKF.md
    ↓
MEMORY.md
    ↓
ARCHITECTURE.md
    ↓
knowledge/INDEX.md
    ↓
Module INDEX.md
    ↓
Knowledge Documents
```

Ensure:

- Every referenced document exists.
- Every module is reachable.
- No broken references exist.
- No circular routing exists.

---

### 7. Retrieval Optimization

Simulate an AI retrieval session.

Verify that:

- Every task begins at `knowledge/INDEX.md`.
- Module `INDEX.md` files route correctly.
- `pkf.loads` loads only the minimum required documents.
- `pkf.related` references only meaningful documents.
- Unrelated modules are never loaded.

The knowledge base should support minimal-context retrieval.

---

## Validation Report

Produce:

### Passed

Successful validation checks.

---

### Warnings

Non-blocking issues.

Include:

- File
- Issue
- Recommendation

---

### Errors

Blocking issues.

Include:

- File
- Issue
- Recommended fix

Stop the PKF pipeline if any blocking errors exist.

---

## Rules

- Never modify documentation.
- Never invent missing information.
- Never ignore validation failures.
- Validate against the repository only.
- Treat the repository as the single source of truth.

---

## Success Criteria

Validation succeeds when:

- PKF runtime is valid.
- OKF knowledge base is structurally complete.
- Every document is OKF compliant.
- Repository knowledge is synchronized.
- Routing is valid.
- Retrieval simulation succeeds.
- AI can navigate using minimal context.
- No blocking errors remain.