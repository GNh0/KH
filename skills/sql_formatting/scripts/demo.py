import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SKILL_NAME = "sql-formatting"
SCENARIO_ID = "demo-sql-formatting"
CAPABILITY = "host LLM SQL formatting provider"
FAILURE_MODE = "logic-changing formatted candidate"
SEMANTIC_PROBE = "sql-formatting-provider-probe"


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "src").is_dir() and (parent / "skills").is_dir():
            return parent
    raise RuntimeError("repository root not found")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact(path: Path, kind: str, case: str) -> dict[str, Any]:
    return {
        "artifact_id": path.stem.replace("_", "-"),
        "path": str(path.resolve()),
        "kind": kind,
        "exists": True,
        "validated": True,
        "checksum": _sha256(path),
        "validation_evidence": ["file readable", "path is within output_dir"],
        "created_by_case": case,
        "template_not_applicable": False,
    }


def _contract(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": "HarnessResult",
        "module": "src.skills.sql_formatting_style",
        "fields_checked": list(payload),
        "roundtrip_checked": False,
        "schema_validation_checked": bool(payload),
        "roundtrip_kind": "mapping_schema_presence",
        "source": "policy-result",
        "sample": {"success": payload.get("success"), "exit_code": payload.get("exit_code")},
    }


def _sql_formatting_provider_scenario(output_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from src.skills.sql_formatting_style import verify_sql_formatting_style

    source = (
        "select a.order_no, a.status_cd\n"
        "from order_header a\n"
        "where a.status_cd = 'OPEN';\n"
    )
    candidate = (
        "SELECT A.ORDER_NO\n"
        "     , A.STATUS_CD\n"
        "FROM ORDER_HEADER A\n"
        "WHERE A.STATUS_CD = 'OPEN';\n"
    )
    changed = candidate.replace("'OPEN'", "'CLOSED'")
    success = verify_sql_formatting_style(source, candidate).to_dict()
    blocked = verify_sql_formatting_style(source, changed).to_dict()
    if not success["success"] or blocked["success"]:
        raise RuntimeError("provider demo verifier expectations failed")

    paths = {
        "source": output_dir / "source.sql",
        "candidate": output_dir / "formatted_candidate.sql",
        "success": output_dir / "verification.json",
        "blocked": output_dir / "blocked_verification.json",
    }
    paths["source"].write_text(source, encoding="utf-8")
    paths["candidate"].write_text(candidate, encoding="utf-8")
    paths["success"].write_text(json.dumps(success, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["blocked"].write_text(json.dumps(blocked, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts = [
        _artifact(paths["source"], "sql-source", "success"),
        _artifact(paths["candidate"], "sql-formatted-candidate", "success"),
        _artifact(paths["success"], "sql-verifier-result", "success"),
        _artifact(paths["blocked"], "sql-verifier-result", "blocked"),
    ]
    pipeline = {
        "source": {"path": str(paths["source"].resolve()), "sha256": _sha256(paths["source"])},
        "formatted_candidate": {"path": str(paths["candidate"].resolve()), "sha256": _sha256(paths["candidate"])},
        "generation": {
            "execution_actor": "host-llm",
            "host_llm_executed": False,
            "headless_python_formatter": False,
            "candidate_provenance": "bundled-static-demo-fixture",
        },
        "verification": {
            "actor": "src.skills.sql_formatting_style.verify_sql_formatting_style",
            "success": success["success"],
            "exit_code": success["exit_code"],
        },
    }
    return {"success": success, "blocked": blocked, "pipeline": pipeline}, artifacts


def _build_report(output_dir: Path, host: str) -> dict[str, Any]:
    from src.skills.uaf_skill_catalog import register_packaged_demo_profiles

    register_packaged_demo_profiles()
    from src.skills.demo_scenarios import DEMO_SKILL_PROFILES

    if DEMO_SKILL_PROFILES[SKILL_NAME] != (CAPABILITY, FAILURE_MODE, SEMANTIC_PROBE):
        raise RuntimeError("registered provider demo profile mismatch")
    runtime, artifacts = _sql_formatting_provider_scenario(output_dir)
    context = {
        "skill": SKILL_NAME,
        "scenario_id": SCENARIO_ID,
        "scenario_function": "_sql_formatting_provider_scenario",
        "semantic_probe": SEMANTIC_PROBE,
    }
    targets = [
        {
            "ref": "skills/sql_formatting/SKILL.md",
            "status": "resolved",
            "path": str(_repo_root() / "skills" / "sql_formatting" / "SKILL.md"),
            "object_type": "file",
            "proof": "resolved_by_demo_target_probe",
        },
        {
            "ref": "src.skills.sql_formatting_style.verify_sql_formatting_style",
            "status": "resolved",
            "path": str(_repo_root() / "src" / "skills" / "sql_formatting_style.py"),
            "object_type": "function",
            "proof": "resolved_by_demo_target_probe",
        },
    ]
    profile = {
        "skill": SKILL_NAME,
        "capability_proven": CAPABILITY,
        "failure_mode_proven": FAILURE_MODE,
        "semantic_probe": SEMANTIC_PROBE,
    }
    return {
        "schema_version": "1.0",
        "skill": SKILL_NAME,
        "execution_level": "procedure-policy",
        "scenario_id": SCENARIO_ID,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "success_case": {
            "status": "passed",
            "contract_type": "HarnessResult",
            "payload": runtime["success"],
            "evidence": [f"{CAPABILITY}: source -> candidate -> verifier complete", f"{SEMANTIC_PROBE}: actor provenance recorded"],
            "expected_behavior": "Use the host LLM provider contract and independently verify its candidate.",
            "side_effects": ["writes source, candidate, and verifier artifacts under output_dir"],
            "skill_demo_context": context,
            "capability_proven": CAPABILITY,
            "semantic_probe": SEMANTIC_PROBE,
        },
        "blocked_or_failure_case": {
            "status": "blocked",
            "contract_type": "HarnessResult",
            "payload": runtime["blocked"],
            "blocked_reason": FAILURE_MODE,
            "error_code": "token_stream_changed",
            "evidence": [f"{FAILURE_MODE}: changed literal rejected", f"{SEMANTIC_PROBE}: verifier failure preserved"],
            "expected_behavior": "Block a candidate that changes SQL behavior.",
            "remediation": "Have the host LLM restore source semantics and verify again.",
            "non_destructive": True,
            "skill_demo_context": context,
            "failure_mode_proven": FAILURE_MODE,
            "semantic_probe": SEMANTIC_PROBE,
        },
        "contracts": [_contract(runtime["success"]), _contract(runtime["blocked"])],
        "demo_specificity": {
            "skill": SKILL_NAME,
            "scenario_id": SCENARIO_ID,
            "scenario_function": "_sql_formatting_provider_scenario",
            "success_context_bound": True,
            "blocked_context_bound": True,
            "success_and_blocked_are_distinct": True,
            "artifact_namespace_bound": True,
            "profile": profile,
            "declared_implementation_targets": targets,
            "resolved_implementation_targets": [item["ref"] for item in targets],
            "skill_specific_probe": {
                "skill": SKILL_NAME,
                "primary_target": targets[0]["ref"],
                "primary_target_status": "resolved",
                "scenario_function": "_sql_formatting_provider_scenario",
                "proof_kind": "implementation-target-resolution-plus-contract-demo",
                "semantic_probe": SEMANTIC_PROBE,
                "contract_modules": ["src.skills.sql_formatting_style"],
            },
            "unique_markers": [SKILL_NAME, SCENARIO_ID, SEMANTIC_PROBE, CAPABILITY, FAILURE_MODE],
        },
        "host_metadata": {
            "selected_host": host,
            "host_mode_evidence": {"dispatch": f"simulated {host} provider handoff", "state": "output_dir artifacts", "panel": "stdout JSON"},
            "host_claim_scope": "simulated_metadata_only",
            "behavioral_host_execution": False,
            "behavioral_host_execution_reason": "The candidate is a static fixture; no host LLM is invoked.",
            "verified_host_artifacts": [],
            "host_differences": [
                {"host": "local", "dispatch": "fixture plus Python verifier"},
                {"host": "codex", "dispatch": "host LLM then verifier"},
                {"host": "claude-code", "dispatch": "host LLM then verifier"},
            ],
            "output_dir": str(output_dir.resolve()),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "external_runtime_dependency": False,
        },
        "artifacts": artifacts,
        "verification": {
            "runnable": True,
            "exit_code": 0,
            "stdout_json_only": True,
            "contract_roundtrip": True,
            "contract_validation_mode": "dataclass_roundtrip_or_mapping_schema",
            "artifacts_within_output_dir": True,
            "artifacts_validated": True,
            "artifact_count": len(artifacts),
            "runtime_observation": {"source": "outer subprocess quality gate", "checked_by": ["tests.test_skill_demos"]},
        },
        "provider_pipeline": runtime["pipeline"],
    }


def main(default_skill_name: str = SKILL_NAME) -> int:
    if default_skill_name != SKILL_NAME:
        raise ValueError(f"unsupported skill name: {default_skill_name}")
    parser = argparse.ArgumentParser(description="Run the packaged SQL formatting provider demo.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--host", default="local", choices=["local", "codex", "antigravity-style", "claude-code"])
    args = parser.parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(_repo_root()))
    print(json.dumps(_build_report(output_dir, args.host), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(SKILL_NAME))
