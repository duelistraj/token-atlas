# Benchmark - Token Atlas Skill Evals

## Purpose

Benchmark Token Atlas with deterministic fixture-based evals.

Benchmarks measure whether the skill creates and maintains accurate, source-backed, minimal-context PKF and OKF knowledge. They are not primarily raw speed tests.

Do not benchmark by running Token Atlas against the token-atlas skill repository itself.

---

## Inputs

- Benchmark suite: `quick`, `core`, or `full`.
- Benchmark output: `text` or `json`.
- Fixture repositories under `benchmarks/fixtures/`.
- Expected reports and scoring rules in each fixture.
- Selected execution profile and options when a fixture requests them.

Default benchmark options:

```yaml
bench_suite: quick
bench_output: text
```

Executable runner defaults:

```text
python scripts\pkf_bench.py --suite quick --mode local --format text
```

Runner options:

| Option | Values | Default |
|--------|--------|---------|
| `--suite` | `quick`, `core`, `full` | `quick` |
| `--mode` | `local`, `codex`, `both` | `local` |
| `--format` | `text`, `json` | `text` |
| `--timeout-seconds` | positive integer | `1200` |
| `--model` | Codex model id | `gpt-5.5` |
| `--model-reasoning-effort` | `minimal`, `low`, `medium`, `high` | `medium` |

The PowerShell `pkf bench` wrapper remains a selector for this workflow and must not implement scoring. The executable benchmark harness is `scripts/pkf_bench.py`.

The runner must pass the resolved model and reasoning effort explicitly to `codex exec`; it must not rely on ambient `config.toml` defaults. Every text and JSON benchmark report must include the resolved model, reasoning effort, and source (`runner-default` or `cli`).

---

## Suites

| Suite | Purpose | Fixtures |
|-------|---------|----------|
| `quick` | Fast command and startup confidence. | `missing-runtime`, `simple-api` |
| `core` | Main skill quality evals. | Startup, extraction, maintenance, routing, stale-evidence, broad-load, and functional-boundary fixtures. |
| `full` | Exhaustive evals including exports. | All core fixtures plus `exports`. |

Use `quick` for local smoke checks, `core` for normal development, and `full` before release or CI gating.

---

## Benchmark Dimensions

Score each fixture on these dimensions:

| Dimension | Checks |
|-----------|--------|
| Startup recovery | Missing or incomplete `.ai/PKF.md` triggers initialization before repository analysis. |
| Initialization | OKF skeleton is complete, metadata is valid, and implementation facts are not invented. |
| Extraction | API, schema, business rule, UI, dependency, and architecture facts are source-backed. |
| Maintenance | Added, modified, deleted, and renamed paths map to affected docs and invalidated facts. |
| Validation | Front matter, broken references, duplicate facts, stale evidence, routing, and CI behavior are reported correctly. |
| Simulation | Representative intents load only expected docs and no unrelated modules. |
| Optimization | Automatic loads stay minimal, optional context stays in `pkf.related`, and token budgets are reported. |
| Exact targeting | Required leaves resolve to exact source symbols, tests/styles when relevant, and targeted locator commands; fallback use is explicit. |
| Exports | Retrieval exports are skipped when disabled and valid JSONL when enabled. |
| Tooling | Wrapper commands remain thin workflow selectors and preserve documented exit codes. |
| Module boundaries | Generated modules are flat, target-derived capabilities; coarse modules migrate only with unambiguous evidence and placeholders remain excluded. |

Performance timing may be recorded, but it must not replace these correctness and retrieval-quality checks.

### Activation Gate Eval

Use the maintainer-only `scripts/pkf_activation_eval.py` after changing skill
trigger or closeout semantics. It runs frozen runtime-v1 and current runtime-v2
read-only cases with identical prompts, records Codex JSONL token usage, and
requires v2 to avoid skill/reference access and status output. Its v2 mutation
control must still synchronize source, test evidence, and PKF knowledge.

Run three repetitions with the pinned model and low reasoning, the smallest
effort compatible with the host's advertised tool set:

```text
python scripts/pkf_activation_eval.py --repetitions 3 --model gpt-5.5 --model-reasoning-effort low --format json
```

This eval is internal maintainer tooling and must not be copied into the public
skill package.

---

## Fixture Contract

Each fixture directory must include a `README.md` with:

- Goal.
- Source shape.
- Benchmark flow.
- Expected selected modules.
- Expected and forbidden generated module inventories when module discovery or migration is under test.
- Expected required docs.
- Forbidden automatic loads.
- Expected warnings.
- Expected errors.
- Token threshold expectations.
- Exit behavior.

Fixtures may include source files, existing `.ai/` Markdown, and optional expected report snapshots. Generated outputs must be compared deterministically and must not become source truth.

Module-boundary fixtures may add `expected_generated_modules` and
`forbidden_generated_modules`. `selected_modules` remains the task-specific
route, while `generated_modules` is the complete flat module inventory. A
fixture may use `expected_ai_from` to share an expected-output overlay with a
related synthetic fixture.

---

## Execution

### 1. Select Fixtures

Use the requested `bench_suite` to select fixture directories.

If a fixture is missing, report it as an error because the benchmark suite is incomplete.

### 2. Prepare Isolated Workspaces

For each fixture:

- Copy the fixture repository into a temporary isolated workspace.
- Preserve fixture Git state when the scenario depends on changed, deleted, or renamed files.
- Do not write generated `.ai/` outputs back into the fixture source directory.
- Do not run Token Atlas against the skill-maintenance repository.

### 3. Run The Required Workflow

Run the workflow requested by the fixture:

- Startup and initialization fixtures use `initialize.md`, then `validation.md`.
- Extraction fixtures use `extract.md`, then `validation.md`.
- Maintenance fixtures use `maintenance.md`, then `extract.md`, `optimize.md`, and `validation.md`.
- Routing fixtures use `simulate.md` and `validation.md`.
- Export fixtures use `export.md` only when `retrieval_exports` is `rag`, `graph`, or `all`.
- Tooling fixtures use `tooling.md` and the local wrapper contract.

### 4. Score Results

For each fixture, report:

```text
Benchmark Fixture
Name: <fixture>
Suite: <quick, core, or full>
Status: <passed, warning, or failed>
Score: <passed checks>/<total checks>
Selected modules: <modules>
Required docs: <docs>
Generated modules: <complete inventory>
Forbidden automatic loads: <passed or failed>
Warnings: <expected and unexpected warnings>
Errors: <expected and unexpected errors>
Token impact: <threshold status>
Source targets: <path:symbol entries>
Targeted commands: <commands>
Fallback search: <yes/no and reason>
Exit behavior: <expected or unexpected>
Evidence: <compact source and routing evidence>
```

When `bench_output: json` is selected, emit deterministic JSON with the same fields and stable fixture ordering.

`scripts/pkf_bench.py --mode both` reports separate `local` and `codex` result blocks for each fixture. The fixture-level status is AND-based: a fixture fails if any executed mode fails, warns if no mode fails but any mode warns, and passes only when all executed modes pass.

`Score` is not a weighted quality metric. It is the contract check count rendered as `<passed checks>/<total checks>`.

Codex execution timeouts are fixture failures, not invalid runner usage. They must be reported with status `timeout` in the Codex mode block and cause runner exit code `1`.

### 5. Aggregate Report

Produce:

- Total fixture count.
- Passed, warning, and failed counts.
- Failing fixture names.
- Regression summary by benchmark dimension.
- Token budget regressions.
- Unexpected broad loads.
- Unexpected stale or unsupported facts.
- Fallback-search count and rate across reported fixture routes.

---

## Scoring Rules

A fixture passes only when all required expectations are met and no unexpected blocking errors appear.

Treat these as failures:

- Invented implementation facts.
- Missing source evidence for durable facts.
- Missing required OKF documents.
- Missing expected modules, forbidden generated modules, or nested module layouts.
- Broken `pkf.loads` or `pkf.related` references.
- Unrelated modules loaded automatically.
- Stale references to deleted or renamed evidence.
- Missing required simulation output.
- Enabled exports with invalid JSONL or unresolved endpoints.
- Wrapper command mapping that diverges from documented workflows.

Treat these as warnings:

- Ambiguous but evidence-backed routing.
- Approximate token estimates when exact tokenization is unavailable.
- Startup or module token costs above warning thresholds.
- Duplicate facts that do not affect source truth, routing, `pkf.loads`, or module ownership.

---

## Rules

- Keep benchmarks deterministic.
- Keep fixture repositories small.
- Prefer source-backed expectations over prose-only assertions.
- Never use `.ai/retrieval/` as source truth.
- Never mutate fixture source directories during scoring.
- Never benchmark the token-atlas skill repo as a target repository.
- Do not add benchmark logic to the thin wrapper beyond selecting `benchmark.md` and validating benchmark options.

---

## Success Criteria

Benchmarking succeeds when:

- The selected fixture suite runs in isolated workspaces.
- Every fixture reports expected modules, docs, warnings, errors, token impact, and exit behavior.
- The aggregate report identifies regressions by benchmark dimension.
- `quick`, `core`, and `full` suites are deterministic.
- Tooling remains a thin selector for documented workflows.
