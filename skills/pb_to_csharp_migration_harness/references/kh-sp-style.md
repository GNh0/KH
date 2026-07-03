# KH Stored Procedure Style

Use this fixed packaged style before drafting or reviewing SQL Server SELECT/SAVE stored procedures for PB-to-C# migrations. Project-specific procedure names and contracts override this packaged baseline.

This reference is intentionally bundled. Do not query live DB procedures only to discover the style on every run. Refresh this document only when the user explicitly asks to update the style baseline.

When the requested style is the user's C_KONE110/KH/Geunho-authored output, read `author-tagged-style-baseline.md` with this file. That baseline captures the current 62-procedure author-tagged dataset, 41 normalized program mappings, and matched C# evidence used to block shallow generated defaults.

## General rules

- Return full paste-ready SQL when the user asks for a procedure or rewrite.
- Preserve procedure names, parameter names, comments, Korean text, literals, table names, and business keys.
- Keep identifiers uppercase outside string literals/comments.
- Use leading commas for procedure parameters and SELECT columns.
- Put the standard metadata comment block immediately above `CREATE/ALTER PROCEDURE`.
  Keep `AUTHOR`, `CREATE DATE`, and `DESCRIPTION` lines in the block; the author value may follow the target procedure evidence, but the block itself is mandatory.
- Use `@WORKTYPE VARCHAR(20) = NULL` or a required `@WORKTYPE` parameter for C_KONE110/KH-style output. Do not generate `@WORKTYPE = ''`.
- Do not default business filter parameters to `''`, `'%'`, `'T'`, or `'1'` unless verified target procedure evidence uses those exact defaults.
- Do not add up-front `SET @WORKTYPE = ISNULL(...)` or `SET @PARAM = (CASE WHEN ISNULL(...) THEN ... END)` normalization blocks unless verified target procedure evidence already uses that pattern.
- Procedure parameters are values sent by C# or the caller. Values used only for SP-internal helper/calculation work must be local variables declared with `DECLARE` and assigned with `SET`.
- When matched C# call evidence is available, the generated SP signature must not introduce parameters outside that caller `DbParameter` set. Extra calculation values belong in local variables.
- Do not expose derived helper values such as `@YYYY`, `@MM`, `@BASYYYY`, or `@LASTDT` as generated procedure parameters. Accept the raw target-style date input from C# and derive local variables inside the procedure when needed.
- Do not generate `IF ISNULL(@GIJUNDT, ...)`, `IF ISNULL(@YYYY, ...)`, `IF ISNULL(@MM, ...)`, `IF ISNULL(@BASYYYY, ...)`, `IF ISNULL(@LASTDT, ...)`, or direct `IF @GIJUNDT <> '' SET @YYYY = ...` guard/default blocks around date derivation. When a derived local value is needed, use `DECLARE` plus `SET`; do not invent fallback branches unless verified target SP evidence proves that exact shape.
- For C_KONE110/KH-style SELECT procedures, include `SET NOCOUNT ON;` and prefer `SET ARITHABORT ON;` unless current target evidence proves otherwise.
- Keep formatting-only work separate from semantic/performance rewrites.
- Avoid CTEs, `#` temporary tables, `MERGE`, `NOT EXISTS`, and helper `@FIND...` variables by default.
- Prefer direct joins, derived tables, aggregate subqueries, table variables, inline predicates, and existing stored-procedure style.
- Do not present a full migration SELECT/SAVE SP body as complete from only a C# call signature, parameter list, or grid column list. Full SP output needs structured PB/DataWindow SQL, verified existing SP definition evidence, pasted SQL, DB schema evidence, or a clearly approved inferred-draft marker. Do not add source-unbacked `SELECT TOP 0/SELECT TOP (0) CAST/CONVERT/TRY_CONVERT(...)` schema-only fallback blocks.
- Generated migration SP text must pass `verify_pb_migration_sp_generation_contract` before completion claims, then pass the separate SQL formatting verifier when formatted output is shown.

## SELECT style

Required header shape:

```sql
-- =============================================
-- AUTHOR:      근호
-- CREATE DATE: 2026-06-15
-- DESCRIPTION: 총괄조회 조회
-- =============================================
ALTER PROCEDURE [DBO].[SP_SAMPLE_SELECT]
      @WORKTYPE    VARCHAR(20) = NULL
```

- Use branch-based `IF @WORKTYPE = 'LIST'` / `ELSE IF` structure when the source procedure already uses it.
- Use flow aliases such as `A`, `B`, `B1`, `C1`, `C2`; restart aliases per branch where appropriate.
- Use `T`, `TA1`, `TB1` for internal derived-table aliases, not outer query aliases.
- Use inline predicates such as `A.ITEMACNT LIKE ISNULL(@ITEMACNT, '') + '%'` when that is the target style.
- Preserve UI binding columns exactly. If TreeList expects `ID` and `ParentID`, do not rename them.
- Preserve C# grid binding columns exactly. If the C# screen expects fields such as `CUSTNM`, `PRNTITEMNM`, `AMT01`-`AMT12`, `AMTTOT`, `CUSTCD`, or `PRNTITEMCD`, treat missing or renamed result columns as a blocked contract until source evidence proves otherwise.

## SAVE style

- Parse XML with `sp_xml_preparedocument` and `OPENXML` when matching current repo patterns.
- Use `DECLARE @tmp... TABLE (...)` or a table variable for XML rows.
- Validate duplicates and simple blocking conditions before opening a transaction when possible.
- Use transaction only for the real write path.
- Use direct `UPDATE` followed by `INSERT` with `LEFT OUTER JOIN ... IS NULL` anti-match when syncing rows.
- Use logical disable/delete when that is the existing business convention.
- Use the standard logging pattern when available: procedure name, worktype, user, and XML payload through the existing log procedure.

## INSERT INTO ... SELECT layout

For wide ERP insert-select mappings, prefer grouped horizontal layout:

```sql
INSERT INTO SA130T
(
    ORGDIV          , ORDNUM        , ORDSEQ        , PORSEQ
  , PRNTITEMCD      , SPECNUM       , CHLDITEMCD    , CHLDITEMNM
  , REGDT           , REGEMPNO      , REGIP
)
SELECT @ORGDIV      , A.ORDNUM      , A.ORDSEQ      , A.PORSEQ
     , A.PRNTITEMCD , A.SPECNUM     , A.CHLDITEMCD  , A.CHLDITEMNM
     , GETDATE()    , @USERID       , @USERIP
FROM SA130T A
WHERE A.ORGDIV = @ORGDIV;
```

If a single source expression is long because of `CASE`, `ROW_NUMBER`, `ISNULL`, arithmetic, concatenation, or function calls, wrap that expression onto continuation lines while keeping the target/source mapping readable.

## Scalar function rule

Convert scalar functions to joins only when the lookup contract is verified from DB/MCP, source, or host-local style guidance. A known lookup function can become a join only if inputs, output column, and null/default behavior are proven. Unknown functions remain unchanged. Stateful sequence procedures or functions with side effects are never join candidates.
