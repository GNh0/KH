# DataWindow Layout Mapping

This reference captures the packaged DataWindow-to-grid behavior. DevExpress XML is the deterministic converter output, but generated C# controls must still follow the target-project/custom -> DevExpress -> WinForms fallback order.

## DataWindowToXml-compatible rule

The known converter is a narrow SRD column helper:

- read `.srd`, `.sru`, or `.txt` as UTF-8 or EUC-KR;
- split on `column=(...)`;
- read `name=...`;
- uppercase the column name;
- generate DevExpress `XtraSerializer` GridView XML as a portable column layout artifact;
- use `FieldName=<COLUMN>`, `Caption=<COLUMN>`, and `Name=<prefix><COLUMN>`;
- default prefix is `colList_`;
- default GridView name is `gridView1`;
- set header and cell font to `Tahoma, 9pt`;
- set header alignment center;
- set `Visible=true`, `VisibleIndex=index`;
- set `ColumnAutoWidth=false`, `ShowFooter=true`, and `ShowAutoFilterRow=true`.

Use `src.skills.pb_to_csharp_migration.extract_datawindow_columns` and `generate_devexpress_grid_xml` for deterministic generation.

## What it does not do

The narrow converter does not map:

- PB x/y/w/h coordinate geometry;
- band/header/detail/footer layout;
- text labels;
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
- Detail entry screens: derive fields and validation from DataWindow metadata, but choose controls from the target form style using the same fallback order.
- Reports/print forms: use the existing report designer, output PDF, screenshot, or printed form as the visual contract when available.
- Complex layouts: produce a wireframe or mapping table first. Do not pretend the XML helper is full layout migration.

## Naming rule

Grid columns should preserve uppercase field names and use the configured prefix for control `Name`. If the target screen already has a prefix convention, use that convention. Otherwise use `colList_`.
