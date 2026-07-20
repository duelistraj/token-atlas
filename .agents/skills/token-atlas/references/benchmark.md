# Token Atlas Conformance Evals and Performance Benchmarks

## Purpose

Evaluate Token Atlas with deterministic fixture-based conformance checks and a
separate real-repository performance benchmark.

Conformance fixtures measure whether the skill creates and maintains accurate,
source-backed, minimal-context PKF and OKF knowledge. The lifecycle harness
measures an explicitly selected external repository; do not treat synthetic
fixture timings as real-repository savings.

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

## Conformance Dimensions

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

Performance timing may be recorded, but it must not replace these correctness
and retrieval-quality checks. Fixture reports use `evaluation_kind:
conformance`; the lifecycle harness uses `evaluation_kind:
real_repository_performance`.

### Activation Gate Eval

Use the maintainer-only `scripts/pkf_activation_eval.py` after changing skill
trigger or closeout semantics. It runs frozen runtime-v1 and current runtime-v3
read-only cases with identical prompts, records Codex JSONL token usage, and
requires v3 to avoid PKF/skill/reference access and status output for a local
read-only task. A separate knowledge-neutral mutation control must emit its
direct `no-op` without Token Atlas access, while the semantic mutation control
must still synchronize source, test evidence, and PKF knowledge.

Run three repetitions with the same Luna/high configuration as the lifecycle
evaluation:

```text
python scripts/pkf_activation_eval.py --repetitions 3 --model gpt-5.6-luna --model-reasoning-effort high --format json
```

This eval is internal maintainer tooling and must not be copied into the public
skill package.

### Real Repository Adaptive Attribution Eval

Use the maintainer-only baseline and performance tools only with explicit
approval. They have no default repository, commit, task, model, reasoning
setting, or phase. Repository-specific prompts, expected answers, patches,
commands, and optional untracked workspace links live in an explicitly supplied
JSON specification under `benchmarks/targets/` or another caller-selected path;
they never influence Token Atlas generation policy.

#### One-time immutable PKF baseline

Create the PKF once for a pinned target tree with `scripts/pkf_baseline.py`.
Archive extraction excludes the target commit's `.ai/` and installed Token Atlas
packages before any file reaches the draft. Only the managed Token Atlas block
is removed from `AGENTS.md`; unrelated repository instructions are preserved,
and unmanaged PKF instructions fail preparation rather than contaminating the
new initialization.

`--prepare-only` performs no model call and leaves a persistent resumable draft.
Without that flag, the tool performs complete initialization, an independent
repository-derived completeness and capability-boundary review, strict
validation, and an unresolved-marker scan. Successful passes are checkpointed:
a failed review resumes from the existing initialized PKF and does not rerun the
initialization pass. A baseline is sealed atomically only after all checks pass.
An existing sealed baseline is verified and reused; it is never silently
regenerated. The performance runner also requires its recorded public-skill
digest to match the current package; a mismatch requires an explicit migration
or approval for a new baseline rather than silent mutation.

```text
python scripts/pkf_baseline.py create --target-repo /path/to/repository --target-commit <commit> --prepare-only
python scripts/pkf_baseline.py create --target-repo /path/to/repository --target-commit <commit> --model <model-id> --model-reasoning-effort <effort>
python scripts/pkf_baseline.py validate --target-repo /path/to/repository --target-commit <commit>
```

#### Independently selectable phases

The performance runner never initializes PKF. It requires the matching sealed
baseline and explicit comma-separated `--phases` selected from:

| Phase | Calls per repetition | State |
| --- | ---: | --- |
| `retrieval` | Each configured task across `source_only`, `probe_only`, and `pkf` | Clean baseline |
| `mutation` | Configured mutation across `probe_only` and `pkf` | Saves reusable state in full artifact mode |
| `post_mutation` | Configured read across `probe_only` and `pkf` | Depends on same-run mutation or `--state-from` |
| `closeout` | Pre-applied control and PKF closeout | Clean baseline plus configured patch |

There is no performance `--suite` and no implicit `all`. The `quick`, `core`,
and `full` suites belong only to deterministic fixture conformance. Select every
performance phase explicitly when desired. Independent calls run concurrently;
`--jobs 0` uses all ready jobs, while a positive value caps parallelism.
Post-mutation work starts as soon as its matching mutation finishes. Each call
uses an isolated workspace and a deterministic call ID.

```text
python scripts/pkf_savings_eval.py --target-repo /path/to/repository --target-commit <commit> --benchmark-spec /path/to/spec.json --phases retrieval --model <model-id> --model-reasoning-effort <effort> --repetitions 1 --dry-run
python scripts/pkf_savings_eval.py --target-repo /path/to/repository --target-commit <commit> --benchmark-spec /path/to/spec.json --phases retrieval,mutation,post_mutation,closeout --model <model-id> --model-reasoning-effort <effort> --repetitions 1
python scripts/pkf_savings_eval.py --target-repo /path/to/repository --target-commit <commit> --benchmark-spec /path/to/spec.json --phases post_mutation --state-from /path/to/prior-run/private/states --model <model-id> --model-reasoning-effort <effort> --repetitions 1
```

The three arms have fixed meanings:

- `source_only`: sanitized target instructions, no PKF, and no adaptive probe policy.
- `probe_only`: the same target instructions plus bounded adaptive local-probe policy, with no PKF installed.
- `pkf`: the same pinned source plus the immutable baseline and adaptive closeout; a task may still bypass retrieval.

Publish total, cached, non-cached, and output tokens separately. Non-cached
input is the primary performance metric; duration and tools are telemetry.
Calculate PKF retrieval savings only for pairs whose PKF arm actually activated
retrieval. Report bypass deltas separately. Initialization is a one-time baseline
provenance cost and is excluded from recurring phase totals.

Correctness, zero local-task PKF reads, required cross-capability activation,
valid route markers, authoritative requirement ownership, complete coverage,
selected-route irredundancy, exact expected leaf reads, no unexpected reads,
focused tests, route-specific closeout, and validation remain blocking quality
gates. Leaf and token counts are observations, not ceilings.

Three repetitions remain the default for replicated claims. One repetition is a
publishable preliminary preflight and must not be pooled into a later replicated
run. New lifecycle reports use schema version 9. Existing artifacts remain
unchanged.

By default each run writes incrementally to
`benchmarks/artifacts/<run-id>/`: `manifest.json` plus sanitized
`public/report.json` and `public/report.md`. `--artifact-mode full` additionally
retains local-only evidence under gitignored `private/`, including sanitized raw
traces, exact PKF snapshots, structured answers, schemas, stderr, source/PKF
diffs, route-helper output, and validation output. `public` omits that subtree;
`off` disables artifact retention. `--artifacts-root` changes the root and
`--run-id` supplies a validated stable ID.

Never retain authentication or an executor home directory. Public artifacts
must never contain a target source workspace, `.git`, dependency trees, or raw
traces. Full local-only artifacts may retain the exact mutation-state workspace
needed by `--state-from`, but must still exclude `.git`, configured workspace
links, and dependency trees. Update the manifest after every completed call and
mark it failed if execution terminates. Public artifacts may be versioned;
exact private artifacts stay local.

This lifecycle eval is internal maintainer tooling and must not be copied into
the public skill package. Human-readable findings live in root
`BENCHMARKS.md`; canonical run bundles live under `benchmarks/artifacts/`.

---

## Conformance Fixture Contract

Each conformance fixture directory must include a `README.md` with:

- Goal.
- Source shape.
- Benchmark flow.
- Expected selected modules.
- Expected and forbidden generated module inventories when module discovery or migration is under test.
- Expected required docs.
- Expected route IDs, requirement count, coverage status, irredundancy status, unique leaves, and estimated route-content tokens when route composition is under test.
- Forbidden automatic loads.
- Expected warnings.
- Expected errors.
- Token measurement expectations.
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
Token impact: <observed measurements>
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

Produce a conformance aggregate containing:

- Total fixture count.
- Passed, warning, and failed counts.
- Failing fixture names.
- Regression summary by benchmark dimension.
- Token measurement regressions.
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
