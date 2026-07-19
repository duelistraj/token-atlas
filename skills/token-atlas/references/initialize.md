# Initialize PKF Runtime

## Purpose

Create a target repository's `.ai/` runtime and OKF knowledge skeleton when
`.ai/PKF.md` is missing. Use deterministic scaffolding for mechanical files;
keep capability boundaries and durable facts source-backed and model-reviewed.

Do not run Token Atlas against its own maintenance repository.

## Fresh Initialization

For a fresh repository, use the bundled dependency-free helper:

```text
python <skill-root>/scripts/pkf_scaffold.py inspect --path .
python <skill-root>/scripts/pkf_scaffold.py create --path .
```

`inspect` writes `.ai/.pkf-init.json` and prints only a compact summary. It
never emits a full file inventory: each pass includes at most 40 candidate
directories and three representative paths per candidate. When
`inspection.truncated` is true, repeat inspection with targeted `--root`
values before finalizing capabilities.

Review the specification before `create`. Populate `capabilities` with flat,
repository-derived capability IDs and their ownership roots:

```json
{
  "schema_version": 1,
  "project": {"name": "<project>"},
  "technologies": [],
  "roots": {"source": [], "test": [], "config": [], "docs": []},
  "commands": {},
  "capabilities": [
    {
      "id": "<module>",
      "title": "<capability>",
      "source_roots": ["<repository-relative-path>"]
    }
  ]
}
```

The helper rejects path traversal, duplicate ownership roots, nested or invalid
module IDs, and overwriting an existing runtime. On success it:

- Creates `PKF.md`, `MEMORY.md`, `ARCHITECTURE.md`, shared knowledge docs,
  and one flat module skeleton per reviewed capability.
- Embeds the adaptive retrieval and closeout protocols from packaged templates.
- Augments `AGENTS.md` inside managed markers without replacing existing
  instructions.
- Marks every implementation leaf pending.
- Runs compact deterministic validation.
- Removes `.ai/.pkf-init.json` unless `--keep-spec` is set.

Do not read or reproduce the template assets during normal initialization; the
helper owns that mechanical context.

## Existing Or Incomplete Runtime

The scaffold helper is fresh-only. When `.ai/` already contains runtime
content, preserve it and repair the smallest missing or invalid surface using
the validator findings and existing documents. Never overwrite an existing
`.ai/PKF.md`, bootstrap, manual note, or materialized leaf with a fresh
template.

## Module Boundary Contract

Module names and boundaries must be derived from the target repository. Keep
modules flat: each module is one directory directly under `.ai/knowledge/`.

Prefer an independently changeable functional capability over a technical or
deployment layer when the repository supports that distinction. Split a coarse
candidate only when it contains at least two independently routable
capabilities, and each resulting capability has either:

- A dedicated implementation subtree; or
- Evidence from at least two of these categories: interfaces, data structures,
  workflows, user-facing behavior, or tests.

When the repository exposes only one capability, or ownership is ambiguous,
retain the repository's existing structural boundary and report the ambiguity.
Do not create modules from placeholders, roadmap entries, empty scaffolding, or
names without implementation evidence. Use abstract placeholders such as
`<module>` and `<capability>` in reusable guidance; never prescribe target-repo
module names.

---

## Hybrid Extraction

After scaffolding:

1. Populate only verified repository commands, shared architecture, dependencies,
   routing, and public entry-point facts.
2. Materialize at most one primary public-entry leaf per capability by default.
   A second leaf is allowed only when the same public surface exposes a distinct
   contract required for correct routing.
3. Leave all other leaves with `pkf.materialization: pending`,
   `source_symbols: {}`, and the exact body marker
   `- TODO: Pending source extraction.`.
4. Every materialized leaf must map repository-relative paths to exact symbols
   in `source_symbols` and include a targeted Edit Map.
5. A complete leaf with no source-backed facts uses
   `pkf.materialization: complete` and
   `- TODO: No source-backed facts.`.

Pending leaves are materialized on demand when retrieval or semantic closeout
selects them. Never inspect unrelated implementation merely to complete the
initial knowledge inventory.

## Validation And Optional Work

The scaffold helper performs the initial mechanical validation. After hybrid
extraction, run one final validation at the selected strictness.

Run affected validation again only if a subsequent optimization changes PKF
files. In the default core profile:

- Optimize only when validation reports a broad route, duplicated authority, or
  token-budget defect.
- Skip initialization-time simulation unless it was explicitly requested as
  `required` or `all`.
- Generate retrieval exports only when enabled.

## Runtime Contract

The generated runtime sets:

```yaml
pkf:
  runtime_version: 3
  retrieval: adaptive
  closeout: adaptive
  loads:
    - .ai/MEMORY.md
    - .ai/ARCHITECTURE.md
    - .ai/knowledge/INDEX.md
  related: []
```

The neutral bootstrap applies the cheap local probe without loading PKF,
activates PKF for cross-capability, architecture, ownership, and repository-wide
work, and knowledge-impact-gates closeout.

## Success Criteria

- The reviewed capability map is complete, flat, and source-backed.
- The deterministic scaffold validates and preserves existing instructions.
- Shared routing and public entry-point facts are verified.
- Deferred leaves are explicitly pending.
- One final post-extraction validation completes.
- No application source or test file is modified.
