import json
import os
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path

from src.orchestration.artifacts import build_design_stage
from src.orchestration.domain_profiles import DomainProfileBuilder, work_design_from_profile
from src.orchestration.quality_harnesses import (
    audit_role_execution,
    build_traceability_matrix_rows,
    evaluate_deliverable_quality,
)


def _write_docx_xml(path: Path, document_xml: str) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", "<Types></Types>")
        package.writestr("_rels/.rels", "<Relationships></Relationships>")
        package.writestr("word/document.xml", document_xml)


def _write_pptx_xml(path: Path) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr(
            "[Content_Types].xml",
            (
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml" />'
                '<Default Extension="xml" ContentType="application/xml" />'
                '<Override PartName="/ppt/presentation.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml" />'
                '<Override PartName="/ppt/slides/slide1.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml" />'
                "</Types>"
            ),
        )
        package.writestr(
            "_rels/.rels",
            (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                'Target="ppt/presentation.xml" />'
                "</Relationships>"
            ),
        )
        package.writestr(
            "ppt/presentation.xml",
            (
                '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<p:sldIdLst><p:sldId id="256" r:id="rId1" /></p:sldIdLst>'
                "</p:presentation>"
            ),
        )
        package.writestr(
            "ppt/_rels/presentation.xml.rels",
            (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
                'Target="slides/slide1.xml" />'
                "</Relationships>"
            ),
        )
        package.writestr(
            "ppt/slides/slide1.xml",
            '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"></p:sld>',
        )


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(chunk_type)
    crc = zlib.crc32(payload, crc) & 0xFFFFFFFF
    return len(payload).to_bytes(4, "big") + chunk_type + payload + crc.to_bytes(4, "big")


def _minimal_png_bytes(width: int = 1, height: int = 1) -> bytes:
    ihdr = (
        width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
    )
    idat = zlib.compress(b"\x00\x00\x00\x00")
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", idat)
        + _png_chunk(b"IEND", b"")
    )


class QualityHarnessTests(unittest.TestCase):
    def test_build_design_stage_attaches_quality_harness_report_and_traceability(self):
        original_runtime_root = os.environ.get("UAF_RUNTIME_ROOT")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                project_dir = Path(tmp) / "demo"
                runtime_root = Path(tmp) / "runtime"
                project_dir.mkdir()
                os.environ["UAF_RUNTIME_ROOT"] = str(runtime_root)

                result = build_design_stage(
                    project_dir=str(project_dir),
                    workflow_id="workflow_demo",
                    design_doc="# Inventory Admin App\nBuild product CRUD and stock alert dashboard.",
                    file_list=["src/app.py", "src/ui.js"],
                    metadata={
                        "domain_hint": "software-development",
                        "scope": "Build a web application feature set with API, UI, data, and QA coverage.",
                    },
                )

                exports = result["deliverable_exports"]
                exported_paths = {Path(item["path"]).name: Path(item["path"]) for item in exports["deliverables"]}

                self.assertIn("quality", exports)
                self.assertEqual(exports["quality"]["status"], "passed")
                self.assertEqual(exports["quality"]["findings"], [])
                self.assertIn("deliverable template quality passed", exports["quality"]["evidence"])
                self.assertIn("artifact render qa passed", exports["quality"]["evidence"])
                self.assertIn("traceability matrix passed", exports["quality"]["evidence"])
                self.assertIn("traceability_matrix", exports["quality"])
                self.assertGreaterEqual(len(exports["quality"]["traceability_matrix"]["rows"]), 2)
                self.assertNotIn("traceability matrix exported", result["evidence"])
                self.assertNotIn("추적성_매트릭스.xlsx", exported_paths)
        finally:
            if original_runtime_root is None:
                os.environ.pop("UAF_RUNTIME_ROOT", None)
            else:
                os.environ["UAF_RUNTIME_ROOT"] = original_runtime_root

    def test_traceability_matrix_rows_map_deliverables_to_evidence_and_gates(self):
        profile = DomainProfileBuilder.build(
            objective="Build an inventory app",
            domain_hint="software-development",
        )
        design = work_design_from_profile(
            profile,
            deliverables=["requirements brief", "functional specification"],
        )
        rows = build_traceability_matrix_rows(
            design,
            [
                {
                    "file_name": "요구정의서.docx",
                    "artifact_type": "requirements-brief",
                    "evidence_key": "requirements brief exported",
                },
                {
                    "file_name": "기능정의서.docx",
                    "artifact_type": "functional-specification",
                    "evidence_key": "functional specification exported",
                },
            ],
        )

        self.assertEqual(
            rows[0],
            [
                "Trace ID",
                "Requirement ID",
                "요구사항",
                "산출물",
                "산출물 유형",
                "증거 키",
                "검토 게이트",
                "상태",
                "비고",
            ],
        )
        self.assertGreaterEqual(len(rows), 3)
        for row in rows[1:]:
            self.assertTrue(row[1].startswith("REQ-"))
            self.assertTrue(row[3])
            self.assertTrue(row[5])
            self.assertTrue(row[6])
            self.assertEqual(row[7], "planned")

    def test_deliverable_quality_blocks_missing_template_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            docx_path = Path(tmp) / "요구정의서.docx"
            _write_docx_xml(
                docx_path,
                "<w:document><w:body><w:p><w:r><w:t>요구사항</w:t></w:r></w:p></w:body></w:document>",
            )

            result = evaluate_deliverable_quality(
                {
                    "profile": "general-orchestration",
                    "deliverables": [
                        {
                            "path": str(docx_path),
                            "file_name": "요구정의서.docx",
                            "artifact_type": "requirements-brief",
                            "evidence_key": "requirements brief exported",
                        }
                    ],
                }
            )

        self.assertEqual(result["status"], "failed")
        self.assertIn("deliverable template quality failed", result["evidence"])
        self.assertTrue(any("문서 정보" in finding for finding in result["findings"]))

    def test_missing_artifact_does_not_emit_template_passed_evidence(self):
        result = evaluate_deliverable_quality(
            {
                "profile": "general-orchestration",
                "deliverables": [
                    {
                        "path": str(Path("missing.docx")),
                        "file_name": "missing.docx",
                        "artifact_type": "requirements-brief",
                    }
                ],
            }
        )

        self.assertEqual(result["status"], "failed")
        self.assertIn("artifact render qa failed", result["evidence"])
        self.assertIn("deliverable template quality failed", result["evidence"])
        self.assertNotIn("deliverable template quality passed", result["evidence"])

    def test_role_execution_audit_requires_artifacts_and_parallel_waves(self):
        role_metadata = {
            "summary": {
                "execution_model": "dag-asyncio-role-waves",
                "success": True,
                "wave_count": 3,
                "parallel_wave_count": 1,
                "runtime_overlap_wave_count": 1,
            },
            "results": [
                {
                    "role": "ceo",
                    "status": "success",
                    "metadata": {"role_artifacts": [{"path": "runtime/ceo.md"}]},
                },
                {
                    "role": "advisor",
                    "status": "success",
                    "metadata": {"role_artifacts": [{"path": "runtime/advisor.md"}]},
                },
            ],
        }

        passed = audit_role_execution(role_metadata, required_roles=["ceo", "advisor"])
        self.assertEqual(passed["status"], "passed")
        self.assertIn("role execution audited", passed["evidence"])

        missing_artifact = json.loads(json.dumps(role_metadata))
        missing_artifact["results"][1]["metadata"]["role_artifacts"] = []
        failed = audit_role_execution(missing_artifact, required_roles=["ceo", "advisor"])
        self.assertEqual(failed["status"], "failed")
        self.assertTrue(any("advisor" in finding for finding in failed["findings"]))

    def test_role_execution_audit_default_requires_product_strategy_and_implementation_when_needed(self):
        role_metadata = {
            "summary": {
                "execution_model": "dag-asyncio-role-waves",
                "success": True,
                "wave_count": 3,
                "parallel_wave_count": 1,
                "implementation_required": True,
                "runtime_overlap_wave_count": 1,
            },
            "results": [
                {
                    "role": "ceo",
                    "status": "success",
                    "metadata": {"role_artifacts": [{"path": "runtime/ceo.md"}]},
                },
                {
                    "role": "advisor",
                    "status": "success",
                    "metadata": {"role_artifacts": [{"path": "runtime/advisor.md"}]},
                },
            ],
        }

        result = audit_role_execution(role_metadata)

        self.assertEqual(result["status"], "failed")
        self.assertTrue(any("product-strategist" in finding for finding in result["findings"]))
        self.assertTrue(any("implementer" in finding for finding in result["findings"]))

    def test_role_execution_audit_fails_when_runtime_overlap_evidence_is_missing(self):
        role_metadata = {
            "summary": {
                "execution_model": "dag-asyncio-role-waves",
                "success": True,
                "wave_count": 2,
                "parallel_wave_count": 1,
                "runtime_overlap_wave_count": 0,
            },
            "results": [
                {
                    "role": "ceo",
                    "status": "success",
                    "metadata": {"role_artifacts": [{"path": "runtime/ceo.md"}]},
                },
            ],
        }

        result = audit_role_execution(role_metadata, required_roles=["ceo"])

        self.assertEqual(result["status"], "failed")
        self.assertTrue(any("runtime overlap" in finding for finding in result["findings"]))

    def test_traceability_matrix_dict_rows_have_named_schema_and_gate_status(self):
        profile = DomainProfileBuilder.build(
            objective="Build an inventory app",
            domain_hint="software-development",
        )
        design = work_design_from_profile(profile, deliverables=["requirements brief"])
        rows = build_traceability_matrix_rows(
            design,
            [
                {
                    "file_name": "requirements.docx",
                    "artifact_type": "requirements-brief",
                    "evidence_key": "requirements brief exported",
                    "gate_status": "passed",
                },
            ],
            as_dict=True,
        )

        self.assertEqual(rows[0]["trace_id"], "TRACE-001")
        self.assertEqual(rows[0]["deliverable"], "requirements.docx")
        self.assertEqual(rows[0]["status"], "passed")

    def test_traceability_dict_rows_can_be_evaluated_directly(self):
        profile = DomainProfileBuilder.build(
            objective="Build an inventory app",
            domain_hint="software-development",
        )
        design = work_design_from_profile(profile, deliverables=["requirements brief"])
        rows = build_traceability_matrix_rows(
            design,
            [
                {
                    "file_name": "requirements.docx",
                    "artifact_type": "requirements-brief",
                    "evidence_key": "requirements brief exported",
                    "gate_status": "passed",
                },
            ],
            as_dict=True,
        )

        result = evaluate_deliverable_quality({"traceability_rows": rows, "deliverables": []})

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["traceability_matrix"]["status"], "passed")

    def test_incomplete_office_package_fails_render_qa(self):
        with tempfile.TemporaryDirectory() as tmp:
            xlsx_path = Path(tmp) / "fake.xlsx"
            with zipfile.ZipFile(xlsx_path, "w", compression=zipfile.ZIP_DEFLATED) as package:
                package.writestr("xl/worksheets/sheet1.xml", "<worksheet><sheetData></sheetData></worksheet>")

            result = evaluate_deliverable_quality(
                {
                    "deliverables": [
                        {
                            "path": str(xlsx_path),
                            "file_name": "fake.xlsx",
                            "format": "xlsx",
                            "artifact_type": "role-task-breakdown",
                        }
                    ]
                }
            )

        self.assertEqual(result["status"], "failed")
        self.assertTrue(any("missing required parts" in finding for finding in result["findings"]))
        self.assertIn("artifact render qa failed", result["evidence"])

    def test_render_qa_accepts_common_typed_deliverables_with_not_applicable_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pptx_path = root / "deck.pptx"
            pdf_path = root / "report.pdf"
            html_path = root / "page.html"
            png_path = root / "image.png"
            csv_path = root / "data.csv"
            _write_pptx_xml(pptx_path)
            pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
            html_path.write_text("<!doctype html><html><body><main>ok</main></body></html>", encoding="utf-8")
            png_path.write_bytes(_minimal_png_bytes())
            csv_path.write_text("id,name\n1,alpha\n2,beta\n", encoding="utf-8")

            result = evaluate_deliverable_quality(
                {
                    "deliverables": [
                        {"path": str(pptx_path), "file_name": "deck.pptx", "format": "pptx", "artifact_type": "presentation", "template_not_applicable": True},
                        {"path": str(pdf_path), "file_name": "report.pdf", "format": "pdf", "artifact_type": "pdf-document", "template_not_applicable": True},
                        {"path": str(html_path), "file_name": "page.html", "format": "html", "artifact_type": "web-page", "template_not_applicable": True},
                        {"path": str(png_path), "file_name": "image.png", "format": "png", "artifact_type": "image", "template_not_applicable": True},
                        {"path": str(csv_path), "file_name": "data.csv", "format": "csv", "artifact_type": "data-export", "template_not_applicable": True},
                    ]
                }
            )

        self.assertEqual(result["status"], "passed")
        self.assertIn("artifact render qa passed", result["evidence"])
        self.assertEqual([check["status"] for check in result["checks"] if check["check_type"] == "render"], ["passed"] * 5)

    def test_render_qa_blocks_malformed_pptx_png_pdf_and_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pptx_path = root / "bad.pptx"
            missing_rels_pptx_path = root / "missing-rels.pptx"
            no_slide_pptx_path = root / "no-slide.pptx"
            png_path = root / "bad.png"
            bad_crc_png_path = root / "bad-crc.png"
            csv_path = root / "bad.csv"
            bad_pdf_path = root / "bad.pdf"
            missing_eof_pdf_path = root / "missing-eof.pdf"
            valid_presentation_xml = (
                '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<p:sldIdLst><p:sldId id="256" r:id="rId1" /></p:sldIdLst>'
                "</p:presentation>"
            )
            with zipfile.ZipFile(pptx_path, "w", compression=zipfile.ZIP_DEFLATED) as package:
                package.writestr("[Content_Types].xml", "<Types></Types>")
                package.writestr("_rels/.rels", "<Relationships></Relationships>")
                package.writestr("ppt/presentation.xml", "<p:presentation></p:presentation>")
                package.writestr(
                    "ppt/_rels/presentation.xml.rels",
                    (
                        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                        '<Relationship Id="rId1" '
                        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
                        'Target="slides/slide1.xml" />'
                        "</Relationships>"
                    ),
                )
                package.writestr(
                    "ppt/slides/slide1.xml",
                    '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"></p:sld>',
                )
            with zipfile.ZipFile(missing_rels_pptx_path, "w", compression=zipfile.ZIP_DEFLATED) as package:
                package.writestr("[Content_Types].xml", "<Types></Types>")
                package.writestr("_rels/.rels", "<Relationships></Relationships>")
                package.writestr("ppt/presentation.xml", valid_presentation_xml)
            with zipfile.ZipFile(no_slide_pptx_path, "w", compression=zipfile.ZIP_DEFLATED) as package:
                package.writestr("[Content_Types].xml", "<Types></Types>")
                package.writestr("_rels/.rels", "<Relationships></Relationships>")
                package.writestr("ppt/presentation.xml", valid_presentation_xml)
                package.writestr(
                    "ppt/_rels/presentation.xml.rels",
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>',
                )
            png_path.write_bytes(b"\x89PNG\r\n\x1a\n")
            bad_crc_png = bytearray(_minimal_png_bytes())
            bad_crc_png[-1] ^= 0x01
            bad_crc_png_path.write_bytes(bytes(bad_crc_png))
            csv_path.write_text('id,name\n1,"unterminated\n', encoding="utf-8")
            bad_pdf_path.write_bytes(b"not a pdf\n")
            missing_eof_pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n")

            result = evaluate_deliverable_quality(
                {
                    "deliverables": [
                        {"path": str(pptx_path), "file_name": "bad.pptx", "format": "pptx", "artifact_type": "presentation", "template_not_applicable": True},
                        {"path": str(missing_rels_pptx_path), "file_name": "missing-rels.pptx", "format": "pptx", "artifact_type": "presentation", "template_not_applicable": True},
                        {"path": str(no_slide_pptx_path), "file_name": "no-slide.pptx", "format": "pptx", "artifact_type": "presentation", "template_not_applicable": True},
                        {"path": str(png_path), "file_name": "bad.png", "format": "png", "artifact_type": "image", "template_not_applicable": True},
                        {"path": str(bad_crc_png_path), "file_name": "bad-crc.png", "format": "png", "artifact_type": "image", "template_not_applicable": True},
                        {"path": str(csv_path), "file_name": "bad.csv", "format": "csv", "artifact_type": "data-export", "template_not_applicable": True},
                        {"path": str(bad_pdf_path), "file_name": "bad.pdf", "format": "pdf", "artifact_type": "pdf-document", "template_not_applicable": True},
                        {"path": str(missing_eof_pdf_path), "file_name": "missing-eof.pdf", "format": "pdf", "artifact_type": "pdf-document", "template_not_applicable": True},
                    ]
                }
            )

        self.assertEqual(result["status"], "failed")
        self.assertIn("artifact render qa failed", result["evidence"])
        self.assertTrue(any("pptx presentation.xml malformed XML" in finding for finding in result["findings"]))
        self.assertTrue(any("pptx package missing required parts" in finding for finding in result["findings"]))
        self.assertTrue(any("pptx package missing slide parts or slide relationships" in finding for finding in result["findings"]))
        self.assertTrue(any("png IHDR chunk missing" in finding for finding in result["findings"]))
        self.assertTrue(any("CRC mismatch" in finding for finding in result["findings"]))
        self.assertTrue(any("csv parse error" in finding for finding in result["findings"]))
        self.assertTrue(any("pdf signature missing" in finding for finding in result["findings"]))
        self.assertTrue(any("pdf EOF marker missing" in finding for finding in result["findings"]))

    def test_unknown_artifact_type_does_not_pass_template_quality_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            text_path = Path(tmp) / "artifact.txt"
            text_path.write_text("plain artifact", encoding="utf-8")

            result = evaluate_deliverable_quality(
                {
                    "deliverables": [
                        {
                            "path": str(text_path),
                            "file_name": "artifact.txt",
                            "format": "txt",
                            "artifact_type": "unknown-artifact",
                        }
                    ]
                }
            )

        self.assertEqual(result["status"], "failed")
        self.assertTrue(any("unknown artifact type" in finding for finding in result["findings"]))


if __name__ == "__main__":
    unittest.main()
