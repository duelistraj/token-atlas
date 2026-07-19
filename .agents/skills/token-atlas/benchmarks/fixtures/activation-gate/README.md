# Activation Gate Eval

This isolated fixture reuses the schema-change repository plus the tracked
`overlay/` and compares the frozen runtime-v1 every-turn closeout contract
with runtime v3's adaptive retrieval and semantic closeout gates.

- Read-only prompt: answer the route path without modifying repository content.
- Knowledge-neutral mutation control: reformat one source entry without changing
  behavior, symbols, evidence, or routing; v3 must emit a direct `no-op` without
  loading PKF or Token Atlas.
- Mutation prompt: rename `/customers` to `/clients` and keep source evidence,
  its test, and the authoritative API leaf synchronized.
- Runtime v1 must exercise closeout on the read-only turn.
- Runtime v3 must not load PKF or Token Atlas or emit a status on the local
  read-only turn or the knowledge-neutral control, but must close out and
  synchronize the semantic mutation turn.
