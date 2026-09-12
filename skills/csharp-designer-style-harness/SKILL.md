---
name: csharp-designer-style-harness
description: Generate, modify, or review WinForms/DevExpress/KoneLib C# and Designer code against the exact project patterns, bindings, and save contracts.
---

# C# and Designer

Read the current files, user edits, specified comparison screen, and actual framework call paths. Do not apply this skill's WinForms rules wholesale to MAUI/PDA or other C# projects.

For migrations and unfinished screens, first identify the modification scope. If the user requests selected deletions, renames, or binding changes based on an original screen, start from its C#/Designer/resx. Do not redesign retained controls' properties or behavior outside the request. The currently specified preservation scope overrides defaults for new screens. Follow [migration with source preservation](references/designer.md).

The migration source defines business behavior; the target project defines required APIs, events, and DB call patterns. Connect missing functionality to the existing screen, query, and event flow. Before writing, check the event's current state and actual helpers; use [data and event contracts](references/data-flow.md) to determine whether new validation, requerying, wrappers, or row-key assignments are necessary. Do not rewrite all code merely to match target style.

For control work, prefer appropriate user controls available in the current project, not just KoneLib. Follow [user-control rules](references/user-controls.md): read and preserve constructor, initialization-helper, and inherited defaults; add only properties needed for the screen's requested behavior. Do not invent or overwrite defaults. Name date controls with ymd and the actual field name.

- For writing/editing C#, read the [user's coding style](references/coding-style.md). Reference source that differs from agreed rules may contain an oversight; do not use the difference to relax those rules.
- For UI/Designer work, read [screen style](references/designer.md). For grids, also read [HTML defaults](references/grid-layout.md).
- For queries, saves, uploads, or row selection, read [data and event contracts](references/data-flow.md).
- For monitoring, multiple UserControls, repeated queries, or grid rebinding, read [screen behavior contracts](references/screen-behavior.md). Check events that overwrite user edits and the actual query timing.
- Use the [scoped default profile](references/default-profile.json) when checking project style. Do not repeat author discovery for every task.
- Use the [checker](references/checks.md) when automated static comparison is needed.

Read only the needed parts of relevant references and source. If a batch output is truncated, retrieve the omitted parts that matter. Including a path in a command does not establish that its contents were inspected.

Keep static controls/layout in Designer and follow actual code-behind patterns for binding/business behavior. Follow the existing constructor's named-handler subscription pattern without duplicate subscriptions. Check the project's DevExpress version/APIs and csproj registration. Reuse existing helpers; assess new abstractions, LINQ, intermediate tables, and unnecessary builds against the [necessity criteria](../work-execution/references/preferences.md).

Use the Load Layout properties from the user's DataWindowToXml.html as grid defaults. Do not add cell TextOptions, SpinEdit EditMask, DisplayFormat (including FormatType), or OptionsBehavior by default. For blocked editing, set AllowEdit=false and ReadOnly=true; for button-like columns whose actions must remain available, set only ReadOnly=true; for editable columns, omit both. Do not reset existing screen properties wholesale. Determine changes needed for specific behavior from current requirements and actual source.

For summaries or string output that need numeric formatting, follow [custom numeric formats](references/coding-style.md). Prefer #,##0, #,##0.##, and similar formats over N0/N2. Do not expand a summary-format or Spin-connection check into permission to add cell/Repository DisplayFormat.

Trace defaults through actual shared-form initialization/helpers as well as user-control constructors. If the current user explicitly requests the same display on a target without that initialization path, you may apply the verified format and decimal precision exactly. An older instruction to avoid a setting must not block a later specific request.

Do not arbitrarily add changed properties to --allow-property-change to suppress warnings. Excluded checks are not passing evidence; verify the actual requirement and necessity separately.

Check the full lifecycle for a full-screen request; keep a local edit scoped. Validate the actual requested behavior at completion. Build results do not guarantee UI or save behavior.

The checker's `status=passed` means the executed static checks found no errors. Also read `comparison_baselines`, `review_status`, `issues`, and `not_checked`. To verify source preservation, supply the pre-change original and compare retained Designer properties, including rename mappings. Omitting the original or resubmitting the edited version as the original does not establish preservation. Reading the skill or passing the checker alone does not establish project-style compliance.
# Limits of supplied snippets

If only snippets/fixtures are supplied without a project, perform the edits possible within that scope. Mark the DevExpress version, csproj, and inherited implementations as unverified. Their absence alone must not block a clear local edit or trigger reading a substitute project. Seek only the missing information needed when an API difference actually determines the solution.
