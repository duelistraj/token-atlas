# functional-boundaries-init

## Goal

Verify that initialization derives flat functional modules from source evidence
instead of copying technical-layer or placeholder names.

## Source Shape

- Two synthetic functional capabilities implemented across two technical layers.
- Each capability has interface, workflow, user-facing, and test evidence.
- One placeholder-only concept has no implementation.

## Expected Behavior

- Generate only the two source-backed capability modules.
- Route the task intent to the first capability's workflow leaf.
- Do not generate technical-layer or placeholder modules.
- Keep all modules flat and retrieval exports disabled.

## Expected Selected Modules

- Only the capability matched by the workflow intent.

## Expected Required Docs

- The startup path, root index, selected module index, and workflow leaf.

## Forbidden Automatic Loads

- The unrelated capability, technical-layer directories, placeholders, and retrieval exports.

## Expected Warnings And Errors

- None when capability evidence and ownership are unambiguous.

## Token Measurements And Exit Behavior

- Startup and selected-module route sizes are observed without numeric ceilings.
- Advisory and CI validation exit successfully.
