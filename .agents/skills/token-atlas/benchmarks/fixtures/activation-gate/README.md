# Activation Gate Eval

This isolated fixture reuses the schema-change repository plus the tracked
`overlay/` and compares the frozen runtime-v1 every-turn closeout contract
with runtime v2's mutation gate.

- Read-only prompt: answer the route path without modifying repository content.
- Mutation prompt: rename `/customers` to `/clients` and keep source evidence,
  its test, and the authoritative API leaf synchronized.
- Runtime v1 must exercise closeout on the read-only turn.
- Runtime v2 must not load Token Atlas closeout or emit a status on the
  read-only turn, but must close out and synchronize the mutation turn.
