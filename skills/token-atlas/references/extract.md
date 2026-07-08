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
- Traceable to a path, symbol, route, command, config key, or test.
- Removed or marked `TODO` when no longer verifiable.

Use compact evidence labels. Do not paste large source snippets.

## Procedure

1. Identify affected modules and docs.
2. Read only the smallest source set needed to verify facts.
3. Update affected OKF documents.
4. Refresh metadata for affected docs.
5. Update root and module routing when modules, paths, keywords, or task routes changed.
6. Run validation after extraction.

## Rules

- Never invent implementation details.
- Never modify application code.
- Preserve useful manual notes when they remain verifiable.
- Do not use `.ai/retrieval/` as source input.
- Prefer evidence-linked bullets and tables over prose.
