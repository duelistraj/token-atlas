# Token Atlas Benchmarks

## PKF vs no PKF lifecycle benchmark

This benchmark compares Token Atlas with a source-only baseline on the real Tether Brain repository at commit `5c458df3c737f0af2a2193186d98af90c45163f0`. The repository was private when measured; no source, credentials, raw traces, or local paths are published here. The pinned commit can be independently checked once the project is public.

Status: **failed**<br>
Recorded: `2026-07-19T14:23:20+00:00`<br>
Model: `gpt-5.6-luna` at `high` reasoning<br>
Repetitions: `1` (`9` calls)

Raw sanitized result: [`pkf-vs-no-pkf-gpt-5.6-luna-high-runtime-v3-1pass-2026-07-19.json`](.agents/skills/token-atlas/benchmarks/results/pkf-vs-no-pkf-gpt-5.6-luna-high-runtime-v3-1pass-2026-07-19.json)

### Method

Each repetition exports the pinned Git tree into disposable workspaces. Both arms start without `.ai/` or Token Atlas instructions. The PKF arm installs the public skill under test, initializes and validates its knowledge base, then both arms run the same two read-only questions, one focused mutation, and one post-mutation question. Arm order alternates by repetition.

Token counts come from Codex JSONL. Total input includes cached input; non-cached input is reported separately. These figures are not pricing estimates.

### Median usage by task

| Task | Arm | Input | Cached | Non-cached | Output | Correct | Duration (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Boards Add task lookup | `no_pkf` | 171932 | 126720 | 45212 | 1389 | 100% | 38175 |
| Boards Add task lookup | `pkf` | 55182 | 28160 | 27022 | 1008 | 100% | 27862 |
| Post-mutation lookup | `no_pkf` | 102574 | 70656 | 31918 | 1651 | 100% | 42262 |
| Post-mutation lookup | `pkf` | 106124 | 77568 | 28556 | 1890 | 100% | 53331 |
| Favorite visibility mutation | `no_pkf` | 1076703 | 1015808 | 60895 | 7971 | n/a | 194888 |
| Favorite visibility mutation | `pkf` | 660175 | 615680 | 44495 | 8842 | n/a | 216813 |
| Initialize PKF | `pkf` | 1735304 | 1635584 | 99720 | 24190 | n/a | 516944 |
| Note/task link lookup | `no_pkf` | 637520 | 557824 | 79696 | 3974 | 100% | 94244 |
| Note/task link lookup | `pkf` | 283310 | 219136 | 64174 | 3016 | 100% | 76690 |

### Median workflow churn by task

Path counts are trace mentions, not confirmed reads. Tool calls and tool-output size are retained to explain cached-context replay.

| Task | Arm | Tool calls | Read/search commands | Tool output chars | Mentioned paths | Mentioned `.ai` paths |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Boards Add task lookup | `no_pkf` | 5 | 5 | 211144 | 74 | 0 |
| Boards Add task lookup | `pkf` | 2 | 2 | 54720 | 12 | 0 |
| Post-mutation lookup | `no_pkf` | 4 | 4 | 78363 | 170 | 0 |
| Post-mutation lookup | `pkf` | 5 | 5 | 49485 | 30 | 4 |
| Favorite visibility mutation | `no_pkf` | 29 | 17 | 155277 | 48 | 0 |
| Favorite visibility mutation | `pkf` | 21 | 12 | 78437 | 58 | 19 |
| Initialize PKF | `pkf` | 25 | 16 | 307225 | 181 | 0 |
| Note/task link lookup | `no_pkf` | 13 | 13 | 294887 | 170 | 0 |
| Note/task link lookup | `pkf` | 8 | 8 | 212296 | 76 | 20 |

### Result

Median complete lifecycle input: **1988729** without PKF and **2840095** with PKF.<br>
Median complete lifecycle non-cached input: **217721** without PKF and **263967** with PKF.<br>
Median paired read-only input saving: **116750 tokens**.<br>
Median paired read-only non-cached input saving: **15522 tokens**.<br>
Break-even including initialization and the measured mutation premium: **15** read-only tasks by total input and **7** by non-cached input.

On this measured workload, PKF is token-beneficial only when the number of comparable read-only tasks exceeds the reported break-even; smaller workloads retain the setup and maintenance overhead.

The cross-capability note/task-link lookup was the clear PKF win: median input fell from **637520** to **283310** tokens, while non-cached input fell from **79696** to **64174**. Focused-mutation input also fell from **1076703** to **660175** tokens; non-cached input fell from **60895** to **44495**.

Every PKF initialization passed strict validation. Both mutation arms passed the focused test, the PKF mutation emitted closeout and passed strict PKF validation, and every post-mutation answer was correct. The recorded failures came from the original mutation scorer combining expected-path checks with a test-title-dependent regex. That scorer cannot distinguish a path failure from a renamed test title; it was corrected after this measurement without rerunning or altering the raw result.

The Boards structured-answer gate passed in every recorded run.

### Preliminary comparison

- The local Boards task bypassed PKF completely: zero `.ai` path mentions, two tool calls instead of five, 67.9% less total input, and 40.2% less non-cached input than the source-only arm.
- The cross-capability note/task-link task activated PKF and used 20 `.ai` path mentions, but reduced total input by 55.6%, non-cached input by 19.5%, and tool calls from 13 to 8.
- The post-mutation read-only PKF arm used 3.5% more total input—inside the proposed 5% ceiling—while using 10.5% less non-cached input.
- PKF initialization used 46.6% less total input, 36.4% less non-cached input, and 30.8% less time than the previous three-pass median.
- Complete-lifecycle PKF overhead fell from the previous median of 274.0% to 42.8% by total input, and from 78.6% to 21.2% by non-cached input. Estimated break-even improved from unavailable/25 tasks to 15/7 tasks respectively.
- These comparisons are directional only: the current result has one repetition, while the previous result used three.

### Limitations

- One application repository, one pinned commit, one model, and one reasoning setting.
- 1 repetition(s) describe this controlled run but are not a population-wide estimate.
- Provider prompt caching can change total-input composition, so cached and non-cached input must be interpreted separately.
- The target was private when measured; external reproduction becomes possible when that exact commit is published.

### Evaluation errors

- repetition 1 no_pkf/favorite_visibility_mutation: mutation did not make the expected source/test change
- repetition 1 pkf/favorite_visibility_mutation: mutation did not make the expected source/test change
