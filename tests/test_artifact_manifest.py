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

                document_xml = _docx_xml(exported_paths["요구정의서.docx"])
                orchestration_xml = _docx_xml(exported_paths["오케스트레이션_설계서.docx"])
                deliverable_xml = _docx_xml(exported_paths["산출물_정의서.docx"])
                process_xml = _docx_xml(exported_paths["처리흐름도.docx"])
                sheet_xml = _xlsx_xml(exported_paths["역할별_작업분해표.xlsx"])
                evidence_xml = _xlsx_xml(exported_paths["증거계획서.xlsx"])
                risk_xml = _xlsx_xml(exported_paths["위험_정책_체크리스트.xlsx"])
                manual_xml = _docx_xml(exported_paths["사용_매뉴얼.docx"])
                _assert_xlsx_rows_match_header(self, exported_paths["역할별_작업분해표.xlsx"])
                _assert_xlsx_rows_match_header(self, exported_paths["증거계획서.xlsx"])
                _assert_xlsx_rows_match_header(self, exported_paths["위험_정책_체크리스트.xlsx"])

                self.assertIn("Warehouse Exception Review", document_xml)
                _assert_contains_all(self, document_xml, [
                    "문서 정보", "개정 이력", "배경 및 목적", "범위",
                    "용어 및 약어", "이해관계자", "기능 요구사항",
                    "비기능 요구사항", "인수 기준", "미해결 확인사항",
                ])
                _assert_contains_all(self, orchestration_xml, [
                    "문서 정보", "설계 원칙", "역할 DAG", "의존성",
                    "병렬 실행 전략", "상태 저장소", "게이트 설계",
                    "장애 및 재작업 절차",
                ])
                _assert_contains_all(self, deliverable_xml, [
                    "산출물 목록", "산출물별 정의", "입력 자료",
                    "품질 기준", "승인 기준", "보관 위치",
                ])
                _assert_contains_all(self, process_xml, [
                    "프로세스 개요", "스윔레인", "단계별 처리 흐름",
                    "의사결정 지점", "예외 흐름", "재작업 루프",
                ])
                _assert_contains_all(self, sheet_xml, [
                    "WBS ID", "작업명", "입력", "출력", "완료 기준",
                    "의존성", "우선순위", "증거",
                ])
                _assert_contains_all(self, evidence_xml, [
                    "증거 ID", "증거 키", "산출물", "검증 방법",
                    "수집 시점", "담당", "통과 기준", "차단 기준",
                ])
                _assert_contains_all(self, risk_xml, [
                    "위험 ID", "분류", "위험 항목", "영향도",
                    "발생 가능성", "위험 수준", "완화 방안", "담당", "차단 기준",
                ])
                _assert_contains_all(self, manual_xml, [
                    "개정 이력", "사용 대상", "사전 준비", "사용 절차",
                    "문제 해결", "문의/지원",
                ])
                self.assertGreaterEqual(sheet_xml.count("<row "), 10)
                self.assertGreaterEqual(evidence_xml.count("<row "), 10)
                self.assertGreaterEqual(risk_xml.count("<row "), 8)
                self.assertIn("리비전 버전 관리", manual_xml)
                self.assertIn("Rev. 1.0", manual_xml)
                self.assertLess(manual_xml.index("리비전 버전 관리"), manual_xml.index("운영"))
                self.assertIn("운영", manual_xml)
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

                self.assertIn("투자_분석보고서.docx", exported_names)
                self.assertIn("가정_시나리오.xlsx", exported_names)
                self.assertNotIn("추적성_매트릭스.xlsx", exported_names)
                self.assertNotIn("사용_매뉴얼.docx", exported_names)
                self.assertNotIn("요구정의서.docx", exported_names)
                self.assertNotIn("manual exported", result["evidence"])

                report_xml = _docx_xml(exported_paths["투자_분석보고서.docx"])
                scenario_xml = _xlsx_xml(exported_paths["가정_시나리오.xlsx"])
                _assert_xlsx_rows_match_header(self, exported_paths["가정_시나리오.xlsx"])
                _assert_xlsx_rows_match_header(self, exported_paths["위험_정책_체크리스트.xlsx"])
                _assert_contains_all(self, report_xml, [
                    "문서 정보", "Executive Summary", "투자 개요",
                    "핵심 가정", "시나리오 분석", "수익/위험 분석",
                    "리스크", "최종 의견", "면책/주의",
                ])
                _assert_contains_all(self, scenario_xml, [
                    "시나리오", "가정 항목", "기준값", "상승",
                    "기준", "하락", "민감도", "근거", "비고",
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
                    "요구정의서.docx",
                    "기능정의서.docx",
                    "개발설계서.docx",
                    "화면_API_정의서.docx",
                    "데이터_정의서.xlsx",
                    "역할별_작업분해표.xlsx",
                    "테스트_검증계획서.xlsx",
                    "위험_정책_체크리스트.xlsx",
                }
                plan_types = {item["artifact_type"] for item in result["deliverable_exports"]["plan"]}

                self.assertEqual(set(exported_paths), expected_names)
                self.assertIn("functional-specification", plan_types)
                self.assertIn("development-design", plan_types)
                self.assertIn("functional specification exported", result["evidence"])

                functional_xml = _docx_xml(exported_paths["기능정의서.docx"])
                design_xml = _docx_xml(exported_paths["개발설계서.docx"])
                screen_api_xml = _docx_xml(exported_paths["화면_API_정의서.docx"])
                data_xml = _xlsx_xml(exported_paths["데이터_정의서.xlsx"])
                test_xml = _xlsx_xml(exported_paths["테스트_검증계획서.xlsx"])
                _assert_xlsx_rows_match_header(self, exported_paths["데이터_정의서.xlsx"])
                _assert_xlsx_rows_match_header(self, exported_paths["역할별_작업분해표.xlsx"])
                _assert_xlsx_rows_match_header(self, exported_paths["테스트_검증계획서.xlsx"])
                _assert_xlsx_rows_match_header(self, exported_paths["위험_정책_체크리스트.xlsx"])

                _assert_contains_all(self, functional_xml, [
                    "문서 정보", "개정 이력", "기능 개요", "기능 목록",
                    "기능 상세", "화면/메뉴", "권한", "입출력 정의",
                    "처리 규칙", "예외 및 검증 규칙", "인수 기준", "추적성",
                ])
                _assert_contains_all(self, design_xml, [
                    "문서 정보", "시스템 구성도", "아키텍처 구성",
                    "모듈 설계", "인터페이스 설계", "데이터베이스 설계",
                    "처리 흐름", "오류 처리 및 로깅", "보안/권한",
                    "배포/운영", "테스트 전략",
                ])
                _assert_contains_all(self, screen_api_xml, [
                    "화면 목록", "화면 레이아웃", "화면 항목 정의",
                    "이벤트 정의", "API 목록", "API 정의",
                    "요청/응답", "상태 코드", "권한",
                ])
                _assert_contains_all(self, data_xml, [
                    "테이블명", "컬럼명", "필드명", "자료형", "길이",
                    "PK", "FK", "필수", "기본값", "설명", "검증 규칙",
                ])
                _assert_contains_all(self, test_xml, [
                    "테스트 ID", "테스트 유형", "기능", "시나리오",
                    "선행 조건", "입력값", "수행 절차", "기대 결과",
                    "검증 방법", "증거 키", "담당", "차단 기준",
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

                self.assertIn("제품_설계서.docx", exported_paths)
                self.assertIn("치수_BOM.xlsx", exported_paths)
                self.assertIn("개념_설계도.svg", exported_paths)
                self.assertIn("개념_설계도.dxf", exported_paths)
                self.assertNotIn("추적성_매트릭스.xlsx", exported_paths)
                self.assertNotIn("요구정의서.docx", exported_paths)
                self.assertIn("technical-drawing", plan_types)
                self.assertIn("cad-drawing", plan_types)
                self.assertIn("technical drawing exported", result["evidence"])
                self.assertIn("cad drawing exported", result["evidence"])

                product_doc_xml = _docx_xml(exported_paths["제품_설계서.docx"])
                bom_xml = _xlsx_xml(exported_paths["치수_BOM.xlsx"])
                svg_text = exported_paths["개념_설계도.svg"].read_text(encoding="utf-8")
                dxf_text = exported_paths["개념_설계도.dxf"].read_text(encoding="utf-8")
                _assert_xlsx_rows_match_header(self, exported_paths["치수_BOM.xlsx"])

                _assert_contains_all(self, product_doc_xml, [
                    "문서 정보", "개정 이력", "설계 개요", "규격 요약",
                    "설계 요구사항", "치수 기준", "BOM", "도면 목록",
                    "검증 방법", "제조 전 확인사항", "승인 기준",
                ])
                _assert_contains_all(self, bom_xml, [
                    "품번", "품명", "재질", "규격", "치수",
                    "수량", "공차", "근거", "비고",
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
