# Token Atlas Benchmarks

## Adaptive attribution benchmark — all — one-pass preflight

This benchmark separates generic source discovery, the adaptive local-probe policy, and PKF knowledge on Tether Brain at commit `5c458df3c737f0af2a2193186d98af90c45163f0`. The repository was private when measured; no source, credentials, local paths, or raw traces are published.

Publication class: **one-pass preflight**<br>
Replicated: **no**<br>
Status: **failed**<br>
Quality: **failed**<br>
Performance: **preliminary_advisory_missed**<br>
Recorded: `2026-07-19T19:23:58+00:00`<br>
Model: `gpt-5.6-luna` at `high` reasoning<br>
Repetitions: `1` (`13` calls)

Raw sanitized result: [`report.json`](report.json)

Artifact manifest: [`manifest.json`](../manifest.json)

### Method

`source_only` has no PKF or probe policy, `probe_only` isolates the bounded local-probe policy without PKF, and `pkf` installs adaptive retrieval and semantic closeout but may bypass PKF for an individual task. Token counts come from Codex JSONL; total and non-cached input are reported separately and are not pricing estimates. Tool input and output are parsed separately. Explicit read targets are distinct from unverified path mentions.

### Single-pass usage by task

| Task | Phase | Arm | Retrieval | Input | Non-cached | Output | Duration ms | Tools | Routed docs | Correct |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| boards_add_task | retrieval | `pkf` | `bypassed:1` | 59900 | 20732 | 1016 | 27445 | 3 | 0 | 100% |
| boards_add_task | retrieval | `probe_only` | `not_applicable:1` | 72017 | 32849 | 1112 | 30984 | 3 | 0 | 100% |
| boards_add_task | retrieval | `source_only` | `not_applicable:1` | 72480 | 24096 | 808 | 27840 | 3 | 0 | 100% |
| favorite_visibility_after_change | post_mutation | `pkf` | `bypassed:1` | 85599 | 29023 | 1230 | 33710 | 3 | 0 | 100% |
| favorite_visibility_after_change | post_mutation | `probe_only` | `not_applicable:1` | 75641 | 25209 | 1546 | 37031 | 3 | 0 | 100% |
| favorite_visibility_mutation | mutation | `pkf` | `not_applicable:1` | 1182611 | 62867 | 9398 | 229938 | 39 | 2 | n/a |
| favorite_visibility_mutation | mutation | `probe_only` | `not_applicable:1` | 540626 | 39378 | 5602 | 143816 | 16 | 0 | n/a |
| initialize | setup | `pkf` | `not_applicable:1` | 3389863 | 132263 | 33753 | 718301 | 90 | 0 | n/a |
| isolated_closeout | closeout | `pkf` | `not_applicable:1` | 355078 | 34054 | 6729 | 156456 | 17 | 2 | n/a |
| isolated_closeout | closeout | `probe_only` | `not_applicable:1` | 11305 | 2345 | 69 | 10233 | 0 | 0 | n/a |
| note_task_links | retrieval | `pkf` | `activated:1` | 236272 | 42224 | 4454 | 100146 | 25 | 3 | 100% |
| note_task_links | retrieval | `probe_only` | `not_applicable:1` | 313816 | 67800 | 2835 | 69607 | 7 | 0 | 100% |
| note_task_links | retrieval | `source_only` | `not_applicable:1` | 426064 | 69456 | 3501 | 88859 | 11 | 0 | 100% |

### PKF knowledge savings

Only paired tasks whose PKF arm actually activated retrieval contribute to this figure; bypassed tasks are excluded.

Activated pairs: `1`; median input saving: `77544`; median non-cached input saving: `25576`.

### Bypassed environment deltas

- `boards_add_task` (1 pair(s)): input -12117, non-cached -12117.
- `favorite_visibility_after_change` (1 pair(s)): input +9958, non-cached +3814.

### Attribution deltas

- `boards_add_task` probe_vs_pkf: input -12117, non-cached -12117, duration -3539 ms.
- `boards_add_task` source_vs_probe: input -463, non-cached +8753, duration +3144 ms.
- `favorite_visibility_after_change` probe_vs_pkf: input +9958, non-cached +3814, duration -3321 ms.
- `favorite_visibility_mutation` probe_vs_pkf: input +641985, non-cached +23489, duration +86122 ms.
- `isolated_closeout` probe_vs_pkf: input +343773, non-cached +31709, duration +146223 ms.
- `note_task_links` probe_vs_pkf: input -77544, non-cached -25576, duration +30539 ms.
- `note_task_links` source_vs_probe: input -112248, non-cached -1656, duration -19252 ms.

### Performance advisories

Evidence strength: **directional**.

- local_input_tokens_overhead: met (`-16.83`, target <= 5%).
- local_non_cached_input_tokens_overhead: met (`-36.89`, target <= 5%).
- local_duration_ms_overhead: met (`-11.42`, target <= 5%).
- cross_capability_non_cached_input_tokens_delta: met (`-25576.00`, target < 0).
- cross_capability_tool_call_count_delta: missed (`18.00`, target < 0).
- initialization_non_cached_input_tokens_delta: missed (`32543.00`, target < 0 versus runtime-v3 one-pass).
- initialization_duration_ms_delta: missed (`201357.00`, target < 0 versus runtime-v3 one-pass).
- mapped_closeout_tool_calls: missed (`17.00`, target <= 6).
- mapped_closeout_routed_documents: met (`2.00`, target <= 2).
- operational_input_tokens_overhead: missed (`89.41`, target <= 5%).
- operational_non_cached_input_tokens_overhead: missed (`12.72`, target <= 5%).
- operational_duration_ms_overhead: missed (`87.78`, target <= 5%).

### Limitations

- One application repository, one pinned commit, one model, and one reasoning setting.
- 1 repetition(s) describe this controlled run but are not a population-wide estimate.
- Provider prompt caching can change total-input composition; interpret cached and non-cached input separately.
- This published one-pass preflight is directional and cannot replace a fresh three-repetition result for replicated claims.

### Evaluation errors

- repetition 1 pkf/favorite_visibility_mutation: mapped mutation closeout loaded Token Atlas workflow instructions
- repetition 1 pkf/favorite_visibility_mutation: mapped mutation closeout used fallback discovery
- repetition 1 pkf/isolated_closeout: mapped isolated closeout loaded Token Atlas workflow instructions
- repetition 1 pkf/isolated_closeout: mapped isolated closeout used fallback discovery
