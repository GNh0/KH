---
name: csharp-designer-style-harness
description: Generate, modify or review C# and WinForms Designer code against actual project APIs, controls, bindings and save contracts.
---

# C# and Designer

Read the [selected personal C# style](../../references/personal-style.md), actual target and a relevant approved same-project example. Migration source establishes behavior; target source establishes available APIs and implementation paths. Personal names, formats and syntax come from the selected style, not the original KH author.

Preserve current edits and change only the requested scope. Trace relevant control initialization, events, data timing, selection, XML/SP and requery behavior. Reuse available appropriate project user controls and their actual defaults, including RepositoryItems and behavior changed through callbacks/helpers; inspect concrete reasons before adding overrides. Do not impose WinForms patterns on another C# framework.

Use [source and Designer contracts](references/contracts.md) for affected paths. Optional static comparison: `python -B <plugin-root>/scripts/company_check.py csharp <absolute-after.cs> --original <absolute-before.cs> --designer <absolute-screen.Designer.cs>`. Supply separate originals and actual control/reference source when the comparison needs them.

Resolve reported warnings against actual source; inspect `not_checked`. A pass is neither full style verification nor a build, Designer load, UI rendering or DB execution. Follow [workspace files](../work-execution/references/workspace-files.md) for scratch and cleanup.
