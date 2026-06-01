import argparse
import json
import sys
from pathlib import Path


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "src").is_dir() and (parent / "skills").is_dir():
            return parent
    raise RuntimeError("repository root not found")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    repo_root = _repo_root()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.orchestration.kh_front_door import build_kh_front_door

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    scenarios = [
        "Create a small static task tracker in this folder and verify it.",
        "Summarize this long pytest log and keep the failing test, file line, assertion values, and exit code.",
        "Explain what this sentence means in simple terms.",
    ]
    results = [
        build_kh_front_door(prompt=scenario, project=repo_root, host="codex").to_summary_dict()
        for scenario in scenarios
    ]
    report = {
        "skill": "automatic-intake-harness",
        "success": all("automatic-intake-harness" in item["runtime_applied_skills"] for item in results),
        "results": results,
    }
    report_path = output_dir / "automatic_intake_demo.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"success": report["success"], "path": str(report_path)}, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
