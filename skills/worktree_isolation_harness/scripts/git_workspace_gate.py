import sys
from pathlib import Path


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "src").is_dir() and (parent / "skills").is_dir():
            return parent
    raise RuntimeError("repository root not found")


if __name__ == "__main__":
    sys.path.insert(0, str(_repo_root()))
    from src.orchestration.git_workspace_gate import main

    raise SystemExit(main())
