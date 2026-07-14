import argparse
import hashlib
import json
import re
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
CANONICAL_RELEASE_PLUGIN_NAME = "kh-uaf"
RELEASE_VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
CANONICAL_RELEASE_HASH_ALGORITHM = "sha256-length-prefixed-path-and-canonical-content-v3"
RAW_RELEASE_HASH_ALGORITHM = "sha256-length-prefixed-path-and-raw-content-v2"
RELEASE_TEXT_SUFFIXES = frozenset({".json", ".md", ".py"})
RELEASE_TEXT_FILENAMES = frozenset({"license", "notice", "readme"})
REQUIRED_RELEASE_MANIFEST_PATHS = (
    Path("plugin.json"),
    Path(".codex-plugin") / "plugin.json",
    Path(".agents") / "plugins" / "kh-uaf" / "plugin.json",
)


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
            "raw_content_hashes_match": False,
            "catalogs_valid": False,
            "catalog_names_match": False,
            "required_release_manifests_present": False,
            "manifest_identity_valid": False,
            "source_manifest_identity": {"status": "missing_root"},
            "cache_manifest_identity": {"status": "missing_root"},
            "source_cache_manifest_identity_mismatches": [],
            "content_hash_algorithm": CANONICAL_RELEASE_HASH_ALGORITHM,
            "raw_content_hash_algorithm": RAW_RELEASE_HASH_ALGORITHM,
            "authenticity_status": "unverified",
            "identity_scope": "local_release_content_only",
            "source_root": str(source_root),
            "cache_root": str(cache_root),
        }

    source_catalog = collect_packaged_skills(str(source_root / "skills"))
    cache_catalog = collect_packaged_skills(str(cache_root / "skills"))
    source_names = {str(item.get("name", "")) for item in source_catalog.get("skills", [])}
    cache_names = {str(item.get("name", "")) for item in cache_catalog.get("skills", [])}
    source_content = _release_content_hash_details(source_root)
    cache_content = _release_content_hash_details(cache_root)
    source_manifest_identity = _release_manifest_identity_details(source_root)
    cache_manifest_identity = _release_manifest_identity_details(cache_root)
    source_cache_manifest_identity_mismatches = _manifest_identity_mismatches(
        source_manifest_identity.get("identity", {}),
        cache_manifest_identity.get("identity", {}),
        left_label="source",
        right_label="cache",
    )
    catalogs_valid = bool(source_catalog.get("validation", {}).get("success")) and bool(
        cache_catalog.get("validation", {}).get("success")
    )
    names_match = source_names == cache_names
    source_hash = str(source_content["canonical_sha256"])
    cache_hash = str(cache_content["canonical_sha256"])
    hashes_match = bool(source_hash) and source_hash == cache_hash
    raw_hashes_match = bool(source_content["raw_sha256"]) and (
        source_content["raw_sha256"] == cache_content["raw_sha256"]
    )
    source_missing_manifests = list(source_manifest_identity["missing_manifest_paths"])
    cache_missing_manifests = list(cache_manifest_identity["missing_manifest_paths"])
    missing_manifests = [*source_missing_manifests, *cache_missing_manifests]
    required_manifests_present = not missing_manifests
    manifest_identity_valid = (
        source_manifest_identity["status"] == "ok"
        and cache_manifest_identity["status"] == "ok"
        and not source_cache_manifest_identity_mismatches
    )
    status = (
        "ok"
        if (
            hashes_match
            and catalogs_valid
            and names_match
            and required_manifests_present
            and manifest_identity_valid
        )
        else "content_mismatch"
    )
    return {
        "status": status,
        "content_hashes_match": hashes_match,
        "raw_content_hashes_match": raw_hashes_match,
        "catalogs_valid": catalogs_valid,
        "catalog_names_match": names_match,
        "required_release_manifest_paths": [
            path.as_posix() for path in REQUIRED_RELEASE_MANIFEST_PATHS
        ],
        "required_release_manifests_present": required_manifests_present,
        "missing_required_manifest_paths": missing_manifests,
        "source_missing_required_manifest_paths": source_missing_manifests,
        "cache_missing_required_manifest_paths": cache_missing_manifests,
        "manifest_identity_valid": manifest_identity_valid,
        "source_manifest_identity": source_manifest_identity,
        "cache_manifest_identity": cache_manifest_identity,
        "source_cache_manifest_identity_mismatches": (
            source_cache_manifest_identity_mismatches
        ),
        "source_content_sha256": source_hash,
        "cache_content_sha256": cache_hash,
        "source_raw_content_sha256": source_content["raw_sha256"],
        "cache_raw_content_sha256": cache_content["raw_sha256"],
        "source_file_count": source_content["file_count"],
        "cache_file_count": cache_content["file_count"],
        "source_text_file_count": source_content["text_file_count"],
        "cache_text_file_count": cache_content["text_file_count"],
        "source_binary_file_count": source_content["binary_file_count"],
        "cache_binary_file_count": cache_content["binary_file_count"],
        "content_hash_algorithm": CANONICAL_RELEASE_HASH_ALGORITHM,
        "raw_content_hash_algorithm": RAW_RELEASE_HASH_ALGORITHM,
        "source_catalog_valid": bool(source_catalog.get("validation", {}).get("success")),
        "cache_catalog_valid": bool(cache_catalog.get("validation", {}).get("success")),
        "source_skill_count": len(source_names),
        "cache_skill_count": len(cache_names),
        "authenticity_status": "unverified",
        "identity_scope": "local_release_content_only",
    }


def _release_content_hash(root: Path) -> tuple[str, int]:
    """Return the canonical release hash while preserving the legacy tuple API."""
    details = _release_content_hash_details(root)
    return str(details["canonical_sha256"]), int(details["file_count"])


def _release_manifest_identity_details(root: Path) -> Dict[str, Any]:
    manifests: List[Dict[str, Any]] = []
    missing_manifest_paths: List[str] = []
    invalid_manifests: List[Dict[str, Any]] = []
    missing_values: List[Dict[str, Any]] = []
    invalid_values: List[Dict[str, Any]] = []
    valid_values: Dict[str, List[Dict[str, str]]] = {"name": [], "version": []}

    for relative_path in REQUIRED_RELEASE_MANIFEST_PATHS:
        manifest_path = (root / relative_path).resolve()
        path_text = str(manifest_path)
        record: Dict[str, Any] = {
            "path": path_text,
            "relative_path": relative_path.as_posix(),
        }
        if not manifest_path.is_file():
            record["status"] = "missing"
            manifests.append(record)
            missing_manifest_paths.append(path_text)
            continue

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except OSError as exc:
            invalid = {"path": path_text, "reason": "read_error", "error": str(exc)}
            record.update({"status": "invalid", **invalid})
            manifests.append(record)
            invalid_manifests.append(invalid)
            continue
        except UnicodeError as exc:
            invalid = {"path": path_text, "reason": "invalid_utf8", "error": str(exc)}
            record.update({"status": "invalid", **invalid})
            manifests.append(record)
            invalid_manifests.append(invalid)
            continue
        except json.JSONDecodeError as exc:
            invalid = {"path": path_text, "reason": "invalid_json", "error": str(exc)}
            record.update({"status": "invalid", **invalid})
            manifests.append(record)
            invalid_manifests.append(invalid)
            continue

        if not isinstance(manifest, dict):
            invalid = {
                "path": path_text,
                "reason": "invalid_document",
                "value_type": type(manifest).__name__,
            }
            record.update({"status": "invalid", **invalid})
            manifests.append(record)
            invalid_manifests.append(invalid)
            continue

        record["status"] = "ok"
        record_issues: List[Dict[str, Any]] = []
        for field in ("name", "version"):
            value = manifest.get(field)
            record[field] = value
            if field not in manifest or value is None or (
                isinstance(value, str) and not value.strip()
            ):
                issue = {"path": path_text, "field": field}
                missing_values.append(issue)
                record_issues.append({"kind": "missing_value", "field": field})
            elif not isinstance(value, str):
                issue = {
                    "path": path_text,
                    "field": field,
                    "value": value,
                    "value_type": type(value).__name__,
                }
                invalid_values.append(issue)
                record_issues.append(
                    {
                        "kind": "invalid_value",
                        "field": field,
                        "value": value,
                        "value_type": type(value).__name__,
                    }
                )
            else:
                valid_values[field].append({"path": path_text, "value": value})
                if field == "name" and value != CANONICAL_RELEASE_PLUGIN_NAME:
                    issue = {
                        "path": path_text,
                        "field": field,
                        "value": value,
                        "reason": "noncanonical_plugin_name",
                        "expected": CANONICAL_RELEASE_PLUGIN_NAME,
                    }
                    invalid_values.append(issue)
                    record_issues.append({"kind": "invalid_value", **issue})
                elif field == "version" and RELEASE_VERSION_PATTERN.fullmatch(value) is None:
                    issue = {
                        "path": path_text,
                        "field": field,
                        "value": value,
                        "reason": "invalid_release_version",
                        "expected_format": "MAJOR.MINOR.PATCH",
                    }
                    invalid_values.append(issue)
                    record_issues.append({"kind": "invalid_value", **issue})
        if record_issues:
            record["status"] = "invalid"
            record["issues"] = record_issues
        manifests.append(record)

    mismatched_values = [
        {
            "field": field,
            "values": values,
        }
        for field, values in valid_values.items()
        if len({item["value"] for item in values}) > 1
    ]
    if missing_manifest_paths:
        status = "missing"
    elif mismatched_values:
        status = "mismatch"
    elif invalid_manifests or missing_values or invalid_values:
        status = "invalid"
    else:
        status = "ok"

    identity = (
        {field: values[0]["value"] for field, values in valid_values.items()}
        if status == "ok"
        else {}
    )
    return {
        "status": status,
        "identity": identity,
        "manifests": manifests,
        "missing_manifest_paths": missing_manifest_paths,
        "invalid_manifests": invalid_manifests,
        "missing_values": missing_values,
        "invalid_values": invalid_values,
        "mismatched_values": mismatched_values,
    }


def _manifest_identity_mismatches(
    left: Dict[str, Any],
    right: Dict[str, Any],
    *,
    left_label: str,
    right_label: str,
) -> List[Dict[str, Any]]:
    if not left or not right:
        return []
    return [
        {
            "field": field,
            f"{left_label}_value": left.get(field),
            f"{right_label}_value": right.get(field),
        }
        for field in ("name", "version")
        if left.get(field) != right.get(field)
    ]


def _release_content_hash_details(root: Path) -> Dict[str, Any]:
    """Hash a release using canonical UTF-8 text and raw-byte diagnostics.

    Only explicitly supported text paths receive strict UTF-8 EOL
    canonicalization. Unknown extensions, invalid UTF-8, and binary-like content
    remain byte-exact. Paths are included, so missing and extra files still fail.
    """
    manifest_paths = list(REQUIRED_RELEASE_MANIFEST_PATHS)
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
    canonical_digest = hashlib.sha256()
    raw_digest = hashlib.sha256()
    count = 0
    text_count = 0
    binary_count = 0
    for relative_path in sorted(set(relative_paths), key=lambda item: item.as_posix()):
        path = root / relative_path
        if not path.is_file():
            continue
        path_bytes = relative_path.as_posix().encode("utf-8")
        raw_content = path.read_bytes()
        canonical_content, is_text = _canonical_release_content(relative_path, raw_content)
        for digest, content in (
            (canonical_digest, canonical_content),
            (raw_digest, raw_content),
        ):
            _update_length_prefixed_release_digest(digest, path_bytes, content)
        if is_text:
            text_count += 1
        else:
            binary_count += 1
        count += 1
    return {
        "canonical_sha256": canonical_digest.hexdigest() if count else "",
        "raw_sha256": raw_digest.hexdigest() if count else "",
        "file_count": count,
        "text_file_count": text_count,
        "binary_file_count": binary_count,
        "missing_required_manifest_paths": [
            str((root / relative_path).resolve())
            for relative_path in REQUIRED_RELEASE_MANIFEST_PATHS
            if not (root / relative_path).is_file()
        ],
    }


def _update_length_prefixed_release_digest(
    digest: Any,
    path: bytes,
    content: bytes,
) -> None:
    digest.update(len(path).to_bytes(8, byteorder="big", signed=False))
    digest.update(path)
    digest.update(len(content).to_bytes(8, byteorder="big", signed=False))
    digest.update(content)


def _is_release_text_path(relative_path: Path) -> bool:
    return (
        relative_path.suffix.casefold() in RELEASE_TEXT_SUFFIXES
        or relative_path.name.casefold() in RELEASE_TEXT_FILENAMES
    )


def _canonical_release_content(relative_path: Path, content: bytes) -> tuple[bytes, bool]:
    if not _is_release_text_path(relative_path):
        return content, False

    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return content, False

    allowed_controls = {"\t", "\n", "\r", "\f"}
    if any(
        (ord(character) < 32 and character not in allowed_controls) or ord(character) == 127
        for character in text
    ):
        return content, False

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.encode("utf-8"), True


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
        and identity.get("required_release_manifests_present") is True
        and identity.get("manifest_identity_valid") is True
    )


def _release_identity_message(identity: Dict[str, Any]) -> str:
    if _release_identity_ok(identity):
        return (
            "local source and installed cache content hashes match and both skill catalogs "
            "are valid; required manifest identities are consistent; authenticity=unverified"
        )
    missing_paths = list(identity.get("missing_required_manifest_paths", []) or [])
    missing_path_evidence = (
        f"; missing_required_manifest_paths={', '.join(str(path) for path in missing_paths)}"
        if missing_paths
        else ""
    )
    return (
        "release identity failed: "
        f"status={identity.get('status', '<missing>')}; "
        f"content_hashes_match={identity.get('content_hashes_match', False)}; "
        f"catalogs_valid={identity.get('catalogs_valid', False)}; "
        f"catalog_names_match={identity.get('catalog_names_match', False)}; "
        f"manifest_identity_valid={identity.get('manifest_identity_valid', False)}; "
        "manifest_identity_statuses="
        f"source:{dict(identity.get('source_manifest_identity', {}) or {}).get('status', '<missing>')},"
        f"cache:{dict(identity.get('cache_manifest_identity', {}) or {}).get('status', '<missing>')}; "
        f"authenticity={identity.get('authenticity_status', 'unverified')}"
        f"{missing_path_evidence}"
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
