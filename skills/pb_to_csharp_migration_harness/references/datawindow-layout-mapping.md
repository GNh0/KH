# DataWindow Layout Mapping

This reference captures the packaged DataWindow-to-grid behavior. DevExpress XML is the deterministic converter output, but generated C# controls must still follow the target-project/custom -> DevExpress -> WinForms fallback order.

## DataWindowToXml-compatible rule

The known converter is a narrow SRD column helper:

- read `.srd`, `.sru`, or `.txt` as UTF-8 or EUC-KR;
- split on `column=(...)`;
- read `name=...`;
- prefer visual `column(...)` entries when present so column order follows the DataWindow layout (`y`, then `x`) instead of blindly trusting `table(column=...)` declaration order;
- match nearby `text(...)` controls to each visual column when possible and use the matched DataWindow caption;
- fall back to the uppercase field name as the caption when no safe caption match exists;
- uppercase the column name;
- generate DevExpress `XtraSerializer` GridView XML as a portable column layout artifact;
- use `FieldName=<COLUMN>`, `Caption=<MATCHED_PB_CAPTION_OR_COLUMN>`, and `Name=<C# column name>`;
- target C# column names follow the existing Designer style: `colList_<COLUMN>` for list/main grids, `colDetail_<COLUMN>` for detail grids, `col<TABLE>_<COLUMN>` when the active screen/table convention uses the source table name, such as `colSA110T_ORDNUM`, or `col<PURPOSE>_<COLUMN>` when table naming is ambiguous and the grid is organized by a business purpose such as `POR`, `BOM`, `ITEM`, or `REQ`;
- target grid control/view names follow the same convention: `grdList/gvwList`, `grdDetail/gvwDetail`, `grd<TABLE>/gvw<TABLE>`, or `grd<PURPOSE>/gvw<PURPOSE>`, such as `grdSA110T/gvwSA110T` or `grdBOM/gvwBOM`;
- default prefix is `colList_`, but generated code must switch to `colDetail_`, `col<TABLE>_`, or `col<PURPOSE>_` when the target screen/input format proves that convention;
- raw DataWindowToXml-style XML helper default GridView name is `gridView1` when no target C# naming context is supplied;
- KH target layout generation should pass the resolved C# view name such as `gvwList`, `gvwDetail`, `gvwSA110T`, or `gvwBOM`;
- set header and cell font to `Tahoma, 9pt`;
- set header alignment center;
- set `Visible=true`, `VisibleIndex=index`;
- set top-level GridView serializer defaults from the attached `DataWindowToXml.html`: `BestFitMaxRowCount=-1`, `PreviewLineCount=-1`, `HorzScrollStep=3`, `FocusRectStyle=CellFocus`, `ScrollStyle=LiveVertScroll, LiveHorzScroll`, `PreviewIndent=-1`, empty `GroupPanelText`, empty `PreviewFieldName`, empty `VertScrollTipFieldName`, `LevelIndent=-1`, `GroupFooterShowMode=VisibleIfExpanded`, empty `NewItemRowText`, `SynchronizeClones=true`, `BorderStyle=Default`, empty `ViewCaption`, `DetailHeight=350`, target view `Name`, `DetailTabHeaderLocation=Top`, and `ActiveFilterEnabled=true`;
- set `OptionsView.ShowViewCaption=false`, `OptionsView.EnableAppearanceEvenRow=true`, `OptionsView.ShowGroupPanel=false`, `OptionsView.ColumnAutoWidth=false`, `OptionsView.ShowFooter=true`, and `OptionsView.ShowAutoFilterRow=true`;
- when generating C# Designer code instead of XML, apply the same safe `OptionsView` defaults to the target GridView so the group panel is hidden and the filter/footer/even-row behavior matches the converter.

Use `src.skills.pb_to_csharp_migration.extract_datawindow_column_specs`, `resolve_csharp_grid_column_prefix`, `resolve_csharp_grid_control_names`, `build_csharp_grid_column_name`, and `generate_devexpress_grid_xml` for deterministic generation.

## What it does not do

The narrow converter does not map:

- PB x/y/w/h coordinate geometry;
- band/header/detail/footer layout;
- text labels that cannot be matched by position;
- computed fields;
- DDDW/dropdowns;
- edit masks;
- protection/read-only rules;
- tab order;
- colors, borders, and conditional formatting;
- retrieve SQL;
- update metadata;
- multi-grid or nested layouts.

When those matter, keep them as migration tasks and ask for SRD/source/screenshot evidence or a target C# layout decision.

## Layout decision rules

- Grid screens: use SRD columns to create grid columns, then apply target-project control naming and binding. If no target grid wrapper exists, use DevExpress GridControl/GridView; if DevExpress is absent, use WinForms DataGridView.
- Detail entry screens: derive fields, captions, editor type hints, and validation from DataWindow metadata or user-described behavior, but choose controls from the target form style using the same fallback order. Use SA100100-style clean alignment: label/editor pairs in fixed rows and columns, consistent label width, editor width, row height, and column gap. Do not copy PB x/y coordinates blindly unless the user asks for exact visual parity.
- Detail editor names should follow the active target project first. Packaged fallback names are field-based: `txtITEMNM` for text, `btnITEMCD` for lookup/button editors, `SpinQty` for SpinEdit, `cboITEMACNT` for lookup/combo, and `chkUSEYN` for boolean fields. Every generated editor must carry the source field name and a `BindingField = "<FIELD>"` assignment.
- Reports/print forms: use the existing report designer, output PDF, screenshot, or printed form as the visual contract when available.
- Complex layouts: produce a wireframe or mapping table first. Do not pretend the XML helper is full layout migration.

## Naming rule

Grid columns should preserve uppercase field names and use the configured prefix for control `Name`. If the target screen already has a prefix convention, use that convention. Otherwise use `colList_`. Common column conventions are `colList_<COLUMN>`, `colDetail_<COLUMN>`, `col<TABLE>_<COLUMN>`, and `col<PURPOSE>_<COLUMN>`. Common grid conventions are `grdList/gvwList`, `grdDetail/gvwDetail`, `grd<TABLE>/gvw<TABLE>`, and `grd<PURPOSE>/gvw<PURPOSE>`.
