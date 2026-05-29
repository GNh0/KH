import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from src.skills.uaf_skill_catalog import collect_packaged_skills


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = PROJECT_ROOT / "skills"

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
}

BANNED_LOCAL_REFERENCES = [
    r"C:\Users\KONEIT\.gemini",
    r"C:\Users\KONEIT\.codex\plugins\cache",
]


def audit_skill_packaging_quality(
    project_root: Path = PROJECT_ROOT,
    run_smoke_scripts: bool = False,
) -> Dict[str, Any]:
    """Audit packaged UAF skills for science-style support-file quality."""
    skills_dir = project_root / "skills"
    catalog = collect_packaged_skills(str(skills_dir))
    skill_reports = []

    for skill in catalog["skills"]:
        skill_dir = skills_dir / skill["relative_path"].split("/", 1)[0]
        skill_path = skill_dir / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")
        issues: List[Dict[str, str]] = []

        for rel_path, rule in REQUIRED_SUPPORT_FILES.items():
            support_path = skill_dir / rel_path
            if not support_path.exists():
                issues.append(_issue("missing_support_file", rel_path, "Required support file is missing."))
                continue

            support_content = support_path.read_text(encoding="utf-8")
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
                    issues.append(
                        _issue(
                            "support_file_missing_marker",
                            rel_path,
                            f"Support file is missing marker: {marker}",
                        )
                    )

            min_bytes = int(rule.get("min_bytes", 0))
            if min_bytes and len(support_content.encode("utf-8")) < min_bytes:
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
                    issues.append(
                        _issue(
                            "smoke_script_syntax_error",
                            rel_path,
                            f"{exc.msg} at line {exc.lineno}",
                        )
                    )

        for banned in BANNED_LOCAL_REFERENCES:
            if banned in content:
                issues.append(
                    _issue(
                        "host_local_reference",
                        "SKILL.md",
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

        skill_reports.append({
            "name": skill["name"],
            "execution_level": skill["execution_level"],
            "relative_path": skill["relative_path"],
            "support_files": sorted(REQUIRED_SUPPORT_FILES),
            "smoke_execution": smoke_execution,
            "issues": issues,
            "valid": not issues,
        })

    issues = [
        issue
        for skill_report in skill_reports
        for issue in skill_report["issues"]
    ]
    return {
        "success": not issues,
        "total_skills": len(skill_reports),
        "valid_skills": sum(1 for item in skill_reports if item["valid"]),
        "invalid_skills": sum(1 for item in skill_reports if not item["valid"]),
        "required_support_files": sorted(REQUIRED_SUPPORT_FILES),
        "smoke_scripts_executed": bool(run_smoke_scripts),
        "skills": sorted(skill_reports, key=lambda item: item["name"]),
    }


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


def main() -> int:
    report = audit_skill_packaging_quality(run_smoke_scripts=True)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
