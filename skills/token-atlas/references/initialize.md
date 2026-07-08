# Initialize PKF Runtime

## Purpose

Create a target repository's `.ai/` PKF runtime and OKF knowledge skeleton when `.ai/PKF.md` is missing or incomplete.

Do not extract implementation details during initialization.

## Inputs

- Target repository structure.
- Existing `.ai/` content, if any.
- Existing README, config, source roots, test roots, and docs.

## Outputs

Create or update:

```text
.ai/
|-- PKF.md
|-- MEMORY.md
|-- ARCHITECTURE.md
`-- knowledge/
    |-- INDEX.md
    |-- glossary.md
    |-- dependencies.md
    |-- decision_log.md
    `-- <module>/
        |-- INDEX.md
        |-- api.md
        |-- schema.md
        |-- business_rules.md
        `-- ui.md
```

Create module directories only for modules supported by repository structure.

## Procedure

1. Discover project name, technologies, source roots, config roots, test roots, docs, and functional modules.
2. Create or repair `PKF.md`, `MEMORY.md`, and `ARCHITECTURE.md`.
3. Create root shared knowledge docs and one module skeleton per detected module.
4. Add OKF front matter to every generated Markdown file:

```yaml
---
type:
title:
description:
resource:
tags:
timestamp:

pkf:
  loads: []
  related: []
---
```

5. Populate only structure-backed facts, routing placeholders, and explicit TODOs.
6. Validate the initialized structure before extraction.

## Rules

- Preserve existing `.ai/` content when possible.
- Never inspect implementation internals for API, schema, business-rule, or UI facts in this phase.
- Keep indexes as routing surfaces, not knowledge dumps.
- Make startup route: `PKF.md -> MEMORY.md -> ARCHITECTURE.md -> knowledge/INDEX.md`.
- Leave unknown values empty or marked `TODO`.

## Success Criteria

- `.ai/PKF.md` exists and defines startup behavior.
- Required runtime and shared docs exist.
- Every detected module has the required OKF skeleton docs.
- Metadata is valid.
- The repository is ready for extraction.
