"""No-write package smoke check for the C# Designer style harness."""

from __future__ import annotations

import ast
import importlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


SKILL_NAME = "csharp-designer-style-harness"
REQUIRED_SUPPORT_FILES = [
    "references/usage.md",
    "examples/minimal-workflow.md",
    "scripts/smoke_check.py",
    "scripts/demo.py",
]
IMPLEMENTATION_TARGETS_PATTERN = re.compile(
    r"^## UAF implementation targets\s*(?P<body>.*?)(?:\n## |\Z)",
    re.MULTILINE | re.DOTALL,
)
BACKTICK_REF_PATTERN = re.compile(r"`([^`]+)`")
RUNTIME_MODULE = "src/skills/csharp_designer_style_contract.py"


def find_repo_root(skill_dir: Path) -> Path | None:
    for candidate in [skill_dir, *skill_dir.parents]:
        if (candidate / "src").is_dir() and (candidate / "tests").is_dir():
            return candidate
    return None


def parse_implementation_targets(content: str) -> list[str]:
    match = IMPLEMENTATION_TARGETS_PATTERN.search(content)
    if not match:
        return []
    return BACKTICK_REF_PATTERN.findall(match.group("body"))


def resolve_target(repo_root: Path, ref: str) -> dict[str, str]:
    if "<" in ref or ">" in ref:
        return {"ref": ref, "status": "template"}
    if ref.startswith("skills/"):
        path = repo_root / ref
        return {"ref": ref, "status": "resolved" if path.exists() else "missing"}
    if not ref.startswith(("src.", "tests.")):
        return {"ref": ref, "status": "unsupported"}

    root_text = str(repo_root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    parts = ref.split(".")
    for index in range(len(parts), 0, -1):
        module_name = ".".join(parts[:index])
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name != module_name:
                return {"ref": ref, "status": "import_error", "detail": str(exc)}
            continue
        current = module
        for attr in parts[index:]:
            if not hasattr(current, attr):
                return {"ref": ref, "status": "missing_attribute", "detail": attr}
            current = getattr(current, attr)
        return {"ref": ref, "status": "resolved"}
    return {"ref": ref, "status": "missing"}


def main() -> int:
    skill_dir = Path(__file__).resolve().parents[1]
    skill_md = skill_dir / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8") if skill_md.exists() else ""
    issues: list[dict[str, str]] = []
    target_results: list[dict[str, str]] = []

    if not content:
        issues.append({"code": "missing_skill_md", "path": "SKILL.md"})
    for rel_path in REQUIRED_SUPPORT_FILES:
        path = skill_dir / rel_path
        if not path.exists():
            issues.append({"code": "missing_support_file", "path": rel_path})
        elif rel_path not in content:
            issues.append({"code": "support_file_not_referenced", "path": rel_path})

    targets = parse_implementation_targets(content)
    if not targets:
        issues.append({"code": "missing_implementation_targets", "path": "SKILL.md"})

    repo_root = find_repo_root(skill_dir)
    if repo_root is None:
        issues.append({"code": "repo_root_not_found", "path": str(skill_dir)})
    else:
        runtime_path = repo_root / RUNTIME_MODULE
        try:
            ast.parse(runtime_path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as exc:
            issues.append({"code": "runtime_ast_failed", "path": RUNTIME_MODULE, "detail": str(exc)})
        for target in targets:
            result = resolve_target(repo_root, target)
            target_results.append(result)
            if result["status"] not in {"resolved", "template"}:
                issues.append({
                    "code": "unresolved_implementation_target",
                    "path": "SKILL.md",
                    "target": target,
                    "status": result["status"],
                })

    demo_result: dict[str, object] = {"success": False, "message": "not run"}
    if not issues:
        with tempfile.TemporaryDirectory(prefix="csharp-designer-style-smoke-") as tmp:
            completed = subprocess.run(
                [sys.executable, str(skill_dir / "scripts" / "demo.py"), "--output-dir", tmp],
                cwd=skill_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            try:
                payload = json.loads(completed.stdout)
            except json.JSONDecodeError as exc:
                issues.append({"code": "demo_json_invalid", "detail": str(exc)})
            else:
                success_payload = dict(payload.get("success_case", {}).get("payload", {}) or {})
                success_metadata = dict(success_payload.get("metadata", {}) or {})
                contract_receipt = dict(success_metadata.get("contract_receipt", {}) or {})
                verification_id = str(success_metadata.get("verification_id", ""))
                contract_sha256 = str(success_metadata.get("contract_sha256", ""))
                demo_result = {
                    "success": completed.returncode == 0,
                    "exit_code": completed.returncode,
                    "success_case": payload.get("success_case", {}).get("status"),
                    "blocked_case": payload.get("blocked_or_failure_case", {}).get("status"),
                    "verification_id": verification_id,
                    "contract_sha256": contract_sha256,
                }
                if completed.returncode != 0:
                    issues.append({"code": "demo_failed", "detail": (completed.stderr or completed.stdout)[-1000:]})
                if payload.get("success_case", {}).get("status") != "passed":
                    issues.append({"code": "demo_success_case_missing"})
                if payload.get("blocked_or_failure_case", {}).get("status") not in {"blocked", "failed"}:
                    issues.append({"code": "demo_failure_case_missing"})
                if success_payload.get("success") is not True or success_metadata.get("status") != "passed":
                    issues.append({"code": "demo_success_verifier_result_missing"})
                if not re.fullmatch(r"csharp-style-[0-9a-f]{32}", verification_id):
                    issues.append({"code": "demo_verification_id_missing_or_invalid"})
                if not re.fullmatch(r"sha256:[0-9a-f]{64}", contract_sha256):
                    issues.append({"code": "demo_contract_sha256_missing_or_invalid"})
                if contract_sha256 != str(contract_receipt.get("sha256", "")):
                    issues.append({"code": "demo_contract_sha256_receipt_mismatch"})

    result = {
        "skill": SKILL_NAME,
        "execution_level": "python-module",
        "success": not issues,
        "support_files": REQUIRED_SUPPORT_FILES,
        "implementation_targets": target_results,
        "runtime_ast": not any(issue.get("code") == "runtime_ast_failed" for issue in issues),
        "demo": demo_result,
        "issues": issues,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
