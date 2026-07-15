# functional-boundaries-migration

## Goal

Verify that maintenance automatically replaces an unambiguously coarse module
with flat, source-backed functional modules without losing durable facts.

## Source Shape

- The same two synthetic capabilities used by the initialization fixture.
- An existing PKF stores both capabilities in one coarse module.
- A placeholder-only concept remains ineligible for module creation.

## Expected Behavior

- Migrate all facts into the two capability modules.
- Remove the superseded coarse module after references validate.
- Route the task to only the selected capability's workflow leaf.

## Expected Selected Modules

- Only the capability matched by the workflow intent.

## Expected Required Docs

- The startup path, root index, selected module index, and workflow leaf.

## Forbidden Automatic Loads

- The unrelated capability, superseded module, technical layers, placeholders, and retrieval exports.

## Expected Warnings And Errors

- None after an unambiguous migration completes.

## Token Thresholds And Exit Behavior

- Startup and selected-module routes remain below their warning thresholds.
- Advisory and CI validation exit successfully after migration.
