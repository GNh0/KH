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


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _read_text_with_fallback(path: Path) -> tuple[str, str]:
    data = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "cp949"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return data.decode("cp949", errors="replace"), "cp949-replace"


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def main() -> int:
    _configure_stdout()
    parser = argparse.ArgumentParser(description="Extract SQL-looking fragments from exported PowerBuilder source.")
    parser.add_argument("--source-root", required=True, help="Exported PB source root, not the source PBL tree.")
    parser.add_argument("--output-dir", required=True, help="Directory for probe JSON output.")
    parser.add_argument("--plan-only", action="store_true", help="Emit a source-safe PBL validation plan only.")
    args = parser.parse_args()

    repo_root = _repo_root()
    sys.path.insert(0, str(repo_root))
    from src.skills.sql_formatting_style import (
        build_powerbuilder_sql_validation_plan,
        extract_powerbuilder_sql_fragments,
        validate_powerbuilder_output_dir,
    )

    source_root = Path(args.source_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    guard = validate_powerbuilder_output_dir(source_root=source_root, output_dir=output_dir)
    if not guard["allowed"]:
        _print_json(
            {
                "status": "blocked",
                "reason": "forbidden_output_dir",
                "output_guard": guard,
                "artifact_written": False,
            }
        )
        return 2

    plan = build_powerbuilder_sql_validation_plan(pbl_root=source_root, output_dir=output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.plan_only:
        payload = {"status": "planned", "plan": plan, "fragments": []}
    else:
        fragments = []
        encodings = {}
        for path in sorted(source_root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".srw", ".sru", ".srd", ".txt", ".sql"}:
                continue
            text, encoding = _read_text_with_fallback(path)
            rel = str(path.relative_to(source_root))
            encodings[rel] = encoding
            fragments.extend(extract_powerbuilder_sql_fragments(text, source_name=rel))
        payload = {
            "status": "fragments_extracted",
            "plan": plan,
            "source_root": str(source_root),
            "output_dir": str(output_dir),
            "fragment_count": len(fragments),
            "fragments": fragments,
            "source_encodings": encodings,
            "source_write_guard": not _is_relative_to(output_dir, source_root),
        }

    output_path = output_dir / "powerbuilder_sql_probe.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    _print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
