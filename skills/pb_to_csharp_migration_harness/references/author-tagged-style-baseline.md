# Author-Tagged SP To C# Style Baseline

This baseline is the bundled evidence for the user's C_KONE110/KH-style PB-to-C# migration output. It is not a generic TY, KoneLib, or DevExpress style guide.

Use this file when a task asks to follow procedures or C# programs written by `KH`, `근호`, or `장근호`, or when a C_KONE110-like migration target needs the user's house style.

## Baseline Rule

Primary style evidence must be selected in this order:

1. Find stored procedures whose definition contains the author text `KH`, `근호`, or `장근호`.
2. Normalize the program key from the procedure name:
   - remove the leading `sp_`;
   - remove trailing `_SELECT` or `_SAVE`;
   - preserve popup suffixes such as `_POP`, `_COPYPOP`, and `_USERPOP`.
3. Find the matching C# screen source by the normalized program key.
4. Use only that matched C# source and its `.Designer.cs` as primary style evidence.
5. If the program has no matching C# screen source, treat the SP as SQL evidence only.
6. Do not use arbitrary same-project C# files as primary style evidence when matched author-tagged evidence exists.

`SA900100` is a current repair target. Do not use its generated state as a seed baseline until it has passed the verifier; use the pre-existing matched programs plus same-module evidence such as `SA800100` for style.

## Snapshot

- Snapshot date: 2026-07-03
- DB source: `C_KONE110` `SYS.OBJECTS` + `SYS.SQL_MODULES`
- SP selector: procedure definition contains `KH`, `근호`, or `장근호`
- SP count: 62
- Normalized program key count: 41
- C# source root used for mapping: `C:\Users\KONEIT\Desktop\Source\TY\C_KONE110_1\Programs`
- Primary C# baseline files analyzed: 37
- Designer files analyzed: 37
- Current target excluded from seed baseline: `SA900100`
- SP-only or non-screen mappings: `SA116T`, `PopDwgnoFrm`, `popSendMail`

## Author-Tagged SP Dataset

| Program key | Procedure | Author hint |
| --- | --- | --- |
| AS100100 | sp_AS100100_SAVE | 근호 |
| AS100100 | sp_AS100100_SELECT | 근호 |
| AS100110 | sp_AS100110_SAVE | 근호 |
| AS100110 | sp_AS100110_SELECT | 근호 |
| AS200100 | sp_AS200100_SELECT | KH |
| AS200110 | sp_AS200110_SELECT | KH |
| BA000100 | sp_BA000100_SAVE | 장근호 |
| BA000100 | sp_BA000100_SELECT | 근호 |
| BA000200 | sp_BA000200_SAVE | 장근호 |
| BA000200 | sp_BA000200_SELECT | 근호 |
| BA000500 | sp_BA000500_SAVE | 장근호 |
| BA000500 | sp_BA000500_SELECT | 근호 |
| BA000600 | sp_BA000600_SAVE | 장근호 |
| BA000600 | sp_BA000600_SELECT | 근호 |
| BA000700 | sp_BA000700_SAVE | 근호 |
| BA000700 | sp_BA000700_SELECT | 근호 |
| DE000500 | sp_DE000500_SAVE | 근호 |
| DE000500 | sp_DE000500_SELECT | 근호 |
| DE000600 | sp_DE000600_SAVE | 근호 |
| DE000600 | sp_DE000600_SELECT | 근호 |
| DE000700 | sp_DE000700_SAVE | 근호 |
| DE000700 | sp_DE000700_SELECT | 근호 |
| DE100100 | sp_DE100100_SELECT | 근호 |
| DE600100 | sp_DE600100_SELECT | 근호 |
| MA100100 | sp_MA100100_SAVE | 근호 |
| MA100100 | sp_MA100100_SELECT | 근호 |
| MA100100_POP | sp_MA100100_POP_SELECT | 근호 |
| MA100200 | sp_MA100200_SAVE | 근호 |
| MA100200 | sp_MA100200_SELECT | 근호 |
| MA200100 | sp_MA200100_SAVE | 근호 |
| MA200100 | sp_MA200100_SELECT | 근호 |
| MA400100 | sp_MA400100_SAVE | KH |
| PopDwgnoFrm | sp_PopDwgnoFrm_SELECT | 근호 |
| popSendMail | sp_popSendMail_SAVE | 근호 |
| popSendMail | sp_popSendMail_SELECT | 근호 |
| PR100350 | sp_PR100350_SAVE | KH |
| PR100350_USERPOP | sp_PR100350_USERPOP_SELECT | 근호 |
| PR300100 | sp_PR300100_SAVE | 근호 |
| PR300100 | sp_PR300100_SELECT | KH |
| PR300110 | sp_PR300110_SAVE | 근호 |
| PR300110 | sp_PR300110_SELECT | KH |
| PR300120 | sp_PR300120_SELECT | KH |
| PR300500 | sp_PR300500_SAVE | 근호 |
| PR300500 | sp_PR300500_SELECT | 근호 |
| PR600100 | sp_PR600100_SELECT | KH |
| PR600200 | sp_PR600200_SELECT | KH |
| QC000100 | sp_QC000100_SAVE | KH |
| QC000100 | sp_QC000100_SELECT | KH |
| QC100100 | sp_QC100100_SAVE | 근호 |
| QC100100 | sp_QC100100_SELECT | 근호 |
| SA100100 | sp_SA100100_SAVE | 근호 |
| SA100100 | sp_SA100100_SELECT | 근호 |
| SA100100_COPYPOP | sp_SA100100_COPYPOP_SAVE | 근호 |
| SA100110 | sp_SA100110_SELECT | 근호 |
| SA116T | sp_SA116T_SAVE | 근호 |
| SA200100 | sp_SA200100_SELECT | 근호 |
| SA200150 | sp_SA200150_SELECT | 근호 |
| SA400100 | sp_SA400100_SAVE | KH |
| SA800100 | sp_SA800100_SAVE | 근호 |
| SA800100 | sp_SA800100_SELECT | 근호 |
| SA900100 | SP_SA900100_SELECT | 근호 |
| TEST | sp_TEST_SELECT | 근호 |

## Program-To-C# Mapping

These are the same-name primary screen mappings under the active source root. Backups and generated repair targets are not used as primary style evidence.

| Program key | Primary C# evidence |
| --- | --- |
| AS100100 | `Programs\50.품질(QC)\Konesystem.QC02\AS100100.cs`, `.Designer.cs` |
| AS100110 | `Programs\50.품질(QC)\Konesystem.QC02\AS100110.cs`, `.Designer.cs` |
| AS200100 | `Programs\50.품질(QC)\Konesystem.QC02\AS200100.cs`, `.Designer.cs` |
| AS200110 | `Programs\50.품질(QC)\Konesystem.QC02\AS200110.cs`, `.Designer.cs` |
| BA000100 | `Programs\10.기준(BA)\Konesystem.BA01\BA000100.cs`, `.Designer.cs` |
| BA000200 | `Programs\10.기준(BA)\Konesystem.BA01\BA000200.cs`, `.Designer.cs` |
| BA000500 | `Programs\10.기준(BA)\Konesystem.BA01\BA000500.cs`, `.Designer.cs` |
| BA000600 | `Programs\10.기준(BA)\Konesystem.BA01\BA000600.cs`, `.Designer.cs` |
| BA000700 | `Programs\10.기준(BA)\Konesystem.BA01\BA000700.cs`, `.Designer.cs` |
| DE000500 | `Programs\60.설계(DE)\Konesystem.DE01\DE000500.cs`, `.Designer.cs` |
| DE000600 | `Programs\60.설계(DE)\Konesystem.DE01\DE000600.cs`, `.Designer.cs` |
| DE000700 | `Programs\60.설계(DE)\Konesystem.DE01\DE000700.cs`, `.Designer.cs` |
| DE100100 | `Programs\60.설계(DE)\Konesystem.DE01\DE100100.cs`, `.Designer.cs` |
| DE600100 | `Programs\60.설계(DE)\Konesystem.DE01\DE600100.cs`, `.Designer.cs` |
| MA100100 | `Programs\30.자재물류(MA)\Konesystem.MA01\MA100100.cs`, `.Designer.cs` |
| MA100100_POP | `Programs\30.자재물류(MA)\Konesystem.MA01\POP\MA100100_POP.cs`, `.Designer.cs` |
| MA100200 | `Programs\30.자재물류(MA)\Konesystem.MA01\MA100200.cs`, `.Designer.cs` |
| MA200100 | `Programs\30.자재물류(MA)\Konesystem.MA01\MA200100.cs`, `.Designer.cs` |
| MA400100 | `Programs\30.자재물류(MA)\Konesystem.MA01\MA400100.cs`, `.Designer.cs` |
| PR100350 | `Programs\40.생산(PR)\Konesystem.PR01\PR100350.cs`, `.Designer.cs` |
| PR100350_USERPOP | `Programs\40.생산(PR)\Konesystem.PR01\POP\PR100350_USERPOP.cs`, `.Designer.cs` |
| PR300100 | `Programs\40.생산(PR)\Konesystem.PR01\PR300100.cs`, `.Designer.cs` |
| PR300110 | `Programs\40.생산(PR)\Konesystem.PR01\PR300110.cs`, `.Designer.cs` |
| PR300120 | `Programs\40.생산(PR)\Konesystem.PR01\PR300120.cs`, `.Designer.cs` |
| PR300500 | `Programs\40.생산(PR)\Konesystem.PR01\PR300500.cs`, `.Designer.cs` |
| PR600100 | `Programs\40.생산(PR)\Konesystem.PR01\PR600100.cs`, `.Designer.cs` |
| PR600200 | `Programs\40.생산(PR)\Konesystem.PR01\PR600200.cs`, `.Designer.cs` |
| QC000100 | `Programs\50.품질(QC)\Konesystem.QC01\QC000100.cs`, `.Designer.cs` |
| QC100100 | `Programs\50.품질(QC)\Konesystem.QC01\QC100100.cs`, `.Designer.cs` |
| SA100100 | `Programs\20.영업(SA)\Konesystem.SA01\SA100100.cs`, `.Designer.cs` |
| SA100100_COPYPOP | `Programs\20.영업(SA)\Konesystem.SA01\POP\SA100100_COPYPOP.cs`, `.Designer.cs` |
| SA100110 | `Programs\20.영업(SA)\Konesystem.SA01\SA100110.cs`, `.Designer.cs` |
| SA200100 | `Programs\20.영업(SA)\Konesystem.SA01\SA200100.cs`, `.Designer.cs` |
| SA200150 | `Programs\20.영업(SA)\Konesystem.SA01\SA200150.cs`, `.Designer.cs` |
| SA400100 | `Programs\20.영업(SA)\Konesystem.SA01\SA400100.cs`, `.Designer.cs` |
| SA800100 | `Programs\20.영업(SA)\Konesystem.SA02\SA800100.cs`, `.Designer.cs` |
| TEST | `Programs\10.기준(BA)\Konesystem.BA01\TEST.cs`, `.Designer.cs` |

## C# Style Analysis

Primary C# files analyzed: 37.

| Pattern | Files | Hits |
| --- | ---: | ---: |
| `dbClient.GetDataSetFromSP(...)` | 35 | 38 |
| `CallSelectProcedure(...)` | 31 | 135 |
| `CallViewQuery(...)` | 5 | 43 |
| `SelectType` | 33 | 339 |
| `SearchCommand` | 34 | 136 |
| `SaveCommand` | 31 | 124 |
| `DataUtil.DataTableToXml(...)` | 27 | 71 |
| `dbClient.ExecSPTrn(...)` | 24 | 32 |
| `dbClient.ExecSP(...)` | 5 | 5 |
| `GetFocusedDataRow(...)` | 27 | 74 |
| `dr["..."].ToString()` / `dr?["..."].ToString()` | 20 | 91 |
| `devFnc.InitControl(...)` | 29 | 154 |

Zero-hit generated patterns in these matched sources:

| Generated pattern | Hits |
| --- | ---: |
| `private sealed class` for retrieve context | 0 |
| `class *Context` / `Get*Context(...)` | 0 |
| local `GetEditValue(...)` helper | 0 |
| local `GetColumnText(...)` helper | 0 |
| `dr["FIELD"] == DBNull.Value ? ...` ternary row wrappers | 0 |
| `_selectType == SelectType.DETAIL ? ...` parameter routing | 0 |
| `?? "%"` wildcard null coalescing | 0 |
| `btn*.EditValue == null ? string.Empty : ...` extraction | 0 |
| `string x = Convert.ToString(rad*.EditValue)` local variables | 0 |
| `CallSelectProcedure(..., value + "%", ...)` inline wildcard arguments | 0 |
| C# `custcd = custcd + "%"` / `itemcd = "%"` LIKE parameter shaping | 0 |
| `if (ymd*.EditValue == null) ymd*.SetToDay(0)` inside search/procedure paths | 0 |
| C# split date parameters such as `@YYYY = ymd*.DateTime.Year.ToString()` and `@MM/@BASYYYY = DateTime.Now...` | 0 |
| ad hoc month/year-end `new DateTime(...)` boundary blocks in screen retrieve code | 0 |
| direct `grd*.DataSource = null` reset in KoneLib-style screens | 0 |

## Designer Style Analysis

Designer files analyzed: 37.

| Pattern | Files | Hits |
| --- | ---: | ---: |
| `u_GridControl` | 35 | 221 |
| `u_GridView` | 21 | 235 |
| `u_TextEdit` | 25 | 1990 |
| `u_ButtonEdit` | 11 | 176 |
| `u_DateEdit` | 28 | 206 |
| `u_SpinEdit` | 18 | 922 |
| `u_RadioButton` | 16 | 265 |
| `u_CheckEdit` | 12 | 246 |
| `BindingField = ...` | 31 | 754 |
| explicit `GridColumn col*_<FIELD>` members | 34 | 2336 |
| `Columns.AddRange(...)` | 35 | 93 |
| `AppearanceHeader.Options.UseFont = true` | 34 | 2493 |
| `AppearanceHeader.TextOptions.HAlignment = Center` | 34 | 2578 |
| `AppearanceHeader.TextOptions.VAlignment = Center` | 33 | 2072 |
| `AppearanceCell.Options.UseFont = true` | 35 | 2432 |
| `.ColumnEdit = this.rps...` | 26 | 387 |
| `RepositoryItemSpinEdit` | 27 | 791 |
| `TabIndex = ...` | 37 | 1911 |

## C# Generation Rules From The Analysis

- Use same-program matched source first. For `sp_SA800100_SELECT`, use `SA800100.cs` and `SA800100.Designer.cs`, not an arbitrary C# file.
- For a current repair target such as `SA900100`, do not treat generated code as proof of style. Use established author-tagged mappings and same-module neighbors as evidence, then verify the target.
- Preserve existing command and event flow: `SearchCommand`, `SaveCommand`, `ClearCommand`, direct event handlers, local procedure-call methods, and direct grid/control binding.
- `CallSelectProcedure(...)` and `CallViewQuery(...)` are valid when already present or when the matched source family proves them.
- Keep procedure parameters explicit and near `dbClient.GetDataSetFromSP(...)`.
- Do not generate `RetrieveContext`, private DTOs, generic `GetEditValue(...)`, generic `GetColumnText(...)`, or broad value-normalization helpers.
- Do not wrap focused-row values in `DBNull.Value ? ...` ternaries for ordinary detail lookup code unless the same target screen proves that pattern.
- Do not route search/detail parameters through `_selectType == SelectType.DETAIL ? ...` ternaries. Keep list/detail branches explicit.
- Do not use `?? "%"` as a generated wildcard fallback unless the matched source proves it.
- Do not inline LIKE wildcard shaping in `CallSelectProcedure(...)` call-site arguments such as `btnCUSTCD.Text + "%"` or `dr["ITEMCD"].ToString() + "%"`.
- Do not shape stored-procedure search parameters in C# with `custcd = custcd + "%"`, `itemcd = itemcd + "%"`, or `itemcd = "%"`. Pass raw values from controls/rows and let the stored procedure own LIKE defaults and wildcard handling.
- Do not add `if (ymd*.EditValue == null) ymd*.SetToDay(0)` inside search or stored-procedure-call paths. Initialize date controls in `Load`/`Clear`, or validate and return before execution.
- Do not split a `u_DateEdit` value into C# parameters such as `@YYYY = ymd*.DateTime.Year.ToString()`, `@MM = DateTime.Now.Month...`, or `@BASYYYY = DateTime.Now.Year...`. Pass the target-style raw date value with `YYYYMMDD()` and let the stored procedure derive related year/month/base-date parameters.
- Do not generate ad hoc month-end or year-end `new DateTime(...)` or boundary string blocks in screen retrieve code. Pass raw date/year values and let the stored procedure own derived date boundaries unless matched source evidence proves otherwise.
- Do not create `string gb = Convert.ToString(radGB.EditValue)` or similar generated radio locals. Pass or read the control value in the existing style.
- Use `devFnc.InitControl(...)` for grid/control reset paths when the matched KoneLib source family does that. Do not generate direct `grd*.DataSource = null` resets unless active target evidence proves that exact local pattern.

## Designer Generation Rules From The Analysis

- Preserve project controls before generic DevExpress controls: `u_GridControl`, `u_TextEdit`, `u_ButtonEdit`, `u_DateEdit`, `u_SpinEdit`, `u_RadioButton`, and `u_CheckEdit`.
- Preserve `BindingField`, `TabIndex`, `Location`, `Size`, parent containment, and existing `Properties.*` assignments when a Designer file exists.
- Generate explicit `GridColumn` members with names such as `colList_ITEMCD`, `colDetail_ORDNUM`, `colSA110T_QTY`, or `colPOR_PORSEQ`.
- Register grid columns through `Columns.AddRange(...)`, not runtime `Columns.Add`, `Columns.AddField`, or helper-generated names.
- Grid header defaults should include `AppearanceHeader.Options.UseFont = true`, horizontal center alignment, and vertical center alignment where target columns use them.
- Grid cell defaults should include `AppearanceCell.Options.UseFont = true` where target columns use it.
- Numeric grid columns such as AMT, QTY, UNP, WGT, PRICE, RATE, COST, and TOTAL should use a `RepositoryItemSpinEdit` through `ColumnEdit`; do not rely on `DisplayFormat` as the primary numeric behavior.

## SP Rules From The Dataset

- Keep the metadata block immediately above `CREATE/ALTER PROCEDURE`:

```sql
-- =============================================
-- AUTHOR:      <author>
-- CREATE DATE: <date>
-- DESCRIPTION: <program description>
-- =============================================
```

- Preserve procedure names, parameter names, Korean literals, comments, table names, aliases, calculations, and row contracts.
- Do not add default `@WORKTYPE = ''`, broad `@CUSTCD = '%'`, `@ITEMCD = '%'`, `@GUBUN = 'T'`, or `@GB = '1'` unless the verified procedure evidence has that exact contract.
- Do not add up-front parameter-normalization blocks such as `SET @WORKTYPE = ISNULL(...)` or `SET @PARAM = CASE WHEN ISNULL(...)`.
- Do not invent schema-only `SELECT TOP 0` fallback result sets for missing evidence.
- Do not introduce CTEs, `#` temp tables, `MERGE`, or `NOT EXISTS` by default.
- Keep wide `INSERT INTO (...) SELECT ...` mappings in grouped horizontal rows when the source style uses that layout.

## Baseline Query

```sql
SELECT O.NAME, M.DEFINITION
FROM SYS.OBJECTS O
     INNER JOIN SYS.SQL_MODULES M
             ON O.OBJECT_ID = M.OBJECT_ID
WHERE O.TYPE = 'P'
  AND (
         M.DEFINITION LIKE N'%장근호%'
      OR M.DEFINITION LIKE N'%근호%'
      OR M.DEFINITION LIKE N'%KH%'
      );
```
