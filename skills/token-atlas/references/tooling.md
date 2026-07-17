# Tooling Contract

## Purpose

Define the bundled deterministic validator and optional local command wrappers
for repeatable developer and CI requests.

Public Token Atlas bundles a dependency-light Python validator under `scripts/`.
It does not bundle a workflow wrapper. If a target repo provides one, it should
remain a thin selector and must not become a second source of truth.

## Bundled Validator

From the target repository, resolve the installed skill root and run:

```bash
python <skill-root>/scripts/pkf_validate.py --path .ai --strictness advisory
python <skill-root>/scripts/pkf_validate.py --path .ai --strictness ci --format json
```

For closeout or incremental maintenance, repeat `--changed-path` for each
repository-relative changed path. Runtime, bootstrap, structure, and routing
checks still run globally; leaf-contract and module token checks are limited to
the matched implementation slice.

```bash
python <skill-root>/scripts/pkf_validate.py --path .ai \
  --changed-path frontend/src/pages/NotesPage.tsx
```

The validator requires only Python 3.12 or newer. It uses the documented
approximate estimator by default. `--model <name>` enables optional exact token
counting only when a compatible tokenizer is installed.

## Recommended Commands

| Command | Workflow |
|---------|----------|
| `pkf init` | `initialize.md` |
| `pkf maintain` | `maintenance.md` |
| mutation-triggered closeout | `closeout.md` |
| `pkf extract` | `extract.md` |
| `pkf optimize` | `optimize.md` |
| `pkf validate` | bundled validator, then semantic `validation.md` |
| `pkf export` | `export.md` |
| `pkf simulate` | `simulate.md` |
| `pkf help` | wrapper help |

## Default Options

```yaml
profile: core
retrieval_exports: off
simulation: changed
token_budget: summary
validation_strictness: advisory
```

## Wrapper Rules

- Validate command and option values locally.
- Print selected workflow and options.
- Detect simple startup failures when useful.
- Do not implement extraction, optimization, validation, simulation, or export logic inside the wrapper.
- Keep documented workflows authoritative.

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Valid command request, help output, or advisory findings. |
| `1` | CI blocking validation error. |
| `2` | Invalid command or invalid option value. |

## CI Defaults

`ci` should imply:

```yaml
validation_strictness: ci
simulation: required
token_budget: full
```
