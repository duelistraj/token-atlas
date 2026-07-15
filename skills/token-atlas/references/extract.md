# Extract Repository Knowledge

## Purpose

Populate and maintain OKF knowledge using verified target repository information.

Prefer incremental extraction. Update only affected PKF/OKF documents whenever possible.

## Inputs

- Repository source, tests, configuration, docs, and scripts.
- Existing `.ai/` runtime and knowledge base.
- Maintenance impact report, when available.

## Extraction Mode

- If `.ai/` does not exist or was just initialized, perform full extraction.
- If `.ai/` exists, perform incremental extraction from maintenance impact or Git changes.

## Knowledge Mapping

| Repository fact | Authoritative target |
|-----------------|----------------------|
| API routes, endpoints, handlers | module `api.md` |
| Models, schemas, migrations, types | module `schema.md` |
| Services, workflows, calculations, policies | module `business_rules.md` |
| Screens, components, visible behavior | module `ui.md` |
| Project structure and ownership | `ARCHITECTURE.md`, `knowledge/INDEX.md` |
| Stable repo-wide facts | `MEMORY.md` |
| Commands, scripts, dependencies, configs | `dependencies.md` or `ARCHITECTURE.md` |

## Fact Standard

Every durable fact must be:

- Verified from source files, tests, configuration, or existing docs.
- Stored in the narrowest authoritative document.
- Traceable to an exact source path and symbol, plus a route, command, config key,
  or test where relevant.
- Removed or marked `TODO` when no longer verifiable.

Use compact evidence labels. Do not paste large source snippets.

## Procedure

1. Identify affected modules and docs.
2. Apply any unambiguous module repartition from the maintenance impact report: create new flat skeletons, then inventory and move facts by capability and knowledge type without duplication.
3. Read only the smallest source set needed to verify facts. Capture declarations,
   test symbols, and UI style selectors or tokens rather than file-only evidence.
4. Update affected OKF documents. For every implementation-bearing leaf:
   - Populate `source_symbols` as a path-to-symbol-list mapping.
   - Use `## Edit Map` as the primary retrieval index with columns `Behavior`,
     `Source symbols`, `Tests`, `Styles/tokens`, and `Locator`.
   - Emit a targeted ast-grep locator only when `sg` is verified as ast-grep;
     otherwise emit `rg -n -F -- '<symbol>' '<path>'`.
5. Refresh metadata for affected docs. For a cross-path capability, use the narrowest common existing `resource` path, falling back to `.` while retaining exact evidence paths in the body.
6. Update `ARCHITECTURE.md`, root and module routing, and every affected `pkf.loads` or `pkf.related` edge.
7. Remove a superseded module directory only after every durable fact and manual note is accounted for and no reference targets it.
8. Run validation after extraction.

## Rules

- Never invent implementation details.
- Never modify application code.
- Preserve useful manual notes when they remain verifiable.
- Do not use `.ai/retrieval/` as source input.
- Prefer evidence-linked bullets and tables over prose.
- Keep only current implementation facts in leaves. Put durable policies in
  `business_rules.md`, keep only still-relevant decisions in `decision_log.md`,
  and remove chronological feature summaries.
- Use `source_symbols: {}` plus `- TODO: No source-backed facts.` for an empty
  leaf; do not invent placeholder symbols.
- Keep modules flat and derive their names from the target repository; never introduce a reusable prescribed vocabulary.
