# Author-Tagged C# / SP Style Baseline

This bundled baseline captures the source data used to model the user's C_KONE110/KH-style PB-to-C# migration output. Use it when the user asks to follow procedures or C# programs written by `KH`, `근호`, or `장근호`, or when a migration target is C_KONE110-like.

This is evidence, not decoration. Do not replace it with a few representative files. If local DB/source access is unavailable, use this snapshot as the fallback style dataset.

## Snapshot

- Snapshot date: 2026-07-02
- DB source: `C_KONE110` `SYS.OBJECTS` + `SYS.SQL_MODULES`
- SP selector: procedure definition contains `KH`, `근호`, or `장근호`
- SP count: 61
- Normalized program key count: 40
- C# source root used for mapping: `C:\Users\KONEIT\Desktop\Source\TY\C_KONE110_1`
- C# source-bearing program mappings: 39
- SP-only or locally unmapped program key: `SA116T`
- Common popup/platform mappings are included: `PopDwgnoFrm`, `popSendMail`

## Complete SP Dataset

| Program key | Procedure | Author hint | Definition length | Arithabort | Bad `SET @WORKTYPE = ISNULL` | Bad `@WORKTYPE = ''` |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| AS100100 | sp_AS100100_SAVE | 근호 | 32875 | 0 | 0 | 0 |
| AS100100 | sp_AS100100_SELECT | 근호 | 10189 | 1 | 0 | 0 |
| AS100110 | sp_AS100110_SAVE | 근호 | 7023 | 0 | 0 | 0 |
| AS100110 | sp_AS100110_SELECT | 근호 | 6368 | 1 | 0 | 0 |
| AS200100 | sp_AS200100_SELECT | KH | 1792 | 1 | 0 | 0 |
| AS200110 | sp_AS200110_SELECT | KH | 2527 | 1 | 0 | 0 |
| BA000100 | sp_BA000100_SAVE | 장근호 | 4610 | 0 | 0 | 0 |
| BA000100 | sp_BA000100_SELECT | 근호 | 1166 | 1 | 0 | 0 |
| BA000200 | sp_BA000200_SAVE | 장근호 | 4647 | 0 | 0 | 0 |
| BA000200 | sp_BA000200_SELECT | 근호 | 1122 | 1 | 0 | 0 |
| BA000500 | sp_BA000500_SAVE | 장근호 | 13849 | 0 | 0 | 0 |
| BA000500 | sp_BA000500_SELECT | 근호 | 6596 | 1 | 0 | 0 |
| BA000600 | sp_BA000600_SAVE | 장근호 | 5294 | 0 | 0 | 0 |
| BA000600 | sp_BA000600_SELECT | 근호 | 3694 | 1 | 0 | 0 |
| BA000700 | sp_BA000700_SAVE | 근호 | 6378 | 0 | 0 | 0 |
| BA000700 | sp_BA000700_SELECT | 근호 | 3126 | 1 | 0 | 0 |
| DE000500 | sp_DE000500_SAVE | 근호 | 4715 | 0 | 0 | 0 |
| DE000500 | sp_DE000500_SELECT | 근호 | 2191 | 1 | 0 | 0 |
| DE000600 | sp_DE000600_SAVE | 근호 | 16750 | 0 | 0 | 0 |
| DE000600 | sp_DE000600_SELECT | 근호 | 7370 | 1 | 0 | 0 |
| DE000700 | sp_DE000700_SAVE | 근호 | 43650 | 0 | 0 | 0 |
| DE000700 | sp_DE000700_SELECT | 근호 | 29316 | 1 | 0 | 0 |
| DE100100 | sp_DE100100_SELECT | 근호 | 4773 | 0 | 0 | 0 |
| DE600100 | sp_DE600100_SELECT | 근호 | 6646 | 1 | 0 | 0 |
| MA100100 | sp_MA100100_SAVE | 근호 | 18473 | 0 | 0 | 0 |
| MA100100 | sp_MA100100_SELECT | 근호 | 28113 | 1 | 0 | 0 |
| MA100100_POP | sp_MA100100_POP_SELECT | 근호 | 10055 | 1 | 0 | 0 |
| MA100200 | sp_MA100200_SAVE | 근호 | 8290 | 0 | 0 | 0 |
| MA100200 | sp_MA100200_SELECT | 근호 | 5820 | 1 | 0 | 0 |
| MA200100 | sp_MA200100_SAVE | 근호 | 11899 | 0 | 0 | 0 |
| MA200100 | sp_MA200100_SELECT | 근호 | 9725 | 1 | 0 | 0 |
| MA400100 | sp_MA400100_SAVE | KH | 14732 | 0 | 0 | 0 |
| PopDwgnoFrm | sp_PopDwgnoFrm_SELECT | 근호 | 2318 | 1 | 0 | 0 |
| popSendMail | sp_popSendMail_SAVE | 근호 | 924 | 1 | 0 | 0 |
| popSendMail | sp_popSendMail_SELECT | 근호 | 720 | 1 | 0 | 0 |
| PR100350 | sp_PR100350_SAVE | KH | 8659 | 0 | 0 | 0 |
| PR100350_USERPOP | sp_PR100350_USERPOP_SELECT | 근호 | 1477 | 1 | 0 | 0 |
| PR300100 | sp_PR300100_SAVE | 근호 | 19628 | 0 | 0 | 0 |
| PR300100 | sp_PR300100_SELECT | KH | 24480 | 1 | 0 | 0 |
| PR300110 | sp_PR300110_SAVE | 근호 | 4639 | 0 | 0 | 0 |
| PR300110 | sp_PR300110_SELECT | KH | 4414 | 1 | 0 | 0 |
| PR300120 | sp_PR300120_SELECT | KH | 3551 | 1 | 0 | 0 |
| PR300500 | sp_PR300500_SAVE | 근호 | 3582 | 0 | 0 | 0 |
| PR300500 | sp_PR300500_SELECT | 근호 | 4122 | 1 | 0 | 0 |
| PR600100 | sp_PR600100_SELECT | KH | 2777 | 1 | 0 | 0 |
| PR600200 | sp_PR600200_SELECT | KH | 6164 | 1 | 0 | 0 |
| QC000100 | sp_QC000100_SAVE | KH | 16549 | 0 | 0 | 0 |
| QC000100 | sp_QC000100_SELECT | KH | 9581 | 1 | 0 | 0 |
| QC100100 | sp_QC100100_SAVE | 근호 | 2335 | 0 | 0 | 0 |
| QC100100 | sp_QC100100_SELECT | 근호 | 13601 | 1 | 0 | 0 |
| SA100100 | sp_SA100100_SAVE | 근호 | 48436 | 0 | 0 | 0 |
| SA100100 | sp_SA100100_SELECT | 근호 | 17179 | 1 | 0 | 0 |
| SA100100_COPYPOP | sp_SA100100_COPYPOP_SAVE | 근호 | 11555 | 1 | 0 | 0 |
| SA100110 | sp_SA100110_SELECT | 근호 | 14186 | 1 | 0 | 0 |
| SA116T | sp_SA116T_SAVE | 근호 | 22203 | 0 | 0 | 0 |
| SA200100 | sp_SA200100_SELECT | 근호 | 9893 | 1 | 0 | 0 |
| SA200150 | sp_SA200150_SELECT | 근호 | 7663 | 1 | 0 | 0 |
| SA400100 | sp_SA400100_SAVE | KH | 14811 | 0 | 0 | 0 |
| SA800100 | sp_SA800100_SAVE | 근호 | 6394 | 0 | 0 | 0 |
| SA800100 | sp_SA800100_SELECT | 근호 | 55084 | 1 | 0 | 0 |
| TEST | sp_TEST_SELECT | 근호 | 2856 | 1 | 0 | 0 |

## Complete Program-to-C# Mapping

| Program key | Mapped C# evidence |
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
| PopDwgnoFrm | `Programs\60.설계(DE)\Konesystem.DE01\POP\DEDWGPOP.cs`; platform popup also calls `sp_PopDwgnoFrm_SELECT` through `KonesystemPlatform\KoneLib.PgmBase\PopDwgFrm.cs` |
| popSendMail | `KonesystemPlatform\KoneLib.PgmBase\PopSendMail.cs` |
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
| SA116T | No C# class/procedure-call match found in `C_KONE110_1`; treat as SP-only evidence unless current source proves otherwise. |
| SA200100 | `Programs\20.영업(SA)\Konesystem.SA01\SA200100.cs`, `.Designer.cs` |
| SA200150 | `Programs\20.영업(SA)\Konesystem.SA01\SA200150.cs`, `.Designer.cs` |
| SA400100 | `Programs\20.영업(SA)\Konesystem.SA01\SA400100.cs`, `.Designer.cs` |
| SA800100 | `Programs\20.영업(SA)\Konesystem.SA02\SA800100.cs`, `.Designer.cs` |
| TEST | `Programs\10.기준(BA)\Konesystem.BA01\TEST.cs`, `.Designer.cs` |

## C# Style Frequency Summary

Primary C# files analyzed: 39.

| Pattern | Count |
| --- | ---: |
| `dbClient.GetDataSetFromSP(...)` | 36 |
| `SelectType` enum/use | 35 |
| `SearchCommand` | 34 |
| `SaveCommand` | 31 |
| `DataUtil.DataTableToXml(...)` | 27 |
| `dbClient.ExecSPTrn(...)` | 25 |
| `DialogResult.OK` | 17 |
| `SetModified(...)` | 11 |
| `CallViewQuery(...)` | 6 |
| `PopCustFrm` | 6 |
| `dbClient.ExecSP(...)` | 5 |
| `PopItemFrm` | 3 |
| `dbClient.GetDataTableFromSP(...)` | 2 |
| `private sealed class` | 0 |
| `class *Context` / `Get*Context(...)` | 0 |
| local `GetEditValue(...)` helper | 0 |
| local `GetColumnText(...)` helper | 0 |

## C# Generation Rules From This Baseline

- Prefer the existing screen's direct event flow: constructor event wiring, `SearchCommand`, `SaveCommand`, `ClearCommand`, local procedure-call methods, and direct grid binding.
- Keep ordinary retrieve parameters as local variables near the procedure call. Do not generate internal DTO/context classes such as `RetrieveContext`.
- Do not generate generic local helpers such as `GetEditValue(...)` or `GetColumnText(...)` for ordinary screen code. Use the target's existing direct access style unless the current screen already proves such helpers.
- Preserve project controls before generic DevExpress controls. In C_KONE110-like targets, `u_GridControl`, `u_TextEdit`, `u_ButtonEdit`, `u_DateEdit`, `u_RadioButton`, and repository controls must be preserved when present.
- A name field such as `txtCUSTNM` is a text edit by default. Do not infer a date control from `txt*`.
- Date/year fields use the target date-edit convention such as `ymd*` when the target source proves it.
- Use explicit Designer grid column members and `Columns.AddRange` with `colList_*`, `colDetail_*`, `col<TABLE>_*`, or `col<PURPOSE>_*` names. Runtime column helper generation is not the C_KONE110 baseline.
- Numeric grid columns such as AMT/QTY/UNP/WGT/PRICE/RATE/COST/TOTAL should use `RepositoryItemSpinEdit` through `ColumnEdit`. Do not rely on `GridColumn.DisplayFormat` as the primary numeric formatting path.

## SP Style Frequency Summary

Author-tagged SPs analyzed: 61.

| Pattern | Count |
| --- | ---: |
| `SET ARITHABORT ON` | 36 |
| `SET @WORKTYPE = ISNULL(...)` | 0 |
| `@WORKTYPE VARCHAR(20) = ''` | 0 |

Representative parameter snippets from `sp_SA100100_SELECT`, `sp_MA100100_SELECT`, `sp_DE000600_SELECT`, `sp_BA000100_SELECT`, and `sp_SA800100_SELECT` use required parameters or `= NULL` defaults. They do not default business filters to `''`, `'%'`, `'T'`, or `'1'` in the procedure signature by default.

## SP Generation Rules From This Baseline

- Preserve existing procedure names, parameter names, branch names, Korean literals, comments, table names, aliases, calculations, and row contracts.
- Keep the standard metadata comment block immediately above `CREATE/ALTER PROCEDURE`: `AUTHOR`, `CREATE DATE`, `DESCRIPTION`, and the separator lines. The author value can follow current target evidence, but the block must not be omitted.
- Use `@WORKTYPE VARCHAR(20) = NULL` or a required `@WORKTYPE` parameter when matching this baseline. Do not default `@WORKTYPE` to `''`.
- Do not add broad parameter defaults such as `@CUSTCD = '%'`, `@ITEMCD = '%'`, `@GUBUN = 'T'`, or `@GB = '1'` unless verified existing target procedure evidence uses those exact defaults.
- Do not add up-front parameter normalization blocks such as `SET @WORKTYPE = ISNULL(@WORKTYPE, '')` or `SET @PARAM = (CASE WHEN ISNULL(@PARAM, '') = '' THEN ... END)` unless verified target procedure evidence already uses the same pattern for that branch.
- For SELECT procedures, include `SET NOCOUNT ON;` and prefer `SET ARITHABORT ON;` when generating C_KONE110/KH-style SELECT output unless local evidence proves the target omits it.
- Do not invent schema-only `SELECT TOP 0` fallback result sets for missing source evidence.
- Do not introduce CTEs, `#` temp tables, `MERGE`, or `NOT EXISTS` by default.
- Keep wide `INSERT INTO (...) SELECT ...` mappings in grouped horizontal rows when the source style uses that layout; do not force one column per line.

## Baseline Queries

SP selector:

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

Program key normalization:

```sql
CASE
    WHEN BASE_NAME LIKE '%[_]SELECT' THEN LEFT(BASE_NAME, LEN(BASE_NAME) - 7)
    WHEN BASE_NAME LIKE '%[_]SAVE' THEN LEFT(BASE_NAME, LEN(BASE_NAME) - 5)
    ELSE BASE_NAME
END
```
