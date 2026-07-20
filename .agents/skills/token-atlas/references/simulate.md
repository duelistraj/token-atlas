# Retrieval Simulator

## Purpose

Simulate PKF retrieval for a natural-language task intent and optional changed file paths.

The simulator predicts the smallest OKF context set an AI agent should load before working. It validates routing quality without changing repository code or generated knowledge.

Do not modify any files.

Only report the simulated retrieval plan and defects.

---

## Inputs

Required:

- Natural-language task intent.

Optional:

- Changed file paths.
- Known module name.
- Known task type.
- Current token estimator, when one is available.
- Simulation mode: `off`, `changed`, `required`, or `all`.

---

## Outputs

Produce a retrieval simulation report with:

- Selected module or modules.
- Required OKF documents.
- Optional related documents.
- Estimated token cost.
- Estimator type: `exact` or `approximate`.
- Source and routing evidence.
- Warnings for ambiguous, broad, stale, or missing routing.
- Errors for unrelated automatic loads.

Use the token budget rules from `SKILL.md` and `validation.md`.

---

## Simulation Modes

Default mode is `changed`.

Use:

- `off`: do not run simulation unless explicitly requested by a user.
- `changed`: simulate only the current task intent or changed file paths.
- `required`: run the required representative scenarios.
- `all`: run changed-path, required, and broad-load scenarios.

`required` and `all` are intended for `ci`, `full`, or explicit validation requests. They are not part of the default `core` token cost.

---

## Execution

### 1. Normalize Intent

Classify the task intent into one or more task types:

- API route change.
- Schema or model change.
- Business logic change.
- UI behavior change.
- Architecture understanding.
- Dependency or tooling update.
- Unknown or mixed task.

Record keywords and changed paths that influenced the classification.

---

### 2. Select Candidate Modules

Use routing evidence in this order:

1. Changed file paths matched by `ARCHITECTURE.md` or `knowledge/INDEX.md` path ownership.
2. The smallest set of matching atomic keyed root-index `pkf.routes` entries for cross-capability intent.
3. Module names and keywords in `knowledge/INDEX.md`.
4. Module `INDEX.md` routing tables.
5. Leaf-level `pkf.related` only as optional context.

If multiple modules match, keep all plausible candidates but mark ambiguity.

Do not load unrelated modules automatically.

For every task, select the smallest context packet that completely covers its requirements, then return the exact `source_symbols` and Edit Map locator commands.
For a cross-capability task, compose the smallest matching atomic route set, deduplicate its leaves, and remove any leaf without unique requirement coverage.
When equally complete alternatives use the same leaf count, prefer the lower estimated token cost.
Do not load adjacent indexes or related leaves.

---

### 3. Select Required Documents

Start from the standard retrieval path:

```text
PKF.md
  -> MEMORY.md
  -> ARCHITECTURE.md
  -> knowledge/INDEX.md
  -> knowledge/<module>/INDEX.md
```

Then select leaf documents by task type:

| Task type | Required OKF document |
|-----------|-----------------------|
| API route change | `api.md` |
| Schema or model change | `schema.md` |
| Business logic change | `business_rules.md` |
| UI behavior change | `ui.md` |
| Architecture understanding | `ARCHITECTURE.md` plus relevant module `INDEX.md` |
| Dependency or tooling update | `dependencies.md` plus affected module `INDEX.md` when applicable |

Use `pkf.loads` only for documents required to answer the simulated task. Put useful but nonessential documents in Optional related documents.

---

### 4. Estimate Token Cost

Estimate token cost for every automatically loaded document.

Use an exact tokenizer when available locally for the target model. Otherwise use the deterministic approximate estimator:

```text
ceil(character_count / 4)
```

Report estimator type, coverage status, minimality status, and actual route size.

Apply structural thresholds and the minimum-sufficient retrieval policy:

- Startup path above 2,500 tokens: warning locally, error in CI.
- Any leaf above 1,500 tokens: warning locally, error in CI.
- Route leaf count and estimated tokens are telemetry, not validation gates.
- Any unrelated module loaded automatically: error.

---

### 5. Collect Evidence

For every selected module or document, include compact evidence:

- Matching task keyword.
- Matching changed file path.
- Routing table row or document section.
- `pkf.loads` or `pkf.related` entry.
- Source evidence path when the route depends on a documented fact.

If evidence is missing, report a warning and recommend the routing document that should be updated.

---

### 6. Report Warnings And Errors

Warn when:

- The task intent maps to multiple modules without enough evidence.
- Changed file paths have no owner.
- Required task type cannot be classified.
- Optional related documents look broad or stale.
- Token estimates cross warning thresholds.
- Evidence suggests a capability split but does not satisfy the Module Boundary Contract.

Error when:

- `pkf.loads` automatically loads an unrelated module.
- Required documents are missing.
- Routing references a missing document.
- The simulation cannot reach a selected module from `knowledge/INDEX.md`.
- A task-specific route must load unrelated capability facts because one module mixes independently routable capabilities.
- A leaf lacks valid source symbols or a targeted Edit Map.
- A selected route is incomplete or contains a leaf without unique requirement coverage.

Treat errors as validation defects.
Simulation never invents or renames modules.

---

## Required Simulation Scenarios

Validation and optimization run these scenarios only in `required` or `all` simulation mode:

| Scenario | Input intent | Expected required docs |
|----------|--------------|------------------------|
| API route | Change an API route | Root index, module index, `api.md` |
| Schema/model | Change a schema or data model | Root index, module index, `schema.md` |
| Business logic | Change business logic | Root index, module index, `business_rules.md` |
| UI behavior | Change UI behavior | Root index, module index, `ui.md` |
| Architecture | Understand repository architecture | `ARCHITECTURE.md`, root index, relevant module index |
| Dependencies/tooling | Update dependencies or tooling | Root index, `dependencies.md`, affected module index when applicable |

If the repository has no module matching a scenario, report it as skipped with evidence. In default `changed` mode, skip this table unless the current task intent matches one of the scenarios.

---

## Report Format

```text
Retrieval Simulation
Intent: <natural-language task>
Changed paths: <paths or none>
Task type: <classified type>
Simulation mode: <off, changed, required, or all>
Selected modules: <modules>
Required docs: <docs loaded automatically>
Optional related docs: <docs not automatically loaded>
Estimated tokens: <count>
Estimator: <exact or approximate>
Coverage status: <complete, incomplete, or unknown>
Minimality status: <minimal, redundant, or unknown>
Source targets: <path:symbol entries>
Targeted commands: <sg when verified as ast-grep, otherwise exact rg commands>
Fallback search: <yes or no>
Fallback reason: <reason or none>
Route telemetry: <route IDs, requirements covered, unique leaves, and estimated tokens>
Routing evidence:
- <evidence item>
Warnings:
- <warning or none>
Errors:
- <error or none>
```

---

## Rules

- Do not modify files.
- Do not invent modules, paths, or document relationships.
- Use `pkf.loads` only for required context.
- Treat `pkf.related` as optional context only.
- Keep simulation deterministic and evidence-backed.
- Treat unrelated automatic loads as validation defects.

---

## Success Criteria

Simulation succeeds when:

- The selected modules are evidence-backed.
- Required documents match the task type.
- Optional related documents are separated from automatic loads.
- Token estimate and estimator type are reported.
- Ambiguous or broad routing is reported.
- The report states which simulation mode was used.
- No unrelated modules are loaded automatically.
