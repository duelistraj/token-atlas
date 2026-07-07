# Developer Tooling Workflow

## Purpose

Define small developer commands that wrap the documented PKF workflows.

Tooling must not become a second source of truth. Commands select profiles, options, and workflows, then report what the PKF skill should execute.

---

## Command Surface

| Command | Workflow |
|---------|----------|
| `pkf init` | `initialize.md` |
| `pkf maintain` | `maintenance.md` |
| `pkf extract` | `extract.md` |
| `pkf optimize` | `optimize.md` |
| `pkf validate` | `validation.md` |
| `pkf export` | `export.md` |
| `pkf simulate` | `simulate.md` |

Default options:

```yaml
profile: core
retrieval_exports: off
simulation: changed
token_budget: summary
validation_strictness: advisory
```

---

## Profiles And Flags

Commands accept these shared options:

| Option | Values | Default |
|--------|--------|---------|
| `--profile` | `core`, `ci`, `retrieval`, `full` | `core` |
| `--retrieval-exports` | `off`, `rag`, `graph`, `all` | `off` |
| `--simulation` | `off`, `changed`, `required`, `all` | `changed` |
| `--token-budget` | `summary`, `full` | `summary` |
| `--validation-strictness` | `advisory`, `ci` | `advisory` |
| `--ci` / `-Ci` | shortcut for CI validation | disabled |

Profile defaults:

- `core`: default options.
- `ci`: `validation_strictness: ci`, `simulation: required`, `token_budget: full`.
- `retrieval`: default options unless `--retrieval-exports` is set.
- `full`: `validation_strictness: ci`, `simulation: all`, `token_budget: full`, `retrieval_exports: all`.

Explicit flags override profile defaults.

---

## Command Behavior

### `pkf init`

Request initialization. If `.ai/PKF.md` is missing, this is the startup recovery command.

### `pkf maintain`

Request incremental maintenance.

Use Git change detection priority:

1. `git diff --cached --name-status`
2. `git diff --name-status`
3. Full scan fallback

### `pkf extract`

Request extraction using `maintenance.md` impact when available.

### `pkf optimize`

Request routing, duplication, and token budget optimization.

### `pkf validate`

Request validation using selected strictness.

- Advisory mode reports warnings and blocking recommendations.
- CI mode exits nonzero on blocking errors.
- Missing `.ai/PKF.md` is a CI blocking startup error.

### `pkf export`

Request retrieval export only when `retrieval_exports` is `rag`, `graph`, or `all`.

If `retrieval_exports: off`, report that exports are disabled and exit successfully.

### `pkf simulate`

Request retrieval simulation.

Inputs:

- `--intent "<task>"`
- `--paths "<path1,path2>"`
- `--simulation changed|required|all`

---

## CI Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Command request is valid, or advisory findings were reported. |
| `1` | CI blocking validation error. |
| `2` | Invalid command or invalid options. |

The wrapper may detect simple startup failures locally, but full PKF validation remains defined by `validation.md`.

---

## Rules

- Keep scripts thin.
- Do not duplicate extraction, optimization, validation, or export logic inside scripts.
- Do not modify application code from tooling wrappers.
- Prefer deterministic local checks for command arguments and startup files.
- Keep documented workflows authoritative.

---

## Completion Criteria

Tooling succeeds when:

- Commands map directly to documented workflows.
- Shared profile options are supported.
- `validate --ci` or `validate -Ci` has CI-friendly nonzero behavior for blocking startup failures.
- `export` is a no-op when `retrieval_exports: off`.
- README examples show default, CI, simulation, and retrieval export usage.