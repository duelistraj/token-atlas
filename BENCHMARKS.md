# Token Atlas Benchmarks

## Current low-token regression gate

Before another complete adaptive-attribution preflight, use the five-call
`regression` suite: one initialization, the cross-capability probe/PKF pair, and
the isolated closeout control/PKF pair. It must be dry-run inspected and requires
the same explicit benchmark approval as every other suite. It publishes a full
one-pass directional report but does not replace the 13-call `all` suite or a
three-repetition headline result.

The gate requires bounded `pkf.routes` retrieval, no Token Atlas workflow read
during cross retrieval, one explicit post-extraction validation, no helper-source
inspection, and mapped closeout with one route and one validation. Canonical
comparison remains `gpt-5.6-luna` at high reasoning.

## Published one-pass preflight

The complete adaptive-attribution `all` suite was run once against Tether Brain
commit `5c458df3c737f0af2a2193186d98af90c45163f0` with `gpt-5.6-luna` at high
reasoning. This is a published directional preflight, not a replicated result
and not the normal benchmark standard.

Status: **preliminary**<br>
Quality: **passed** (`13/13` calls, no blocking errors)<br>
Performance: **preliminary advisory missed**<br>
Recorded: `2026-07-19T17:01:30+00:00`

Full report: [`report.md`](benchmarks/artifacts/token-atlas-adaptive-attribution-gpt-5.6-luna-high-all-one-pass-preflight-2026-07-19/public/report.md)<br>
Raw sanitized result: [`report.json`](benchmarks/artifacts/token-atlas-adaptive-attribution-gpt-5.6-luna-high-all-one-pass-preflight-2026-07-19/public/report.json)<br>
Artifact manifest: [`manifest.json`](benchmarks/artifacts/token-atlas-adaptive-attribution-gpt-5.6-luna-high-all-one-pass-preflight-2026-07-19/manifest.json)

The local bypass and initialization targets improved, but cross-capability PKF
retrieval used 57.3% more non-cached input and eight more tool calls than the
probe-only arm. Isolated closeout passed validation but consumed 49,135
non-cached input tokens and 15 tool calls. These findings should be investigated
before starting a fresh three-repetition benchmark.

## PKF vs no PKF lifecycle benchmark

This benchmark compares Token Atlas with a source-only baseline on the real Tether Brain repository at commit `5c458df3c737f0af2a2193186d98af90c45163f0`. The repository was private when measured; no source, credentials, raw traces, or local paths are published here. The pinned commit can be independently checked once the project is public.

Status: **failed**<br>
Recorded: `2026-07-17T14:44:14+00:00`<br>
Model: `gpt-5.6-luna` at `high` reasoning<br>
Repetitions: `3` (`27` calls)

Raw sanitized result: [`report.json`](benchmarks/artifacts/pkf-vs-no-pkf-gpt-5.6-luna-high-2026-07-17/public/report.json)<br>
Artifact manifest: [`manifest.json`](benchmarks/artifacts/pkf-vs-no-pkf-gpt-5.6-luna-high-2026-07-17/manifest.json)

### Method

Each repetition exports the pinned Git tree into disposable workspaces. Both arms start without `.ai/` or Token Atlas instructions. The PKF arm installs the public skill under test, initializes and validates its knowledge base, then both arms run the same two read-only questions, one focused mutation, and one post-mutation question. Arm order alternates by repetition.

Token counts come from Codex JSONL. Total input includes cached input; non-cached input is reported separately. These figures are not pricing estimates.

### Median usage by task

| Task | Arm | Input | Cached | Non-cached | Output | Correct | Duration (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Boards Add task lookup | `no_pkf` | 124546 | 84992 | 41270 | 1525 | 0% | 38952 |
| Boards Add task lookup | `pkf` | 176926 | 143360 | 40802 | 2773 | 67% | 72703 |
| Post-mutation lookup | `no_pkf` | 96948 | 61696 | 29373 | 1398 | 100% | 34411 |
| Post-mutation lookup | `pkf` | 137767 | 82432 | 28935 | 2069 | 100% | 53786 |
| Favorite visibility mutation | `no_pkf` | 462028 | 421120 | 40908 | 6250 | n/a | 144020 |
| Favorite visibility mutation | `pkf` | 713615 | 642304 | 68377 | 8318 | n/a | 206151 |
| Initialize PKF | `pkf` | 3251337 | 3094528 | 156809 | 36988 | n/a | 747313 |
| Note/task link lookup | `no_pkf` | 486425 | 413184 | 73241 | 3649 | 100% | 91051 |
| Note/task link lookup | `pkf` | 270750 | 214272 | 56478 | 4112 | 100% | 107953 |

### Result

Median complete lifecycle input: **1343276** without PKF and **5024503** with PKF.<br>
Median complete lifecycle non-cached input: **195947** without PKF and **349944** with PKF.<br>
Median paired read-only input saving: **-13289 tokens**.<br>
Median paired read-only non-cached input saving: **7447 tokens**.<br>
Break-even including initialization and the measured mutation premium: **not reached** read-only tasks by total input and **25** by non-cached input.

On this measured workload, PKF did not produce positive median read-only total-input savings, so no lifecycle break-even was observed.

The cross-capability note/task-link lookup was the clear PKF win: median input fell from **486425** to **270750** tokens, while non-cached input fell from **73241** to **56478**. The focused mutation moved the other way: median input rose from **462028** to **713615** because PKF also synchronized and validated knowledge.

Every PKF initialization passed strict validation. Every mutation arm made the expected source/test change and passed the focused test; every PKF mutation also emitted closeout and passed strict validation. The link and post-mutation lookup answers were 100% correct in both arms.

The strict benchmark status is failed because 4 Boards answers missed the expected `right-side` toast-placement field. The local action calls `toast.error`, while placement is inherited from the application's default Toaster configuration, so this field mixes local behavior with a global dependency default. Token measurements are retained, but the result is not a clean quality-equivalent win for either arm.

### Limitations

- One application repository, one pinned commit, one model, and one reasoning setting.
- Three repetitions describe this controlled run but are not a population-wide estimate.
- Provider prompt caching can change total-input composition, so cached and non-cached input must be interpreted separately.
- The target was private when measured; external reproduction becomes possible when that exact commit is published.
- The Boards correctness field depended on implicit toast placement and should be narrowed before the next benchmark series.

### Evaluation errors

- repetition 1 no_pkf/boards_add_task: incorrect structured answer
- repetition 2 pkf/boards_add_task: incorrect structured answer
- repetition 2 no_pkf/boards_add_task: incorrect structured answer
- repetition 3 no_pkf/boards_add_task: incorrect structured answer

## Artifact archive

All future runs use `benchmarks/artifacts/<run-id>/`. Public sanitized reports
and a manifest are versioned. With the default `full` artifact mode, exact PKF
snapshots, sanitized raw traces, answers, schemas, stderr, diffs, route output,
and validation evidence are retained under a gitignored, local-only `private/`
subtree. Authentication, Codex home directories, full target workspaces, Git
metadata, and dependency trees are never copied.

- [Original three-repetition lifecycle result](benchmarks/artifacts/pkf-vs-no-pkf-gpt-5.6-luna-high-2026-07-17/manifest.json)
- [Runtime-v3 one-pass result](benchmarks/artifacts/pkf-vs-no-pkf-gpt-5.6-luna-high-runtime-v3-1pass-2026-07-19/manifest.json)
- [Adaptive-attribution one-pass preflight](benchmarks/artifacts/token-atlas-adaptive-attribution-gpt-5.6-luna-high-all-one-pass-preflight-2026-07-19/manifest.json)

Historical private artifacts were not retained and are explicitly marked
unavailable in their manifests; they have not been fabricated during migration.
