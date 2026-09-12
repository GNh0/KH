# KH SQL style

Current SQL semantics and explicit requirements take priority. General cleanup includes alias normalization; preserve aliases for “별칭 그대로/정렬만” (keep aliases/format only). Distinguish generation, cleanup, optimization, comparison, and execution.

- Use A for the main query target, B/C/D for subsequent business roles, and B1/B2 for multiple tables within one role group. Use T-family aliases inside derived queries to distinguish scope. Different physical tables can share a business role. Do not assign E/F or E1/E2 solely from BA011T or MAINCD.
- Follow the target's approved uppercase style for keywords and identifiers. Do not change strings, Korean text, or comments. Distinguish table-alias AS from output-column AS.
- Follow the relevant examples' leading commas in SELECT, UPDATE SET, and SP parameters. Take SP parameter defaults from the approved template and actual caller contract.
- For ordinary table JOINs, align ON and the same JOIN's AND with the I in the final IN of JOIN. For derived table JOINs, vertically align the closing ) and ON/AND with the opening (. Place SELECT, FROM, WHERE, GROUP BY, and other clauses inside FROM/JOIN parentheses one space to the right of the opening (. Anchor each nested block to its own opening (. Do not arbitrarily abbreviate LEFT OUTER JOIN.
- Align EXISTS parentheses vertically; start inner SQL on the next line, one space to the right of the opening parenthesis. Keep short GROUP BY/ORDER BY clauses on one line and follow the relevant example's CASE parentheses.
- Match INSERT columns to SELECT/VALUES values using the same horizontal groups, order, tab positions, and line breaks. UPDATE SET uses a vertical list. Aligned text does not replace checking the semantic column/value mapping.
- Preserve JOIN types/order, filters, output fields, literals, and existing comments. When asked to comment out existing logic, do not delete it.

Basic layout example:

```sql
SELECT A.ITEMCD
     , B.ITEMNM
FROM MA210T A
        LEFT OUTER JOIN BA030T B
                     ON A.ITEMCD = B.ITEMCD
WHERE A.ORGDIV = @ORGDIV
```

Distinguish alignment anchors for ordinary table JOINs and derived table JOINs. For a derived JOIN, place the opening `(`, closing `)`, and that JOIN's line-leading `ON`/`AND`/`OR` in the same column. Do not move the closing parenthesis back to the JOIN's LEFT/INNER start. Keep the alias on the closing parenthesis's line.

```sql
SELECT A.ORDERNO
     , B.QTY
FROM ORDERS A
        LEFT OUTER JOIN (
                         SELECT T.ORDERNO
                              , SUM(T.QTY) AS QTY
                         FROM WORK_LOG T
                         GROUP BY T.ORDERNO
                        ) B
                        ON A.ORDERNO = B.ORDERNO
                        AND A.QTY = B.QTY
```

This example indents FROM by 0 spaces, JOIN by 8, opening/closing parentheses and ON/AND by 24, and inner clauses by 25. These numbers are not global indentation constants; the actual opening parenthesis is the anchor. Apply the rule to AND/OR connecting the same JOIN's conditions. Retain the containing clause's layout for BETWEEN's AND, conditions inside CASE, and subquery conditions.

Use the same parenthesis anchor for the first derived FROM source and nesting with UNION ALL. Keep SELECT-list leading commas and WHERE conditions positioned relative to their inner clause. For example, with FROM indented by 4 spaces, outer parentheses are at 9 and inner clauses at 10; parentheses in that inner FROM are at 15 and its inner clauses at 16.

```sql
    SELECT A.PERIOD
         , A.QTY
    FROM (
          SELECT T.PERIOD
               , SUM(T.QTY) AS QTY
          FROM (
                SELECT T.PERIOD, T.QTY
                FROM HISTORY T

                UNION ALL

                SELECT T.PERIOD, T.QTY
                FROM ORDERS T
               ) T
          GROUP BY T.PERIOD
         ) A
    ORDER BY A.PERIOD
```

In the final SQL, compare actual opening parentheses with inner clauses, continuation lines, closing parentheses, and JOIN conditions together. `--normalize-layout` handles supported derived FROM/JOIN queries and JOIN/EXISTS layout; it is not a complete SQL formatter. Inspect remaining diagnostics, such as clause separation interrupted by comments, directly in the final text.

Prefer JOINs over unnecessary WHERE/SELECT subqueries or NOT EXISTS, but do not substitute them when NULL behavior, duplicates, or cardinality would change. Before replacing a function with a JOIN, inspect its actual definition and execution semantics. Preserve existing exchange-rate functions such as GET_CHGRAT and original business constants; do not hardcode new example exchange rates.

If only an UPDATE is requested, complete the requested UPDATE FROM/CROSS APPLY form. For an actual database-change request, verify the exact connection, database, keys, transaction, resulting values, and excluded rows. Do not report delivered SQL as executed.

For queries returning multiple results, compare periods, filters, JOIN keys, NULL handling, and aggregation units across headers, grids, and charts. Check that UNION branches and total/ratio calculations use the actual comparison target's conditions too. Do not introduce temporary tables merely to shorten duplicated SQL; follow the existing [necessity criteria](../../work-execution/references/preferences.md).
