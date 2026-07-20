# Token Atlas Benchmarks

## Adaptive attribution benchmark — all — one-pass preflight

This benchmark separates generic source discovery, the adaptive local-probe policy, and PKF knowledge on Tether Brain at commit `5c458df3c737f0af2a2193186d98af90c45163f0`. The repository was private when measured; no source, credentials, local paths, or raw traces are published.

Publication class: **one-pass preflight**<br>
Replicated: **no**<br>
Status: **failed**<br>
Quality: **failed**<br>
Performance: **preliminary**<br>
Recorded: `2026-07-20T12:55:51+00:00`<br>
Model: `gpt-5.6-luna` at `high` reasoning<br>
Repetitions: `1` (`13` calls)

Raw sanitized result: [`report.json`](report.json)

Artifact manifest: [`manifest.json`](../manifest.json)

### Method

`source_only` has no PKF or probe policy, `probe_only` isolates the bounded local-probe policy without PKF, and `pkf` installs adaptive retrieval and semantic closeout but may bypass PKF for an individual task. Token counts come from Codex JSONL; total and non-cached input are reported separately and are not pricing estimates. Tool input and output are parsed separately. Explicit read targets are distinct from unverified path mentions.

### Single-pass usage by task

| Task | Phase | Arm | Retrieval | Initial route | Input | Non-cached | Output | Duration ms | Tools | Routed docs | Correct |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| boards_add_task | retrieval | `pkf` | `bypassed:1` | `n/a` | 48427 | 25387 | 1057 | 34049 | 2 | 0 | 100% |
| boards_add_task | retrieval | `probe_only` | `not_applicable:1` | `n/a` | 69820 | 22460 | 983 | 31034 | 3 | 0 | 100% |
| boards_add_task | retrieval | `source_only` | `not_applicable:1` | `n/a` | 83719 | 33287 | 1127 | 41554 | 3 | 0 | 100% |
| favorite_visibility_after_change | post_mutation | `pkf` | `bypassed:1` | `n/a` | 129980 | 28860 | 1849 | 51471 | 4 | 0 | 100% |
| favorite_visibility_after_change | post_mutation | `probe_only` | `not_applicable:1` | `n/a` | 50542 | 22382 | 1030 | 57331 | 2 | 0 | 100% |
| favorite_visibility_mutation | mutation | `pkf` | `not_applicable:1` | `mapped:1` | 554539 | 37931 | 6774 | 171487 | 20 | 1 | n/a |
| favorite_visibility_mutation | mutation | `probe_only` | `not_applicable:1` | `n/a` | 396895 | 32351 | 5001 | 126053 | 12 | 0 | n/a |
| initialize | setup | `pkf` | `not_applicable:1` | `n/a` | 4661416 | 160424 | 55160 | 1184882 | 56 | 10 | n/a |
| isolated_closeout | closeout | `pkf` | `not_applicable:1` | `mapped:1` | 102078 | 11710 | 1829 | 57073 | 6 | 1 | n/a |
| isolated_closeout | closeout | `probe_only` | `not_applicable:1` | `n/a` | 11005 | 6141 | 66 | 21940 | 0 | 0 | n/a |
| note_task_links | retrieval | `pkf` | `activated:1` | `n/a` | 366529 | 69569 | 5649 | 137529 | 12 | 3 | 100% |
| note_task_links | retrieval | `probe_only` | `not_applicable:1` | `n/a` | 344610 | 61986 | 3204 | 89239 | 8 | 0 | 100% |
| note_task_links | retrieval | `source_only` | `not_applicable:1` | `n/a` | 471838 | 79902 | 3001 | 84280 | 8 | 0 | 100% |

### Routing and validation evidence

- Initialization: 1 explicit validation(s); opaque helper source reads: .ai/tools; fallback-style broad scan invocations: 1.
- Cross routes `authenticated-note-task-linking` (valid marker, 3 reported unique leaves, coverage=complete, irredundancy=irredundant, requirements=3/3, conflicts=none, uncovered=none, unresolved=none, estimated route-content tokens=2867 (approximate)): declared .ai/knowledge/boards-tasks/api.md, .ai/knowledge/platform-contracts/api.md, .ai/knowledge/workspace-notes/api.md; redundant none; expected .ai/knowledge/boards-tasks/api.md, .ai/knowledge/platform-contracts/api.md, .ai/knowledge/workspace-notes/api.md; observed .ai/knowledge/boards-tasks/api.md, .ai/knowledge/platform-contracts/api.md, .ai/knowledge/workspace-notes/api.md; missing none; unexpected none.
- `favorite_visibility_mutation` closeout: 1 validation(s); unexpected reads frontend/node_modules, frontend/src/notes/noteSectionState.test.ts, frontend/src/notes/noteSectionState.ts, frontend/vite.config.ts.
- `isolated_closeout` closeout: 1 validation(s); unexpected reads frontend/src/notes/noteSectionState.test.ts, frontend/src/notes/noteSectionState.ts.

### Mutation phase attribution

Implementation and isolated closeout are separate calls; the integrated row is the directly observed combined mutation. The composed row is their explicit sum.

| Evidence | Input | Non-cached | Output | Duration ms | Tools |
| --- | ---: | ---: | ---: | ---: | ---: |
| implementation | 396895 | 32351 | 5001 | 126053 | 12 |
| closeout | 102078 | 11710 | 1829 | 57073 | 6 |
| closeout_control | 11005 | 6141 | 66 | 21940 | 0 |
| closeout_incremental | 91073 | 5569 | 1763 | 35133 | 6 |
| composed_probe_plus_closeout | 498973 | 44061 | 6830 | 183126 | 18 |
| integrated_observed | 554539 | 37931 | 6774 | 171487 | 20 |

Integrated mutation tool segments:

- `implementation`: 6 tools, 5 reads/searches, fallback rate 0%.
- `routing`: 1 tools, 0 reads/searches, fallback rate 0%.
- `closeout`: 13 tools, 5 reads/searches, fallback rate 100%.

### PKF knowledge savings

Only paired tasks whose PKF arm actually activated retrieval contribute to this figure; bypassed tasks are excluded.

Activated pairs: `1`; median input saving: `-21919`; median non-cached input saving: `-7583`.
Estimated break-even activated tasks: input `not reached`, non-cached input `not reached`.

### Bypassed environment deltas

- `boards_add_task` (1 pair(s)): input -21393, non-cached +2927.
- `favorite_visibility_after_change` (1 pair(s)): input +79438, non-cached +6478.

### Attribution deltas

- `boards_add_task` probe_vs_pkf: input -21393, non-cached +2927, duration +3015 ms.
- `boards_add_task` source_vs_probe: input -13899, non-cached -10827, duration -10520 ms.
- `favorite_visibility_after_change` probe_vs_pkf: input +79438, non-cached +6478, duration -5860 ms.
- `favorite_visibility_mutation` probe_vs_pkf: input +157644, non-cached +5580, duration +45434 ms.
- `isolated_closeout` probe_vs_pkf: input +91073, non-cached +5569, duration +35133 ms.
- `note_task_links` probe_vs_pkf: input +21919, non-cached +7583, duration +48290 ms.
- `note_task_links` source_vs_probe: input -127228, non-cached -17916, duration +4959 ms.

### Phase performance scorecard

Evidence strength: **directional**. These targets are advisory and do not change the quality verdict.

- `local_bypass` — **directional_missed**: PKF-inactive local work should remain near probe-only cost.
  - boards_add_task_non_cached_input_tokens_overhead: missed (`13.03`, target <= 5%).
  - boards_add_task_duration_ms_overhead: missed (`9.72`, target <= 5%).
  - boards_add_task_tool_call_count_overhead: met (`-33.33`, target <= 5%).
  - favorite_visibility_after_change_non_cached_input_tokens_overhead: missed (`28.94`, target <= 5%).
  - favorite_visibility_after_change_duration_ms_overhead: met (`-10.22`, target <= 5%).
  - favorite_visibility_after_change_tool_call_count_overhead: missed (`100.00`, target <= 5%).

- `cross_retrieval` — **directional_missed**: Activated PKF should replace broad cross-capability discovery.
  - cross_capability_non_cached_input_tokens_delta: missed (`7583.00`, target < 0).
  - cross_capability_tool_call_delta: missed (`4.00`, target < 0).

- `mutation_implementation` — **measured**: Implementation stays source-first; closeout cost is attributed separately.

- `closeout` — **directional_met**: Required knowledge maintenance is measured as a maintenance premium.
  - mapped_closeout_tool_calls: met (`6.00`, target <= 6).

- `initialization` — **measured**: One-time setup is reported for coverage and runaway detection, not historical cost parity.

- `amortization` — **measured**: Break-even estimates relate setup and maintenance premiums to activated retrieval savings.

### Limitations

- One application repository, one pinned commit, one model, and one reasoning setting.
- 1 repetition(s) describe this controlled run but are not a population-wide estimate.
- Provider prompt caching can change total-input composition; interpret cached and non-cached input separately.
- This published one-pass preflight is directional and cannot replace a fresh three-repetition result for replicated claims.

### Evaluation errors

- repetition 1 pkf/initialize: initialized PKF failed strict validation
- repetition 1 pkf/initialize: initialization read opaque helper source: .ai/tools
- repetition 1 pkf/note_task_links: configured cross-capability retrieval used fallback discovery
- repetition 1 pkf/favorite_visibility_mutation: PKF failed validation after mutation
- repetition 1 pkf/favorite_visibility_mutation: mapped mutation closeout used fallback discovery
- repetition 1 pkf/favorite_visibility_mutation: mapped mutation closeout read paths outside returned leaves: frontend/node_modules, frontend/src/notes/noteSectionState.test.ts, frontend/src/notes/noteSectionState.ts, frontend/vite.config.ts
- repetition 1 pkf/isolated_closeout: isolated closeout left PKF invalid
- repetition 1 pkf/isolated_closeout: mapped isolated closeout read paths outside returned leaves: frontend/src/notes/noteSectionState.test.ts, frontend/src/notes/noteSectionState.ts
