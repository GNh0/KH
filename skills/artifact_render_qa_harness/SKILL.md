---
name: artifact-render-qa-harness
description: Use when UAF deliverables must prove generated DOCX, XLSX, SVG, or DXF files are readable and structurally valid.
---

# Artifact Render QA Harness

This harness verifies that generated files can be opened or parsed enough for deterministic QA. It is a runtime evidence harness, so its detailed findings stay in UAF metadata unless the user explicitly asks for a user-facing QA report.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.

## Workflow

1. Read each generated artifact from the deliverable export records.
2. For DOCX and XLSX, verify the ZIP package and required Office XML parts exist.
3. For XLSX, verify every row has the same column width as the header.
4. For SVG and DXF, verify required structural markers such as `<svg>`, `SECTION`, and `ENTITIES`.
5. Emit render QA evidence without adding harness-only files to `docs/`.

## Structural Checks

- DOCX requires `[Content_Types].xml`, `_rels/.rels`, and `word/document.xml`.
- XLSX requires `[Content_Types].xml`, `_rels/.rels`, `xl/workbook.xml`, `xl/_rels/workbook.xml.rels`, and `xl/worksheets/sheet1.xml`.
- XLSX rows must have the same cell count as the header row.
- SVG must include an `<svg>` root and closing `</svg>`.
- DXF must include `SECTION` and `ENTITIES`.
- A malformed-file probe should fail with `artifact render qa failed`, not a template pass.

## External Benchmark Recipe

Use this harness before presenting generated files as usable:

1. Read the export manifest and open every listed artifact path.
2. Validate package structure for DOCX/XLSX before checking template content.
3. Validate SVG/DXF structural markers and reject empty or partial drawings.
4. Record per-file findings with artifact type, missing part, and suggested regeneration step.
5. Keep QA details in metadata unless the user asks for a separate QA report.

Pressure scenario: if an XLSX zip contains `xl/workbook.xml` but no worksheet part, render QA fails even if the filename and template type look correct.

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
