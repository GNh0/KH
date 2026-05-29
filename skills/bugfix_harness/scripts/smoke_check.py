import importlib
import json
import re
import sys
from pathlib import Path


SKILL_NAME = 'bugfix-harness'
REQUIRED_SUPPORT_FILES = [
    "references/usage.md",
    "examples/minimal-workflow.md",
    "scripts/smoke_check.py",
]
IMPLEMENTATION_TARGETS_PATTERN = re.compile(
    r"^## UAF implementation targets\s*(?P<body>.*?)(?:\n## |\Z)",
    re.MULTILINE | re.DOTALL,
)
BACKTICK_REF_PATTERN = re.compile(r"`([^`]+)`")


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
    if ref == "tests":
        path = repo_root / "tests"
        return {"ref": ref, "status": "resolved" if path.is_dir() else "missing"}
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
    issues = []
    target_results = []

    if not skill_md.exists():
        issues.append({"code": "missing_skill_md", "path": "SKILL.md"})
        content = ""
    else:
        content = skill_md.read_text(encoding="utf-8")

    for rel_path in REQUIRED_SUPPORT_FILES:
        path = skill_dir / rel_path
        if not path.exists():
            issues.append({"code": "missing_support_file", "path": rel_path})
            continue
        if rel_path not in content:
            issues.append({"code": "support_file_not_referenced", "path": rel_path})

    targets = parse_implementation_targets(content)
    if not targets:
        issues.append({"code": "missing_implementation_targets", "path": "SKILL.md"})

    repo_root = find_repo_root(skill_dir)
    if repo_root is not None:
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
    else:
        target_results = [{"ref": target, "status": "repo_root_not_found"} for target in targets]

    result = {
        "skill": SKILL_NAME,
        "success": not issues,
        "support_files": REQUIRED_SUPPORT_FILES,
        "implementation_targets": target_results,
        "issues": issues,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
