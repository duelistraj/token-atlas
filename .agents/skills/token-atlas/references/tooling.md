# Developer Tooling Workflow

## Purpose

Define small developer commands that wrap the documented PKF workflows.

Tooling must not become a second source of truth. Commands select profiles, options, and workflows, then report what the PKF skill should execute.

The canonical dependency-light validator modules live in the repository root
`scripts/` directory. Release copies under `skills/token-atlas/scripts/` must
remain byte-for-byte identical. The public package does not include the local
PowerShell or benchmark runners.

---

## Command Surface

| Command | Workflow |
|---------|----------|
| `pkf init` | `initialize.md` |
| `pkf maintain` | `maintenance.md` |
| mutation-triggered closeout | `closeout.md` |
| `pkf extract` | `extract.md` |
| `pkf optimize` | `optimize.md` |
| `pkf validate` | `validation.md` |
| `pkf export` | `export.md` |
| `pkf simulate` | `simulate.md` |
| `pkf bench` | `benchmark.md` |
| `pkf help` | local wrapper help |

Default options:

```yaml
profile: core
retrieval_exports: off
simulation: changed
token_budget: summary
validation_strictness: advisory
```

---

## Help Surface

The local PowerShell wrapper must support these help forms:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 help
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 --help
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 -Help
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 validate --help
```

Help output must include:

- Wrapper purpose and the rule that documented workflows remain authoritative.
- Available commands and their workflow files.
- Profiles and default options.
- Supported PowerShell parameters and kebab-case aliases.
- Examples for default validation, CI validation, simulation, retrieval export, and benchmarking.
- Exit codes.
- A short distinction between Codex skill usage and the local script wrapper.

---

## Profiles And Flags

Commands accept these shared options. PowerShell-style parameters are canonical for the script; kebab-case aliases exist for common CLI muscle memory.

| Script option | Alias | Values | Default |
|---------------|-------|--------|---------|
| `-Profile` | `--profile` | `core`, `ci`, `retrieval`, `full` | `core` |
| `-RetrievalExports` | `--retrieval-exports` | `off`, `rag`, `graph`, `all` | `off` |
| `-Simulation` | `--simulation` | `off`, `changed`, `required`, `all` | `changed` |
| `-TokenBudget` | `--token-budget` | `summary`, `full` | `summary` |
| `-ValidationStrictness` | `--validation-strictness` | `advisory`, `ci` | `advisory` |
| `-Ci` | `--ci` | shortcut for CI validation | disabled |
| `-BenchSuite` | `--bench-suite` | `quick`, `core`, `full` | `quick` |
| `-BenchOutput` | `--bench-output` | `text`, `json` | `text` |
| `-Intent` | `--intent` | task text for simulation | empty |
| `-Paths` | `--paths` | changed paths for simulation | empty |
| `-Help` | `--help` | print local wrapper help | disabled |

Profile defaults:

- `core`: default options.
- `ci`: `validation_strictness: ci`, `simulation: required`, `token_budget: full`.
- `retrieval`: default options unless `--retrieval-exports` is set.
- `full`: `validation_strictness: ci`, `simulation: all`, `token_budget: full`, `retrieval_exports: all`.

Explicit flags override profile defaults.

---

## Codex Skill Usage

Codex skill usage is not the same as local wrapper execution.

In Codex, select the skill by naming it and state options in natural language, for example:

```text
Use the token-atlas skill with profile=ci, simulation=required, token_budget=full.
```

The local `scripts/pkf.ps1` wrapper is for repeatable developer and CI requests. It prints the selected workflow and options so Codex or a developer can execute the documented workflow.

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

- `-Intent "<task>"` or `--intent "<task>"`
- `-Paths "<path1>","<path2>"` or `--paths "<path1>","<path2>"`
- `-Simulation changed|required|all` or `--simulation changed|required|all`

### `pkf bench`

Request fixture-based skill benchmarking through `benchmark.md`.

Inputs:

- `-BenchSuite quick|core|full` or `--bench-suite quick|core|full`
- `-BenchOutput text|json` or `--bench-output text|json`

Benchmarking must use isolated fixture repositories under `benchmarks/fixtures/` and must not run Token Atlas against the token-atlas skill-maintenance repository itself.

---

## CI Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Command request is valid, help was printed, or advisory findings were reported. |
| `1` | CI blocking validation error. |
| `2` | Invalid command or invalid options. |

The wrapper may detect simple startup failures locally, but full PKF validation remains defined by `validation.md`.

---

## Rules

- Keep scripts thin.
- Do not duplicate extraction, optimization, validation, benchmark scoring, or export logic inside scripts.
- Do not modify application code from tooling wrappers.
- Prefer deterministic local checks for command arguments and startup files.
- Keep documented workflows authoritative.

---

## Completion Criteria

Tooling succeeds when:

- Commands map directly to documented workflows.
- Shared profile options are supported.
- `help`, `--help`, `-Help`, and command-local `--help` print useful wrapper guidance.
- `validate --ci` or `validate -Ci` has CI-friendly nonzero behavior for blocking startup failures.
- `export` is a no-op when `retrieval_exports: off`.
- `bench` maps to `benchmark.md` and validates benchmark suite/output options without implementing scoring in the wrapper.
- README examples show help, default, CI, simulation, retrieval export, and benchmark usage.
