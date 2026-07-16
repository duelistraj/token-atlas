# Tooling Contract

## Purpose

Define optional local command wrappers for repeatable developer and CI requests.

Public Token Atlas does not require a bundled wrapper. If a target repo provides one, it should be a thin workflow selector and must not become a second source of truth.

## Recommended Commands

| Command | Workflow |
|---------|----------|
| `pkf init` | `initialize.md` |
| `pkf maintain` | `maintenance.md` |
| automatic end-of-turn closeout | `closeout.md` |
| `pkf extract` | `extract.md` |
| `pkf optimize` | `optimize.md` |
| `pkf validate` | `validation.md` |
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
