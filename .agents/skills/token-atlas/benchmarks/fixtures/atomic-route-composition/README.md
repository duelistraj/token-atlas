# functional-route-minimality

## Goal

Verify that functional `boards` and `notes` routes are selected by complete requirement coverage rather than a leaf or token allowance.

## Scenario

The fixture transforms a deliberately technical `backend`/`frontend` repository into functional `boards` and `notes` capability modules.

- `note-task-visibility` crosses both capabilities but needs only the authoritative notes UI leaf.
- `note-task-policy` needs three independently useful leaves for permissions, lifecycle, and relationship policy.
- The broad task composes both routes into four unique leaves.

## Expected behavior

- Every route requirement is covered.
- Every selected leaf uniquely covers at least one requirement.
- The one-leaf route remains valid even though it names two participating modules.
- Leaf count and estimated tokens are telemetry and never a validation ceiling.
- The composed packet is deduplicated and contains no redundant leaves.
