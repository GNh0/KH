# PB To C# Migration Harness Usage

Use this reference when a PowerBuilder/GWERP workflow must be migrated, reviewed, or planned as TY/C_KONE110-style C# WinForms/DevExpress screens and SQL Server SELECT/SAVE stored procedures.

## When to use

Use this harness for requests involving PB, PBL, PBD, ORCA, PblScripter, SRU, SRW, SRD, DataWindow, DataWindowToXml, GWERP, TY, C_KONE110, C# migration, DevExpress grid/layout migration, or SELECT/SAVE stored-procedure migration.

Use it even when the local toolchain is absent. The packaged references are the fallback baseline. Local PBL exports, source trees, converter HTML, C# examples, and live DB access increase confidence but are not required just to start the workflow.

Do not use this harness as the SQL formatter. SQL formatting belongs to the host-local `sql-formatting` skill; this harness decides migration flow and verifies that PB/C#/SP work follows the migration contract.

## Inputs to collect

- Objective: screen, program, report, save flow, query, popup, or DataWindow being migrated.
- Available source evidence: PBL, exported `.sru`, `.srw`, `.srd`, pasted PB text, screenshots, existing C# screen, existing SP, feature spec, or DB access.
- Migration mode: `standalone`, `pasted-source`, `partial-reference`, or `full-reference`.
- PB flow: object name, parent window/user object, event path, `OpenWithParm`, `Retrieve`, `Update`, DataWindow `dataobject`, and linked SQL.
- DataWindow fields: column names, update table, retrieve arguments, display labels, computed fields, DDDW/dropdown dependencies, edit masks, protection, tab order, and layout constraints.
- C# target: namespace/module, form class, control names, `SelectType`, `CallViewQuery`, `CallProc`, `DataUtil.DataTableToXml`, `SetModified`, and current binding/result contract.
- SP target: `sp_<PROGRAM>_SELECT`, `sp_<PROGRAM>_SAVE`, `@WORKTYPE`, XML input shape, transaction/logging/error pattern, and formatting verifier needs.
- Evidence limits: missing tool, missing source, ORCA failure, license failure, stale path, no live DB, or formatting-only boundary.

## Execution pattern

1. Read `SKILL.md` and this usage reference first.
2. Run or emulate `build_pb_to_csharp_migration_plan(objective, state)` so the run has a concrete `HarnessResult` and migration mode.
3. Select only the reference files needed for the current slice:
   - PBL export and ORCA problems: `pbl-export-process.md`.
   - PB event/source tracing: `powerbuilder-source-analysis.md`.
   - DataWindow grid/layout: `datawindow-layout-mapping.md`.
   - TY C# implementation: `ty-csharp-style.md`.
   - Stored procedure drafting/review: `kh-sp-style.md`.
   - SQL formatter/verifier composition: `sql-formatting-bridge.md`.
   - Completion/handoff: `migration-output-checklist.md`.
4. If a PBL/tool/source exists, inspect the real artifact first and keep exports outside the PB source tree. If not, use standalone mode and state which claims cannot be proven.
5. For DataWindow column conversion, call `extract_datawindow_columns` and `generate_devexpress_grid_xml` or follow the same narrow rule manually. This reproduces the packaged DataWindowToXml-compatible behavior.
6. For C# work, preserve the current screen flow rather than adding a separate parallel helper. Reuse existing `CallViewQuery` and `CallProc` paths whenever they already match the target procedure.
7. For SQL work, keep original SQL uncompressed, apply host-local `sql-formatting`, and run `sql-formatting-style-harness` verification when proof is required.
8. Mark token optimizer as `passthrough` for PB/C#/SQL source text. Use optimization only for noisy command output or subagent transcripts where required facts are preserved.
9. Before completion, produce the migration checklist and name blocked evidence. Do not claim PB parity, DB semantic equivalence, or UI layout fidelity without the matching evidence.

## Evidence to produce

- `HarnessResult` from `build_pb_to_csharp_migration_plan` or `build_datawindow_grid_layout`.
- `mode`: `standalone`, `pasted-source`, `partial-reference`, or `full-reference`.
- `strong_evidence` and `weak_evidence` explaining what was actually available.
- PB trace summary: object names, source files, event flow, DataWindows, retrieve/update/save paths, and gaps.
- DataWindow mapping: extracted columns, generated DevExpress XML shape, unsupported visual/layout features, and fallback status.
- TY C# plan: target class, existing method path, controls, XML serialization rule, and result-binding expectations.
- SP plan: SELECT/SAVE procedures, XML/table variable shape, transaction boundary, logging, duplicate checks, and formatting verification.
- SQL verifier status and semantic limits.
- `token_optimizer_status` with `passthrough` reason for source-of-truth text or before/after stats when noisy output was compressed.
- `actual_runtime_path`: module, script, verifier, or procedural path that produced the evidence.

## Failure handling

- Missing PblScripter: continue in standalone, pasted-source, or partial-reference mode; ask for exported source only if correctness depends on PB event flow.
- ORCA runtime failure: distinguish missing runtime path, bad library, and license/SySAM failure. Do not claim the PBL is invalid until that is known.
- Binary-only evidence: treat strings as weak evidence; they can reveal names or SQL fragments, not full event or save semantics.
- Missing DataWindowToXml: use the packaged DataWindow column-to-grid rules or ask for SRD text.
- Missing TY samples: use `ty-csharp-style.md` as the baseline and mark style confidence lower.
- Missing live DB: do not claim schema, scalar-function equivalence, execution plan, or semantic parity.
- Formatting-only request: do not perform performance tuning or scalar-function rewrites unless the user asks and evidence exists.

## Quality bar

A valid run lets another agent answer what PB behavior was traced, what was only inferred, how DataWindow fields map to DevExpress/C# controls, which TY C# path should be reused, what SELECT/SAVE SP contract is expected, what SQL formatting verifier said, what remains blocked, and whether local evidence was present or absent.

It must work from bundled references alone. Local host paths are examples, not requirements. The harness should degrade honestly instead of pretending it inspected unavailable PB, C#, HTML, or DB artifacts.
