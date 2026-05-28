import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from src.orchestration.artifacts import ArtifactStore, build_design_stage
from src.orchestration.domain_profiles import DomainProfileBuilder, work_design_from_profile


class ArtifactStoreTests(unittest.TestCase):
    def test_default_artifact_storage_does_not_create_project_uaf_folder(self):
        original_runtime_root = os.environ.get("UAF_RUNTIME_ROOT")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                project_dir = Path(tmp) / "demo"
                runtime_root = Path(tmp) / "runtime"
                project_dir.mkdir()
                os.environ["UAF_RUNTIME_ROOT"] = str(runtime_root)
                profile = DomainProfileBuilder.build(objective="Design a plan", domain_hint="ops")
                design = work_design_from_profile(profile, deliverables=["plan"])
                store = ArtifactStore(str(project_dir))

                result = store.save_work_design(
                    workflow_id="workflow_demo",
                    work_design=design,
                    source_design_doc="# Source design",
                )

                self.assertFalse((project_dir / ".uaf").exists())
                self.assertTrue(str(result["store"]["manifest_path"]).startswith(str(runtime_root)))
                self.assertTrue(Path(result["store"]["manifest_path"]).exists())
        finally:
            if original_runtime_root is None:
                os.environ.pop("UAF_RUNTIME_ROOT", None)
            else:
                os.environ["UAF_RUNTIME_ROOT"] = original_runtime_root

    def test_store_saves_work_design_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = DomainProfileBuilder.build(
                objective="Design a launch plan",
                domain_hint="marketing",
                artifact_types=["channel-plan"],
            )
            design = work_design_from_profile(profile, deliverables=["launch memo"])
            store = ArtifactStore(tmp)

            result = store.save_work_design(
                workflow_id="workflow_demo",
                work_design=design,
                source_design_doc="# Source design",
            )

            manifest_path = Path(result["store"]["manifest_path"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            artifact_path = Path(result["manifest"]["design_artifacts"][0]["path"])

            self.assertTrue(artifact_path.exists())
            self.assertEqual(manifest["workflow_id"], "workflow_demo")
            self.assertIn("work design saved", result["evidence"])
            self.assertIn("artifact manifest saved", result["evidence"])
            self.assertIn("required design artifacts saved", result["evidence"])

    def test_store_saves_additional_design_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ArtifactStore(tmp)

            result = store.save_design_artifacts(
                workflow_id="workflow_demo",
                domain="generic",
                artifact_specs=[
                    {
                        "artifact_id": "risk_matrix",
                        "kind": "risk-matrix",
                        "title": "Risk Matrix",
                        "content": "# Risks\n",
                        "owner_role": "risk-policy-reviewer",
                        "required_for": ["review"],
                    }
                ],
            )

            self.assertEqual(result["manifest"]["design_artifacts"][0]["artifact_id"], "risk_matrix")
            self.assertTrue(Path(result["manifest"]["design_artifacts"][0]["path"]).exists())

    def test_store_trims_artifact_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ArtifactStore(tmp)
            profile = DomainProfileBuilder.build(objective="Design a plan", domain_hint="ops")
            design = work_design_from_profile(profile, deliverables=["plan"])

            store.save_work_design("workflow_demo", design, "# Source")
            store.save_design_artifacts(
                workflow_id="workflow_demo",
                domain="generic",
                artifact_specs=[
                    {
                        "artifact_id": "risk_matrix",
                        "kind": "risk-matrix",
                        "title": "Risk Matrix",
                        "content": "# Risks\n",
                    }
                ],
            )

            summary = store.trim_events(max_events=1)
            lines = Path(store.events_path).read_text(encoding="utf-8").splitlines()

            self.assertEqual(summary["before"], 2)
            self.assertEqual(summary["after"], 1)
            self.assertEqual(json.loads(lines[0])["event_type"], "design_artifact_saved")

    def test_build_design_stage_exports_domain_neutral_office_deliverables_to_docs(self):
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
                    design_doc="# Warehouse Exception Review\nCoordinate exception review across operations.",
                    file_list=["exception-report", "operator-handoff"],
                    metadata={
                        "domain_hint": "operations",
                        "scope": "Coordinate a repeatable cross-team review workflow.",
                        "manual_revision": "Rev. 1.0",
                        "manual_revision_note": "Initial operations handoff manual.",
                    },
                )

                exported = result["deliverable_exports"]["deliverables"]
                exported_paths = {Path(item["path"]).name: Path(item["path"]) for item in exported}
                expected_names = {
                    "요구정의서.docx",
                    "오케스트레이션_설계서.docx",
                    "산출물_정의서.docx",
                    "처리흐름도.docx",
                    "역할별_작업분해표.xlsx",
                    "증거계획서.xlsx",
                    "위험_정책_체크리스트.xlsx",
                    "사용_매뉴얼.docx",
                }

                self.assertEqual(set(exported_paths), expected_names)
                self.assertFalse((project_dir / ".uaf").exists())
                self.assertFalse((project_dir / ".snapshots").exists())
                for path in exported_paths.values():
                    self.assertEqual(path.parent, project_dir / "docs")
                    self.assertTrue(path.exists())
                    self.assertTrue(zipfile.is_zipfile(path))

                with zipfile.ZipFile(exported_paths["요구정의서.docx"]) as package:
                    document_xml = package.read("word/document.xml").decode("utf-8")
                with zipfile.ZipFile(exported_paths["오케스트레이션_설계서.docx"]) as package:
                    orchestration_xml = package.read("word/document.xml").decode("utf-8")
                with zipfile.ZipFile(exported_paths["산출물_정의서.docx"]) as package:
                    deliverable_xml = package.read("word/document.xml").decode("utf-8")
                with zipfile.ZipFile(exported_paths["처리흐름도.docx"]) as package:
                    process_xml = package.read("word/document.xml").decode("utf-8")
                with zipfile.ZipFile(exported_paths["역할별_작업분해표.xlsx"]) as package:
                    sheet_xml = package.read("xl/worksheets/sheet1.xml").decode("utf-8")
                with zipfile.ZipFile(exported_paths["증거계획서.xlsx"]) as package:
                    evidence_xml = package.read("xl/worksheets/sheet1.xml").decode("utf-8")
                with zipfile.ZipFile(exported_paths["위험_정책_체크리스트.xlsx"]) as package:
                    risk_xml = package.read("xl/worksheets/sheet1.xml").decode("utf-8")
                with zipfile.ZipFile(exported_paths["사용_매뉴얼.docx"]) as package:
                    manual_xml = package.read("word/document.xml").decode("utf-8")

                self.assertIn("Warehouse Exception Review", document_xml)
                self.assertIn("기능 요구사항", document_xml)
                self.assertIn("인수 기준", document_xml)
                self.assertIn("미해결 확인사항", document_xml)
                self.assertIn("역할 DAG", orchestration_xml)
                self.assertIn("병렬 실행 전략", orchestration_xml)
                self.assertIn("재작업 루프", process_xml)
                self.assertIn("단계별 처리 흐름", process_xml)
                self.assertIn("산출물 품질 기준", deliverable_xml)
                self.assertIn("생성 조건", deliverable_xml)
                self.assertIn("operator-handoff", sheet_xml)
                self.assertIn("완료 기준", sheet_xml)
                self.assertIn("검증 방법", evidence_xml)
                self.assertIn("차단 기준", risk_xml)
                self.assertGreaterEqual(sheet_xml.count("<row "), 10)
                self.assertGreaterEqual(evidence_xml.count("<row "), 10)
                self.assertGreaterEqual(risk_xml.count("<row "), 8)
                self.assertIn("리비전 버전 관리", manual_xml)
                self.assertIn("Rev. 1.0", manual_xml)
                self.assertLess(manual_xml.index("리비전 버전 관리"), manual_xml.index("운영"))
                self.assertIn("운영", manual_xml)
                self.assertIn("requirements brief exported", result["evidence"])
                self.assertIn("manual exported", result["evidence"])
        finally:
            if original_runtime_root is None:
                os.environ.pop("UAF_RUNTIME_ROOT", None)
            else:
                os.environ["UAF_RUNTIME_ROOT"] = original_runtime_root

    def test_build_design_stage_skips_manual_for_investment_analysis_by_default(self):
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
                    design_doc="# Portfolio Review\nAssess an investment thesis.",
                    file_list=["investment-memo"],
                    metadata={
                        "domain_hint": "investment",
                        "scope": "Analyze risk, valuation, and investment decision evidence.",
                    },
                )

                exported_names = {
                    Path(item["path"]).name
                    for item in result["deliverable_exports"]["deliverables"]
                }

                self.assertIn("투자_분석보고서.docx", exported_names)
                self.assertIn("가정_시나리오.xlsx", exported_names)
                self.assertNotIn("사용_매뉴얼.docx", exported_names)
                self.assertNotIn("요구정의서.docx", exported_names)
                self.assertNotIn("manual exported", result["evidence"])
        finally:
            if original_runtime_root is None:
                os.environ.pop("UAF_RUNTIME_ROOT", None)
            else:
                os.environ["UAF_RUNTIME_ROOT"] = original_runtime_root

    def test_build_design_stage_routes_product_design_to_drawing_artifacts(self):
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
                    design_doc="# 22kW CABLE GLAND PLATE 389\nCreate a design drawing from the supplied specification guide.",
                    file_list=["CABLE GLAND PLATE 389"],
                    metadata={
                        "domain_hint": "product-design",
                        "scope": "Create concept drawing and CAD handoff artifacts for cable gland plate specification.",
                    },
                )

                exported = result["deliverable_exports"]["deliverables"]
                exported_paths = {Path(item["path"]).name: Path(item["path"]) for item in exported}
                plan = result["deliverable_exports"]["plan"]
                plan_types = {item["artifact_type"] for item in plan}

                self.assertIn("제품_설계서.docx", exported_paths)
                self.assertIn("치수_BOM.xlsx", exported_paths)
                self.assertIn("개념_설계도.svg", exported_paths)
                self.assertIn("개념_설계도.dxf", exported_paths)
                self.assertNotIn("요구정의서.docx", exported_paths)
                self.assertIn("technical-drawing", plan_types)
                self.assertIn("cad-drawing", plan_types)
                self.assertIn("technical drawing exported", result["evidence"])
                self.assertIn("cad drawing exported", result["evidence"])

                svg_text = exported_paths["개념_설계도.svg"].read_text(encoding="utf-8")
                dxf_text = exported_paths["개념_설계도.dxf"].read_text(encoding="utf-8")

                self.assertIn("CABLE GLAND PLATE 389", svg_text)
                self.assertIn("SECTION", dxf_text)
                self.assertIn("ENTITIES", dxf_text)
        finally:
            if original_runtime_root is None:
                os.environ.pop("UAF_RUNTIME_ROOT", None)
            else:
                os.environ["UAF_RUNTIME_ROOT"] = original_runtime_root

    def test_store_rejects_unsafe_artifact_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ArtifactStore(tmp)

            with self.assertRaises(ValueError):
                store.save_design_artifacts(
                    workflow_id="workflow_demo",
                    domain="generic",
                    artifact_specs=[
                        {
                            "artifact_id": "../outside",
                            "kind": "bad",
                            "title": "Bad",
                            "content": "bad",
                        }
                    ],
                )


if __name__ == "__main__":
    unittest.main()
