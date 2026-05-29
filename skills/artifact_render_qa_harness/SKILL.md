---
name: artifact-render-qa-harness
description: Use when UAF deliverables must prove generated DOCX, XLSX, SVG, or DXF files are readable and structurally valid.
---

# Artifact Render QA Harness

This harness verifies that generated files can be opened or parsed enough for deterministic QA. It is a runtime evidence harness, so its detailed findings stay in UAF metadata unless the user explicitly asks for a user-facing QA report.

## Workflow

1. Read each generated artifact from the deliverable export records.
2. For DOCX and XLSX, verify the ZIP package and required Office XML parts exist.
3. For XLSX, verify every row has the same column width as the header.
4. For SVG and DXF, verify required structural markers such as `<svg>`, `SECTION`, and `ENTITIES`.
5. Emit render QA evidence without adding harness-only files to `docs/`.

## Required outputs

- `artifact render qa passed` when every artifact is readable and structurally consistent.
- `artifact render qa failed` with per-file findings when a file is missing, unreadable, or malformed.

## Common mistakes

- Do not treat file existence as render quality; open or parse the artifact format.
- Do not require a browser or Office installation for basic structural checks.
- Do not write render QA workbooks into the user's `docs/` folder by default.
- Do not hide corrupt optional artifacts when they were listed in the export plan.

## UAF implementation targets

- `src.orchestration.quality_harnesses.evaluate_deliverable_quality`
- `src.orchestration.deliverable_exports.export_office_deliverables`
- `tests.test_quality_harnesses`
- `tests.test_artifact_manifest`
