# Real-Repository Performance Workspace

This tree keeps real-repository performance inputs and outputs separate from
Token Atlas core behavior.

- `targets/`: explicit repository-specific task specifications.
- `patches/`: target-specific pre-applied mutation patches referenced by a
  target specification.
- `schemas/`: baseline, target-specification, and published-report schemas.
- `baselines/`: ignored immutable PKF baselines and resumable generation drafts.
- `artifacts/<run-id>/public/`: sanitized publishable reports.
- `artifacts/<run-id>/private/`: ignored local traces, PKF snapshots,
  validation evidence, diffs, and reusable mutation states.

The baseline and performance tools require explicit target, model, reasoning,
and phase inputs. They never initialize or benchmark the Token Atlas maintenance
repository itself.
