---
name: csharp-designer-style-harness
description: Generate, modify, or review WinForms/DevExpress C#, Designer and XtraReports preview/printing against actual project controls, patterns, bindings and save contracts.
---

# C# and Designer

Apply to the actual target project. Do not impose WinForms architecture on MAUI/PDA or other C# projects.

Complete the required [source-style cycle](../work-execution/references/source-style-cycle.md): before editing, inspect and briefly identify the actual reference program/methods for each changed responsibility and their complete relevant call path; after writing, audit the final production code against them. A file opening or unrelated example does not establish that comparison.

For C# body work, first read the relevant [coding-style](references/coding-style.md) sections. For Designer creation/edits, first read [Designer](references/designer.md). These are the baseline routes; then select the task-specific references below. Loading this entrypoint alone does not load those rules.

## Working basis

1. Apply the latest request and agreed style; preserve current user edits. Conflicting samples do not create exceptions.
2. Reference programs establish style; the actual target establishes APIs and behavior. Read complete relevant caller/callee bodies for return handling, data timing and initialization/reset ownership. For save changes, trace selected rows, XML/state, SP calls and failure/success refresh together. Preserve query and report behavior separately.
3. Add code/settings only for an identified missing behavior or verified dependency after checking what the current path already does. A feature name, available API or familiar sample does not establish necessity.

For any control or RepositoryItem creation/change, including ColumnEdit, first read [user controls](references/user-controls.md), actual Designer/library source and shared initialization. Preserve effective defaults through direct properties, callbacks and helpers. Distinguish display from input behavior; a data type/display request alone does not justify an editor or override.

Keep changes at the requested member scope: column settings do not authorize view-wide Appearance or shared-default resets. For labels/single-line inputs, match height and constraints to similar actual-screen controls. Inherit initialized font, H/V alignment and UseTextOptions, including the source's Default fallback; do not impose a global alignment. Width may grow for content. Establish actual role/request exceptions from source and inspect runtime/layout overwrite paths.

## Read for the current change

Read the needed sections, not every reference. Inspect relevant source bodies completely; retrieve material omissions from truncated output.

| Change | Reference |
| --- | --- |
| Grid layout, Appearance and editor defaults | [HTML defaults](references/grid-layout.md) |
| Query/save, XML, row handling, selection and binding | [Data and event contracts](references/data-flow.md) |
| Report creation, data/preview/printing, bands and project integration | [Reports](references/reports.md) |
| Monitoring, repeated queries or rebinding | [Screen behavior](references/screen-behavior.md) |
| Optional automated comparison | [Checks](references/checks.md) and the [scoped profile](references/default-profile.json) |

Use the [necessity criteria](../work-execution/references/preferences.md) for LINQ, intermediate tables and builds. Keep auxiliary files outside project/source trees using [workspace files](../work-execution/references/workspace-files.md).

When scope moves from analysis to implementation or adds SQL/report work, enter that artifact's workflow before writing it. An earlier PB analysis or C# style excerpt does not cover the new responsibility.

After the final write, compare changed C# bodies and Designer blocks with the selected sources through the source-style cycle and shared rule audit. Resolve unsupported differences, checker warnings and `not_checked` from actual source/requirements. A read, pass or build is not style verification. Imports/full style corrections need standalone inspection too, so differential suppression does not hide retained mistakes.

With snippets only, perform the clear scoped edit. Mark unavailable project APIs, inherited paths and registration as unverified; seek missing information only when it determines the implementation. Do not substitute another project's APIs for missing target evidence.

Before final handover, complete the shared [rule audit](../rule-audit/SKILL.md) for this task's applicable rules.
