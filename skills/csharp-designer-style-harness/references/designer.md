# WinForms / Designer

## Migration with source preservation

When importing an original screen for renames, control deletion, or partial edits, copy its existing Designer and resx, then change only what is needed. Screenshots establish deletion/change scope; they do not justify recreating visible controls in a new Designer. Do not replace retained controls' Font, Size, AutoHeight, alignment, buttons, masks, display properties, or other settings with new defaults. Preserve existing properties the current user explicitly requests, even when they differ from an older general preference to avoid them.

Apply the user-control/default rules below to newly added controls. If target API differences require replacing an existing control, limit edits to those differences. For renames, align declarations, Name, references, events, and resx keys. For deletion, check fields, initialization, registration, events, and resource references. Verify preservation of retained properties and behavior against the actual original diff.

Preserve copies of the original C#/Designer/resx before editing. Use explicit rename mappings for comparison; do not alter the original's properties or conditions to match the candidate just to pass. The [checker](checks.md) can compare explicit assignments in retained Designer members with `--preserve-existing` and `--member-rename`. Separately check deletions, new controls, indirect initialization, and resource contents against the actual request and diff.

## New controls and general structural review

When a supplied slide defines a new screen, inspect the complete rendered slide with its text, shapes, tables and images together before deriving the column list. Extracted embedded images are partial evidence; they can omit or separate captions and reorder the intended layout. Compare the final ordered captions/fields and editable columns with the full slide and latest user corrections. A rendering or temporary extraction belongs outside the project source tree.

For new controls, follow [user-control selection and initialization](user-controls.md). Prefer appropriate user controls from the current project and retain their constructor, initialization, and inherited defaults unless a property has a specific requirement. This applies to all user controls.

Keep static fields and control/column/Repository creation, layout, and properties in Designer. Helper-based construction that Visual Studio Designer cannot read is a compatibility defect. Keep business logic and dynamic binding in the current framework's code-behind.

This does not move all event subscriptions into Designer. Follow the existing screen's [coding style](coding-style.md): connect named handlers after InitializeComponent in the constructor, without duplicating existing subscriptions.

Read and retain current UserControl defaults for width, height, AutoHeight, buttons, and alignment. Use default width/height as the floor for new controls; expand for long content, and shrink only for an explicit compact-size requirement. Do not hardcode 100x25 or a particular font for all controls; an explicit size for the current screen still takes precedence. Check right-side lookup/date buttons in the rendered form, since their initialization can live in Designer rather than the user-control constructor. Preserve user-edited font and Visible values. Align TabIndex with the specified input order, including container order.

Follow [DataWindowToXml rules](grid-layout.md) for grid defaults, Appearance, and editing modes. Do not extend centered headers to cell alignment. Connect numbers to the actual Spin Repository, codes/display values to lookup binding, and buttons to real actions. A request for a Spin Repository alone does not justify EditMask. Preserve its actual creation and shared-initialization defaults; add display/edit format settings only for the verified missing behavior. Review callbacks and helper paths that override the same behavior. Keep permitted report expression formats in their report scope.

Check default counts, summaries, group footer/merge/EvenRow, and requested display locations. Use current project naming such as colList_, colDetail_, or colTABLE_FIELD. Correct names without bindings are incomplete.

Check the actual referenced DevExpress version/APIs and csproj/.resx registration. Do not apply this UI contract wholesale to MAUI/PDA.

Do not add business-manager, DB, or Task cleanup to Designer Dispose. Attach required cleanup to the actual shutdown/cancellation lifecycle in current code-behind without duplicating inherited/partial Dispose implementations. Successfully reopening Designer does not verify Task cleanup during shutdown.

If column widths or numeric editors change after a query or resize, also trace runtime overwrites using [screen behavior contracts](screen-behavior.md).
