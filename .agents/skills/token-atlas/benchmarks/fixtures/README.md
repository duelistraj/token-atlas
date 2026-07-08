# Benchmark Fixtures

These directories define deterministic benchmark contracts for Token Atlas.

Fixtures are intentionally isolated from this repository's own `.ai/` state. A benchmark runner or agent must copy each fixture into a temporary workspace before running the selected PKF workflows.

| Fixture | Purpose |
|---------|---------|
| `missing-runtime` | Startup recovery and initialization gate. |
| `simple-api` | API extraction and route simulation. |
| `schema-change` | Schema/model extraction and changed-path routing. |
| `ui-change` | UI behavior extraction and changed-path routing. |
| `deleted-evidence` | Stale source evidence detection. |
| `broad-loads` | Detection of unrelated automatic loads. |
| `exports` | Retrieval export mode and JSONL validation. |

