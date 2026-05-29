import json
import os
import tempfile
import unittest
import zipfile
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
        package.writestr("word/document.xml", document_xml)


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

    def test_role_execution_audit_requires_artifacts_and_parallel_waves(self):
        role_metadata = {
            "summary": {
                "execution_model": "dag-asyncio-role-waves",
                "success": True,
                "wave_count": 3,
                "parallel_wave_count": 1,
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


if __name__ == "__main__":
    unittest.main()
