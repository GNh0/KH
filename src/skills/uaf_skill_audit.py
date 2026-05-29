import importlib
import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.skills.uaf_skill_catalog import collect_packaged_skills


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TARGET_SECTION_RE = re.compile(
    r"## UAF implementation targets\s*(?P<body>.*?)(?:\n## |\Z)",
    re.DOTALL,
)
BACKTICK_REF_RE = re.compile(r"`([^`]+)`")


def extract_implementation_targets(content: str) -> List[str]:
    match = TARGET_SECTION_RE.search(content)
    if not match:
        return []
    return BACKTICK_REF_RE.findall(match.group("body"))


def resolve_target(ref: str, project_root: Path = PROJECT_ROOT) -> Dict[str, Any]:
    if "<" in ref or ">" in ref:
        return {"ref": ref, "status": "template", "path": ""}

    if ref.startswith("skills/"):
        target_path = project_root / ref
        return {
            "ref": ref,
            "status": "resolved" if target_path.exists() else "missing",
            "path": str(target_path) if target_path.exists() else "",
        }

    if not ref.startswith(("src.", "tests")):
        return {"ref": ref, "status": "unsupported", "path": ""}

    module, attr_path = _import_longest_module(ref)
    if module is None:
        return {"ref": ref, "status": "missing", "path": ""}

    current = module
    for attr in attr_path:
        if not hasattr(current, attr):
            return {
                "ref": ref,
                "status": "missing_attribute",
                "path": getattr(module, "__file__", "") or "",
                "missing_attribute": attr,
            }
        current = getattr(current, attr)

    return {
        "ref": ref,
        "status": "resolved",
        "path": getattr(module, "__file__", "") or "",
        "object_type": type(current).__name__ if attr_path else "module",
    }


def audit_packaged_skills(project_root: Path = PROJECT_ROOT, skill_name: str = "") -> Dict[str, Any]:
    catalog = collect_packaged_skills(str(project_root / "skills"))
    test_index = _build_test_index(project_root / "tests")
    skill_audits = []

    for skill in catalog["skills"]:
        if skill_name and skill["name"] != skill_name:
            continue
        skill_path = project_root / "skills" / skill["relative_path"]
        content = skill_path.read_text(encoding="utf-8")
        targets = extract_implementation_targets(content)
        target_results = []
        for ref in targets:
            target = resolve_target(ref, project_root)
            target["test_evidence"] = _test_evidence_for_target(ref, target, test_index)
            target_results.append(target)

        unresolved = [
            target for target in target_results
            if target["status"] not in {"resolved", "template"}
        ]
        executable = skill["execution_level"] in {"python-module", "hybrid-harness"}
        has_test_evidence = any(target["test_evidence"] for target in target_results)
        status = "passed"
        if unresolved:
            status = "failed"
        elif executable and not has_test_evidence:
            status = "needs-test-evidence"

        skill_audits.append({
            "name": skill["name"],
            "execution_level": skill["execution_level"],
            "relative_path": skill["relative_path"],
            "target_count": len(targets),
            "resolved_targets": sum(1 for target in target_results if target["status"] == "resolved"),
            "template_targets": sum(1 for target in target_results if target["status"] == "template"),
            "unresolved_targets": unresolved,
            "has_test_evidence": has_test_evidence,
            "status": status,
            "targets": target_results,
        })

    return {
        "success": all(skill["status"] == "passed" for skill in skill_audits),
        "total_skills": len(skill_audits),
        "execution_levels": catalog["execution_levels"],
        "skills": skill_audits,
    }


def render_markdown_report(report: Dict[str, Any]) -> str:
    lines = [
        "# KH UAF Skill and Harness Deep Audit",
        "",
        "This report audits every packaged `skills/<name>/SKILL.md` item as one host-visible skill/harness unit.",
        "",
        "## Summary",
        "",
        f"- Total packaged skills/harnesses: {report['total_skills']}",
        f"- Overall status: {'passed' if report['success'] else 'failed'}",
        f"- Execution levels: {json.dumps(report['execution_levels'], ensure_ascii=False, sort_keys=True)}",
        "",
        "## Skill Matrix",
        "",
        "| Skill | Level | Status | Targets | Test evidence |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for skill in report["skills"]:
        evidence = "yes" if skill["has_test_evidence"] else "no"
        lines.append(
            f"| `{skill['name']}` | `{skill['execution_level']}` | `{skill['status']}` | "
            f"{skill['target_count']} | {evidence} |"
        )

    lines.extend(["", "## Detailed Target Checks", ""])
    for skill in report["skills"]:
        lines.extend([
            f"### {skill['name']}",
            "",
            f"- Execution level: `{skill['execution_level']}`",
            f"- Status: `{skill['status']}`",
            f"- Skill file: `skills/{skill['relative_path']}`",
            "",
        ])
        for target in skill["targets"]:
            tests = ", ".join(f"`{item}`" for item in target["test_evidence"]) or "none"
            lines.append(
                f"- `{target['ref']}`: {target['status']}; tests: {tests}"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _import_longest_module(ref: str) -> Tuple[Any, List[str]]:
    parts = ref.split(".")
    for index in range(len(parts), 0, -1):
        module_name = ".".join(parts[:index])
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name != module_name:
                raise
            continue
        return module, parts[index:]
    return None, []


def _build_test_index(tests_dir: Path) -> Dict[str, str]:
    if not tests_dir.is_dir():
        return {}
    return {
        str(path.relative_to(PROJECT_ROOT)).replace(os.sep, "/"): path.read_text(encoding="utf-8")
        for path in sorted(tests_dir.glob("test_*.py"))
    }


def _test_evidence_for_target(ref: str, target: Dict[str, Any], test_index: Dict[str, str]) -> List[str]:
    if ref.startswith("tests."):
        path = ref.replace(".", "/") + ".py"
        return [path] if path in test_index else []
    if ref == "tests":
        return sorted(test_index)

    if target.get("status") == "template":
        return []

    tokens = _coverage_tokens(ref, target)
    evidence = []
    for path, content in test_index.items():
        if any(token and token in content for token in tokens):
            evidence.append(path)
    return evidence


def _coverage_tokens(ref: str, target: Dict[str, Any]) -> List[str]:
    tokens = [ref]
    parts = ref.split(".")
    if parts:
        tokens.append(parts[-1])
    path = target.get("path", "")
    if path:
        stem = Path(path).stem
        tokens.append(stem)
        try:
            rel = Path(path).resolve().relative_to(PROJECT_ROOT).as_posix()
            tokens.append(rel)
        except ValueError:
            pass
    return sorted(set(tokens), key=len, reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit packaged KH UAF skill implementation targets and tests.")
    parser.add_argument("--summary", action="store_true", help="Print only aggregate audit status.")
    parser.add_argument("--skill", default="", help="Audit one skill by frontmatter name.")
    args = parser.parse_args()

    report = audit_packaged_skills(skill_name=args.skill)
    if args.skill and report["total_skills"] == 0:
        payload = {
            "success": False,
            "total_skills": 0,
            "failed_skills": [args.skill],
            "error": f"skill not found: {args.skill}",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    if args.summary:
        print(json.dumps({
            "success": report["success"],
            "total_skills": report["total_skills"],
            "failed_skills": [
                skill["name"]
                for skill in report["skills"]
                if skill["status"] != "passed"
            ],
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
