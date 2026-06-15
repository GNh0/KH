---
name: artifact-render-qa-harness
description: Use when kh-uaf:always-on-front-door has already run and selected this skill; use it when UAF deliverables must prove generated documents, spreadsheets, drawings, images, web pages, data exports, or other typed files are readable and pass format-specific structural or sanity checks.
---

# Artifact Render QA Harness

## KH Entry Contract

- Start every non-trivial turn through `always-on-front-door` unless this skill is that bootstrap step or the current turn was classified as light/direct.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, or a required follow-up gate selects it.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

This harness verifies that generated files can be opened or parsed enough for deterministic QA. It is a runtime evidence harness, so its detailed findings stay in UAF metadata unless the user explicitly asks for a user-facing QA report.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## Workflow

1. Read each generated artifact from the deliverable export records.
2. For DOCX, XLSX, and PPTX, verify the ZIP package and required Office XML parts exist.
3. For XLSX and CSV, verify tabular rows are structurally consistent with the header.
4. For SVG, DXF, PDF, HTML, and PNG, verify format-specific structural markers, header/EOF sanity checks, or chunk structure.
5. For other text or binary formats, require an explicit format-specific probe or mark the artifact as blocked/not-applicable instead of passing by filename alone.
6. Emit render QA evidence without adding harness-only files to `docs/`.

## Structural Checks

- DOCX requires `[Content_Types].xml`, `_rels/.rels`, and `word/document.xml`.
- XLSX requires `[Content_Types].xml`, `_rels/.rels`, `xl/workbook.xml`, `xl/_rels/workbook.xml.rels`, and `xl/worksheets/sheet1.xml`.
- PPTX requires `[Content_Types].xml`, `_rels/.rels`, `ppt/presentation.xml`, `ppt/_rels/presentation.xml.rels`, parseable `ppt/presentation.xml`, and at least one slide part or slide relationship.
- XLSX rows must have the same cell count as the header row.
- CSV must parse with strict quoting and rows must have the same column count as the header row.
- SVG must include an `<svg>` root and closing `</svg>`.
- DXF must include `SECTION` and `ENTITIES`.
- PDF uses a header/EOF sanity check only: it must start with the `%PDF-` file signature and include an EOF marker, but this is not full PDF structural validation.
- HTML must include a document structure marker such as `<html`, `<!doctype html`, or an intentional fragment marker.
- PNG must pass a minimal chunk check: PNG signature, IHDR as the first chunk, sane dimensions, valid chunk CRCs, and IEND presence.
- A malformed-file probe should fail with `artifact render qa failed`, not a template pass.

## External Benchmark Recipe

Use this harness before presenting generated files as usable:

1. Read the export manifest and open every listed artifact path.
2. Validate package structure for DOCX/XLSX/PPTX before checking template content.
3. Validate SVG/DXF/HTML structural markers, PDF header/EOF sanity, PNG chunk structure, and CSV strict parsing; reject empty or partial artifacts.
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
