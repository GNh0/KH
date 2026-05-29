import sys
from pathlib import Path


SKILL_NAME = "scenario-evaluation-harness"


def _find_repo_root() -> Path:
    for candidate in [Path(__file__).resolve(), *Path(__file__).resolve().parents]:
        if (candidate / "src").is_dir() and (candidate / "tests").is_dir():
            return candidate
    raise RuntimeError("repository root not found")


def main() -> int:
    repo_root = _find_repo_root()
    root_text = str(repo_root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    from src.skills.demo_scenarios import main

    return main(SKILL_NAME)


if __name__ == "__main__":
    raise SystemExit(main())
