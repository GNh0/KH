---
name: csharp-designer-style-harness
description: Generate, modify, or review WinForms/DevExpress/KoneLib C# and Designer code against the exact project patterns, bindings, and save contracts.
---

# C# and Designer

Apply to the actual target project. Do not impose WinForms architecture on MAUI/PDA or other C# projects.

## Working basis

1. Use the latest request and agreed style. Preserve current user edits and keep the change scoped. A conflicting sample does not weaken an agreed rule.
2. Read the actual target and a relevant same-project example before writing. Match event responsibilities, data timing and initialization paths. Migration source defines business behavior; target source defines APIs and implementation patterns. Available APIs alone do not establish the intended workflow.
3. Add or change behavior/settings only for the requested function or a concrete implementation need. Reuse the established path. Resolve differences against actual source before completion; necessary departures require a concrete reason.

Keep these decisions in the working context; no intake form or audit file is required.

For labels and single-line inputs added or edited, match height and sizing constraints to similar controls in the actual screen. Inherit the selected control's initialized label font, H/V alignment and UseTextOptions; avoid arbitrary overrides. Read a self-property Default fallback from that source rather than imposing one global alignment. Apply needed role/request exceptions with their actual basis. Width may grow for content. Resolve differences before completion.

## Read for the current change

Read the needed sections, not every reference. Inspect relevant source bodies completely; retrieve material omissions from truncated output.

| Change | Reference |
| --- | --- |
| C# syntax, names, events and DB-call style | [Coding style](references/coding-style.md) |
| Control selection, defaults, dimensions and initialization | [User controls](references/user-controls.md) |
| Layout, import preservation, Designer/resx and slides | [Designer](references/designer.md); for grids, [HTML defaults](references/grid-layout.md) |
| Query/save, XML, row handling, selection and binding | [Data and event contracts](references/data-flow.md) |
| Monitoring, repeated queries or rebinding | [Screen behavior](references/screen-behavior.md) |
| Optional automated comparison | [Checks](references/checks.md) and the [scoped profile](references/default-profile.json) |

Use the [necessity criteria](../work-execution/references/preferences.md) for LINQ, intermediate tables and builds. Keep auxiliary files outside project/source trees using [workspace files](../work-execution/references/workspace-files.md).

Static checks cover only their reported items. Use actual comparison inputs, resolve relevant warnings and inspect `not_checked`; a pass or build is not project-style verification. New imports/full style corrections also need standalone inspection so unchanged foreign mistakes are not hidden.

With snippets only, perform the clear scoped edit. Mark unavailable project APIs, inherited paths and registration as unverified; seek missing information only when it determines the implementation. Do not substitute another project.
