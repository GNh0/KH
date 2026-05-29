import argparse
import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.skills.uaf_skill_audit import audit_packaged_skills
from src.skills.uaf_skill_catalog import collect_packaged_skills


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = PROJECT_ROOT / "skills"

MINIMUM_PRACTICAL_QUALITY_SCORE = 8.0
CORE_PRODUCTION_QUALITY_SCORE = 9.0

CORE_PRODUCTION_SKILLS = {
    "adapter-contract-harness",
    "artifact-render-qa-harness",
    "brainstorming-harness",
    "compound-engineering-harness",
    "deliverable-template-quality-harness",
    "domain-orchestration-harness",
    "goal-state-harness",
    "health-check-harness",
    "memory-state-harness",
    "orchestration-role-graph",
    "parallel-orchestration-harness",
    "qa-gate-harness",
    "review-gate-harness",
    "request-complexity-router",
    "scenario-evaluation-harness",
    "role-execution-audit-harness",
    "snapshot-state-harness",
    "subagent-review-pipeline",
    "token-optimizer",
    "traceability-matrix-harness",
}

QUALITY_RUBRIC = {
    "trigger_discovery": {
        "max": 1.0,
        "basis": "Frontmatter trigger, concise description, and searchable skill body.",
    },
    "workflow_procedure": {
        "max": 1.5,
        "basis": "Host-readable workflow, required outputs, support-file wiring, and scenario coverage.",
    },
    "runtime_implementation": {
        "max": 2.0,
        "basis": "Resolved UAF implementation targets, execution-level distinction, and runnable support checks.",
    },
    "verification_evidence": {
        "max": 2.0,
        "basis": "Smoke execution, deep target audit, and repository test evidence.",
    },
    "failure_safety": {
        "max": 1.0,
        "basis": "Failure handling, common mistakes, blocked/fallback language, and host-path independence.",
    },
    "examples_references": {
        "max": 1.0,
        "basis": "Usage reference and minimal workflow depth, evidence, failure cases, and done criteria.",
    },
    "integration_observability": {
        "max": 1.0,
        "basis": "Evidence, gates, roles, state, artifacts, dispatch, contracts, and runtime-path observability.",
    },
    "maintainability": {
        "max": 0.5,
        "basis": "Support files referenced from SKILL.md, parseable smoke scripts, and clean audit issues.",
    },
}

REQUIRED_SUPPORT_FILES = {
    "references/usage.md": {
        "min_bytes": 1500,
        "required_markers": [
            "# ",
            "## When to use",
            "## Inputs to collect",
            "## Execution pattern",
            "## Evidence to produce",
            "## Failure handling",
            "## Quality bar",
        ],
    },
    "examples/minimal-workflow.md": {
        "min_bytes": 1200,
        "required_markers": [
            "# ",
            "## Scenario",
            "## Expected steps",
            "## Expected evidence",
            "## Failure cases",
            "## Done criteria",
            "actual_runtime_path",
        ],
    },
    "scripts/smoke_check.py": {
        "min_bytes": 1700,
        "required_markers": [
            "SKILL_NAME",
            "REQUIRED_SUPPORT_FILES",
            "IMPLEMENTATION_TARGETS_PATTERN",
            "resolve_target",
            "def main",
        ],
    },
    "scripts/demo.py": {
        "min_bytes": 450,
        "required_markers": [
            "SKILL_NAME",
            "src.skills.demo_scenarios",
            "main(SKILL_NAME)",
        ],
    },
}

BANNED_LOCAL_REFERENCES = [
    r"C:\Users\KONEIT\.gemini",
    r"C:\Users\KONEIT\.codex\plugins\cache",
]


def audit_skill_packaging_quality(
    project_root: Path = PROJECT_ROOT,
    run_smoke_scripts: bool = False,
) -> Dict[str, Any]:
    """Audit UAF skills against a practical 10-point skill/harness rubric."""
    skills_dir = project_root / "skills"
    catalog = collect_packaged_skills(str(skills_dir))
    deep_audit = audit_packaged_skills(project_root)
    deep_by_name = {item["name"]: item for item in deep_audit["skills"]}
    skill_reports = []

    for skill in catalog["skills"]:
        skill_dir = skills_dir / skill["relative_path"].split("/", 1)[0]
        skill_path = skill_dir / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")
        issues: List[Dict[str, str]] = []
        support_contents: Dict[str, str] = {}
        support_report = {}

        for rel_path, rule in REQUIRED_SUPPORT_FILES.items():
            support_path = skill_dir / rel_path
            support_detail = {
                "present": support_path.exists(),
                "referenced_from_skill_md": rel_path in content,
                "bytes": 0,
                "missing_markers": [],
                "parseable": True,
            }
            support_report[rel_path] = support_detail

            if not support_path.exists():
                issues.append(_issue("missing_support_file", rel_path, "Required support file is missing."))
                continue

            support_content = support_path.read_text(encoding="utf-8")
            support_contents[rel_path] = support_content
            support_detail["bytes"] = len(support_content.encode("utf-8"))

            if rel_path not in content:
                issues.append(
                    _issue(
                        "support_file_not_referenced",
                        rel_path,
                        "Support file must be referenced from SKILL.md with when-to-read or when-to-run guidance.",
                    )
                )

            for marker in rule["required_markers"]:
                if marker not in support_content:
                    support_detail["missing_markers"].append(marker)
                    issues.append(
                        _issue(
                            "support_file_missing_marker",
                            rel_path,
                            f"Support file is missing marker: {marker}",
                        )
                    )

            min_bytes = int(rule.get("min_bytes", 0))
            if min_bytes and support_detail["bytes"] < min_bytes:
                issues.append(
                    _issue(
                        "support_file_too_shallow",
                        rel_path,
                        f"Support file is below the minimum useful size: {min_bytes} bytes.",
                    )
                )

            if rel_path.endswith(".py"):
                try:
                    ast.parse(support_content)
                except SyntaxError as exc:
                    support_detail["parseable"] = False
                    issues.append(
                        _issue(
                            "smoke_script_syntax_error",
                            rel_path,
                            f"{exc.msg} at line {exc.lineno}",
                        )
                    )

        all_skill_text = "\n".join([content, *support_contents.values()])
        for banned in BANNED_LOCAL_REFERENCES:
            if banned in all_skill_text:
                issues.append(
                    _issue(
                        "host_local_reference",
                        "skill_package",
                        f"Skill must not depend on local host path {banned}.",
                    )
                )

        smoke_execution = {}
        if run_smoke_scripts:
            smoke_execution = _run_smoke_script(skill_dir)
            if not smoke_execution.get("success"):
                issues.append(
                    _issue(
                        "smoke_script_failed",
                        "scripts/smoke_check.py",
                        smoke_execution.get("message", "Smoke script failed."),
                    )
                )

        demo_execution = {}
        if run_smoke_scripts:
            demo_execution = _run_demo_script(skill_dir, skill["name"])
            if not demo_execution.get("success"):
                issues.append(
                    _issue(
                        "demo_script_failed",
                        "scripts/demo.py",
                        demo_execution.get("message", "Demo script failed."),
                    )
                )

        deep_skill = deep_by_name.get(skill["name"], {})
        quality_components, quality_gaps = _score_skill_quality(
            skill=skill,
            skill_md=content,
            support_contents=support_contents,
            support_report=support_report,
            issues=issues,
            smoke_execution=smoke_execution,
            demo_execution=demo_execution,
            deep_skill=deep_skill,
        )
        quality_score = round(sum(quality_components.values()), 1)
        quality_rating = _quality_rating(quality_score)
        minimum_required_score = (
            CORE_PRODUCTION_QUALITY_SCORE
            if skill["name"] in CORE_PRODUCTION_SKILLS
            else MINIMUM_PRACTICAL_QUALITY_SCORE
        )

        skill_reports.append({
            "name": skill["name"],
            "description": skill["description"],
            "execution_level": skill["execution_level"],
            "relative_path": skill["relative_path"],
            "support_files": sorted(REQUIRED_SUPPORT_FILES),
            "support_report": support_report,
            "smoke_execution": smoke_execution,
            "demo_execution": demo_execution,
            "deep_audit": {
                "status": deep_skill.get("status"),
                "target_count": deep_skill.get("target_count", 0),
                "resolved_targets": deep_skill.get("resolved_targets", 0),
                "template_targets": deep_skill.get("template_targets", 0),
                "has_test_evidence": deep_skill.get("has_test_evidence", False),
            },
            "quality_components": quality_components,
            "quality_score": quality_score,
            "quality_rating": quality_rating,
            "minimum_required_score": minimum_required_score,
            "quality_gaps": quality_gaps,
            "issues": issues,
            "valid": not issues and quality_score >= minimum_required_score,
        })

    packaging_issues = [
        issue
        for skill_report in skill_reports
        for issue in skill_report["issues"]
    ]
    low_quality = [
        {
            "name": item["name"],
            "score": item["quality_score"],
            "required": item["minimum_required_score"],
            "rating": item["quality_rating"],
            "gaps": item["quality_gaps"],
        }
        for item in skill_reports
        if item["quality_score"] < item["minimum_required_score"]
    ]
    lowest_score = min((item["quality_score"] for item in skill_reports), default=0.0)
    return {
        "success": not packaging_issues and not low_quality,
        "quality_success": not low_quality,
        "total_skills": len(skill_reports),
        "valid_skills": sum(1 for item in skill_reports if item["valid"]),
        "invalid_skills": sum(1 for item in skill_reports if not item["valid"]),
        "minimum_practical_quality_score": MINIMUM_PRACTICAL_QUALITY_SCORE,
        "core_production_quality_score": CORE_PRODUCTION_QUALITY_SCORE,
        "core_production_skills": sorted(CORE_PRODUCTION_SKILLS),
        "lowest_quality_score": lowest_score,
        "quality_rubric": QUALITY_RUBRIC,
        "required_support_files": sorted(REQUIRED_SUPPORT_FILES),
        "smoke_scripts_executed": bool(run_smoke_scripts),
        "low_quality_skills": low_quality,
        "skills": sorted(skill_reports, key=lambda item: item["name"]),
    }


def _score_skill_quality(
    *,
    skill: Dict[str, Any],
    skill_md: str,
    support_contents: Dict[str, str],
    support_report: Dict[str, Dict[str, Any]],
    issues: List[Dict[str, str]],
    smoke_execution: Dict[str, Any],
    demo_execution: Dict[str, Any],
    deep_skill: Dict[str, Any],
) -> Tuple[Dict[str, float], List[str]]:
    usage = support_contents.get("references/usage.md", "")
    example = support_contents.get("examples/minimal-workflow.md", "")
    combined = "\n".join([skill_md, usage, example]).lower()
    issue_codes = {issue["code"] for issue in issues}
    target_count = int(deep_skill.get("target_count") or 0)
    resolved_count = int(deep_skill.get("resolved_targets") or 0)
    template_count = int(deep_skill.get("template_targets") or 0)
    target_resolution_ratio = (
        (resolved_count + template_count) / target_count if target_count else 0.0
    )
    target_evidence_count = sum(
        1
        for target in deep_skill.get("targets", [])
        if target.get("test_evidence")
    )
    target_evidence_ratio = target_evidence_count / target_count if target_count else 0.0
    gaps: List[str] = []

    components = {
        "trigger_discovery": 0.0,
        "workflow_procedure": 0.0,
        "runtime_implementation": 0.0,
        "verification_evidence": 0.0,
        "failure_safety": 0.0,
        "examples_references": 0.0,
        "integration_observability": 0.0,
        "maintainability": 0.0,
    }

    description = skill.get("description", "")
    _add(components, "trigger_discovery", 0.35, description.startswith("Use when"), gaps, "description must start with 'Use when'")
    _add(components, "trigger_discovery", 0.20, 30 <= len(description) <= 500, gaps, "description must be specific but concise")
    _add(components, "trigger_discovery", 0.20, "# " in skill_md, gaps, "SKILL.md needs a primary heading")
    name_tokens = [token for token in skill["name"].split("-") if len(token) > 3]
    _add(
        components,
        "trigger_discovery",
        0.25,
        any(token in combined for token in name_tokens),
        gaps,
        "skill body should include searchable name-specific keywords",
    )

    _add(components, "workflow_procedure", 0.25, "## Required outputs" in skill_md, gaps, "SKILL.md needs required outputs")
    _add(
        components,
        "workflow_procedure",
        0.25,
        any(
            marker in skill_md
            for marker in [
                "## Workflow",
                "## Instructions",
                "## Pattern basis",
                "## CLI",
                "## Core Flow",
                "## Command lifecycle",
                "## Hook workflow",
                "## Runtime contract",
                "## Stage order",
            ]
        ),
        gaps,
        "SKILL.md needs an explicit workflow or instruction section",
    )
    _add(
        components,
        "workflow_procedure",
        0.25,
        all(path in skill_md for path in REQUIRED_SUPPORT_FILES),
        gaps,
        "SKILL.md must reference every support file",
    )
    _add(
        components,
        "workflow_procedure",
        0.30,
        _support_markers_ok(support_report, "references/usage.md"),
        gaps,
        "usage reference is missing required workflow markers",
    )
    _add(
        components,
        "workflow_procedure",
        0.25,
        _support_markers_ok(support_report, "examples/minimal-workflow.md"),
        gaps,
        "minimal workflow example is missing required markers",
    )
    _add(
        components,
        "workflow_procedure",
        0.20,
        "execution level:" in usage.lower() and "implementation targets" in usage.lower(),
        gaps,
        "usage reference must state execution level and implementation targets",
    )

    _add(components, "runtime_implementation", 0.35, target_count > 0, gaps, "missing UAF implementation targets")
    _add(
        components,
        "runtime_implementation",
        0.50,
        target_resolution_ratio == 1.0,
        gaps,
        "all UAF implementation targets must resolve or be explicit templates",
    )
    _add(components, "runtime_implementation", 0.25, target_count >= 3, gaps, "implementation target coverage is too thin")
    _add(
        components,
        "runtime_implementation",
        0.25,
        skill.get("execution_level") in {"python-module", "hybrid-harness", "procedure-policy"},
        gaps,
        "execution level must be cataloged",
    )
    _add(
        components,
        "runtime_implementation",
        0.25,
        bool(smoke_execution.get("success")) and bool(demo_execution.get("success")),
        gaps,
        "smoke and demo scripts must execute successfully",
    )
    _add(
        components,
        "runtime_implementation",
        0.20,
        any(marker in combined for marker in ["python -m", "python -c", "dispatch", "adapter", "policy"]),
        gaps,
        "runtime or procedural application path must be explicit",
    )
    _add(
        components,
        "runtime_implementation",
        0.20,
        deep_skill.get("status") == "passed",
        gaps,
        "deep target audit must pass",
    )

    _add(
        components,
        "verification_evidence",
        0.30,
        "smoke_script_syntax_error" not in issue_codes,
        gaps,
        "smoke script must be parseable",
    )
    _add(components, "verification_evidence", 0.35, bool(smoke_execution.get("success")) and bool(demo_execution.get("success")), gaps, "smoke and runnable demo execution evidence are required")
    _add(components, "verification_evidence", 0.45, bool(deep_skill.get("has_test_evidence")), gaps, "implementation targets need test evidence")
    _add(
        components,
        "verification_evidence",
        0.35,
        target_evidence_ratio >= 0.5,
        gaps,
        "at least half of implementation targets should have direct test evidence",
    )
    _add(components, "verification_evidence", 0.25, deep_skill.get("status") == "passed", gaps, "deep target audit must pass")
    _add(
        components,
        "verification_evidence",
        0.20,
        "verification" in example.lower() or "tests." in combined,
        gaps,
        "example should describe verification evidence",
    )
    _add(
        components,
        "verification_evidence",
        0.10,
        "actual_runtime_path" in example,
        gaps,
        "example must expose actual runtime path",
    )

    _add(components, "failure_safety", 0.25, "## Common mistakes" in skill_md, gaps, "SKILL.md needs common mistakes")
    _add(components, "failure_safety", 0.25, "## Failure handling" in usage, gaps, "usage reference needs failure handling")
    _add(components, "failure_safety", 0.20, "do not" in combined, gaps, "skill should include explicit do-not constraints")
    _add(
        components,
        "failure_safety",
        0.15,
        any(term in combined for term in ["blocked", "fallback", "stop using", "withhold completion"]),
        gaps,
        "failure path should mention blocked, fallback, or stop behavior",
    )
    _add(components, "failure_safety", 0.15, "host_local_reference" not in issue_codes, gaps, "skill must not depend on local host paths")

    _add(
        components,
        "examples_references",
        0.35,
        _support_depth_ok(support_report, "references/usage.md") and _support_depth_ok(support_report, "examples/minimal-workflow.md"),
        gaps,
        "usage and example support files must meet depth requirements",
    )
    _add(
        components,
        "examples_references",
        0.25,
        all(marker in example for marker in ["## Scenario", "## Expected evidence", "## Failure cases", "## Done criteria"]),
        gaps,
        "minimal workflow must include scenario, evidence, failure cases, and done criteria",
    )
    _add(
        components,
        "examples_references",
        0.25,
        all(marker in usage for marker in ["## Inputs to collect", "## Evidence to produce", "## Quality bar"]),
        gaps,
        "usage reference must include inputs, evidence, and quality bar",
    )
    _add(
        components,
        "examples_references",
        0.15,
        "implementation_targets" in example.lower() and "Implementation targets" in usage,
        gaps,
        "examples and references must repeat implementation targets",
    )

    observability_terms = [
        "evidence",
        "gate",
        "state",
        "role",
        "artifact",
        "dispatch",
        "adapter",
        "contract",
        "harness",
    ]
    observed_terms = {term for term in observability_terms if term in combined}
    _add(components, "integration_observability", 0.25, "evidence" in combined, gaps, "skill must require evidence")
    _add(
        components,
        "integration_observability",
        0.25,
        len(observed_terms) >= 3,
        gaps,
        "skill should connect to UAF role/gate/state/artifact/contract observability",
    )
    _add(components, "integration_observability", 0.15, "actual_runtime_path" in example, gaps, "actual runtime path must be recorded")
    _add(components, "integration_observability", 0.15, "## UAF implementation targets" in skill_md, gaps, "SKILL.md needs UAF implementation targets")
    _add(components, "integration_observability", 0.10, "execution_level" in example.lower(), gaps, "example must state execution level")
    _add(
        components,
        "integration_observability",
        0.10,
        skill.get("source") == "uaf_skill_folder" and not skill.get("external_runtime_dependency"),
        gaps,
        "skill should be packaged and not depend on external runtime skill folders",
    )

    _add(
        components,
        "maintainability",
        0.15,
        "support_file_not_referenced" not in issue_codes and "missing_support_file" not in issue_codes,
        gaps,
        "support files must be present and linked",
    )
    _add(components, "maintainability", 0.15, not issues, gaps, "packaging issues must be cleared")
    _add(components, "maintainability", 0.10, _support_parseable(support_report, "scripts/smoke_check.py"), gaps, "smoke script must be parseable")
    _add(components, "maintainability", 0.10, not deep_skill.get("unresolved_targets"), gaps, "target audit must have no unresolved targets")

    return {name: round(score, 2) for name, score in components.items()}, gaps


def _add(
    components: Dict[str, float],
    component: str,
    amount: float,
    condition: bool,
    gaps: List[str],
    gap: str,
) -> None:
    if condition:
        components[component] += amount
    else:
        gaps.append(gap)


def _support_markers_ok(support_report: Dict[str, Dict[str, Any]], rel_path: str) -> bool:
    detail = support_report.get(rel_path, {})
    return bool(detail.get("present")) and not detail.get("missing_markers")


def _support_depth_ok(support_report: Dict[str, Dict[str, Any]], rel_path: str) -> bool:
    detail = support_report.get(rel_path, {})
    rule = REQUIRED_SUPPORT_FILES[rel_path]
    return bool(detail.get("present")) and detail.get("bytes", 0) >= int(rule.get("min_bytes", 0))


def _support_parseable(support_report: Dict[str, Dict[str, Any]], rel_path: str) -> bool:
    detail = support_report.get(rel_path, {})
    return bool(detail.get("present")) and bool(detail.get("parseable", False))


def _quality_rating(score: float) -> str:
    if score >= 9.0:
        return "excellent"
    if score >= 8.0:
        return "production-ready"
    if score >= 7.0:
        return "usable-with-caveats"
    if score >= 6.0:
        return "needs-hardening"
    return "weak"


def _issue(code: str, path: str, message: str) -> Dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _run_smoke_script(skill_dir: Path) -> Dict[str, Any]:
    script_path = skill_dir / "scripts" / "smoke_check.py"
    if not script_path.exists():
        return {
            "success": False,
            "returncode": None,
            "message": "Smoke script is missing.",
        }

    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=skill_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    message = (completed.stdout or completed.stderr or "").strip()
    return {
        "success": completed.returncode == 0,
        "returncode": completed.returncode,
        "message": message[:2000],
    }


def _run_demo_script(skill_dir: Path, skill_name: str) -> Dict[str, Any]:
    script_path = skill_dir / "scripts" / "demo.py"
    if not script_path.exists():
        return {
            "success": False,
            "returncode": None,
            "message": "Demo script is missing.",
        }

    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / skill_name
        completed = subprocess.run(
            [sys.executable, str(script_path), "--output-dir", str(output_dir)],
            cwd=skill_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        message = (completed.stdout or completed.stderr or "").strip()
        if completed.returncode != 0:
            return {
                "success": False,
                "returncode": completed.returncode,
                "message": message[:2000],
            }
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            return {
                "success": False,
                "returncode": completed.returncode,
                "message": f"Demo stdout is not JSON: {exc}",
            }

        validation_errors = _validate_demo_payload(skill_name, payload, output_dir)
        if validation_errors:
            return {
                "success": False,
                "returncode": completed.returncode,
                "message": f"Demo payload failed validation: {', '.join(validation_errors[:8])}",
            }
        return {
            "success": True,
            "returncode": completed.returncode,
            "message": json.dumps({
                "schema_version": payload.get("schema_version"),
                "skill": payload.get("skill"),
                "artifact_count": len(payload.get("artifacts", [])),
                "contract_count": len(payload.get("contracts", [])),
                "verification": payload.get("verification", {}),
            }, ensure_ascii=False),
        }


def _validate_demo_payload(skill_name: str, payload: Dict[str, Any], output_dir: Path) -> List[str]:
    errors: List[str] = []
    required_keys = {
        "schema_version",
        "skill",
        "success_case",
        "blocked_or_failure_case",
        "contracts",
        "host_metadata",
        "artifacts",
        "verification",
    }
    for key in sorted(required_keys.difference(payload)):
        errors.append(f"missing {key}")
    if payload.get("schema_version") != "1.0":
        errors.append("schema_version must be 1.0")
    if payload.get("skill") != skill_name:
        errors.append("skill name mismatch")

    success_case = dict(payload.get("success_case", {}) or {})
    if success_case.get("status") != "passed":
        errors.append("success_case.status must be passed")
    if not success_case.get("contract_type"):
        errors.append("success_case.contract_type missing")
    if not success_case.get("evidence"):
        errors.append("success_case evidence missing")

    blocked_case = dict(payload.get("blocked_or_failure_case", {}) or {})
    if blocked_case.get("status") not in {"blocked", "failed"}:
        errors.append("blocked_or_failure_case.status must be blocked or failed")
    if not blocked_case.get("contract_type"):
        errors.append("blocked_or_failure_case.contract_type missing")
    if not (blocked_case.get("blocked_reason") or blocked_case.get("error_code")):
        errors.append("blocked/failure reason missing")
    if not blocked_case.get("remediation"):
        errors.append("blocked/failure remediation missing")
    if blocked_case.get("non_destructive") is not True:
        errors.append("blocked/failure case must be non_destructive")

    contracts = list(payload.get("contracts", []) or [])
    if not contracts:
        errors.append("contracts empty")
    for index, contract in enumerate(contracts):
        if not contract.get("name"):
            errors.append(f"contract {index} missing name")
        if not contract.get("module"):
            errors.append(f"contract {index} missing module")
        if not contract.get("fields_checked"):
            errors.append(f"contract {index} fields_checked empty")
        if contract.get("roundtrip_checked") is not True:
            errors.append(f"contract {index} did not roundtrip")
        if contract.get("source") not in {"dataclass", "gate-result", "policy-result", "artifact-validator"}:
            errors.append(f"contract {index} source invalid")

    host = dict(payload.get("host_metadata", {}) or {})
    if host.get("selected_host") not in {"local", "codex", "antigravity-style", "claude-code"}:
        errors.append("host selected_host invalid")
    if len(host.get("host_differences", []) or []) < 3:
        errors.append("host_differences too shallow")
    if Path(str(host.get("output_dir", ""))) != output_dir:
        errors.append("host output_dir mismatch")
    if host.get("external_runtime_dependency") is not False:
        errors.append("external_runtime_dependency must be false")

    artifacts = list(payload.get("artifacts", []) or [])
    if not artifacts:
        errors.append("artifacts empty")
    for index, artifact in enumerate(artifacts):
        artifact_path = Path(str(artifact.get("path", "")))
        if not artifact_path.exists():
            errors.append(f"artifact {index} path missing")
        if not _path_is_relative_to(artifact_path, output_dir):
            errors.append(f"artifact {index} outside output_dir")
        if artifact.get("validated") is not True:
            errors.append(f"artifact {index} not validated")
        if not artifact.get("checksum"):
            errors.append(f"artifact {index} checksum missing")
        if not artifact.get("validation_evidence"):
            errors.append(f"artifact {index} validation evidence missing")

    verification = dict(payload.get("verification", {}) or {})
    for key in [
        "runnable",
        "stdout_json_only",
        "contract_roundtrip",
        "artifacts_within_output_dir",
        "artifacts_validated",
    ]:
        if verification.get(key) is not True:
            errors.append(f"verification {key} must be true")
    if verification.get("exit_code") != 0:
        errors.append("verification exit_code must be 0")
    runtime_observation = dict(verification.get("runtime_observation", {}) or {})
    if runtime_observation.get("source") != "outer subprocess quality gate":
        errors.append("verification runtime_observation source invalid")
    declared_paths = {Path(str(artifact.get("path", ""))).resolve() for artifact in artifacts}
    generated_paths = {path.resolve() for path in output_dir.rglob("*") if path.is_file()}
    if generated_paths != declared_paths:
        errors.append("artifact manifest does not declare every generated file")
    return errors


def _path_is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit packaged UAF skills against the local quality gate.")
    parser.add_argument("--no-smoke", action="store_true", help="Skip per-skill smoke_check.py execution.")
    parser.add_argument("--summary", action="store_true", help="Print a compact summary instead of full JSON.")
    args = parser.parse_args()

    report = audit_skill_packaging_quality(run_smoke_scripts=not args.no_smoke)
    if args.summary:
        print(json.dumps({
            "success": report["success"],
            "total_skills": report["total_skills"],
            "valid_skills": report["valid_skills"],
            "invalid_skills": report["invalid_skills"],
            "lowest_quality_score": report["lowest_quality_score"],
            "low_quality_skills": report["low_quality_skills"],
        }, ensure_ascii=False, indent=2))
        return 0 if report["success"] else 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
