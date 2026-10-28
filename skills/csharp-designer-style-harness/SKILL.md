---
name: csharp-designer-style-harness
description: Generate, modify, or review WinForms/DevExpress C#, Designer and XtraReports preview/printing against actual project controls, patterns, bindings and save contracts.
---

# C# and Designer

Apply to the actual target project. Do not impose WinForms architecture on MAUI/PDA or other C# projects.

Before writing and after the final write, complete the required [source-style cycle](../work-execution/references/source-style-cycle.md): inspect actual comparison-project code first, then re-read and audit the finished code against it.

For C# body work, first read the relevant [coding-style](references/coding-style.md) sections. For Designer creation/edits, first read [Designer](references/designer.md). These are the baseline routes; then select the task-specific references below. Loading this entrypoint alone does not load those rules.

## Working basis

1. Use the latest request and agreed style. Preserve current user edits and keep the change scoped. A conflicting sample does not weaken an agreed rule.
2. Read the actual target and complete relevant event/caller bodies before writing. Use the user's named comparison project, otherwise an approved comparable other project; previously generated or user-rejected code is not an approved style reference. Match return handling, event responsibilities, data timing and initialization/reset owners. For save changes, trace selected rows, row states/XML, SP calls and success/failure refresh paths; preserve query and report behavior separately. Migration source defines business behavior; target source defines available APIs. A style example from another project does not establish target API compatibility. Matching names or available APIs alone does not establish the intended workflow.
3. Before adding code/settings, compare the requested behavior, actual data/result types and what the current path already does. Identify the concrete gap or verified dependency the addition resolves. Preserve a path that already meets the request; a feature name or available API alone does not establish a need. Resolve uncertain necessity from actual source/API behavior first.

Keep these decisions in the working context; no intake form or audit file is required.

For any control or RepositoryItem creation/change, including a new ColumnEdit assignment, read [user controls](references/user-controls.md) and its actual Designer, library and shared initialization before writing. Preserve effective defaults through properties, callbacks and helpers alike. Determine display versus input behavior first; a data type or display request alone does not justify an editor or override.

Keep required property changes at their actual control/member scope. Column settings do not authorize view-wide Appearance changes or shared-default resets; inspect the relevant initialization and layout-loading paths.

For labels and single-line inputs added or edited, match height and sizing constraints to similar controls in the actual screen. Inherit the selected control's initialized label font, H/V alignment and UseTextOptions; avoid arbitrary overrides. Read a self-property Default fallback from that source rather than imposing one global alignment. Apply needed role/request exceptions with their actual basis. Width may grow for content. Resolve differences before completion.

## Read for the current change

Read the needed sections, not every reference. Inspect relevant source bodies completely; retrieve material omissions from truncated output.

| Change | Reference |
| --- | --- |
| C# syntax, names, events and DB-call style | [Coding style](references/coding-style.md) |
| Control selection, defaults, dimensions and initialization | [User controls](references/user-controls.md) |
| Layout, import preservation, Designer/resx and slides | [Designer](references/designer.md); for grids, [HTML defaults](references/grid-layout.md) |
| Query/save, XML, row handling, selection and binding | [Data and event contracts](references/data-flow.md) |
| Report creation, data/preview/printing, bands and project integration | [Reports](references/reports.md) |
| Monitoring, repeated queries or rebinding | [Screen behavior](references/screen-behavior.md) |
| Optional automated comparison | [Checks](references/checks.md) and the [scoped profile](references/default-profile.json) |

Use the [necessity criteria](../work-execution/references/preferences.md) for LINQ, intermediate tables and builds. Keep auxiliary files outside project/source trees using [workspace files](../work-execution/references/workspace-files.md).

Before completion, compare each changed C# body and Designer block with the agreed style and relevant project source. Correct unsupported differences; justify necessary departures from actual behavior or API constraints and preserve the surrounding style. Reading the references alone does not complete this comparison.

Reassess these routes when the request changes from analysis to implementation or adds a report, SQL or another artifact. Load that domain's entrypoint and needed reference before writing it; an earlier PB analysis or C# style read does not cover a later report implementation.

Static checks cover only their reported items. Use actual comparison inputs, resolve relevant warnings and inspect `not_checked`; a pass or build is not project-style verification. New imports/full style corrections also need standalone inspection so unchanged foreign mistakes are not hidden.

With snippets only, perform the clear scoped edit. Mark unavailable project APIs, inherited paths and registration as unverified; seek missing information only when it determines the implementation. Do not substitute another project's APIs for missing target evidence.

Before final handover, complete the shared [rule audit](../rule-audit/SKILL.md) for this task's applicable rules.
