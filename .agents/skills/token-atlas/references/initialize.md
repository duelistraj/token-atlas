# Initialize PKF Runtime

## Purpose

Create a complete target-repository `.ai/` runtime when `.ai/PKF.md` is missing.
Initialization is a one-time installation lifecycle: derive repository knowledge,
validate it end to end, and leave no deferred or placeholder knowledge.

Do not run Token Atlas against its own maintenance repository.

## Fresh Initialization

For a fresh repository, use the bundled dependency-free helper:

```text
python <skill-root>/scripts/pkf_scaffold.py inspect --path .
python <skill-root>/scripts/pkf_scaffold.py create --path .
```

`inspect` writes `.pkf-init.json` outside the runtime and prints only a compact summary. It
never emits a full file inventory: each pass includes at most 40 candidate
directories and three representative paths per candidate. When
`inspection.truncated` is true, repeat inspection with targeted `--root`
values before finalizing capabilities.

Review the schema-2 specification before `create`. Populate `capabilities` with
flat repository-derived IDs, symbol-scoped ownership, and only applicable
evidence-backed leaves:

```json
{
  "schema_version": 2,
  "project": {"name": "<project>"},
  "technologies": [],
  "roots": {"source": [], "test": [], "config": [], "docs": []},
  "commands": {},
  "capabilities": [
    {
      "id": "<module>",
      "title": "<capability>",
      "ownership": {
        "<repository-relative-path>": ["<owned-symbol>"]
      },
      "leaves": [
        {
          "file": "<api.md|schema.md|business_rules.md|ui.md>",
          "title": "<title>",
          "description": "<description>",
          "resource": "<resolving-source-path>",
          "source_symbols": {"<path>": ["<symbol>"]},
          "body": "<complete source-backed Markdown with Edit Map>"
        }
      ]
    }
  ]
}
```

The helper rejects path traversal, conflicting path-symbol ownership, unresolved
symbols, nested or invalid module IDs, incomplete leaves, and overwriting an
existing runtime. On success it:

- Creates complete runtime documents and one flat module per reviewed capability.
- Embeds the adaptive retrieval and closeout protocols from packaged templates.
- Augments `AGENTS.md` inside managed markers without replacing existing
  instructions.
- Installs dependency-free route and validation helpers under `.ai/tools/` so
  routine closeout never needs to locate the installed skill.
- Records machine-readable symbol-scoped `pkf.ownership` on each module index.
- Emits only applicable leaves and marks every emitted leaf complete.
- Runs compact deterministic validation.
- Removes `.pkf-init.json` unless `--keep-spec` is set.

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

## Complete Initialization Extraction

After scaffolding:

1. Populate only verified repository commands, shared architecture, dependencies,
   routing, and public behavior facts. Treat bundled helper scripts as opaque
   executables and never read their source during normal initialization.
2. Materialize the source-backed leaves needed to represent every verified public behavior, important mutation entrypoint, and contract connecting capabilities.
   Separate leaves when ownership, evidence sets, or retrieval intents differ; do not impose a fixed per-capability leaf count.
3. Record every verified cross-capability contract as a keyed entry under `pkf.routes` in `.ai/knowledge/INDEX.md`.
   Each atomic route represents one narrow intent and contains `intent`, a non-empty `triggers` list, exact `modules`, requirement IDs, exact complete leaf paths in `loads`, and a `load_coverage` mapping.
   Inspect existing root-route metadata before assigning requirements. Use globally descriptive, non-empty kebab-case IDs and reuse an existing authoritative leaf whenever an ID already exists.
   Every requirement ID must resolve to exactly one authoritative leaf across the root route catalog; one leaf may own several related requirements, and a requirement that needs multiple owners must be split into narrower IDs.
   Every requirement must be covered and every route-declared leaf must contribute at least one requirement.
   A broad task composes matching routes and deduplicates repeated requirement IDs and leaf references.
   Avoid semantically broad, vague, or duplicate requirements, but treat that judgment as model-reviewed authoring quality rather than a deterministic validator capability.

   ```yaml
   requirements:
     - <task-requirement-id>
   loads:
     - .ai/knowledge/<module>/<leaf>.md
   load_coverage:
     ".ai/knowledge/<module>/<leaf>.md": [<task-requirement-id>]
   ```

4. Prefer the complete route combination with the fewest unique leaves.
   When alternatives use the same leaf count, prefer the lower estimated token cost, then the narrower source evidence.
   Sufficient, deduplicated, and irredundant context is validated. Minimum-sufficient context remains the retrieval objective but is not mathematically proven.
   Record leaf counts and estimated route-content tokens as telemetry rather than treating them as an allowance or ceiling.
5. Omit nonapplicable knowledge leaves. Do not emit empty, pending, unknown, or
   placeholder leaves merely to complete a fixed document set.
6. Every emitted leaf must map repository-relative paths to exact symbols
   in `source_symbols` and include a targeted Edit Map. Public-behavior UI and
   business-rule leaves must inspect capability-local state/behavior helpers and
   focused tests; every source or test cited by the Edit Map must be included in
   `source_symbols`.
7. Inspect the complete relevant public behavior, mutation entrypoint, ownership,
   and cross-capability surface before sealing. Do not claim facts that source
   evidence cannot verify.

## Validation And Optional Work

The scaffold helper performs mechanical validation. After extraction, run strict
validation, repair every finding, and revalidate until the complete runtime
passes. A failed draft remains resumable and must not be treated as installed.

Run affected validation again only if a subsequent optimization changes PKF
files. In the default core profile:

- Run `simulation=changed` over every newly materialized or changed route. Use
  `required` or `all` only when the caller asks for broader coverage.
- Optimize only when simulation or validation reports a broad route, duplicated
  authority, fallback, or token-budget defect, then revalidate only the affected
  slice when optimization changes PKF files.
- Generate retrieval exports only when enabled.

## Runtime Contract

The generated runtime sets:

```yaml
pkf:
  runtime_version: 4
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
work, and knowledge-impact-gates closeout. Routine mapped closeout uses the
exact repository-local commands embedded by the scaffold.

## Success Criteria

- The reviewed capability map is complete, flat, and source-backed.
- The deterministic scaffold validates and preserves existing instructions.
- Shared routing, public behavior, and source-backed cross-capability contracts
  are verified.
- Startup, architecture, root-index, and module-index `pkf.related` values are empty; every atomic route has complete requirement coverage and no redundant leaves.
- Broader tasks compose routes without duplicate or non-contributing leaf reads.
- Public-behavior implementation helpers and focused tests route directly to
  their materialized leaves.
- Changed-route simulation covers every newly materialized route.
- No generated Markdown contains TODO, pending materialization, unresolved
  metadata, or placeholder knowledge.
- One final post-extraction validation completes.
- No application source or test file is modified.
