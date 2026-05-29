import os
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.contracts import WorkDesign
from src.orchestration.roles import default_role_profiles


QUALITY_EVIDENCE = {
    "template_passed": "deliverable template quality passed",
    "template_failed": "deliverable template quality failed",
    "render_passed": "artifact render qa passed",
    "render_failed": "artifact render qa failed",
    "traceability_passed": "traceability matrix passed",
    "traceability_failed": "traceability matrix failed",
    "role_audit_passed": "role execution audited",
    "role_audit_failed": "role execution audit failed",
}

NON_TEMPLATE_ARTIFACT_TYPES = {
    "technical-drawing",
    "cad-drawing",
}


TEMPLATE_MARKERS = {
    "requirements-brief": [
        "문서 정보", "개정 이력", "배경 및 목적", "범위",
        "기능 요구사항", "비기능 요구사항", "인수 기준",
    ],
    "orchestration-design": [
        "문서 정보", "설계 원칙", "역할 DAG", "병렬 실행 전략",
        "상태 저장소", "게이트 설계",
    ],
    "deliverable-definition": [
        "산출물 목록", "산출물별 정의", "품질 기준", "승인 기준",
    ],
    "process-flow": [
        "프로세스 개요", "스윔레인", "단계별 처리 흐름", "의사결정 지점", "예외 흐름",
    ],
    "role-task-breakdown": [
        "WBS ID", "작업명", "입력", "출력", "완료 기준", "의존성", "증거",
    ],
    "evidence-plan": [
        "증거 ID", "증거 키", "산출물", "검증 방법", "통과 기준", "차단 기준",
    ],
    "risk-policy-checklist": [
        "위험 ID", "분류", "위험 항목", "영향도", "발생 가능성", "완화 방안", "차단 기준",
    ],
    "user-manual": [
        "개정 이력", "사용 대상", "사전 준비", "사용 절차", "문제 해결",
    ],
    "manual": [
        "개정 이력", "사용 대상", "사전 준비", "사용 절차", "문제 해결",
    ],
    "functional-specification": [
        "문서 정보", "개정 이력", "기능 개요", "기능 목록", "기능 상세",
        "화면/메뉴", "권한", "입출력 정의", "처리 규칙", "인수 기준", "추적성",
    ],
    "development-design": [
        "문서 정보", "시스템 구성도", "아키텍처 구성", "모듈 설계",
        "인터페이스 설계", "데이터베이스 설계", "처리 흐름", "테스트 전략",
    ],
    "screen-api-definition": [
        "화면 목록", "화면 레이아웃", "화면 항목 정의", "이벤트 정의",
        "API 목록", "API 정의", "요청/응답", "상태 코드",
    ],
    "data-definition": [
        "테이블명", "컬럼명", "필드명", "자료형", "PK", "FK", "필수", "검증 규칙",
    ],
    "test-verification-plan": [
        "테스트 ID", "테스트 유형", "시나리오", "수행 절차", "기대 결과", "증거 키",
    ],
    "product-design-document": [
        "문서 정보", "개정 이력", "설계 개요", "규격 요약", "설계 요구사항",
        "치수 기준", "BOM", "도면 목록", "검증 방법", "승인 기준",
    ],
    "design-document": [
        "문서 정보", "개정 이력", "설계 개요", "규격 요약", "설계 요구사항",
        "치수 기준", "BOM", "도면 목록", "검증 방법", "승인 기준",
    ],
    "dimension-bom": [
        "품번", "품명", "재질", "규격", "치수", "수량", "공차", "근거",
    ],
    "table-model": [
        "품번", "품명", "재질", "규격", "치수", "수량", "공차", "근거",
    ],
    "analysis-report": [
        "문서 정보", "Executive Summary", "투자 개요", "핵심 가정",
        "시나리오 분석", "수익/위험 분석", "리스크", "최종 의견",
    ],
    "scenario-model": [
        "시나리오", "가정 항목", "기준값", "상승", "기준", "하락", "민감도", "근거",
    ],
    "traceability-matrix": [
        "Trace ID", "Requirement ID", "요구사항", "산출물", "산출물 유형",
        "증거 키", "검토 게이트", "상태",
    ],
}


def build_traceability_matrix_rows(
    work_design: WorkDesign,
    deliverable_records: Iterable[Dict[str, Any]],
    as_dict: bool = False,
) -> List[Any]:
    design = _as_work_design(work_design)
    records = [dict(record) for record in deliverable_records]
    header = [
        "Trace ID",
        "Requirement ID",
        "요구사항",
        "산출물",
        "산출물 유형",
        "증거 키",
        "검토 게이트",
        "상태",
        "비고",
    ]
    rows = [header]
    dict_rows: List[Dict[str, str]] = []
    requirements = list(design.deliverables) or ["final output"]
    gates = list(design.review_gates) or ["review gate", "qa gate", "release gate"]
    for index, record in enumerate(records, start=1):
        requirement = requirements[(index - 1) % len(requirements)]
        evidence_key = _record_evidence_key(record)
        row = [
            f"TRACE-{index:03d}",
            f"REQ-{index:03d}",
            str(requirement),
            _record_file_name(record),
            str(record.get("artifact_type") or record.get("kind") or record.get("format") or "deliverable"),
            evidence_key,
            gates[(index - 1) % len(gates)],
            str(record.get("gate_status") or record.get("status") or "planned"),
            "source input, deliverable, evidence, and gate must stay aligned",
        ]
        rows.append(row)
        dict_rows.append(_traceability_dict_row(row))
    if len(rows) == 1:
        row = [
            "TRACE-001",
            "REQ-001",
            design.objective or "final output",
            "final output",
            "deliverable",
            "workflow dispatch completed",
            gates[0],
            "planned",
            "fallback trace row",
        ]
        rows.append(row)
        dict_rows.append(_traceability_dict_row(row))
    return dict_rows if as_dict else rows


def evaluate_deliverable_quality(export_result: Dict[str, Any]) -> Dict[str, Any]:
    deliverables = [dict(item) for item in export_result.get("deliverables", [])]
    traceability_enabled = "traceability_rows" in export_result
    traceability_rows = _normalize_traceability_rows(export_result.get("traceability_rows", []) or [])
    findings: List[str] = []
    checks: List[Dict[str, Any]] = []
    template_failed = False
    render_failed = False
    traceability_failed = False

    for record in deliverables:
        path = Path(str(record.get("path", "")))
        artifact_type = str(record.get("artifact_type") or record.get("kind") or "")
        file_name = _record_file_name(record)
        render = _read_deliverable_text(path, str(record.get("format", "")))
        if render["status"] != "passed":
            render_failed = True
            template_failed = True
            findings.append(f"{file_name}: {render['message']}")
            checks.append(_check(file_name, "render", "failed", render["message"]))
            checks.append(_check(file_name, "template", "failed", "template markers were not evaluated because render failed"))
            continue
        checks.append(_check(file_name, "render", "passed", render["message"]))

        markers = TEMPLATE_MARKERS.get(artifact_type, [])
        if not markers:
            if artifact_type in NON_TEMPLATE_ARTIFACT_TYPES or record.get("template_not_applicable") or record.get("template_optional"):
                checks.append(_check(file_name, "template", "skipped", f"no template marker policy for {artifact_type or 'unknown artifact type'}"))
                continue
            template_failed = True
            findings.append(f"{file_name}: unknown artifact type `{artifact_type or 'unknown'}` has no template marker policy")
            checks.append(_check(file_name, "template", "failed", "unknown artifact type has no template marker policy"))
            continue
        missing = [marker for marker in markers if marker not in render["text"]]
        if missing:
            template_failed = True
            for marker in missing:
                findings.append(f"{file_name}: missing template marker `{marker}`")
            checks.append(_check(file_name, "template", "failed", f"missing: {', '.join(missing)}"))
        else:
            checks.append(_check(file_name, "template", "passed", "required markers present"))

        if artifact_type == "traceability-matrix":
            trace_status = _evaluate_traceability_text(render["text"])
            if trace_status["status"] != "passed":
                traceability_failed = True
                findings.extend(f"{file_name}: {item}" for item in trace_status["findings"])
            checks.append(_check(file_name, "traceability", trace_status["status"], trace_status["message"]))

    if traceability_enabled:
        traceability_status = _evaluate_traceability_rows(traceability_rows)
        if traceability_status["status"] != "passed":
            traceability_failed = True
            findings.extend(traceability_status["findings"])
        checks.append(_check(
            "traceability_matrix",
            "traceability",
            traceability_status["status"],
            traceability_status["message"],
        ))
    else:
        traceability_status = {
            "status": "skipped",
            "message": "traceability rows not supplied",
            "findings": [],
        }

    evidence = [
        QUALITY_EVIDENCE["template_failed" if template_failed else "template_passed"],
        QUALITY_EVIDENCE["render_failed" if render_failed else "render_passed"],
    ]
    if traceability_enabled:
        evidence.append(QUALITY_EVIDENCE["traceability_failed" if traceability_failed else "traceability_passed"])
    status = "failed" if template_failed or render_failed or traceability_failed else "passed"
    return {
        "status": status,
        "profile": export_result.get("profile", ""),
        "deliverable_count": len(deliverables),
        "checks": checks,
        "findings": findings,
        "traceability_matrix": {
            "storage": "metadata",
            "row_count": len(traceability_rows),
            "rows": traceability_rows,
            "status": traceability_status["status"],
        },
        "evidence": evidence,
    }


def audit_role_execution(
    role_metadata: Dict[str, Any],
    required_roles: Iterable[str] = None,
) -> Dict[str, Any]:
    summary = dict(role_metadata.get("summary", {}) or {})
    results = [dict(item) for item in role_metadata.get("results", []) or []]
    required = list(required_roles or _default_required_audit_roles(summary, results))
    by_role = {str(result.get("role", "")): result for result in results}
    findings: List[str] = []
    checks: List[Dict[str, Any]] = []

    if summary.get("execution_model") != "dag-asyncio-role-waves":
        findings.append("role orchestration execution_model is not dag-asyncio-role-waves")
    if not summary.get("success", False):
        findings.append("role orchestration summary is not successful")
    if int(summary.get("wave_count") or 0) <= 0:
        findings.append("role orchestration has no execution waves")
    if int(summary.get("parallel_wave_count") or 0) <= 0:
        findings.append("role orchestration did not record any parallel wave")

    for role in required:
        result = by_role.get(role)
        if not result:
            findings.append(f"{role} did not execute")
            continue
        if result.get("status") != "success":
            findings.append(f"{role} status is {result.get('status')}")
        metadata = dict(result.get("metadata", {}) or {})
        if role == "implementer" and metadata.get("evidence"):
            continue
        if not metadata.get("role_artifacts"):
            findings.append(f"{role} has no role_artifacts evidence")

    checks.append({
        "name": "role-execution-audit",
        "status": "failed" if findings else "passed",
        "required_roles": required,
        "role_count": len(results),
        "summary": summary,
    })
    passed = not findings
    return {
        "status": "passed" if passed else "failed",
        "findings": findings,
        "checks": checks,
        "evidence": [
            QUALITY_EVIDENCE["role_audit_passed" if passed else "role_audit_failed"]
        ],
    }


def _default_required_audit_roles(summary: Dict[str, Any], results: List[Dict[str, Any]]) -> List[str]:
    required = [
        profile.name
        for profile in default_role_profiles()
        if profile.name != "implementer"
    ]
    roles_present = {str(result.get("role", "")) for result in results}
    if summary.get("implementation_required") or "implementer" in roles_present:
        required.insert(required.index("spec-reviewer"), "implementer")
    return required


def _as_work_design(work_design: Any) -> WorkDesign:
    if isinstance(work_design, WorkDesign):
        return work_design
    if isinstance(work_design, dict):
        return WorkDesign.from_dict(work_design)
    raise TypeError("work_design must be WorkDesign or dict")


def _record_file_name(record: Dict[str, Any]) -> str:
    if record.get("file_name"):
        return str(record["file_name"])
    path = str(record.get("path", ""))
    return os.path.basename(path) if path else str(record.get("title", "deliverable"))


def _record_evidence_key(record: Dict[str, Any]) -> str:
    return str(record.get("evidence_key") or record.get("evidence") or f"{_record_file_name(record)} exported")


def _read_deliverable_text(path: Path, file_format: str) -> Dict[str, Any]:
    if not path.exists():
        return {"status": "failed", "message": "file does not exist", "text": ""}
    suffix = path.suffix.lower().lstrip(".")
    fmt = (file_format or suffix).lower()
    try:
        if fmt == "docx":
            if not zipfile.is_zipfile(path):
                return {"status": "failed", "message": "docx is not a zip package", "text": ""}
            with zipfile.ZipFile(path) as package:
                missing_parts = _missing_package_parts(package, [
                    "[Content_Types].xml",
                    "_rels/.rels",
                    "word/document.xml",
                ])
                if missing_parts:
                    return {"status": "failed", "message": f"docx package missing required parts: {', '.join(missing_parts)}", "text": ""}
                text = package.read("word/document.xml").decode("utf-8")
            return {"status": "passed", "message": "docx package readable", "text": text}
        if fmt == "xlsx":
            if not zipfile.is_zipfile(path):
                return {"status": "failed", "message": "xlsx is not a zip package", "text": ""}
            with zipfile.ZipFile(path) as package:
                missing_parts = _missing_package_parts(package, [
                    "[Content_Types].xml",
                    "_rels/.rels",
                    "xl/workbook.xml",
                    "xl/_rels/workbook.xml.rels",
                    "xl/worksheets/sheet1.xml",
                ])
                if missing_parts:
                    return {"status": "failed", "message": f"xlsx package missing required parts: {', '.join(missing_parts)}", "text": ""}
                text = package.read("xl/worksheets/sheet1.xml").decode("utf-8")
            widths = _xlsx_row_widths(path)
            if not widths or any(width != widths[0] for width in widths):
                return {"status": "failed", "message": f"xlsx row widths do not match header: {widths}", "text": text}
            return {"status": "passed", "message": "xlsx package readable and row widths match", "text": text}
        if fmt == "svg":
            text = path.read_text(encoding="utf-8")
            if "<svg" not in text or "</svg>" not in text:
                return {"status": "failed", "message": "svg root element missing", "text": text}
            return {"status": "passed", "message": "svg readable", "text": text}
        if fmt == "dxf":
            text = path.read_text(encoding="ascii")
            if "SECTION" not in text or "ENTITIES" not in text:
                return {"status": "failed", "message": "dxf SECTION/ENTITIES missing", "text": text}
            return {"status": "passed", "message": "dxf readable", "text": text}
        text = path.read_text(encoding="utf-8")
        return {"status": "passed", "message": f"{fmt or 'text'} readable", "text": text}
    except Exception as exc:
        return {"status": "failed", "message": f"{type(exc).__name__}: {exc}", "text": ""}


def _xlsx_row_widths(path: Path) -> List[int]:
    with zipfile.ZipFile(path) as package:
        root = ET.fromstring(package.read("xl/worksheets/sheet1.xml"))
    widths: List[int] = []
    for row in root.iter():
        if row.tag == "row" or row.tag.endswith("}row"):
            widths.append(sum(1 for cell in row if cell.tag == "c" or cell.tag.endswith("}c")))
    return widths


def _missing_package_parts(package: zipfile.ZipFile, required_parts: List[str]) -> List[str]:
    names = set(package.namelist())
    return [part for part in required_parts if part not in names]


def _normalize_traceability_rows(rows: Iterable[Any]) -> List[List[str]]:
    rows = list(rows)
    if not rows:
        return []
    if all(isinstance(row, dict) for row in rows):
        header = [
            "Trace ID",
            "Requirement ID",
            "요구사항",
            "산출물",
            "산출물 유형",
            "증거 키",
            "검토 게이트",
            "상태",
            "비고",
        ]
        normalized = [header]
        for row in rows:
            normalized.append([
                str(row.get("trace_id", "")),
                str(row.get("requirement_id", "")),
                str(row.get("requirement", "")),
                str(row.get("deliverable", "")),
                str(row.get("deliverable_type", "")),
                str(row.get("evidence_key", "")),
                str(row.get("gate", "")),
                str(row.get("status", "")),
                str(row.get("notes", "")),
            ])
        return normalized
    return [list(row) for row in rows]


def _evaluate_traceability_text(text: str) -> Dict[str, Any]:
    missing = [
        marker
        for marker in TEMPLATE_MARKERS["traceability-matrix"]
        if marker not in text
    ]
    if missing:
        return {
            "status": "failed",
            "message": f"missing traceability markers: {', '.join(missing)}",
            "findings": [f"missing traceability marker `{marker}`" for marker in missing],
        }
    return {
        "status": "passed",
        "message": "traceability matrix has required columns",
        "findings": [],
    }


def _evaluate_traceability_rows(rows: List[List[str]]) -> Dict[str, Any]:
    if len(rows) < 2:
        return {
            "status": "failed",
            "message": "traceability matrix has no data rows",
            "findings": ["traceability matrix has no data rows"],
        }
    expected_header = TEMPLATE_MARKERS["traceability-matrix"]
    header = rows[0]
    missing = [marker for marker in expected_header if marker not in header]
    findings = [f"traceability matrix missing column `{marker}`" for marker in missing]
    width = len(header)
    for index, row in enumerate(rows[1:], start=2):
        if len(row) != width:
            findings.append(f"traceability row {index} width {len(row)} does not match header width {width}")
        if len(row) > 7 and not (row[1] and row[3] and row[5] and row[6]):
            findings.append(f"traceability row {index} is missing requirement, deliverable, evidence, or gate")
    if findings:
        return {
            "status": "failed",
            "message": f"{len(findings)} traceability finding(s)",
            "findings": findings,
        }
    return {
        "status": "passed",
        "message": "traceability matrix rows map requirements to deliverables, evidence, and gates",
        "findings": [],
    }


def _check(file_name: str, check_type: str, status: str, message: str) -> Dict[str, str]:
    return {
        "file_name": file_name,
        "check_type": check_type,
        "status": status,
        "message": message,
    }


def _traceability_dict_row(row: List[str]) -> Dict[str, str]:
    return {
        "trace_id": row[0],
        "requirement_id": row[1],
        "requirement": row[2],
        "deliverable": row[3],
        "deliverable_type": row[4],
        "evidence_key": row[5],
        "gate": row[6],
        "status": row[7],
        "notes": row[8],
    }
