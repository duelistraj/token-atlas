# Conformance Fixtures

These directories define deterministic conformance contracts for Token Atlas.

Fixtures are intentionally isolated from this repository's own `.ai/` state. A benchmark runner or agent must copy each fixture into a temporary workspace before running the selected PKF workflows.

Each fixture contains:

- `fixture.yaml`: machine-readable expectations for future deterministic scoring.
- `repo/`: the miniature repository to copy into an isolated workspace.
- `changes.patch`: optional Git patch for fixtures that depend on changed or deleted paths.

| Fixture | Purpose |
|---------|---------|
| `missing-runtime` | Startup recovery and initialization gate. |
| `simple-api` | API extraction and route simulation. |
| `schema-change` | Schema/model extraction and changed-path routing. |
| `ui-change` | UI behavior extraction and changed-path routing. |
| `deleted-evidence` | Stale source evidence detection. |
| `broad-loads` | Detection of unrelated automatic loads. |
| `functional-route-irredundancy` | Functional boards/notes routes prove one-leaf sufficiency, authoritative ownership, shared-route deduplication, and multi-leaf composition. |
| `exports` | Retrieval export mode and JSONL validation. |
| `functional-boundaries-init` | Generic flat capability discovery without technical-layer or placeholder modules. |
| `functional-boundaries-migration` | Automatic migration from an unambiguously coarse module. |
