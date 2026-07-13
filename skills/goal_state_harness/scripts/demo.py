import hashlib
import json
import os
import subprocess
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path


SKILL_NAME = "goal-state-harness"


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "src").is_dir() and (parent / "skills").is_dir():
            return parent
    raise RuntimeError("repository root not found")


def _output_dir() -> Path:
    try:
        index = sys.argv.index("--output-dir")
        return Path(sys.argv[index + 1]).resolve()
    except (ValueError, IndexError):
        return (Path.cwd() / ".kh-demo" / SKILL_NAME).resolve()


def _run_observed_command(
    capture_evidence_envelope,
    scope,
    *,
    producer_boundary,
    command,
    command_id,
    evidence_key,
    blocker_code="",
):
    completed = subprocess.run(
        command,
        cwd=_repo_root(),
        capture_output=True,
        encoding="utf-8",
        text=True,
    )
    command_text = subprocess.list2cmdline(command)
    captured_output = f"{completed.stdout}\n{completed.stderr}".strip()
    envelope = capture_evidence_envelope(
        producer_boundary=producer_boundary,
        evidence_type="test",
        evidence_key=evidence_key,
        producer="goal-state-demo",
        scope=scope,
        observed_at=datetime.now(timezone.utc).isoformat(),
        status="passed" if completed.returncode == 0 else "failed",
        captured_output=captured_output,
        command=command_text,
        command_id=command_id,
        exit_code=completed.returncode,
        blocker={
            "policy": "repeated_observation_v1",
            "code": blocker_code,
        }
        if completed.returncode and blocker_code
        else None,
    )
    return envelope, {
        "executed": True,
        "command": command_text,
        "command_id": command_id,
        "exit_code": completed.returncode,
        "output_hash": envelope["output_hash"],
    }


def _artifact_record(path: Path, output_dir: Path) -> dict:
    raw = path.read_bytes()
    return {
        "artifact_id": path.relative_to(output_dir).as_posix().replace("/", "-").replace(".", "-"),
        "path": str(path.resolve()),
        "kind": "goal-runtime-demo-artifact",
        "exists": True,
        "validated": True,
        "checksum": hashlib.sha256(raw).hexdigest(),
        "validation_evidence": [
            "file exists",
            "content checksum recorded",
            "path is within output_dir",
        ],
        "template_not_applicable": False,
    }


if __name__ == "__main__":
    sys.path.insert(0, str(_repo_root()))
    from src.skills.demo_scenarios import main
    from src.orchestration.goal_evidence import capture_evidence_envelope
    from src.orchestration.goal_runtime import GoalRuntime

    output = StringIO()
    with redirect_stdout(output):
        exit_code = main(SKILL_NAME)
    payload = json.loads(output.getvalue())
    payload["goal_runtime_cli"] = {
        "module": "python -m src.orchestration.goal_runtime",
        "commands": [
            "start",
            "status",
            "capture-evidence",
            "add-evidence",
            "update",
            "evaluate",
            "close",
        ],
    }
    payload["goal_backend_policy"] = {
        "automatic_default": "kh_ledger",
        "host_goal_requires_authorization": True,
        "host_goal_requires_correlated_receipt": True,
        "hybrid_requires_both_evidence_paths": True,
        "fallback": "unavailable",
        "skill_read_is_execution": False,
    }
    demo_output = _output_dir()
    project = demo_output / "goal-runtime-project"
    project.mkdir(parents=True, exist_ok=True)
    previous_runtime_root = os.environ.get("UAF_RUNTIME_ROOT")
    os.environ["UAF_RUNTIME_ROOT"] = str(demo_output / "goal-runtime-state")
    try:
        runtime = GoalRuntime(str(project), thread_id="demo-thread", task_id="demo-task")
        started = runtime.start(
            objective="Execute the GoalRuntime demo lifecycle.",
            success_criteria=["goal runtime contract test passes"],
            evidence_required=["goal runtime contract test passed"],
        )
        success_scope = dict(started["goal"]["metadata"]["scope"])
        runtime.add_evidence(["goal runtime contract test passed"])
        asserted_rejected = not runtime.close()["closed"]
        success_envelope, success_command = _run_observed_command(
            capture_evidence_envelope,
            success_scope,
            producer_boundary=runtime.evidence_producer,
            command=[
                sys.executable,
                "-B",
                "-m",
                "unittest",
                (
                    "tests.test_goal_runtime.GoalRuntimeTests."
                    "test_required_goal_rejects_empty_completion_contract"
                ),
            ],
            command_id="demo-success",
            evidence_key="goal runtime contract test passed",
        )
        if success_command["exit_code"] != 0:
            raise RuntimeError("goal runtime demo verification command failed")
        runtime.add_evidence([success_envelope])
        closed = runtime.close()
        final_status = runtime.status()["goal"]["status"]

        blocker_started = runtime.start(
            objective="Demonstrate blocker policy failure.",
            success_criteria=["goal runtime contract test passes"],
            evidence_required=["goal runtime contract test passed"],
            replacement_policy={
                "mode": "archive_current",
                "reason": "demo failure-case transition",
            },
        )
        blocker_scope = dict(blocker_started["goal"]["metadata"]["scope"])
        first_blocker_command_line = [
            sys.executable,
            "-B",
            "-c",
            "import sys; print('observed demo blocker 1', file=sys.stderr); sys.exit(1)",
        ]
        first_blocker, first_blocker_command = _run_observed_command(
            capture_evidence_envelope,
            blocker_scope,
            producer_boundary=runtime.evidence_producer,
            command=first_blocker_command_line,
            command_id="demo-blocker-1",
            evidence_key="goal runtime contract test passed",
            blocker_code="demo_external_blocker",
        )
        runtime.add_evidence([first_blocker])
        try:
            runtime.close(status="blocked", blocker_code="demo_external_blocker")
            single_blocker_rejected = False
        except ValueError:
            single_blocker_rejected = True
        second_blocker, second_blocker_command = _run_observed_command(
            capture_evidence_envelope,
            blocker_scope,
            producer_boundary=runtime.evidence_producer,
            command=[
                sys.executable,
                "-B",
                "-c",
                "import sys; print('observed demo blocker 2', file=sys.stderr); sys.exit(1)",
            ],
            command_id="demo-blocker-2",
            evidence_key="goal runtime contract test passed",
            blocker_code="demo_external_blocker",
        )
        runtime.add_evidence([second_blocker])
        blocked = runtime.close(status="blocked", blocker_code="demo_external_blocker")

        payload["runtime_demo"] = {
            "success": {
                "start_status": started["status"],
                "closed": bool(closed["closed"]),
                "final_status": final_status,
                "command_evidence": success_command,
            },
            "blocked": {
                "closed": bool(blocked["closed"]),
                "final_status": runtime.status()["goal"]["status"],
                "command_evidence": second_blocker_command,
            },
            "failures": {
                "asserted_text_close": "rejected" if asserted_rejected else "accepted",
                "single_blocker_close": "rejected" if single_blocker_rejected else "accepted",
                "first_blocker_command": first_blocker_command,
            },
            "references": {
                "state_path": started["runtime_receipt"]["state_path"],
                "receipt_result_id": started["runtime_receipt"]["result_id"],
            },
        }
    finally:
        if previous_runtime_root is None:
            os.environ.pop("UAF_RUNTIME_ROOT", None)
        else:
            os.environ["UAF_RUNTIME_ROOT"] = previous_runtime_root
    payload["artifacts"] = [
        _artifact_record(path, demo_output)
        for path in sorted(demo_output.rglob("*"))
        if path.is_file()
    ]
    payload["verification"]["artifact_count"] = len(payload["artifacts"])
    payload["verification"]["artifacts_within_output_dir"] = True
    payload["verification"]["artifacts_validated"] = True
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    raise SystemExit(exit_code)
