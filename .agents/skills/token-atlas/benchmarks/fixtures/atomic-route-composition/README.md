# functional-route-irredundancy

## Goal

Verify that functional `boards` and `notes` routes provide sufficient, deduplicated, and irredundant selected-route context rather than obeying a leaf or token allowance.

## Scenario

The fixture transforms a deliberately technical `backend`/`frontend` repository into functional `boards` and `notes` capability modules.

- `note-visibility` crosses both capabilities but needs only the authoritative notes UI leaf.
- `link-permissions` and `link-lifecycle` reuse `note-link-policy` with the same authoritative notes leaf.
- The lifecycle route also uses that leaf for a second related requirement, while the broad task composes all three routes into four unique leaves.

## Expected behavior

- Every route requirement is covered.
- Every requirement has one authoritative leaf across the root route catalog.
- Shared requirements and leaf references are deduplicated across selected routes.
- The one-leaf route remains valid even though it names two participating modules.
- Leaf count and estimated tokens are telemetry and never a validation ceiling.
- The composed packet is sufficient, deduplicated, and irredundant relative to the selected routes.
- Route-to-task relevance and mathematical minimality are not mechanically proven.
