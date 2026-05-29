---
name: traceability-matrix-harness
description: Use when UAF workflows need requirements, deliverables, evidence keys, and review gates mapped without exporting internal harness spreadsheets.
---

# Traceability Matrix Harness

This harness builds an internal traceability matrix linking requirements, deliverables, evidence, and gates. The matrix is stored in metadata by default because it is workflow evidence, not automatically a user-facing deliverable.

## Workflow

1. Build rows from `WorkDesign.deliverables`, exported deliverable records, evidence keys, and review gates.
2. Require each trace row to have a requirement ID, deliverable, artifact type, evidence key, gate, and status.
3. Attach rows to `deliverable_exports.quality.traceability_matrix` and runtime metadata.
4. Do not create `docs/추적성_매트릭스.xlsx` unless a user explicitly asks for that as a deliverable.
5. Emit `traceability matrix passed` or `traceability matrix failed` evidence.

## Required outputs

- `traceability_matrix.rows`: internal rows with requirement-to-evidence mapping.
- `traceability_matrix.status`: `passed` or `failed`.
- Goal evidence for traceability pass/fail status.

## UAF implementation targets

- `src.orchestration.quality_harnesses.build_traceability_matrix_rows`
- `src.orchestration.quality_harnesses.evaluate_deliverable_quality`
- `src.contracts.WorkDesign`
- `tests.test_quality_harnesses`
