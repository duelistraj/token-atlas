# Token Atlas Benchmarks

## Adaptive attribution benchmark — all — one-pass preflight

This benchmark separates generic source discovery, the adaptive local-probe policy, and PKF knowledge on Tether Brain at commit `5c458df3c737f0af2a2193186d98af90c45163f0`. The repository was private when measured; no source, credentials, local paths, or raw traces are published.

Publication class: **one-pass preflight**<br>
Replicated: **no**<br>
Status: **failed**<br>
Quality: **failed**<br>
Performance: **preliminary_advisory_missed**<br>
Recorded: `2026-07-20T07:06:30+00:00`<br>
Model: `gpt-5.6-luna` at `high` reasoning<br>
Repetitions: `1` (`13` calls)

Raw sanitized result: [`report.json`](report.json)

Artifact manifest: [`manifest.json`](../manifest.json)

### Method

`source_only` has no PKF or probe policy, `probe_only` isolates the bounded local-probe policy without PKF, and `pkf` installs adaptive retrieval and semantic closeout but may bypass PKF for an individual task. Token counts come from Codex JSONL; total and non-cached input are reported separately and are not pricing estimates. Tool input and output are parsed separately. Explicit read targets are distinct from unverified path mentions.

### Single-pass usage by task

| Task | Phase | Arm | Retrieval | Initial route | Input | Non-cached | Output | Duration ms | Tools | Routed docs | Correct |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| boards_add_task | retrieval | `pkf` | `bypassed:1` | `n/a` | 85677 | 25261 | 994 | 29193 | 4 | 0 | 100% |
| boards_add_task | retrieval | `probe_only` | `not_applicable:1` | `n/a` | 89485 | 18061 | 1153 | 32430 | 4 | 0 | 100% |
| boards_add_task | retrieval | `source_only` | `not_applicable:1` | `n/a` | 96675 | 38051 | 1201 | 35430 | 4 | 0 | 100% |
| favorite_visibility_after_change | post_mutation | `pkf` | `bypassed:1` | `n/a` | 77268 | 25812 | 1313 | 34733 | 3 | 0 | 100% |
| favorite_visibility_after_change | post_mutation | `probe_only` | `not_applicable:1` | `n/a` | 83516 | 26940 | 1652 | 41395 | 3 | 0 | 100% |
| favorite_visibility_mutation | mutation | `pkf` | `not_applicable:1` | `mapped:1` | 402245 | 49477 | 4928 | 137018 | 17 | 1 | n/a |
| favorite_visibility_mutation | mutation | `probe_only` | `not_applicable:1` | `n/a` | 541611 | 39595 | 6253 | 164763 | 18 | 0 | n/a |
| initialize | setup | `pkf` | `not_applicable:1` | `mapped:1` | 6653125 | 191685 | 55541 | 1166712 | 60 | 0 | n/a |
| isolated_closeout | closeout | `pkf` | `not_applicable:1` | `mapped:1` | 267946 | 34986 | 4344 | 106783 | 12 | 1 | n/a |
| isolated_closeout | closeout | `probe_only` | `not_applicable:1` | `n/a` | 11278 | 2318 | 60 | 12247 | 0 | 0 | n/a |
| note_task_links | retrieval | `pkf` | `activated:1` | `n/a` | 332397 | 62573 | 4296 | 106314 | 10 | 8 | 100% |
| note_task_links | retrieval | `probe_only` | `not_applicable:1` | `n/a` | 161162 | 43658 | 2946 | 69025 | 5 | 0 | 100% |
| note_task_links | retrieval | `source_only` | `not_applicable:1` | `n/a` | 469529 | 84761 | 2980 | 82920 | 10 | 0 | 100% |

### Mutation phase attribution

Implementation and isolated closeout are separate calls; the integrated row is the directly observed combined mutation. The composed row is their explicit sum.

| Evidence | Input | Non-cached | Output | Duration ms | Tools |
| --- | ---: | ---: | ---: | ---: | ---: |
| implementation | 541611 | 39595 | 6253 | 164763 | 18 |
| closeout | 267946 | 34986 | 4344 | 106783 | 12 |
| closeout_control | 11278 | 2318 | 60 | 12247 | 0 |
| closeout_incremental | 256668 | 32668 | 4284 | 94536 | 12 |
| composed_probe_plus_closeout | 809557 | 74581 | 10597 | 271546 | 30 |
| integrated_observed | 402245 | 49477 | 4928 | 137018 | 17 |

Integrated mutation tool segments:

- `implementation`: 12 tools, 7 reads/searches, fallback rate 100%.
- `routing`: 1 tools, 0 reads/searches, fallback rate 0%.
- `closeout`: 4 tools, 2 reads/searches, fallback rate 0%.

### PKF knowledge savings

Only paired tasks whose PKF arm actually activated retrieval contribute to this figure; bypassed tasks are excluded.

Activated pairs: `1`; median input saving: `-171235`; median non-cached input saving: `-18915`.

### Bypassed environment deltas

- `boards_add_task` (1 pair(s)): input -3808, non-cached +7200.
- `favorite_visibility_after_change` (1 pair(s)): input -6248, non-cached -1128.

### Attribution deltas

- `boards_add_task` probe_vs_pkf: input -3808, non-cached +7200, duration -3237 ms.
- `boards_add_task` source_vs_probe: input -7190, non-cached -19990, duration -3000 ms.
- `favorite_visibility_after_change` probe_vs_pkf: input -6248, non-cached -1128, duration -6662 ms.
- `favorite_visibility_mutation` probe_vs_pkf: input -139366, non-cached +9882, duration -27745 ms.
- `isolated_closeout` probe_vs_pkf: input +256668, non-cached +32668, duration +94536 ms.
- `note_task_links` probe_vs_pkf: input +171235, non-cached +18915, duration +37289 ms.
- `note_task_links` source_vs_probe: input -308367, non-cached -41103, duration -13895 ms.

### Performance advisories

Evidence strength: **directional**.

- local_input_tokens_overhead: met (`-4.26`, target <= 5%).
- local_non_cached_input_tokens_overhead: missed (`39.86`, target <= 5%).
- local_duration_ms_overhead: met (`-9.98`, target <= 5%).
- cross_capability_non_cached_input_tokens_delta: missed (`18915.00`, target < 0).
- cross_capability_tool_call_count_delta: missed (`5.00`, target < 0).
- initialization_non_cached_input_tokens_delta: missed (`91965.00`, target < 0 versus runtime-v3 one-pass).
- initialization_duration_ms_delta: missed (`649768.00`, target < 0 versus runtime-v3 one-pass).
- mapped_closeout_tool_calls: missed (`12.00`, target <= 6).
- mapped_closeout_routed_documents: met (`1.00`, target <= 2).
- composed_mutation_input_tokens_overhead: missed (`49.47`, target <= 5%).
- composed_mutation_non_cached_input_tokens_overhead: missed (`88.36`, target <= 5%).
- composed_mutation_duration_ms_overhead: missed (`64.81`, target <= 5%).
- operational_input_tokens_overhead: met (`2.49`, target <= 5%).
- operational_non_cached_input_tokens_overhead: missed (`27.19`, target <= 5%).
- operational_duration_ms_overhead: met (`-0.12`, target <= 5%).

### Limitations

- One application repository, one pinned commit, one model, and one reasoning setting.
- 1 repetition(s) describe this controlled run but are not a population-wide estimate.
- Provider prompt caching can change total-input composition; interpret cached and non-cached input separately.
- This published one-pass preflight is directional and cannot replace a fresh three-repetition result for replicated claims.

### Evaluation errors

- repetition 1 pkf/favorite_visibility_mutation: mutation did not emit PKF closeout status
- repetition 1 pkf/favorite_visibility_mutation: mapped mutation closeout read paths outside returned leaves
- repetition 1 pkf/isolated_closeout: isolated closeout loaded PKF or Token Atlas before routing
- repetition 1 pkf/isolated_closeout: isolated closeout did not emit status
- repetition 1 pkf/isolated_closeout: mapped isolated closeout read paths outside returned leaves
- repetition 1 pkf/isolated_closeout: mapped isolated closeout must run exactly one validation
