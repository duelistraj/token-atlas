<!-- token-atlas:bootstrap:start -->
## Project Knowledge Framework

This repository uses a Project Knowledge Framework under `.ai/`.

Use a cheap local probe of at most two targeted searches and three source files
for a likely single-capability task. If it resolves the target, inspect source
directly without reading PKF. Activate PKF retrieval and follow the **Retrieval
Protocol in `.ai/PKF.md`** for cross-capability, architecture, ownership, or
repository-wide work, or before the probe expands into broad search.

After an intentional repository mutation, first apply the knowledge-impact gate
without loading PKF. Read-only turns bypass closeout silently. If no durable
facts, evidence, or routing changed, report a knowledge-neutral `no-op` without
loading Token Atlas or PKF. Otherwise run the repository-local helper exactly
once, repeating `--changed-path` for every turn-owned path:

`python -S .ai/tools/pkf_route.py --path . --changed-path <path> --format json`

For `mapped`, read and update only returned leaves; do not load PKF startup
documents, indexes, the Token Atlas skill, or workflow references. For `partial`,
use returned leaves and only the module indexes named by `fallback_routes`. For
`unmapped`, report the routing-coverage defect and use exceptional Token Atlas
maintenance. After a knowledge update, run exactly one summary validation:

`python -S .ai/tools/pkf_validate.py --path .ai --scope <affected|full> --strictness advisory --format json --detail summary --changed-path <path>`

These generated rules are the routine mapped subset of the **Closeout Protocol
in `.ai/PKF.md`**; load that protocol only when the route is exceptional.
<!-- token-atlas:bootstrap:end -->
