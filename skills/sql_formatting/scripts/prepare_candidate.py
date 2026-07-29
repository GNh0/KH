import argparse
import hashlib
import json
import sys
from pathlib import Path


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "src").is_dir() and (parent / "skills").is_dir():
            return parent
    raise RuntimeError("repository root not found")


def _read_utf8(path: Path) -> str:
    return path.read_bytes().decode("utf-8", errors="strict")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Apply a source-bound alias plan and canonical JOIN whitespace to a SQL candidate. "
            "The plan must contain the exact candidate SHA-256 and per-scope declaration fingerprints."
        )
    )
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--alias-role-plan")
    args = parser.parse_args()

    repo_root = _repo_root()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from src.skills.sql_formatting_style import (
        apply_sql_alias_role_plan,
        normalize_sql_join_layout,
    )

    candidate_path = Path(args.candidate).resolve()
    output_path = Path(args.output).resolve()
    try:
        candidate = _read_utf8(candidate_path)
        prepared = candidate
        alias_plan_applied = False
        alias_plan_source_sql_sha256 = ""
        if args.alias_role_plan:
            plan = json.loads(_read_utf8(Path(args.alias_role_plan).resolve()))
            prepared = apply_sql_alias_role_plan(prepared, plan)
            alias_plan_applied = True
            alias_plan_source_sql_sha256 = str(plan.get("source_sql_sha256", ""))
        prepared = normalize_sql_join_layout(prepared)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(prepared.encode("utf-8"))
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "candidate": str(candidate_path),
                    "output": str(output_path),
                    "error": str(exc),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1

    print(
        json.dumps(
            {
                "status": "prepared",
                "candidate": str(candidate_path),
                "output": str(output_path),
                "alias_plan_applied": alias_plan_applied,
                "alias_plan_binding_verified": alias_plan_applied,
                "alias_plan_source_sql_sha256": alias_plan_source_sql_sha256,
                "changed": prepared != candidate,
                "candidate_sha256": _sha256(candidate),
                "prepared_sha256": _sha256(prepared),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
