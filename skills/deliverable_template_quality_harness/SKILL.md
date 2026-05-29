---
name: deliverable-template-quality-harness
description: Use when UAF-generated user deliverables need template completeness, required section coverage, or evidence-backed quality checks.
---

# Deliverable Template Quality Harness

This harness checks user-facing deliverables against recognizable document and spreadsheet templates. It is for quality evidence, not for creating extra user documents about UAF internals.

## Workflow

1. Inspect the deliverable export plan from `WorkflowDispatchResult.metadata["deliverable_exports"]`.
2. Check each generated DOCX/XLSX against the required markers for its artifact type.
3. Keep quality findings in workflow metadata and goal evidence.
4. Do not write harness-only reports into the target project's `docs/` folder.
5. Block or mark findings when a required section, table column, owner, approval basis, or verification marker is missing.

## Required outputs

- `quality.status`: `passed` or `failed`.
- `quality.findings`: actionable template issues.
- `quality.checks`: per-file checks for template and render quality.
- Evidence keys such as `deliverable template quality passed` or `deliverable template quality failed`.

## Common mistakes

- Do not pass a deliverable only because a filename exists; inspect required headings and table markers.
- Do not apply software-only sections to product design, analysis, or operations deliverables.
- Do not export quality findings as user-facing files by default.
- Do not mark the workflow complete when required template markers are missing.

## UAF implementation targets

- `src.orchestration.quality_harnesses.evaluate_deliverable_quality`
- `src.orchestration.deliverable_exports.export_office_deliverables`
- `src.orchestration.artifacts.build_design_stage`
- `tests.test_quality_harnesses`
- `tests.test_artifact_manifest`
