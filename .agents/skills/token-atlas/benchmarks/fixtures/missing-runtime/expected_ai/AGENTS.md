# AGENTS

This repository uses a Project Knowledge Framework (PKF) with a knowledge base
under `.ai/`.

Use a cheap local probe of at most two targeted searches and three source files
for a likely single-capability task. If it resolves the target, inspect source
directly without reading PKF. Activate PKF retrieval and follow the **Retrieval
Protocol in `.ai/PKF.md`** for cross-capability, architecture, ownership, or
repository-wide tasks, or before the probe expands into broad search.

After an intentional repository mutation, first apply the knowledge-impact gate
without loading PKF. Read-only turns bypass closeout silently. If no durable
facts, evidence, or routing changed, report a knowledge-neutral `no-op` without
loading Token Atlas or PKF. Otherwise follow the **Closeout Protocol in
`.ai/PKF.md`** exactly once, update only affected leaves, and run affected-slice
summary validation. Do not rerun closeout because closeout changed `.ai/`.
