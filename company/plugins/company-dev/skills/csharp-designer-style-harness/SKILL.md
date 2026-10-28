---
name: csharp-designer-style-harness
description: Generate, modify or review C#, WinForms Designer and XtraReports preview/printing against actual project APIs, controls, bindings and save contracts.
---

# C# and Designer

Read the [selected personal C# style](../../references/personal-style.md), actual target and the user's named comparison, otherwise a relevant approved same-project example. Migration source establishes behavior; target source establishes available APIs. A style example from another project does not establish target API compatibility. Personal names, formats and syntax come from the selected style, not the original KH author.

Preserve current edits and change only the requested scope. Compare complete relevant event/caller bodies for return handling, initialization/reset ownership, data timing, selection, XML/SP and success/failure requery behavior. Reuse available appropriate project user controls and their actual defaults, including RepositoryItems and behavior changed through callbacks/helpers; inspect concrete reasons before adding overrides. Do not impose WinForms patterns on another C# framework.

Keep required property changes at their actual control/member scope. Column settings do not authorize view-wide Appearance changes or shared-default resets; inspect relevant initialization and layout-loading paths.

Use [source and Designer contracts](references/contracts.md) for affected paths. Optional static comparison: `python -B <plugin-root>/scripts/company_check.py csharp <absolute-after.cs> --original <absolute-before.cs> --designer <absolute-screen.Designer.cs>`. Supply separate originals and actual control/reference source when the comparison needs them.

For report creation or changes to preview/printing, read [reports](references/reports.md). Reassess the applicable domain entrypoint/references when the request changes from analysis to implementation or adds SQL/report work; an earlier style excerpt does not cover the new artifact.

Before completion, compare each changed C# body and Designer block with the selected style and relevant project source. Correct unsupported differences; justify necessary departures from actual behavior or API constraints and preserve the surrounding style. Reading the references alone does not complete this comparison.

Resolve reported warnings against actual source; inspect `not_checked`. A pass is neither full style verification nor a build, Designer load, UI rendering or DB execution. Follow [workspace files](../work-execution/references/workspace-files.md) for scratch and cleanup.
