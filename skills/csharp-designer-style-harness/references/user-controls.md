# User-control selection and default initialization

These rules are not limited to KoneLib. They apply to every user control available in the current project that fits the requested role, across UI creation/editing, Designer, and PB-to-C# migration.

1. Identify controls from current solution/project references and the comparison screen. Prefer a user control for the role when available. Familiarity alone does not justify choosing a new standard DevExpress/WinForms control. A specialized derived control's existence does not justify replacing an existing appropriate user control.
2. Read the selected control's constructor, InitializeComponent, called initialization helpers, and base classes. Follow their defaults for fonts, height, minimum/maximum sizes, AutoHeight, alignment, colors, borders, buttons, input masks, edit/display formats, Enter/Tab navigation, and other properties. Do not copy values changed by culture/mode branches or events into global defaults.
3. On the screen, specify only name, location/parent layout, display text, actual bindings/events, and properties required by the current request. Do not duplicate or override user-control defaults. Distinguish screen-owned properties such as name/location from control-defined properties such as height/Font. Do not expand the task into unconditional removal of identical defaults reserialized by Visual Studio.
4. Connect a necessary property change to the current requirement and that property's role. Settings seen elsewhere, aesthetic guesses, or formats inferred solely from data types do not justify changes. Preserve existing user-edited values and explicit exceptions. If available controls or actual API constraints require a standard control, implement it on that basis.

If defaults have not been inspected, do not fill them from remembered DevExpress defaults or another project's KoneLib values. Check the current target's declarations and initialization path. This is source inspection during the task, not a procedure requiring the same explanation, approval, or profile file from the user every time.

## Naming and date controls

Combine `ymd` with actual field meaning for date inputs: FRDT/TODT become `ymdFRDT`/`ymdTODT`. Do not derive a new `deFRDT` name from the DateEdit type name. Align declarations, construction, Name, event wiring, and code-behind references. First determine whether renaming an existing control is in scope.

For other inputs, follow prefixes/bindings in current user controls and the comparison screen. Recurring BA/SA/MA prefixes include txt/cbo/btn/memo, grd/gvw/col/rps, and grp/pn. Auto-generated names or inconsistent samples do not weaken agreed naming. Do not invent new prefixes for every control.

Retain the following naming rules from the pre-3.0.0 harness. For new inputs, Field is the actual binding field; for containers, Role is the actual screen role. Samples such as `panMaster` or `repositoryItem...1` do not override existing agreements.

| Role | Name |
| --- | --- |
| Text/numeric/date inputs | `txt<Field>`, `Spin<Field>`, `ymd<Field>` |
| Lookup/button/check/memo inputs | `cbo<Field>`, `btn<FieldOrRole>`, `Chk<Field>`, `memo<Field>` |
| Panels/groups/grids/views | `pn<Role>`, `grp<Role>`, `grd<Role>`, `gvw<Role>` |
| Columns | `col<Role>_<FIELD>` |
| Numeric/lookup/button/check Repositories | `rpsSpin<Field>`, `rpscbo<Field>`, `rpsbtn<Field>`, `rpschk<Field>` |
| Labels/tabs/trees | `lbl<FieldOrRole>`, `tab<Role>`, `treeList<Role>` |

The default numeric Repository name is `rpsSpin<Field>`. If another grid on the same screen needs an additional Repository for that field, distinguish it as `rps<Role>Spin<Field>`. For example, when List already has `rpsSpinQTY` and Detail needs a separate QTY Repository, retain the old name and create `rpsDetailSpinQTY`. Role is the grid's role, such as Detail in `grdDetail`; do not move it after Spin as in `rpsSpinDetailQTY` or mask collisions with numeric suffixes. Do not split established Repository sharing through a local naming edit alone.

Do not retain auto-generated names such as `gridControl1`, `gridView1`, `gridColumn1`, `repositoryItem...1`, or `textEdit1` in new screens. Follow names explicitly specified by the current user. Do not forcibly rename an entire existing screen to fit these rules. Correct names without BindingField, FieldName, ColumnEdit, or event connections are incomplete.

DateEdit follows the same default-initialization principle. Dates alone do not justify additional DisplayFormat, EditFormat, EditMask, or Mask settings. For requested input behavior such as automatic year → month → day navigation, first check whether the control already implements it; add only properties needed for missing behavior. Do not globally prohibit masks or remove required input behavior while cleaning up display formats.

Also apply the user's explicit [grid HTML defaults](grid-layout.md) and three column-editing rules as screen requirements. Do not extend grid rules to property values of every TextEdit, button, or panel.

## Optional static comparison

Optionally supply the selected user controls' actual C# source to the checker with `--control-source`. No separate JSON list of defaults is required.

```powershell
python <plugin-root>/scripts/kh_check.py designer <after.Designer.cs> --original <before.Designer.cs> --control-source <actual-InputBox.cs> --control-source <actual-DateBox.cs>
```

Review standard-control selection from supplied inheritance declarations regardless of names/namespaces. Compare direct parameterless-constructor assignments and supplied parent-constructor assignments: new default overrides are warnings, identical reassignments are informational. Unchanged screen assignments are not flagged for wholesale cleanup. Use the existing `--allow-property-change member.Property` for specifically required properties without overriding explicit preservation contracts.

This check does not execute control libraries or discover every default. It inspects simple inheritance and direct assignments; separately inspect initialization helpers, unsupplied partials/base classes, conditions, runtime values, and actual project references. Exclude conditionally overwritten properties from confirmed defaults. Without source, preferred-control selection and default overrides remain unverified. Regardless of checker coverage, the code author must read the actual initialization paths described above.
