# Packaged SQL Formatting Style Contract

Use this standalone fallback only when no host-local `sql-formatting` contract is available. Exact user constraints and source SQL remain authoritative.

## Formatting Boundary

Formatting may change whitespace, safe identifier/keyword case, and aliases covered by a complete approved plan. It preserves the ordered token stream for every T-SQL statement, including `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `MERGE`, DDL, transactions, and control flow.

Preserve exactly:

- object, column, variable, parameter, and function identity;
- operators, expressions, assignments, predicates, joins, grouping, ordering, and statement order;
- string and numeric literals;
- comments and commented-out SQL;
- result columns and output aliases;
- types, lengths, defaults, transaction behavior, and procedure side effects;
- every scalar function call.

Any CTE/temp-table introduction, scalar-to-join conversion, optional-token addition/removal, predicate rewrite, or query-shape change is not formatting.

## Case and Identifiers

- Uppercase SQL keywords and ordinary identifiers outside strings/comments.
- Preserve string and comment content exactly.
- PowerBuilder host-variable spelling after `:` may remain caller-controlled.
- Do not change quoted or bracketed identifier identity.

## Alias Roles

Business grouping is reviewer/LLM judgment supported by concrete source references. Python does not infer roles from table names, repeated object names, or source order.

- Each scope has exactly one main source, and it is `A`. Main aliases `A1`, `A2`, and later are invalid.
- Each subsequent distinct business-role family advances through `B`, `C`, `D`, and so on.
- A singleton non-main family uses its bare letter.
- Multiple sibling sources in one non-main family use suffixes from the first member, such as `B1`, `B2`; the next distinct family then advances to `C`.
- Role letters are sequential; do not skip a family.
- `T`, `T1`, and related families are reserved for derived-query internals.
- A plan is per scope and covers every declaration/reference affected by an alias change.
- Numbered main-family declaration aliases (`A1`, `A2`, and later) are invalid in every parsed scope even when aliases are unchanged. Numbered non-main families such as `B1`/`B2` are valid.
- Every changed scope supplies one or more structured basis objects with `kind="reviewer_approved_business_role"`, a controlled reviewer artifact URI `source` using the `review`, `spec`, `ticket`, or `design` scheme, literal `reviewer_approved=true`, and `role_names` that exactly cover the scope's declared role names. The only compatibility form is `review://<review-id>/<declared-role-names>-roles`, whose URI scheme and role path explicitly declare reviewer-approved business-role evidence. Other strings and identity/order URI schemes do not satisfy this evidence contract.
- If evidence is missing, retain existing aliases. Never guess a role.

### Non-Normative Example

If reviewed caller/source evidence says `SALES_ORDER` is the driver, two `SALES_ORDER_LINE` sources are sibling line roles, and `STATUS_CODE` is a distinct status role, the aliases are `A`, `B1`, `B2`, and `C`. The repeated `SALES_ORDER_LINE` object name does not establish sibling membership by itself; that grouping comes from the reviewed business-role evidence.

## Stored Procedures

Every stored-procedure draft or cleanup deliverable includes the standard metadata separator. Preserve an existing metadata block and values. Never invent `AUTHOR`; include an author line only when the source or caller provides it. `DESCRIPTION` must state the actual procedure purpose, not a generic label. Do not invent unsupported dates or history.

```sql
-- =============================================
-- DESCRIPTION: 주문 조회
-- =============================================
CREATE OR ALTER PROCEDURE [DBO].[SP_ORDER_SELECT]
```

Adding a missing metadata block to existing SQL changes comment tokens. Treat that as an explicit cleanup edit and do not report the pair as formatting-preserved.

Parameter rules:

- Preserve every existing parameter name, type, length, direction, order, and default exactly.
- Do not apply a universal `= NULL` rule.
- For a new procedure, only caller-provided inputs are procedure parameters.
- Values derived inside the procedure are local variables declared and assigned with `DECLARE`/`SET` (or the established local assignment style), not invented input parameters.
- Put the first parameter on the line after the procedure name; use leading commas for later parameters.

```sql
-- =============================================
-- DESCRIPTION: 주문 조회
-- =============================================
CREATE OR ALTER PROCEDURE [DBO].[SP_ORDER_SELECT]
      @COMPANY_CD    VARCHAR(2)
    , @ORDER_NO      VARCHAR(20) = 'CURRENT'
AS
BEGIN
    DECLARE @TODAY CHAR(8)

    SET @TODAY = CONVERT(CHAR(8), GETDATE(), 112)
END
```

The non-null default above is an example of a caller/source-provided default, not a fallback policy.

## SELECT and JOIN Layout

- Keep the first projection after `SELECT`; put later projections on leading-comma lines.
- Preserve `AS` tokens when present; do not add/remove optional tokens under a formatting-equivalence claim.
- Parenthesize existing `CASE` expressions as required by the selected style only when the token change is explicitly accepted; otherwise report the difference.
- Use eight spaces before a top-level `JOIN`; align `ON` and following `AND` terms.
- Preserve join type, source order, and every condition.

```sql
SELECT A.ORDER_NO
     , B.QUANTITY
FROM ORDER_HEADER A
        LEFT OUTER JOIN ORDER_DETAIL B
                     ON A.COMPANY_CD = B.COMPANY_CD
                     AND A.ORDER_NO = B.ORDER_NO
```

## INSERT INTO ... SELECT

For wide business mappings, keep target columns and source expressions in comparable grouped horizontal rows. Wrap only an individual long expression. Do not reorder values or convert the whole mapping to one-column-per-line unless explicitly requested outside formatting preservation.

## Predicates, Control Flow, and Comments

- Keep logical operators, grouping, branches, and statement order unchanged.
- Do not add `ELSE`, rewrite `AND` to `OR`, reorder `ORDER BY`, or alter `UPDATE SET`/`INSERT VALUES` expressions.
- Keep comments as lexer tokens. A `--` sequence inside a string is string content, not a comment.
- Keep commented conditions commented and preserve localized business text exactly.

## CTEs, Temporary Tables, and Guards

Formatting preserves existing CTEs and temporary tables and never introduces or removes them. A concrete reason may document a separately scoped design change, but it cannot waive token preservation.

Preserve existing `IF EXISTS` shape. New guards should use established direct joins or simple predicates; do not introduce nested `WHERE ... IN/EXISTS/(SELECT ...)` as a formatting preference.

## Scalar-Function-to-Join Refactors

Formatting retains every scalar function. A function or table name never proves lookup behavior.

For a separately requested conversion, inspect the actual function definition from DB/MCP/project source when available and prove:

1. the function is a pure deterministic lookup;
2. the exact source table, key mappings, filters, return expression, and null behavior;
3. zero-or-one match cardinality for each outer row;
4. equivalent unmatched-row behavior;
5. why a join is preferable for this query;
6. externally correlated DB/result comparison for semantic verification.

Retain the function and mark conversion `blocked`/`not_proven` when source is unavailable or behavior includes calculation, aggregation, security filtering, dynamic SQL/state, ambiguity, side effects, or uncertain cardinality. Python checks evidence completeness and hash correlation only.

## Output Priority

1. Preserve exact behavior-sensitive tokens.
2. Apply only an approved complete alias plan.
3. Apply style lint without semantic drift.
4. Report encoding and integrity limits.
5. Keep semantic status `not_proven` without trusted correlated external evidence.
