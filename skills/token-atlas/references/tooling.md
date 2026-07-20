# Tooling Contract

## Purpose

Define the bundled deterministic helpers and optional local command wrappers for
repeatable developer and CI requests.

Public Token Atlas bundles dependency-light scaffold, changed-path route, and
validation helpers under `scripts/`. Fresh scaffolding copies the runtime route,
validator, and their dependency-free modules under `.ai/tools/` so repository
closeout has stable commands without resolving the installed skill. They implement mechanical operations, not
capability-boundary judgment, knowledge-impact judgment, extraction, or
optimization. If a target repo provides a workflow wrapper, it should remain a
thin selector and must not become a second source of truth.

## Scaffold Helper

For fresh initialization, create a bounded structural draft, review its
capability map, then create the runtime:

```bash
python <skill-root>/scripts/pkf_scaffold.py inspect --path .
python <skill-root>/scripts/pkf_scaffold.py create --path .
```

The helper refuses to overwrite an existing runtime. Use
`references/initialize.md` for the full contract and preservation fallback.

## Changed-Path Route Helper

After the semantic knowledge-impact gate accepts a durable mutation, resolve
the smallest affected slice without loading leaf contents:

```bash
python -S .ai/tools/pkf_route.py --path . \
  --changed-path src/example.py --format json
```

Repeat `--changed-path` for all turn-owned paths and rename endpoints. A valid
request exits `0` even when its status is `partial` or `unmapped`; invalid usage
or malformed PKF data exits `2`.

## Bundled Validator

From an initialized target repository, run the repository-local validator:

```bash
python -S .ai/tools/pkf_validate.py --path .ai --strictness advisory
python -S .ai/tools/pkf_validate.py --path .ai --strictness ci --format json
```

For closeout or incremental maintenance, repeat `--changed-path` for each
repository-relative changed path. Runtime, bootstrap, structure, and routing
checks still run globally; leaf-contract and module token checks are limited to
the matched implementation slice.

```bash
python -S .ai/tools/pkf_validate.py --path .ai \
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
- Do not implement extraction, optimization, validation, simulation, export,
  scaffold, or changed-path routing logic inside the wrapper.
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
