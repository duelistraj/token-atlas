# Token Atlas Conformance Evals and Performance Benchmarks

## Purpose

Evaluate Token Atlas with deterministic fixture-based conformance checks and a
separate real-repository performance benchmark.

Conformance fixtures measure whether the skill creates and maintains accurate,
source-backed, minimal-context PKF and OKF knowledge. The pinned Tether Brain
lifecycle harness measures end-to-end performance; do not treat synthetic
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

Use the maintainer-only `scripts/pkf_savings_eval.py` to separate generic source
discovery, the adaptive local-probe policy, and PKF knowledge on a pinned
external repository. Run it only with explicit approval. The default target is
Tether Brain commit `5c458df3c737f0af2a2193186d98af90c45163f0`; the runner
requires a local checkout containing that commit, exports the tree into isolated
workspaces, and never targets this maintenance repository.

The runner provides split suites:

| Suite | Per repetition | Purpose |
| --- | ---: | --- |
| `retrieval` | 7 calls | Initialization plus both read-only tasks across source-only, probe-only, and PKF arms. |
| `lifecycle` | 5 calls | Initialization plus mutation and post-mutation work across probe-only and PKF. |
| `closeout` | 3 calls | Initialization plus an identical pre-applied mutation control and PKF closeout. |
| `regression` | 5 calls | Token-limited gate: initialization, cross-capability probe/PKF pair, and isolated closeout control/PKF pair. |
| `all` | 13 calls | All phases sharing one initialization. |

The retrieval suite uses a Latin-square three-arm order; two-arm phases alternate
by repetition. The closeout suite applies the checked-in patch under
`benchmarks/patches/` to identical clean workspaces and supplies the same changed
paths and semantic summary to both calls.

Use `regression` as an optional developer smoke check after initialization,
retrieval-routing, attribution, or closeout changes. It is not a formal
preflight or a headline replacement for `all`. The formal one-pass preflight is
`--suite all --repetitions 1` and publishes all 13 calls.

Pin the model and reasoning explicitly and inspect the call matrix before
execution:

```text
python scripts/pkf_savings_eval.py --target-repo /path/to/tether-brain --suite regression --model gpt-5.6-luna --model-reasoning-effort high --repetitions 1 --dry-run
python scripts/pkf_savings_eval.py --target-repo /path/to/tether-brain --suite regression --model gpt-5.6-luna --model-reasoning-effort high --repetitions 1
python scripts/pkf_savings_eval.py --target-repo /path/to/tether-brain --suite all --model gpt-5.6-luna --model-reasoning-effort high --repetitions 1 --dry-run
python scripts/pkf_savings_eval.py --target-repo /path/to/tether-brain --suite all --model gpt-5.6-luna --model-reasoning-effort high --repetitions 1
python scripts/pkf_savings_eval.py --target-repo /path/to/tether-brain --suite all --model gpt-5.6-luna --model-reasoning-effort high --repetitions 3 --dry-run
python scripts/pkf_savings_eval.py --target-repo /path/to/tether-brain --suite all --model gpt-5.6-luna --model-reasoning-effort high --repetitions 3
```

Publish total, cached, non-cached, and output tokens separately. Parse tool input
and output separately and report explicit read targets, searched roots, `.ai`
read/search calls, skill/reference reads, and unverified path mentions as
different metrics. Classify actual shell invocations rather than command-text
substrings: a `--detail` argument is not `tail`, and searching a validator path
is not a validator execution. Publish exact unexpected read paths, initialization
validation counts, opaque-helper source reads, and selected cross-route leaves.
Keep initialization, local retrieval, cross-capability
retrieval, mutation, post-mutation, and closeout phases separable.

The three arms have fixed meanings:

- `source_only`: no PKF and no adaptive probe instructions.
- `probe_only`: the bounded adaptive local probe with no PKF installed.
- `pkf`: PKF installed with adaptive retrieval and closeout; a particular task
  may still bypass PKF.

Record `retrieval_decision` as `activated`, `bypassed`, or `not_applicable` for
every call. Calculate PKF knowledge savings only from paired tasks whose PKF arm
was `activated`. Report PKF-arm tasks that bypassed retrieval separately as
environment deltas; do not attribute those differences to PKF reads. Include
materialized and pending leaf counts and the number of routed leaf documents.

Correctness, zero local-task PKF reads, required cross-capability activation, a valid compact route marker, selected route IDs that exist in `pkf.routes`, complete requirement coverage, zero redundant leaves, exact reads of the deduplicated configured leaf union, zero fallback or cross-route skill reads, one explicit initialization validation, zero opaque-helper source reads, focused tests, route-specific closeout, and validation are blocking quality gates.
Do not hard-code a benchmark-specific route ID, leaf names, or a global task-route leaf cap.

Performance uses a phase scorecard rather than a universal 5% verdict:

- Local bypass targets no more than 5% overhead in non-cached input, duration,
  and tool calls relative to `probe_only`.
- Cross-capability retrieval targets lower non-cached input and fewer tools than `probe_only`, while reporting route count, requirement coverage, minimality, deduplicated leaf count, and estimated route tokens.
- Mutation implementation must remain source-first; closeout is attributed and
  reported separately.
- Mapped closeout retains its six-tool target and structural fast-path gates;
  its token and latency cost are a knowledge-maintenance premium, not a 5%
  comparison with doing no maintenance.
- Initialization reports cost, materialization coverage, one final validation,
  opaque-helper behavior, and repeated broad-scan defects without a historical
  cost target.
- Amortization reports the activated retrieval count needed to recover setup and
  maintenance premiums.

Performance targets are advisory and never change quality status. A negative
saving remains a valid reported result.

Three repetitions remain the default and are required for replicated claims.
`--repetitions 1` is a publishable one-pass preflight: publish its complete
sanitized report, calculate performance checks with `directional` evidence, and
label its status `preliminary`. It must not replace a headline replicated result
or be pooled into a later three-repetition run.
Sanitize local paths, credentials, source contents, and raw traces. Pin both the
target commit, public-skill digest, and benchmark-harness digest so future skill
revisions can rerun the same application baseline and measurement logic.

By default each run writes incrementally to
`benchmarks/artifacts/<run-id>/`: `manifest.json` plus sanitized
`public/report.json` and `public/report.md`. `--artifact-mode full` additionally
retains local-only evidence under gitignored `private/`, including sanitized raw
traces, exact PKF snapshots, structured answers, schemas, stderr, source/PKF
diffs, route-helper output, and validation output. `public` omits that subtree;
`off` disables artifact retention. `--artifacts-root` changes the root and
`--run-id` supplies a validated stable ID.

Never retain authentication, a Codex home directory, a complete target source
workspace, `.git`, `node_modules`, or other dependency trees. Update the
manifest after every completed call and mark it failed if execution terminates.
Public artifacts may be versioned; exact private artifacts stay local.

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
- Expected route IDs, requirement count, coverage status, minimality status, unique leaves, and estimated route tokens when route composition is under test.
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

Produce a conformance aggregate containing:

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
