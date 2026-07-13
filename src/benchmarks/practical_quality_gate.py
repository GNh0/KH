import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.benchmarks.kh_bench_verified import run_kh_bench_verified
from src.orchestration.plugin_install_audit import audit_kh_plugin_install
from src.skills.uaf_skill_catalog import collect_packaged_skills
from src.skills.uaf_skill_quality import audit_skill_packaging_quality


PRACTICAL_GATE_NAME = "KH Practical Quality Gate"
PRACTICAL_GATE_SCHEMA_VERSION = "kh-practical-quality/v1"
PRIMARY_SIGNAL = "kh_bench_verified"
STATIC_QUALITY_ROLE = "advisory_structure_gate"
MINIMUM_BENCH_PASS_RATE = 1.0
MINIMUM_BENCH_TASK_COUNT = 8


def run_practical_quality_gate(output_root: Optional[Path] = None) -> Dict[str, Any]:
    """Run the practical release gate for KH UAF."""
    started = time.perf_counter()
    output_root = Path(output_root or tempfile.gettempdir()).resolve()
    static_report = audit_skill_packaging_quality(run_smoke_scripts=True)
    bench_report = run_kh_bench_verified(output_root=output_root)
    install_audit = audit_kh_plugin_install()
    cache_smoke = _installed_cache_front_door_smoke(install_audit.to_dict())
    report = build_practical_quality_report(
        static_report,
        bench_report,
        source_tests_available=_source_tests_available(),
        plugin_install_audit_report=install_audit.to_dict(),
        installed_cache_front_door_report=cache_smoke,
    )
    report["duration_seconds"] = round(time.perf_counter() - started, 6)
    report["output_root"] = str(output_root)
    return report


def build_practical_quality_report(
    static_quality_report: Dict[str, Any],
    kh_bench_report: Dict[str, Any],
    *,
    source_tests_available: Optional[bool] = None,
    plugin_install_audit_report: Optional[Dict[str, Any]] = None,
    installed_cache_front_door_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a fail-closed release decision from static and practical evidence."""
    bench_summary = dict(kh_bench_report.get("summary", {}) or {})
    static_success = bool(static_quality_report.get("success"))
    if source_tests_available is None:
        source_tests_available = _source_tests_available()
    bench_total = int(bench_summary.get("total") or 0)
    bench_passed = int(bench_summary.get("passed") or 0)
    bench_pass_rate = float(bench_summary.get("pass_rate") or 0.0)
    unresolved = list(kh_bench_report.get("unresolved", []) or [])
    install_audit = dict(plugin_install_audit_report or {})
    cache_smoke = dict(installed_cache_front_door_report or {})
    install_ok = bool(install_audit) and install_audit.get("status") == "ok"
    cache_smoke_ok = _installed_cache_front_door_smoke_ok(cache_smoke, install_audit)
    release_identity = dict(cache_smoke.get("release_identity", {}) or {})
    release_identity_ok = _release_identity_ok(release_identity)

    checks = [
        {
            "name": "static skill structure gate",
            "role": STATIC_QUALITY_ROLE,
            "required": True,
            "passed": static_success,
            "message": "packaged skill structure is valid"
            if static_success
            else "static skill structure gate failed",
        },
        {
            "name": "source test evidence availability",
            "role": STATIC_QUALITY_ROLE,
            "required": True,
            "passed": source_tests_available,
            "message": "repository test files are available"
            if source_tests_available
            else (
                "repository tests are not packaged in this runtime; run release quality from a full source "
                "checkout, not from an installed plugin cache"
            ),
        },
        {
            "name": "Codex plugin install audit",
            "role": "runtime_install_gate",
            "required": True,
            "passed": install_ok,
            "message": "installed plugin cache, marketplace ref, and source version are aligned"
            if install_ok
            else "plugin install audit is missing or attention_required",
        },
        {
            "name": "installed-cache front-door smoke",
            "role": "runtime_install_gate",
            "required": True,
            "passed": cache_smoke_ok,
            "message": _installed_cache_front_door_smoke_message(cache_smoke, install_audit),
        },
        {
            "name": "release content identity",
            "role": "runtime_install_gate",
            "required": True,
            "passed": release_identity_ok,
            "message": _release_identity_message(release_identity),
        },
        {
            "name": "KH-Bench Verified pass rate",
            "role": "primary_practical_signal",
            "required": True,
            "passed": bench_pass_rate >= MINIMUM_BENCH_PASS_RATE and not unresolved,
            "message": f"pass_rate={bench_pass_rate}; unresolved={unresolved}",
        },
        {
            "name": "SIDE regression task coverage",
            "role": "primary_practical_signal",
            "required": True,
            "passed": bench_total >= MINIMUM_BENCH_TASK_COUNT,
            "message": f"task_count={bench_total}; required>={MINIMUM_BENCH_TASK_COUNT}",
        },
    ]

    blocking_findings = [
        {
            "name": check["name"],
            "message": check["message"],
        }
        for check in checks
        if check["required"] and not check["passed"]
    ]
    release_ready = not blocking_findings
    practical_confidence_score = _confidence_score(
        static_success=static_success,
        bench_total=bench_total,
        bench_passed=bench_passed,
        unresolved=unresolved,
    )
    return {
        "schema_version": PRACTICAL_GATE_SCHEMA_VERSION,
        "name": PRACTICAL_GATE_NAME,
        "generated_at": _utc_now(),
        "release_ready": release_ready,
        "primary_signal": PRIMARY_SIGNAL,
        "static_quality_role": STATIC_QUALITY_ROLE,
        "source_tests_available": source_tests_available,
        "practical_confidence_score": practical_confidence_score,
        "minimum_bench_pass_rate": MINIMUM_BENCH_PASS_RATE,
        "minimum_bench_task_count": MINIMUM_BENCH_TASK_COUNT,
        "checks": checks,
        "blocking_findings": blocking_findings,
        "static_quality": {
            "success": static_success,
            "total_skills": static_quality_report.get("total_skills"),
            "lowest_quality_score": static_quality_report.get("lowest_quality_score"),
            "low_quality_skills": static_quality_report.get("low_quality_skills", []),
            "tests_packaged": static_quality_report.get("tests_packaged"),
        },
        "plugin_install_audit": install_audit,
        "installed_cache_front_door": cache_smoke,
        "kh_bench_verified": {
            "benchmark": kh_bench_report.get("benchmark", "KH-Bench Verified"),
            "summary": bench_summary,
            "unresolved": unresolved,
            "run_id": kh_bench_report.get("run_id"),
        },
    }



def _installed_cache_front_door_smoke(audit_report: Dict[str, Any]) -> Dict[str, Any]:
    caches = list(audit_report.get("installed_caches", []) or [])
    if not caches:
        return {"status": "missing_cache", "message": "no installed KH UAF cache found"}
    latest = caches[0]
    root = Path(str(latest.get("root", "")))
    script = root / "skills" / "always_on_front_door" / "scripts" / "front_door.py"
    if not script.is_file():
        return {"status": "missing_wrapper", "script": str(script)}
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(script),
                "--prompt",
                "What is an API?",
                "--project",
                str(Path.cwd()),
                "--host",
                "codex",
                "--summary",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as exc:  # pragma: no cover - defensive runtime evidence
        return {"status": "error", "script": str(script), "error": str(exc)}
    if completed.returncode != 0:
        return {
            "status": "failed",
            "script": str(script),
            "returncode": completed.returncode,
            "stderr": completed.stderr[-1000:],
        }
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {"status": "invalid_json", "script": str(script), "error": str(exc)}
    return {
        "status": "ok",
        "script": str(script),
        "skill_source": payload.get("skill_source", {}),
        "front_door_status": payload.get("front_door_status", ""),
        "classification": payload.get("classification", {}),
        "release_identity": _build_release_identity_report(
            Path(str(audit_report.get("repository_root", ""))),
            root,
        ),
    }


def _build_release_identity_report(source_root: Path, cache_root: Path) -> Dict[str, Any]:
    source_root = source_root.resolve()
    cache_root = cache_root.resolve()
    if not source_root.is_dir() or not cache_root.is_dir():
        return {
            "status": "missing_release_root",
            "content_hashes_match": False,
            "catalogs_valid": False,
            "catalog_names_match": False,
            "authenticity_status": "unverified",
            "identity_scope": "local_release_content_only",
            "source_root": str(source_root),
            "cache_root": str(cache_root),
        }

    source_catalog = collect_packaged_skills(str(source_root / "skills"))
    cache_catalog = collect_packaged_skills(str(cache_root / "skills"))
    source_names = {str(item.get("name", "")) for item in source_catalog.get("skills", [])}
    cache_names = {str(item.get("name", "")) for item in cache_catalog.get("skills", [])}
    source_hash, source_count = _release_content_hash(source_root)
    cache_hash, cache_count = _release_content_hash(cache_root)
    catalogs_valid = bool(source_catalog.get("validation", {}).get("success")) and bool(
        cache_catalog.get("validation", {}).get("success")
    )
    names_match = source_names == cache_names
    hashes_match = bool(source_hash) and source_hash == cache_hash
    status = "ok" if hashes_match and catalogs_valid and names_match else "content_mismatch"
    return {
        "status": status,
        "content_hashes_match": hashes_match,
        "catalogs_valid": catalogs_valid,
        "catalog_names_match": names_match,
        "source_content_sha256": source_hash,
        "cache_content_sha256": cache_hash,
        "source_file_count": source_count,
        "cache_file_count": cache_count,
        "source_catalog_valid": bool(source_catalog.get("validation", {}).get("success")),
        "cache_catalog_valid": bool(cache_catalog.get("validation", {}).get("success")),
        "source_skill_count": len(source_names),
        "cache_skill_count": len(cache_names),
        "authenticity_status": "unverified",
        "identity_scope": "local_release_content_only",
    }


def _release_content_hash(root: Path) -> tuple[str, int]:
    manifest_paths = [Path("plugin.json"), Path(".codex-plugin") / "plugin.json"]
    relative_paths = [*manifest_paths]
    relative_paths.extend(_manifest_executable_paths(root, manifest_paths))
    for folder in [root / "src", root / "skills"]:
        if folder.is_dir():
            relative_paths.extend(
                path.relative_to(root)
                for path in folder.rglob("*")
                if path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix.lower() not in {".pyc", ".pyo"}
            )
    digest = hashlib.sha256()
    count = 0
    for relative_path in sorted(set(relative_paths), key=lambda item: item.as_posix()):
        path = root / relative_path
        if not path.is_file():
            continue
        digest.update(relative_path.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
        count += 1
    return (digest.hexdigest() if count else "", count)


def _manifest_executable_paths(root: Path, manifest_paths: List[Path]) -> List[Path]:
    targets: set[Path] = set()
    for relative_manifest_path in manifest_paths:
        manifest_path = root / relative_manifest_path
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        for declared_target in _declared_executable_targets(manifest):
            target_path = (root / declared_target.replace("\\", "/")).resolve()
            try:
                relative_target = target_path.relative_to(root.resolve())
            except ValueError:
                continue
            if target_path.is_file():
                targets.add(relative_target)
    return sorted(targets, key=lambda item: item.as_posix())


def _declared_executable_targets(value: Any) -> List[str]:
    targets: List[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"entrypoint", "executable"} and isinstance(child, str) and child.strip():
                targets.append(child.strip())
            else:
                targets.extend(_declared_executable_targets(child))
    elif isinstance(value, list):
        for child in value:
            targets.extend(_declared_executable_targets(child))
    return targets


def _release_identity_ok(identity: Dict[str, Any]) -> bool:
    return (
        identity.get("status") == "ok"
        and identity.get("content_hashes_match") is True
        and identity.get("catalogs_valid") is True
        and identity.get("catalog_names_match") is True
    )


def _release_identity_message(identity: Dict[str, Any]) -> str:
    if _release_identity_ok(identity):
        return (
            "local source and installed cache content hashes match and both skill catalogs "
            "are valid; authenticity=unverified"
        )
    return (
        "release identity failed: "
        f"status={identity.get('status', '<missing>')}; "
        f"content_hashes_match={identity.get('content_hashes_match', False)}; "
        f"catalogs_valid={identity.get('catalogs_valid', False)}; "
        f"catalog_names_match={identity.get('catalog_names_match', False)}; "
        f"authenticity={identity.get('authenticity_status', 'unverified')}"
    )


def _installed_cache_front_door_smoke_ok(cache_smoke: Dict[str, Any], install_audit: Dict[str, Any]) -> bool:
    if cache_smoke.get("status") != "ok":
        return False
    source = dict(cache_smoke.get("skill_source", {}) or {})
    if source.get("source_type") != "codex-plugin-cache":
        return False
    expected = str(install_audit.get("expected_source_version") or "")
    if expected and str(source.get("version") or "") != expected:
        return False
    return cache_smoke.get("front_door_status") == "ok"


def _installed_cache_front_door_smoke_message(cache_smoke: Dict[str, Any], install_audit: Dict[str, Any]) -> str:
    if _installed_cache_front_door_smoke_ok(cache_smoke, install_audit):
        source = dict(cache_smoke.get("skill_source", {}) or {})
        return f"installed cache wrapper ran front-door from {source.get('source_type')} version {source.get('version')}"
    source = dict(cache_smoke.get("skill_source", {}) or {})
    expected = str(install_audit.get("expected_source_version") or "")
    actual = str(source.get("version") or "")
    if cache_smoke.get("status") == "ok" and expected and actual and expected != actual:
        return f"installed cache front-door version mismatch: installed={actual}, expected={expected}"
    if cache_smoke.get("status") == "ok" and source.get("source_type") != "codex-plugin-cache":
        return f"installed cache front-door smoke used {source.get('source_type', '<missing>')} instead of codex-plugin-cache"
    return f"installed cache front-door smoke failed: status={cache_smoke.get('status', '<missing>')}"

def _confidence_score(
    *,
    static_success: bool,
    bench_total: int,
    bench_passed: int,
    unresolved: List[str],
) -> float:
    if bench_total <= 0:
        return 0.0
    score = 10.0 * (bench_passed / bench_total)
    if unresolved:
        score -= min(3.0, 0.5 * len(unresolved))
    if not static_success:
        score -= 1.0
    if bench_total < MINIMUM_BENCH_TASK_COUNT:
        score -= 1.0
    return round(max(0.0, min(10.0, score)), 1)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _source_tests_available() -> bool:
    tests_dir = Path(__file__).resolve().parents[2] / "tests"
    return tests_dir.is_dir() and any(tests_dir.glob("test_*.py"))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the KH UAF practical release quality gate.")
    parser.add_argument("--output-dir", default="", help="Directory for gate and benchmark outputs.")
    parser.add_argument("--summary", action="store_true", help="Print compact release decision JSON.")
    args = parser.parse_args(argv)
    report = run_practical_quality_gate(output_root=Path(args.output_dir) if args.output_dir else None)
    payload = {
        "name": report["name"],
        "release_ready": report["release_ready"],
        "primary_signal": report["primary_signal"],
        "static_quality_role": report["static_quality_role"],
        "source_tests_available": report["source_tests_available"],
        "practical_confidence_score": report["practical_confidence_score"],
        "kh_bench_summary": report["kh_bench_verified"]["summary"],
        "blocking_findings": report["blocking_findings"],
        "plugin_install_audit_status": report["plugin_install_audit"].get("status", ""),
        "installed_cache_front_door_status": report["installed_cache_front_door"].get("status", ""),
    } if args.summary else report
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if report["release_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
