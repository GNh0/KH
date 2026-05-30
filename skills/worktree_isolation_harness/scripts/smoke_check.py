import importlib
import os
import sys
from pathlib import Path

SKILL_NAME = "worktree-isolation-harness"
REQUIRED_SUPPORT_FILES = [
    "references/usage.md",
    "examples/minimal-workflow.md",
    "scripts/smoke_check.py",
    "scripts/demo.py",
]
IMPLEMENTATION_TARGETS_PATTERN = "## UAF implementation targets"
IMPLEMENTATION_TARGETS = [
    "src.orchestration.development_progress.WORKSPACE_STRATEGIES",
    "skills/worktree_isolation_harness/SKILL.md",
    "skills/parallel_orchestration_harness/SKILL.md",
    "skills/development_lifecycle_harness/SKILL.md",
]


def find_repo_root(skill_root: Path) -> Path | None:
    env_root = os.environ.get("UAF_REPO_ROOT", "")
    if env_root:
        candidate = Path(env_root).resolve()
        if (candidate / "src").is_dir() and (candidate / "skills").is_dir():
            return candidate
    for candidate in [*skill_root.parents, Path.cwd(), *Path.cwd().parents]:
        if (candidate / "src").is_dir() and (candidate / "skills").is_dir():
            return candidate
    return None


def resolve_target(ref: str) -> bool:
    repo_root = find_repo_root(Path(__file__).resolve().parents[1])
    if "<" in ref or ">" in ref:
        return True
    if ref.startswith("skills/"):
        return bool(repo_root and (repo_root / ref).exists())
    if not ref.startswith(("src.", "tests.")):
        return bool(ref)
    if repo_root and str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    parts = ref.split(".")
    for index in range(len(parts), 0, -1):
        module_name = ".".join(parts[:index])
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name != module_name:
                raise
            continue
        current = module
        for attr in parts[index:]:
            if not hasattr(current, attr):
                return False
            current = getattr(current, attr)
        return True
    return False


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    skill_md = root / "SKILL.md"
    assert skill_md.exists(), "missing SKILL.md"
    for rel_path in REQUIRED_SUPPORT_FILES:
        assert (root / rel_path).exists(), f"missing {rel_path}"
    content = skill_md.read_text(encoding="utf-8")
    assert IMPLEMENTATION_TARGETS_PATTERN in content
    for target in IMPLEMENTATION_TARGETS:
        assert resolve_target(target), f"unresolved {target}"
    print(f"{SKILL_NAME} smoke_check ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
