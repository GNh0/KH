import argparse
import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.benchmarks.kh_bench_verified import run_kh_bench_verified
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
    report = build_practical_quality_report(static_report, bench_report)
    report["duration_seconds"] = round(time.perf_counter() - started, 6)
    report["output_root"] = str(output_root)
    return report


def build_practical_quality_report(
    static_quality_report: Dict[str, Any],
    kh_bench_report: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a fail-closed release decision from static and practical evidence."""
    bench_summary = dict(kh_bench_report.get("summary", {}) or {})
    static_success = bool(static_quality_report.get("success"))
    bench_total = int(bench_summary.get("total") or 0)
    bench_passed = int(bench_summary.get("passed") or 0)
    bench_pass_rate = float(bench_summary.get("pass_rate") or 0.0)
    unresolved = list(kh_bench_report.get("unresolved", []) or [])

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
        },
        "kh_bench_verified": {
            "benchmark": kh_bench_report.get("benchmark", "KH-Bench Verified"),
            "summary": bench_summary,
            "unresolved": unresolved,
            "run_id": kh_bench_report.get("run_id"),
        },
    }


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
        "practical_confidence_score": report["practical_confidence_score"],
        "kh_bench_summary": report["kh_bench_verified"]["summary"],
        "blocking_findings": report["blocking_findings"],
    } if args.summary else report
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if report["release_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
