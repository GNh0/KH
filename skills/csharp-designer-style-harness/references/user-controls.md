# User-control selection and default initialization

1. Find the actual project control for the requested role. Read its constructor, InitializeComponent, helpers and base classes. Identify unconditional defaults separately from event, culture and mode settings.
2. Set the screen-owned name, layout, text, bindings and events. Preserve control defaults and user edits. Add an override only when the target behavior needs it. Existing equivalent Designer serialization can stay.
3. Match label and single-line input height to visible same-role controls on the actual screen. Check Size, constraints, AutoHeight, usable space and embedded buttons together. Keep default width for short text and widen when content requires it.
4. Preserve label Font, H/V alignment, UseTextOptions and AutoSizeMode. In the supplied u_Label, Default resolves to Far / Center and an initialized non-Default value survives. Verify the selected control's effective values and rendering.
5. For a larger screen-specific font, compare unchanged peers or an approved comparable Designer. A constructor can supply the default font. Labels edited together cannot independently establish a screen exception.
6. Read screen initialization as well as library code. Restore required editor and calendar Buttons.AddRange collections, including buttons later hidden by shared code. Use the RepositoryItem's own initialization and property paths.
7. Trace display/edit formats, masks, navigation, colors and borders through binding and callbacks. Add only missing behavior in its owning scope. Choose a standard control when actual project availability or API requirements call for it.

## Naming and date controls

Use the binding field for inputs and screen role for containers. Preserve requested names, actual wiring and existing sharing.

| Role | Name |
| --- | --- |
| Text, numeric, date | `txt<Field>`, `Spin<Field>`, `ymd<Field>` |
| Lookup, button, check, memo | `cbo<Field>`, `btn<FieldOrRole>`, `Chk<Field>`, `memo<Field>` |
| Panel, group, grid, view | `pn<Role>`, `grp<Role>`, `grd<Role>`, `gvw<Role>` |
| Column | `col<Role>_<FIELD>` |
| Numeric, lookup, button, check Repository | `rpsSpin<Field>`, `rpscbo<Field>`, `rpsbtn<Field>`, `rpschk<Field>` |
| Label, tab, tree | `lbl<FieldOrRole>`, `tab<Role>`, `treeList<Role>` |

- Use `ymdFRDT` / `ymdTODT` for those date fields. For a second, genuinely distinct numeric Repository use `rpsDetailSpinQTY` alongside `rpsSpinQTY`. Check declarations, creation, Name, events, FieldName and ColumnEdit.
- Use meaningful names for new controls. Rename existing controls only in scope.
- A displayed date or timestamp uses the existing display path. Create a DateEdit Repository for an actual editing/popup need. Inspect navigation and masks before adding overrides. Preserve time precision and SQL types.
- Apply the [grid HTML and column editing rules](grid-layout.md) to the grid.

## Optional static comparison

```powershell
python <plugin-root>/scripts/kh_check.py designer <after.Designer.cs> --original <before.Designer.cs> --control-source <control.cs> --style-reference-designer <approved.Designer.cs>
```

Supply the actual control library and role-matched Designer. Resolve inherited or conditional settings in source. Select relevant peers when controls disagree. Use `--allow-property-change member.Property` for a verified exception within the current scope. Inspect the saved screen at the target DPI for effective height and alignment.
