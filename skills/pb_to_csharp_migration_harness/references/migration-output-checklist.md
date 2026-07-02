# Migration Output Checklist

Use this checklist before handoff or completion.

## Required sections

- Objective and target operator.
- Migration mode and evidence strength.
- PB source trace summary.
- DataWindow field/layout mapping.
- Detail form label/editor layout, source field names, target control names, and `BindingField` assignments when the migrated screen has input controls.
- Target C# implementation plan.
- Target C# control fallback map.
- SELECT/SAVE SP plan.
- SQL formatting/verifier status.
- Traceability from PB behavior to C# method and SP branch.
- Verification plan.
- Blocked items and missing evidence.

## Completion criteria

- No claim of full PB parity without exported or pasted source evidence.
- No claim of DB semantic equivalence without DB-backed check.
- No claim of layout fidelity without visual/layout source.
- Detail form controls are aligned as readable label/editor pairs instead of blindly copying PB coordinates unless exact visual parity was explicitly requested.
- No generated user-facing files outside the exact requested target path.
- No hidden use of global memory as a substitute for current artifacts.
- Token optimizer status is recorded.
- SQL formatter and verifier roles are separated.
- Project-specific controls are not hard-coded from a sample project. The selected control provider is target-project/custom, DevExpress, or WinForms with a reason.
- Remaining assumptions are visible.

## User-facing output

For normal work, return the deliverable or migration plan in the user's language. Keep internal KH evidence out of the final answer unless the user asks for a skill/harness audit.
