---
name: zephyr-pkf
description: Generate and maintain this repository's PKF runtime and OKF-compatible knowledge base. Use when Codex needs to initialize, extract, validate, or optimize `.ai/` knowledge files for the zephyr-pkf repository while preserving source-code truth and avoiding application-code changes.
---

# Zephyr PKF

## Purpose

Generate and maintain a repository-specific, Open Knowledge Format (OKF) compatible knowledge base optimized for AI context retrieval.

---

## Execution

### 1. Analyze Repository

Determine:

- Repository structure
- Technologies
- Functional modules
- Existing PKF runtime (`.ai/`)
- Existing OKF knowledge base

Do not modify files during analysis.

---

### 2. Determine Execution Mode

If `.ai/` does **not** exist:

- Execute `initialize.md`
- Validate
- Execute `extract.md` using **Full Extraction**
- Validate
- Execute `optimize.md`
- Validate

Otherwise:

- Execute `extract.md` using **Incremental Extraction**
- Validate
- Execute `optimize.md`
- Validate

Stop immediately if validation fails.

---

## Global Rules

- Source code is the single source of truth.
- Generate an OKF-compatible knowledge base.
- Preserve existing documentation whenever possible.
- Never invent implementation details.
- Never modify application code.
- Prefer incremental updates.
- Optimize for minimal AI context retrieval.

---

## Success

Execution succeeds only when:

- Validation passes after every phase.
- The PKF runtime is synchronized.
- The OKF knowledge base reflects the repository.
- AI retrieval is optimized.
