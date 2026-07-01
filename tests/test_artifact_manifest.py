import json
import os
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from src.orchestration.artifacts import ArtifactStore, build_design_stage
from src.orchestration.domain_profiles import DomainProfileBuilder, work_design_from_profile


def _docx_xml(path: Path) -> str:
    with zipfile.ZipFile(path) as package:
        return package.read("word/document.xml").decode("utf-8")


def _xlsx_xml(path: Path) -> str:
    with zipfile.ZipFile(path) as package:
        return package.read("xl/worksheets/sheet1.xml").decode("utf-8")


def _xlsx_row_widths(path: Path):
    with zipfile.ZipFile(path) as package:
        root = ET.fromstring(package.read("xl/worksheets/sheet1.xml"))
    widths = []
    for row in root.iter():
        if row.tag == "row" or row.tag.endswith("}row"):
            widths.append(sum(1 for cell in row if cell.tag == "c" or cell.tag.endswith("}c")))
    return widths


def _assert_xlsx_rows_match_header(test_case: unittest.TestCase, path: Path):
    widths = _xlsx_row_widths(path)
    test_case.assertGreater(len(widths), 1, path.name)
    test_case.assertTrue(
        all(width == widths[0] for width in widths),
        f"{path.name} row widths must match header: {widths}",
    )


def _assert_contains_all(test_case: unittest.TestCase, text: str, markers):
    for marker in markers:
        test_case.assertIn(marker, text)


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
                    "requirements_brief.docx",
                    "orchestration_design.docx",
                    "deliverable_definition.docx",
                    "process_flow.docx",
                    "role_task_breakdown.xlsx",
                    "evidence_plan.xlsx",
                    "risk_policy_checklist.xlsx",
                    "user_manual.docx",
                }

                self.assertEqual(set(exported_paths), expected_names)
                self.assertFalse((project_dir / ".uaf").exists())
                self.assertFalse((project_dir / ".snapshots").exists())
                for path in exported_paths.values():
                    self.assertEqual(path.parent, project_dir / "docs")
                    self.assertTrue(path.exists())
                    self.assertTrue(zipfile.is_zipfile(path))

                document_xml = _docx_xml(exported_paths["requirements_brief.docx"])
                orchestration_xml = _docx_xml(exported_paths["orchestration_design.docx"])
                deliverable_xml = _docx_xml(exported_paths["deliverable_definition.docx"])
                process_xml = _docx_xml(exported_paths["process_flow.docx"])
                sheet_xml = _xlsx_xml(exported_paths["role_task_breakdown.xlsx"])
                evidence_xml = _xlsx_xml(exported_paths["evidence_plan.xlsx"])
                risk_xml = _xlsx_xml(exported_paths["risk_policy_checklist.xlsx"])
                manual_xml = _docx_xml(exported_paths["user_manual.docx"])
                _assert_xlsx_rows_match_header(self, exported_paths["role_task_breakdown.xlsx"])
                _assert_xlsx_rows_match_header(self, exported_paths["evidence_plan.xlsx"])
                _assert_xlsx_rows_match_header(self, exported_paths["risk_policy_checklist.xlsx"])

                self.assertIn("Warehouse Exception Review", document_xml)
                _assert_contains_all(self, document_xml, [
                    "Document Info", "Revision History", "Background and Purpose", "Scope",
                    "Terms and Abbreviations", "Stakeholders", "Functional Requirements",
                    "Non-Functional Requirements", "Acceptance Criteria", "Open Questions",
                ])
                _assert_contains_all(self, orchestration_xml, [
                    "Document Info", "Design Principles", "Role DAG", "Dependencies",
                    "Parallel Execution Strategy", "State Stores", "Gate Design",
                    "Failure and Rework Procedure",
                ])
                _assert_contains_all(self, deliverable_xml, [
                    "Deliverable List", "Deliverable Definitions", "Input Materials",
                    "Quality Criteria", "Approval Criteria", "Storage Location",
                ])
                _assert_contains_all(self, process_xml, [
                    "Process Overview", "Swimlanes", "Step-by-Step Flow",
                    "Decision Points", "Exception Flow", "Rework Loop",
                ])
                _assert_contains_all(self, sheet_xml, [
                    "WBS ID", "Task Name", "Input", "Output", "Done Criteria",
                    "Dependency", "Priority", "Evidence",
                ])
                _assert_contains_all(self, evidence_xml, [
                    "Evidence ID", "Evidence Key", "Deliverable", "Verification Method",
                    "Collection Point", "Owner", "Pass Criteria", "Block Criteria",
                ])
                _assert_contains_all(self, risk_xml, [
                    "Risk ID", "Category", "Risk Item", "Impact",
                    "Probability", "Risk Level", "Mitigation", "Owner", "Block Criteria",
                ])
                _assert_contains_all(self, manual_xml, [
                    "Revision History", "Audience", "Prerequisites", "Procedure",
                    "Troubleshooting", "Support",
                ])
                self.assertGreaterEqual(sheet_xml.count("<row "), 10)
                self.assertGreaterEqual(evidence_xml.count("<row "), 10)
                self.assertGreaterEqual(risk_xml.count("<row "), 8)
                self.assertIn("Revision History", manual_xml)
                self.assertIn("Rev. 1.0", manual_xml)
                self.assertLess(manual_xml.index("Revision History"), manual_xml.index("Procedure"))
                self.assertIn("Procedure", manual_xml)
                self.assertIn("requirements brief exported", result["evidence"])
                self.assertIn("traceability matrix passed", result["evidence"])
                self.assertIn("deliverable template quality passed", result["evidence"])
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
                exported_paths = {
                    Path(item["path"]).name: Path(item["path"])
                    for item in result["deliverable_exports"]["deliverables"]
                }

                self.assertIn("investment_analysis_report.docx", exported_names)
                self.assertIn("scenario_model.xlsx", exported_names)
                self.assertNotIn("traceability_matrix.xlsx", exported_names)
                self.assertNotIn("user_manual.docx", exported_names)
                self.assertNotIn("requirements_brief.docx", exported_names)
                self.assertNotIn("manual exported", result["evidence"])

                report_xml = _docx_xml(exported_paths["investment_analysis_report.docx"])
                scenario_xml = _xlsx_xml(exported_paths["scenario_model.xlsx"])
                _assert_xlsx_rows_match_header(self, exported_paths["scenario_model.xlsx"])
                _assert_xlsx_rows_match_header(self, exported_paths["risk_policy_checklist.xlsx"])
                _assert_contains_all(self, report_xml, [
                    "Document Info", "Executive Summary", "Investment Overview",
                    "Key Assumptions", "Scenario Analysis", "Return and Risk Analysis",
                    "Risks", "Final View", "Disclaimer",
                ])
                _assert_contains_all(self, scenario_xml, [
                    "Scenario", "Assumption Item", "Base Value", "Upside",
                    "Base", "Downside", "Sensitivity", "Basis", "Notes",
                ])
        finally:
            if original_runtime_root is None:
                os.environ.pop("UAF_RUNTIME_ROOT", None)
            else:
                os.environ["UAF_RUNTIME_ROOT"] = original_runtime_root

    def test_build_design_stage_routes_software_development_to_functional_spec(self):
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
                    design_doc=(
                        "# Inventory Admin App\n"
                        "Build product CRUD, stock alert dashboard, and approval workflow."
                    ),
                    file_list=["src/app.py", "src/ui.js"],
                    metadata={
                        "domain_hint": "software-development",
                        "scope": "Build a web application feature set with API, UI, data, and QA coverage.",
                    },
                )

                exported = result["deliverable_exports"]["deliverables"]
                exported_paths = {Path(item["path"]).name: Path(item["path"]) for item in exported}
                expected_names = {
                    "requirements_brief.docx",
                    "functional_specification.docx",
                    "development_design.docx",
                    "screen_api_definition.docx",
                    "data_definition.xlsx",
                    "role_task_breakdown.xlsx",
                    "test_verification_plan.xlsx",
                    "risk_policy_checklist.xlsx",
                }
                plan_types = {item["artifact_type"] for item in result["deliverable_exports"]["plan"]}

                self.assertEqual(set(exported_paths), expected_names)
                self.assertIn("functional-specification", plan_types)
                self.assertIn("development-design", plan_types)
                self.assertIn("functional specification exported", result["evidence"])

                functional_xml = _docx_xml(exported_paths["functional_specification.docx"])
                design_xml = _docx_xml(exported_paths["development_design.docx"])
                screen_api_xml = _docx_xml(exported_paths["screen_api_definition.docx"])
                data_xml = _xlsx_xml(exported_paths["data_definition.xlsx"])
                test_xml = _xlsx_xml(exported_paths["test_verification_plan.xlsx"])
                _assert_xlsx_rows_match_header(self, exported_paths["data_definition.xlsx"])
                _assert_xlsx_rows_match_header(self, exported_paths["role_task_breakdown.xlsx"])
                _assert_xlsx_rows_match_header(self, exported_paths["test_verification_plan.xlsx"])
                _assert_xlsx_rows_match_header(self, exported_paths["risk_policy_checklist.xlsx"])

                _assert_contains_all(self, functional_xml, [
                    "Document Info", "Revision History", "Feature Overview", "Feature List",
                    "Feature Details", "Screens and Menus", "Permissions", "Input and Output",
                    "Processing Rules", "Exception and Validation Rules", "Acceptance Criteria", "Traceability",
                ])
                _assert_contains_all(self, design_xml, [
                    "Document Info", "System Context", "Architecture",
                    "Module Design", "Interface Design", "Database Design",
                    "Processing Flow", "Error Handling and Logging", "Security and Permissions",
                    "Deployment and Operations", "Test Strategy",
                ])
                _assert_contains_all(self, screen_api_xml, [
                    "Screen List", "Screen Layout", "Screen Field Definitions",
                    "Event Definitions", "API List", "API Definition",
                    "Request and Response", "Status Codes", "Permissions",
                ])
                _assert_contains_all(self, data_xml, [
                    "Table Name", "Column Name", "Field Name", "Data Type", "Length",
                    "PK", "FK", "Required", "Default", "Description", "Validation Rule",
                ])
                _assert_contains_all(self, test_xml, [
                    "Test ID", "Test Type", "Feature", "Scenario",
                    "Precondition", "Input", "Steps", "Expected Result",
                    "Verification Method", "Evidence Key", "Owner", "Block Criteria",
                ])
                self.assertGreaterEqual(data_xml.count("<row "), 8)
                self.assertGreaterEqual(test_xml.count("<row "), 8)
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
                    design_doc=(
                        "# 22kW CABLE GLAND PLATE 389\n"
                        "Create a design drawing from the supplied specification guide.\n"
                        "Plate size 200x120 mm, material SUS304, four M20 cable gland holes."
                    ),
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

                self.assertIn("product_design_document.docx", exported_paths)
                self.assertIn("dimension_bom.xlsx", exported_paths)
                self.assertIn("concept_drawing.svg", exported_paths)
                self.assertIn("concept_drawing.dxf", exported_paths)
                self.assertNotIn("traceability_matrix.xlsx", exported_paths)
                self.assertNotIn("requirements_brief.docx", exported_paths)
                self.assertIn("technical-drawing", plan_types)
                self.assertIn("cad-drawing", plan_types)
                self.assertIn("technical drawing exported", result["evidence"])
                self.assertIn("cad drawing exported", result["evidence"])

                product_doc_xml = _docx_xml(exported_paths["product_design_document.docx"])
                bom_xml = _xlsx_xml(exported_paths["dimension_bom.xlsx"])
                svg_text = exported_paths["concept_drawing.svg"].read_text(encoding="utf-8")
                dxf_text = exported_paths["concept_drawing.dxf"].read_text(encoding="utf-8")
                _assert_xlsx_rows_match_header(self, exported_paths["dimension_bom.xlsx"])

                _assert_contains_all(self, product_doc_xml, [
                    "Document Info", "Revision History", "Design Overview", "Specification Summary",
                    "Design Requirements", "Dimension Basis", "BOM", "Drawing List",
                    "Verification Method", "Manufacturing Readiness Checks", "Approval Criteria",
                ])
                _assert_contains_all(self, bom_xml, [
                    "Part No", "Part Name", "Material", "Specification", "Dimension",
                    "Quantity", "Tolerance", "Basis", "Notes",
                ])
                self.assertIn("CABLE GLAND PLATE 389", svg_text)
                self.assertIn("200", svg_text)
                self.assertIn("120", svg_text)
                self.assertIn("SUS304", svg_text)
                self.assertIn("4 x M20", svg_text)
                self.assertEqual(svg_text.count("<circle "), 4)
                self.assertIn("SECTION", dxf_text)
                self.assertIn("ENTITIES", dxf_text)
                self.assertIn("200x120", dxf_text)
                self.assertIn("SUS304", dxf_text)
                self.assertIn("4xM20", dxf_text)
                self.assertEqual(dxf_text.count("CIRCLE"), 4)
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
