import sys
from pathlib import Path


SKILL_NAME = "compound-engineering-harness"


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "src").is_dir() and (parent / "skills").is_dir():
            return parent
    raise RuntimeError("repository root not found")


if __name__ == "__main__":
    sys.path.insert(0, str(_repo_root()))
    from src.skills.demo_scenarios import main

    raise SystemExit(main(SKILL_NAME))
