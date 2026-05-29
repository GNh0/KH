---
name: traceability-matrix-harness
description: Use when UAF workflows need requirements, deliverables, evidence keys, and review gates mapped without exporting internal harness spreadsheets.
---

# Traceability Matrix Harness

This harness builds an internal traceability matrix linking requirements, deliverables, evidence, and gates. The matrix is stored in metadata by default because it is workflow evidence, not automatically a user-facing deliverable.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.

## Workflow

1. Build rows from `WorkDesign.deliverables`, exported deliverable records, evidence keys, and review gates; use `as_dict=True` when another harness needs named fields instead of spreadsheet rows.
2. Require each trace row to have a requirement ID, deliverable, artifact type, evidence key, gate, and status.
3. Attach rows to `deliverable_exports.quality.traceability_matrix` and runtime metadata.
4. Do not create `docs/추적성_매트릭스.xlsx` unless a user explicitly asks for that as a deliverable.
5. Emit `traceability matrix passed` or `traceability matrix failed` evidence.

## External Benchmark Recipe

Use this harness to prove every important output has an owner and evidence:

1. Assign a stable requirement id before export.
2. Link each requirement to one deliverable, one artifact type, one evidence key, and one gate.
3. Use typed rows (`as_dict=True`) when another harness must inspect named fields.
4. Mark rows failed when the deliverable file is missing or the evidence key was not produced.
5. Keep the matrix internal unless the user explicitly requests a traceability workbook.

Pressure scenario: if a generated DOCX exists but no requirement row maps to it, the workflow is not evidence-complete.

## Required outputs

- `traceability_matrix.rows`: internal rows with requirement-to-evidence mapping.
- Typed rows with `trace_id`, `requirement_id`, `deliverable`, `evidence_key`, `gate`, and `status` when `as_dict=True`.
- `traceability_matrix.status`: `passed` or `failed`.
- Goal evidence for traceability pass/fail status.

## Common mistakes

- Do not export internal traceability spreadsheets into `docs/` by default.
- Do not leave rows without requirement id, deliverable, evidence, gate, or status.
- Do not treat traceability as complete when generated files are missing.
- Do not use trace rows as user-facing deliverables unless explicitly requested.

## UAF implementation targets

- `src.orchestration.quality_harnesses.build_traceability_matrix_rows`
- `src.orchestration.quality_harnesses.evaluate_deliverable_quality`
- `src.contracts.WorkDesign`
- `tests.test_quality_harnesses`
