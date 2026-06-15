---
name: sql-formatting-style-harness
description: Use when KH must verify SQL/T-SQL formatting output against the host-local sql-formatting style contract without replacing that host-local skill.
---

# SQL Formatting Style Harness

## KH Entry Contract

- Start through `always-on-front-door` for work-bearing requests before this harness is selected.
- If `kh_active_directive=active` was set by an earlier user instruction, keep KH-routed setup active for this work-bearing request.
- Use the host-local `sql-formatting` skill as the primary formatting standard when it exists.
- Do not replace, suppress, or reinterpret the host-local skill. This harness verifies outputs from that skill or from an agent that claims to follow it.
- Treat SQL, T-SQL, stored procedures, comments, Korean literals, and business rule text as contract-sensitive passthrough content. Do not token-compress it.
- Report this skill as applied only when `src.skills.sql_formatting_style.verify_sql_formatting_style` or the module CLI produced a `HarnessResult`-shaped result.
- A `selected_not_executed_skills` entry, a skill-file read, or a style-standard mention is not execution evidence.

## Support files

- Read `references/usage.md` before applying this harness to real SQL or stored procedure work.
- Use `examples/minimal-workflow.md` as the compact success/blocked workflow.
- Run `python scripts/smoke_check.py` to verify the packaged skill folder and implementation targets.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success and blocked demo.
- Run `python scripts/powerbuilder_sql_probe.py --source-root <exported-pb-source> --output-dir <tmp>` for bounded PowerBuilder SQL fragment discovery.

## Workflow

1. Apply or delegate formatting to the host-local `sql-formatting` skill first.
2. Preserve the original SQL text exactly for comparison.
3. Run the verifier with original and formatted SQL.
4. Block completion when mechanical preservation checks fail.
5. Block or request DB-backed evidence when semantic equivalence matters beyond regex checks.
6. Include the verifier result, style contract source path/hash, and token optimizer passthrough status in handoff evidence.

## Mechanical checks

- Preserve string literals, Korean literals, comment shape/count, key predicates, JOIN conditions, calculations, and `ELSE` count.
- Permit alias-only identifier/casing updates inside still-commented SQL conditions, but block removed, uncommented, or business-text-changing comments.
- Check uppercase identifiers outside literals/comments.
- Check stored procedure parameter leading-comma layout.
- Check SELECT leading-comma columns.
- Check JOIN indentation shape.
- Check parenthesized CASE expressions.
- Check BA011T scalar-to-join conversion shape when the scalar function appears in the original SQL.

## PowerBuilder validation path

- For GWERP or other PowerBuilder sources, use `C:\PblScripter\Export-PBL.ps1` only to export readable source into a separate output directory.
- Do not write to `C:\GWERP` or the source PBL tree.
- Extract SQL-looking fragments containing `SELECT`, `UPDATE`, `DELETE`, or `INSERT` from exported `.srw`, `.sru`, `.srd`, `.txt`, or `.sql` files.
- Keep extracted fragments as passthrough text, format them through host-local `sql-formatting`, then run this verifier on each original/formatted pair.
- If the sweep is too large for the current pass, record `build_powerbuilder_sql_validation_plan` output and report the sweep as follow-up.

## Semantic boundary

The harness does not claim to prove DB semantics. Execution-plan changes, result-set equivalence, trigger side effects, transaction behavior, collation behavior, and statistics must be proven with database-backed checks when they matter.

## Required outputs

- `HarnessResult.success`, `exit_code`, `stdout`, `stderr`, and `metadata`.
- `metadata.style_contract_source` with host-local path/hash when available or packaged fallback reference otherwise.
- `metadata.mechanical_checks.status`.
- Preservation issue list for string literals, Korean literals, comment shape/count/text, predicates, JOIN conditions, calculations, and `ELSE` additions.
- Style issue list for uppercase identifiers, stored procedure parameter layout, SELECT leading commas, JOIN indentation, CASE parentheses, and BA011T conversion shape.
- `metadata.semantic_checks.status=not_proven` unless separate DB-backed evidence is attached outside this regex verifier.
- `metadata.token_optimizer_status=passthrough`.
- PowerBuilder validation plan or fragment-level verifier results when the source is a PBL/PB export.

## Common mistakes

- Do not claim the host-local `sql-formatting` skill was used without verifier evidence when the request requires proof.
- Do not use this KH harness as a formatter or as a replacement for the host-local style skill.
- Do not token-compress SQL, stored procedures, Korean literals, comments, or other contract-sensitive text.
- Do not treat regex preservation checks as proof of DB semantic equivalence.
- Do not trigger the harness for mention-only risk examples that are not actionable SQL formatting requests.
- Do not write exports, fragments, or verifier output into `C:\GWERP`.

## UAF implementation targets

- `src.skills.sql_formatting_style.verify_sql_formatting_style`
- `src.skills.sql_formatting_style.resolve_style_contract_source`
- `src.skills.sql_formatting_style.extract_powerbuilder_sql_fragments`
- `src.skills.sql_formatting_style.build_powerbuilder_sql_validation_plan`
- `src.contracts.HarnessResult`
- `tests.test_sql_formatting_style_harness`
- `skills/sql_formatting_style_harness/SKILL.md`
