# Token Atlas Benchmarks

## Adaptive attribution benchmark — all — one-pass preflight

This benchmark separates generic source discovery, the adaptive local-probe policy, and PKF knowledge on Tether Brain at commit `5c458df3c737f0af2a2193186d98af90c45163f0`. The repository was private when measured; no source, credentials, local paths, or raw traces are published.

Publication class: **one-pass preflight**<br>
Replicated: **no**<br>
Status: **preliminary**<br>
Quality: **passed**<br>
Performance: **preliminary_advisory_missed**<br>
Recorded: `2026-07-19T17:01:30+00:00`<br>
Model: `gpt-5.6-luna` at `high` reasoning<br>
Repetitions: `1` (`13` calls)

Raw sanitized result: [`token-atlas-adaptive-attribution-gpt-5.6-luna-high-all-one-pass-preflight-2026-07-19.json`](.agents/skills/token-atlas/benchmarks/results/token-atlas-adaptive-attribution-gpt-5.6-luna-high-all-one-pass-preflight-2026-07-19.json)

### Method

`source_only` measures generic discovery, `probe_only` isolates the bounded local-probe policy, and `pkf` adds adaptive knowledge retrieval and semantic closeout. Token counts come from Codex JSONL; total and non-cached input are reported separately and are not pricing estimates. Tool input and output are parsed separately. Explicit read targets are distinct from unverified path mentions.

### Single-pass usage by task

| Task | Phase | Arm | Input | Non-cached | Output | Duration ms | Tools | Explicit .ai reads | Correct |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| boards_add_task | retrieval | `pkf` | 59006 | 20862 | 824 | 25691 | 3 | 0 | 100% |
| boards_add_task | retrieval | `probe_only` | 66139 | 23899 | 983 | 25267 | 3 | 0 | 100% |
| boards_add_task | retrieval | `source_only` | 79735 | 29303 | 892 | 24535 | 3 | 0 | 100% |
| favorite_visibility_after_change | post_mutation | `pkf` | 72401 | 24017 | 1204 | 34466 | 3 | 0 | 100% |
| favorite_visibility_after_change | post_mutation | `probe_only` | 88182 | 24694 | 1421 | 37909 | 4 | 0 | 100% |
| favorite_visibility_mutation | mutation | `pkf` | 670367 | 45471 | 7082 | 181316 | 23 | 8 | n/a |
| favorite_visibility_mutation | mutation | `probe_only` | 698703 | 42063 | 5181 | 139493 | 15 | 0 | n/a |
| initialize | setup | `pkf` | 1562263 | 91543 | 17044 | 392357 | 45 | 0 | n/a |
| isolated_closeout | closeout | `pkf` | 325615 | 49135 | 5159 | 124512 | 15 | 7 | n/a |
| isolated_closeout | closeout | `probe_only` | 11269 | 2309 | 66 | 7836 | 0 | 0 | n/a |
| note_task_links | retrieval | `pkf` | 489957 | 76517 | 4153 | 99730 | 13 | 13 | 100% |
| note_task_links | retrieval | `probe_only` | 182547 | 48659 | 2720 | 63765 | 5 | 0 | 100% |
| note_task_links | retrieval | `source_only` | 224632 | 56184 | 2550 | 59415 | 6 | 0 | 100% |

### Attribution deltas

- `boards_add_task` probe_vs_pkf: input -7133, non-cached -3037, duration +424 ms.
- `boards_add_task` source_vs_probe: input -13596, non-cached -5404, duration +732 ms.
- `favorite_visibility_after_change` probe_vs_pkf: input -15781, non-cached -677, duration -3443 ms.
- `favorite_visibility_mutation` probe_vs_pkf: input -28336, non-cached +3408, duration +41823 ms.
- `isolated_closeout` probe_vs_pkf: input +314346, non-cached +46826, duration +116676 ms.
- `note_task_links` probe_vs_pkf: input +307410, non-cached +27858, duration +35965 ms.
- `note_task_links` source_vs_probe: input -42085, non-cached -7525, duration +4350 ms.

### Performance advisories

Evidence strength: **directional**.

- local_input_tokens_overhead: met (`-10.78`, target <= 5%).
- local_non_cached_input_tokens_overhead: met (`-12.71`, target <= 5%).
- local_duration_ms_overhead: met (`1.68`, target <= 5%).
- cross_capability_non_cached_input_tokens_delta: missed (`27858.00`, target < 0).
- cross_capability_tool_call_count_delta: missed (`8.00`, target < 0).
- initialization_non_cached_input_tokens_delta: met (`-8177.00`, target < 0 versus runtime-v3 one-pass).
- initialization_duration_ms_delta: met (`-124587.00`, target < 0 versus runtime-v3 one-pass).
- operational_input_tokens_overhead: missed (`54.50`, target <= 5%).
- operational_non_cached_input_tokens_overhead: missed (`52.52`, target <= 5%).
- operational_duration_ms_overhead: missed (`69.80`, target <= 5%).

### Preflight interpretation

- All 13 calls completed, every structured answer was correct, both mutations
  passed the focused test, and PKF initialization and closeout passed strict
  validation. The preflight therefore passed its blocking quality gates.
- The local Boards task bypassed PKF as intended. Against `probe_only`, the PKF
  arm used 12.7% less non-cached input with 1.7% more latency and no explicit
  `.ai` or Token Atlas reads.
- Initialization improved against the runtime-v3 one-pass reference by 8,177
  non-cached tokens (8.2%) and 124,587 ms (24.1%).
- The expected cross-capability benefit did not survive this pass. PKF used
  27,858 more non-cached input tokens (57.3%), eight more tool calls, and 35,965
  ms more than `probe_only`, despite returning the same correct answer.
- Isolated PKF closeout consumed 49,135 non-cached input tokens and 124,512 ms,
  versus 2,309 tokens and 7,836 ms for the no-PKF acknowledgement control. It
  completed correctly, but its 15 tool calls and seven explicit `.ai` reads show
  that affected-slice closeout remains substantially heavier than intended.
- The reported 52.5% operational non-cached overhead is an aggregate of every
  experiment in the `all` suite, including both mutation-integrated closeout and
  the separate isolated-closeout measurement. It is useful as a preflight alarm,
  not as a literal production-lifecycle estimate.

This result is sufficient reason to inspect cross-capability routing and
closeout execution before spending tokens on a fresh three-repetition run.

### Limitations

- One application repository, one pinned commit, one model, and one reasoning setting.
- 1 repetition(s) describe this controlled run but are not a population-wide estimate.
- Provider prompt caching can change total-input composition; interpret cached and non-cached input separately.
- This published one-pass preflight is directional and cannot replace a fresh three-repetition result for replicated claims.
