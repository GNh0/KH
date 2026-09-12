# DataWindow and screen mapping

Map PBL/object, base classes, linked DWs, retrieve arguments, SQL, column/compute, protect/taborder, update properties, and events. Reflect groups, panels, grids, captions, column order, and defaults from HTML-to-XML input in the actual layout.

Preserve raw composite-key components and create display keys separately. Derive component counts and business names from input. Migrate read-only/editable states, list/detail connections, selection/focus, user permissions, and lookup/numeric/button Repositories using current C# patterns.

For reports, preserve H/D/F, group, band, and page order. Review shared paths for converting multiple reports to HTML while checking constructor side effects and render order. Check actual contracts for missing bands and empty values. Do not replace output behavior with simple HTML concatenation.
# Generator scope

XML generation/checking in `src.pb.datawindow` reproduces the DataWindowToXml defaults the user restated on 2026-09-08. Apply these [grid defaults](../../csharp-designer-style-harness/references/grid-layout.md) to C# screens too. Do not impose this template's Tahoma 9pt or display values on every existing screen. First inspect actual DataWindow captions and current Designer properties.

`build_csharp_grid_column_designer_plan` returns a draft of a new configuration; it does not replace an entire existing screen. It accepts explicit C# names. Use `column_properties` (field/member name → properties/actual C# expressions) and `view_properties` to prioritize current Font, Visible, alignment, and other settings over the template. Property value `None` omits that assignment. Returned code does not imply actual API/Designer validation.

Like the HTML, default calls generate no AllowEdit, ReadOnly, or OptionsBehavior. Specify only required columns with `column_edit_modes={'FIELD': 'read_only', 'colAction': 'action', 'EDITFIELD': 'editable'}`. read_only sets AllowEdit=false and ReadOnly=true; action sets ReadOnly=true only; editable omits both. Explicit `default_allow_edit=False` generates both ordinary editing-block properties; True omits both. Conflicting explicit modes and property overrides return failure. Do not add EditMask/DisplayFormat when connecting a Spin Repository.

If another grid on the same screen has a Repository for the same numeric field, pass `existing_repository_names=["rpsSpinQTY"]` to the generator. The Detail grid creates `rpsDetailSpinQTY`, connecting ColumnEdit, declaration, registration, and Name together. The default role comes from the generated grd name; specify `repository_role` if the actual role differs. Do not rename existing Repositories. If the role-qualified name also exists, report the collision instead of inventing a numeric suffix.
