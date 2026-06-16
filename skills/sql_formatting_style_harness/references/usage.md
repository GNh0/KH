# SQL Formatting Style Harness Usage

Use this harness after SQL/T-SQL formatting has been produced by the host-local `sql-formatting` skill or by an agent claiming to follow that skill.

## Inputs

- Original SQL or stored procedure text.
- Formatted SQL or stored procedure text.
- Optional path to the host-local `sql-formatting` `SKILL.md`.
- A decision on whether DB-backed semantic evidence is required.

## Execution pattern

1. Keep original and formatted SQL uncompressed.
2. Call `src.skills.sql_formatting_style.verify_sql_formatting_style(original, formatted)`.
   If a CTE or `#` temporary table was intentionally introduced, pass `cte_temp_table_reason="<concrete reason>"`.
3. Inspect `metadata.mechanical_checks.status`.
4. Treat any preservation error as blocking.
5. Treat `metadata.semantic_checks.status=not_proven` as a required follow-up when DB semantics, performance, or schema-dependent rewrites matter.
6. Record `metadata.style_contract_source` in evidence so reviewers can see whether the host-local skill or packaged fallback reference was used.

## Composition policy

- The host-local `sql-formatting` skill formats SQL.
- KH `sql-formatting-style-harness` verifies preservation and style evidence.
- Light one-off formatting can route to host-local `sql-formatting` alone.
- Medium, heavy, multi-file, stored-procedure, evidence-heavy, or "prove/verify" SQL formatting requests should compose host-local formatting plus this verifier.
- Mention-only prompts, risk examples, or review prompts about whether the skill exists must not trigger formatting or verifier execution.

## Preservation rules

The verifier blocks when string literals, Korean literals, comment shape/count, predicates, JOIN conditions, calculations, or `ELSE` counts change mechanically. It permits alias-only identifier/casing updates inside still-commented SQL conditions, but removed, uncommented, or business-text-changing comments remain blocking.

## Style rules

The verifier checks the established host-local style: uppercase identifiers outside literals/comments, leading-comma procedure parameters and SELECT columns, wide `INSERT INTO ... SELECT` grouped horizontal layout with per-mapping continuation lines for long expressions, no newly introduced CTEs or `#` temporary tables by default, JOIN indentation, parenthesized CASE expressions, and verified scalar lookup conversion shape when applicable. Unknown scalar functions stay unchanged unless DB/MCP metadata, project source, or the host-local style contract proves an equivalent lookup join. `DBO.F_BA011T_FIND_SUBNM(MAINCD, SUBCD, USEYN)` is treated as a verified `BA011T` lookup contract when the host-local `sql-formatting` skill is available.

Use CTEs or `#` temporary tables only as exceptions: explicit user request, recursive logic, repeated multi-statement reuse, a large intermediate set that needs indexing/statistics, procedural staging that cannot be expressed cleanly inline, or measured performance evidence. If one is used, the formatter should state the reason; otherwise recommendations should stay in the direct join, derived table, aggregate subquery, and existing stored-procedure style.

## Evidence

Report:

- `success`, `exit_code`, `stdout`, and `stderr`.
- `metadata.style_contract_source.path` and `sha256`.
- `metadata.mechanical_checks.preservation_issues`.
- `metadata.mechanical_checks.style_issues`.
- `metadata.semantic_checks.status` and reason.
- `metadata.token_optimizer_status=passthrough`.
- `metadata.cte_temp_table_reason` when an exception was used.

## Failure handling

If the host-local `sql-formatting` skill is unavailable, the verifier records the packaged fallback reference. That fallback is evidence for the verifier's checks only; it is not a replacement formatting standard.

## PowerBuilder source validation hook

For PowerBuilder/PBL validation, keep the sweep bounded and source-safe:

1. Use `C:\PblScripter\Export-PBL.ps1` to export PBL objects into a caller-provided output directory, not into `C:\GWERP`.
2. Run `scripts/powerbuilder_sql_probe.py --source-root <exported-source> --output-dir <probe-output>`.
3. The probe extracts SQL-looking fragments containing `SELECT`, `UPDATE`, `DELETE`, or `INSERT`.
4. Format extracted fragments with host-local `sql-formatting`.
5. Run `verify_sql_formatting_style` on each original/formatted pair.
6. Report broad PBL sweep status separately from unit-test fixture coverage.

This implementation pass includes the bounded hook and fixture coverage. It does not perform a broad `C:\GWERP` sweep unless explicitly run with an external output directory.
