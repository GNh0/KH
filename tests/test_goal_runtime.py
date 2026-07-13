import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from src.orchestration.goal_evidence import capture_evidence_envelope, sha256_text
from src.orchestration.goal_runtime import (
    GoalRuntime,
    build_goal_activation,
    capture_host_goal_receipt,
    resolve_goal_backend,
    validate_goal_runtime_receipt,
    validate_host_goal_receipt,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def observed_test(
    scope,
    producer_boundary,
    key="focused tests passed",
    *,
    command_id="cmd-1",
    exit_code=0,
    blocker_code="",
    supersedes="",
):
    return capture_evidence_envelope(
        producer_boundary=producer_boundary,
        evidence_type="test",
        evidence_key=key,
        producer="python-unittest",
        scope=scope,
        observed_at=datetime.now(timezone.utc).isoformat(),
        status="passed" if exit_code == 0 else "failed",
        command="python -m unittest tests.test_goal_runtime",
        command_id=command_id,
        exit_code=exit_code,
        captured_output=f"{command_id}:{exit_code}",
        supersedes=supersedes,
        blocker={
            "policy": "repeated_observation_v1",
            "code": blocker_code,
        }
        if blocker_code
        else None,
    )


class GoalRuntimeTests(unittest.TestCase):
    def test_kh_ledger_lifecycle_stays_outside_target_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            runtime_root = root / "runtime"
            project.mkdir()
            with patch.dict(
                os.environ,
                {
                    "UAF_RUNTIME_ROOT": str(runtime_root),
                    "UAF_PROJECT_MARKDOWN": "0",
                },
                clear=False,
            ):
                runtime = GoalRuntime(str(project))
                started = runtime.start(
                    objective="Implement the Goal runtime.",
                    success_criteria=["focused tests pass"],
                    evidence_required=["focused tests passed"],
                )

                self.assertEqual(started["goal_backend"], "kh_ledger")
                self.assertEqual(started["goal"]["status"], "active")
                self.assertTrue(
                    started["goal_ledger"]["current_goal_path"].startswith(str(runtime_root))
                )
                self.assertFalse((project / ".uaf").exists())
                self.assertFalse((project / ".kh").exists())
                self.assertEqual(started["runtime_channels"]["kh_goal_ledger"]["status"], "executed")
                self.assertEqual(started["runtime_channels"]["host_goal"]["status"], "not_executed")

                scope = started["goal"]["metadata"]["scope"]
                failed = observed_test(
                    scope,
                    runtime.evidence_producer,
                    command_id="cmd-failed",
                    exit_code=1,
                )
                runtime.add_evidence([failed])
                rejected = runtime.close()
                self.assertFalse(rejected["closed"])
                self.assertEqual(rejected["evaluation"]["metadata"]["missing_evidence"], [])
                self.assertEqual(
                    rejected["evaluation"]["metadata"]["failed_evidence"],
                    ["focused tests passed"],
                )

                runtime.add_evidence(
                    [
                        observed_test(
                            scope,
                            runtime.evidence_producer,
                            supersedes=failed["receipt_id"],
                        )
                    ]
                )
                evaluated = runtime.evaluate()
                self.assertTrue(evaluated["ready_to_close"])
                closed = runtime.close()

                self.assertTrue(closed["closed"])
                self.assertEqual(runtime.status()["goal"]["status"], "complete")
                self.assertEqual(
                    [event["event_type"] for event in runtime.ledger.read_events()],
                    [
                        "goal_started",
                        "goal_evidence_added",
                        "goal_close_rejected",
                        "goal_evidence_added",
                        "goal_evaluated",
                        "goal_closed",
                    ],
                )

    def test_asserted_text_cannot_close_and_terminal_goal_is_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"UAF_RUNTIME_ROOT": str(Path(tmp) / "runtime")}, clear=False):
                project = Path(tmp) / "project"
                project.mkdir()
                runtime = GoalRuntime(str(project), thread_id="thread-a", task_id="task-a")
                started = runtime.start(
                    objective="Ship the scoped runtime.",
                    success_criteria=["focused tests pass"],
                    evidence_required=["focused tests passed"],
                )

                runtime.add_evidence(["focused tests passed"], evidence_status="passed")
                rejected = runtime.close()
                self.assertFalse(rejected["closed"])
                self.assertEqual(
                    rejected["evaluation"]["metadata"]["asserted_evidence"],
                    ["focused tests passed"],
                )

                runtime.add_evidence(
                    [
                        observed_test(
                            started["goal"]["metadata"]["scope"],
                            runtime.evidence_producer,
                        )
                    ]
                )
                self.assertTrue(runtime.close()["closed"])
                for mutation in (
                    lambda: runtime.update(progress_notes=["late mutation"]),
                    lambda: runtime.add_evidence(["late evidence"]),
                    lambda: runtime.close(status="blocked", blocked_reason="changed my mind"),
                ):
                    with self.assertRaisesRegex(ValueError, "terminal goal"):
                        mutation()

    def test_evaluate_persists_observed_workflow_evidence_for_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"UAF_RUNTIME_ROOT": str(Path(tmp) / "runtime")}, clear=False):
                project = Path(tmp) / "project"
                project.mkdir()
                runtime = GoalRuntime(str(project), thread_id="thread-a")
                started = runtime.start(
                    objective="Persist evaluated evidence.",
                    success_criteria=["focused tests pass"],
                    evidence_required=["focused tests passed"],
                )
                evaluated = runtime.evaluate(
                    workflow_evidence=[
                        observed_test(
                            started["goal"]["metadata"]["scope"],
                            runtime.evidence_producer,
                        )
                    ]
                )

                self.assertTrue(evaluated["ready_to_close"])
                self.assertTrue(runtime.close()["closed"])

    def test_active_goal_rejects_overwrite_without_explicit_archive_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"UAF_RUNTIME_ROOT": str(Path(tmp) / "runtime")}, clear=False):
                project = Path(tmp) / "project"
                project.mkdir()
                runtime = GoalRuntime(str(project), thread_id="thread-a")
                runtime.start(
                    objective="First objective",
                    success_criteria=["first criterion"],
                    evidence_required=["first evidence"],
                )

                with self.assertRaisesRegex(ValueError, "active goal"):
                    runtime.start(
                        objective="Unrelated second objective",
                        success_criteria=["second criterion"],
                        evidence_required=["second evidence"],
                    )

                replaced = runtime.start(
                    objective="Unrelated second objective",
                    success_criteria=["second criterion"],
                    evidence_required=["second evidence"],
                    replacement_policy={
                        "mode": "archive_current",
                        "reason": "explicit user-selected replacement",
                    },
                )
                self.assertEqual(replaced["goal"]["objective"], "Unrelated second objective")
                archive_dir = runtime.ledger.state_dir / "archived_goals"
                self.assertEqual(len(list(archive_dir.glob("*.json"))), 1)

    def test_complete_requires_every_criterion_to_have_an_evidence_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"UAF_RUNTIME_ROOT": str(Path(tmp) / "runtime")}, clear=False):
                project = Path(tmp) / "project"
                project.mkdir()
                runtime = GoalRuntime(str(project))
                with self.assertRaisesRegex(ValueError, "criterion evidence mapping"):
                    runtime.start(
                        objective="Ship two outcomes",
                        success_criteria=["tests pass", "review passes"],
                        evidence_required=["tests passed", "review passed"],
                        criterion_evidence_map={"tests pass": ["tests passed"]},
                    )

    def test_blocked_close_requires_repeated_policy_qualified_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"UAF_RUNTIME_ROOT": str(Path(tmp) / "runtime")}, clear=False):
                project = Path(tmp) / "project"
                project.mkdir()
                runtime = GoalRuntime(str(project), thread_id="thread-a")
                started = runtime.start(
                    objective="Run an external verification.",
                    success_criteria=["verification passes"],
                    evidence_required=["verification passed"],
                )
                with self.assertRaisesRegex(ValueError, "repeated blocker observations"):
                    runtime.close(status="blocked", blocked_reason="service unavailable")

                scope = started["goal"]["metadata"]["scope"]
                runtime.add_evidence(
                    [
                        observed_test(
                            scope,
                            runtime.evidence_producer,
                            key="verification passed",
                            command_id="attempt-1",
                            exit_code=1,
                            blocker_code="external_service_unavailable",
                        )
                    ]
                )
                with self.assertRaisesRegex(ValueError, "repeated blocker observations"):
                    runtime.close(status="blocked", blocker_code="external_service_unavailable")

                runtime.add_evidence(
                    [
                        observed_test(
                            scope,
                            runtime.evidence_producer,
                            key="verification passed",
                            command_id="attempt-2",
                            exit_code=1,
                            blocker_code="external_service_unavailable",
                        )
                    ]
                )
                closed = runtime.close(
                    status="blocked",
                    blocker_code="external_service_unavailable",
                )
                self.assertTrue(closed["closed"])
                self.assertEqual(closed["goal"]["blocked_reason"], "external_service_unavailable")

    def test_runtime_receipt_requires_existing_scoped_parseable_matching_hashed_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime_root = root / "runtime"
            project = root / "project"
            other_project = root / "other"
            project.mkdir()
            other_project.mkdir()
            objective = "Implement correlated Goal receipts."
            with patch.dict(os.environ, {"UAF_RUNTIME_ROOT": str(runtime_root)}, clear=False):
                runtime = GoalRuntime(
                    str(project), thread_id="thread-a", task_id="task-a"
                )
                started = runtime.start(
                    objective=objective,
                    success_criteria=["receipt validation passes"],
                    evidence_required=["receipt validation passed"],
                )
                receipt = started["runtime_receipt"]

                valid = validate_goal_runtime_receipt(
                    receipt,
                    project=str(project),
                    thread_id="thread-a",
                    task_id="task-a",
                    objective=objective,
                    producer_boundary=runtime.receipt_producer,
                )
                self.assertTrue(valid["valid"], valid)

                cases = {}
                missing = deepcopy(receipt)
                missing["state_path"] = str(runtime_root / "missing.json")
                cases["state_path_missing"] = missing
                cross_scope = deepcopy(receipt)
                cross_scope["project_id"] = "project-forged"
                cases["project_scope_mismatch"] = cross_scope
                bad_hash = deepcopy(receipt)
                bad_hash["content_hash"] = sha256_text("forged")
                cases["content_hash_mismatch"] = bad_hash
                bad_lineage = deepcopy(receipt)
                bad_lineage["lineage_id"] = "lineage-forged"
                cases["lineage_mismatch"] = bad_lineage
                fabricated = deepcopy(receipt)
                fabricated["result_id"] = sha256_text("caller-fabricated-runtime-receipt")
                cases["runtime_producer_claim_mismatch"] = fabricated

                for expected_error, candidate in cases.items():
                    with self.subTest(expected_error=expected_error):
                        checked = validate_goal_runtime_receipt(
                            candidate,
                            project=str(project),
                            thread_id="thread-a",
                            task_id="task-a",
                            objective=objective,
                            producer_boundary=runtime.receipt_producer,
                        )
                        self.assertFalse(checked["valid"])
                        self.assertIn(expected_error, checked["errors"])

                wrong_project = validate_goal_runtime_receipt(
                    receipt,
                    project=str(other_project),
                    thread_id="thread-a",
                    task_id="task-a",
                    objective=objective,
                    producer_boundary=runtime.receipt_producer,
                )
                self.assertFalse(wrong_project["valid"])
                self.assertIn("state_path_outside_runtime_scope", wrong_project["errors"])

                state_path = Path(receipt["state_path"])
                state_path.write_text("not-json", encoding="utf-8")
                malformed = validate_goal_runtime_receipt(
                    receipt,
                    project=str(project),
                    thread_id="thread-a",
                    task_id="task-a",
                    objective=objective,
                    producer_boundary=runtime.receipt_producer,
                )
                self.assertFalse(malformed["valid"])
                self.assertIn("state_parse_failed", malformed["errors"])

    def test_caller_constructed_host_goal_receipt_is_claimed_not_executed(self):
        objective = "Create a durable host goal."
        context = {
            "goal_backend_preference": "host_goal",
            "host_goal_available": True,
            "host_goal_authorized": True,
            "thread_id": "thread-a",
            "task_id": "task-a",
        }
        classification = {"complexity": "heavy", "reasons": []}
        pending = build_goal_activation(
            classification,
            project=str(REPO_ROOT),
            context=context,
            objective=objective,
        )
        self.assertEqual(pending["status"], "pending")
        self.assertEqual(pending["channels"]["host_goal"]["status"], "pending")

        receipt = {
            "schema_version": 1,
            "receipt_type": "host_goal_tool",
            "host": "codex",
            "tool_name": "create_goal",
            "tool_call_id": "call-123",
            "result_id": "result-123",
            "result_status": "success",
            "goal_id": "goal-123",
            "thread_id": "thread-a",
            "task_id": "task-a",
            "objective_hash": sha256_text(objective),
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "output_hash": sha256_text("result-123:success"),
        }
        checked = validate_host_goal_receipt(
            receipt,
            thread_id="thread-a",
            task_id="task-a",
            objective=objective,
        )
        self.assertFalse(checked["valid"], checked)
        self.assertIn("external_host_execution_unverified", checked["errors"])
        still_pending = build_goal_activation(
            classification,
            project=str(REPO_ROOT),
            context={**context, "host_goal_receipt": receipt},
            objective=objective,
        )
        self.assertEqual(still_pending["status"], "pending")
        self.assertEqual(still_pending["channels"]["host_goal"]["status"], "pending")

        forged = deepcopy(receipt)
        forged["thread_id"] = "other-thread"
        self.assertFalse(
            validate_host_goal_receipt(
                forged,
                thread_id="thread-a",
                task_id="task-a",
                objective=objective,
            )["valid"]
        )

    def test_public_host_receipt_helper_cannot_mint_trusted_host_execution(self):
        objective = "Create a durable host goal."
        context = {
            "goal_backend_preference": "host_goal",
            "host_goal_available": True,
            "host_goal_authorized": True,
            "thread_id": "thread-a",
            "task_id": "task-a",
        }
        classification = {"complexity": "heavy", "reasons": []}
        receipt = capture_host_goal_receipt(
            host="codex",
            tool_name="create_goal",
            tool_call_id="call-123",
            result_id="result-123",
            result_status="success",
            goal_id="goal-123",
            thread_id="thread-a",
            task_id="task-a",
            objective=objective,
            captured_output={"goal_id": "goal-123", "status": "active"},
        )

        claimed = build_goal_activation(
            classification,
            project=str(REPO_ROOT),
            context={**context, "host_goal_receipt": receipt},
            objective=objective,
        )

        self.assertEqual(receipt["authority"], "claimed_unverified")
        self.assertEqual(claimed["status"], "pending")
        self.assertEqual(claimed["channels"]["host_goal"]["status"], "pending")
        self.assertIn(
            "external_host_execution_unverified",
            claimed["channels"]["host_goal"]["validation"]["errors"],
        )

    def test_local_runtime_receipt_is_single_use_through_durable_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            objective = "Activate the local Goal runtime."
            with patch.dict(os.environ, {"UAF_RUNTIME_ROOT": str(root / "runtime")}, clear=False):
                runtime = GoalRuntime(str(project), thread_id="thread-a", task_id="task-a")
                started = runtime.start(
                    objective=objective,
                    success_criteria=["activation is recorded"],
                    evidence_required=["activation recorded"],
                )
                context = {
                    "thread_id": "thread-a",
                    "task_id": "task-a",
                    "goal_runtime_receipt": started["runtime_receipt"],
                }
                classification = {"complexity": "heavy", "reasons": []}

                executed = build_goal_activation(
                    classification,
                    project=str(project),
                    context=context,
                    objective=objective,
                )
                replayed = build_goal_activation(
                    classification,
                    project=str(project),
                    context=context,
                    objective=objective,
                )

                self.assertEqual(executed["status"], "executed")
                self.assertEqual(
                    executed["receipt_validation_scope"],
                    "durable_local_runtime_integrity_and_state_correlation",
                )
                self.assertEqual(executed["external_authenticity"], "unverified")
                self.assertEqual(replayed["status"], "pending")
                self.assertIn(
                    "replayed_receipt",
                    replayed["channels"]["kh_goal_ledger"]["validation"]["errors"],
                )

    def test_cross_process_runtime_receipt_validates_but_external_authenticity_stays_unverified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            objective = "Keep persisted receipts non-authoritative."
            env = os.environ.copy()
            env["UAF_RUNTIME_ROOT"] = str(root / "runtime")
            with patch.dict(os.environ, {"UAF_RUNTIME_ROOT": env["UAF_RUNTIME_ROOT"]}, clear=False):
                runtime = GoalRuntime(str(project), thread_id="thread-a", task_id="task-a")
                receipt = runtime.start(
                    objective=objective,
                    success_criteria=["receipt remains scoped"],
                    evidence_required=["receipt scope checked"],
                )["runtime_receipt"]

            code = (
                "import json,sys; "
                "from src.orchestration.goal_runtime import validate_goal_runtime_receipt; "
                "result=validate_goal_runtime_receipt(json.loads(sys.argv[1]),project=sys.argv[2],"
                "thread_id='thread-a',task_id='task-a',objective=sys.argv[3],consume=True); "
                "print(json.dumps(result,sort_keys=True))"
            )
            completed = subprocess.run(
                [sys.executable, "-B", "-c", code, json.dumps(receipt), str(project), objective],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            checked = json.loads(completed.stdout)

            self.assertTrue(checked["valid"], checked)
            self.assertEqual(
                checked["validation_scope"],
                "durable_local_runtime_integrity_and_state_correlation",
            )
            self.assertEqual(checked["external_authenticity"], "unverified")

    def test_invalid_receipt_validation_does_not_consume_corrected_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            objective = "Preserve a valid receipt after a failed validation."
            with patch.dict(os.environ, {"UAF_RUNTIME_ROOT": str(root / "runtime")}, clear=False):
                receipt = GoalRuntime(
                    str(project), thread_id="thread-a", task_id="task-a"
                ).start(
                    objective=objective,
                    success_criteria=["receipt validates"],
                    evidence_required=["receipt validation passed"],
                )["runtime_receipt"]

                invalid = validate_goal_runtime_receipt(
                    receipt,
                    project=str(project),
                    thread_id="thread-a",
                    task_id="task-a",
                    objective="Wrong objective",
                    consume=True,
                )
                corrected = validate_goal_runtime_receipt(
                    receipt,
                    project=str(project),
                    thread_id="thread-a",
                    task_id="task-a",
                    objective=objective,
                    consume=True,
                )
                replayed = validate_goal_runtime_receipt(
                    receipt,
                    project=str(project),
                    thread_id="thread-a",
                    task_id="task-a",
                    objective=objective,
                    consume=True,
                )

            self.assertFalse(invalid["valid"])
            self.assertIn("objective_hash_mismatch", invalid["errors"])
            self.assertTrue(corrected["valid"], corrected)
            self.assertFalse(replayed["valid"])
            self.assertIn("replayed_receipt", replayed["errors"])

    def test_close_preserves_prior_workflow_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"UAF_RUNTIME_ROOT": str(Path(tmp) / "runtime")}, clear=False):
                project = Path(tmp) / "project"
                project.mkdir()
                runtime = GoalRuntime(str(project))
                started = runtime.start(
                    objective="Do not erase a failed workflow.",
                    success_criteria=["focused tests pass"],
                    evidence_required=["focused tests passed"],
                )
                runtime.add_evidence(
                    [
                        observed_test(
                            started["goal"]["metadata"]["scope"],
                            runtime.evidence_producer,
                        )
                    ]
                )
                evaluated = runtime.evaluate(workflow_success=False)
                closed = runtime.close()

                self.assertFalse(evaluated["ready_to_close"])
                self.assertFalse(closed["closed"])
                self.assertTrue(closed["evaluation"]["metadata"]["workflow_failure_asserted"])

    def test_atomic_replace_failure_preserves_previous_goal_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"UAF_RUNTIME_ROOT": str(Path(tmp) / "runtime")}, clear=False):
                project = Path(tmp) / "project"
                project.mkdir()
                runtime = GoalRuntime(str(project))
                runtime.start(
                    objective="Keep atomic state writes.",
                    success_criteria=["state remains parseable"],
                    evidence_required=["state parse passed"],
                )
                before = runtime.ledger.load_current_goal()

                with patch(
                    "src.orchestration.goal_ledger.os.replace",
                    side_effect=OSError("replace interrupted"),
                ):
                    with self.assertRaisesRegex(OSError, "replace interrupted"):
                        runtime.update(progress_notes=["must not partially persist"])

                after = runtime.ledger.load_current_goal()
                self.assertEqual(after["goal"], before["goal"])
                self.assertEqual(
                    list(runtime.ledger.state_dir.glob("current_goal.json.*.tmp")),
                    [],
                )

    def test_replacement_failure_keeps_old_goal_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"UAF_RUNTIME_ROOT": str(Path(tmp) / "runtime")}, clear=False):
                project = Path(tmp) / "project"
                project.mkdir()
                runtime = GoalRuntime(str(project), thread_id="thread-a")
                runtime.start(
                    objective="Original active objective",
                    success_criteria=["original criterion"],
                    evidence_required=["original evidence"],
                )

                from src.orchestration import goal_ledger

                real_atomic_write = goal_ledger._atomic_write_text

                def fail_new_current(path, payload):
                    parsed = json.loads(payload)
                    if (
                        path.name == "current_goal.json"
                        and parsed.get("objective") == "Replacement objective"
                    ):
                        raise OSError("replacement current write failed")
                    return real_atomic_write(path, payload)

                with patch(
                    "src.orchestration.goal_ledger._atomic_write_text",
                    side_effect=fail_new_current,
                ):
                    with self.assertRaisesRegex(OSError, "replacement current write failed"):
                        runtime.start(
                            objective="Replacement objective",
                            success_criteria=["replacement criterion"],
                            evidence_required=["replacement evidence"],
                            replacement_policy={
                                "mode": "archive_current",
                                "reason": "fault injection",
                            },
                        )

                current = runtime.ledger.load_current_goal()["goal"]
                self.assertEqual(current["objective"], "Original active objective")
                self.assertEqual(current["status"], "active")

    def test_concurrent_process_transitions_are_serialized_and_conflicts_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            env = os.environ.copy()
            env["UAF_RUNTIME_ROOT"] = str(root / "runtime")
            with patch.dict(os.environ, {"UAF_RUNTIME_ROOT": env["UAF_RUNTIME_ROOT"]}, clear=False):
                runtime = GoalRuntime(str(project), thread_id="thread-a")
                runtime.start(
                    objective="Serialize concurrent transitions.",
                    success_criteria=["one terminal transition wins"],
                    evidence_required=["transition serialized"],
                )

            gate = root / "go"
            worker = (
                "import sys,time\n"
                "from pathlib import Path\n"
                "from src.orchestration.goal_ledger import GoalLedger\n"
                "ledger=GoalLedger(sys.argv[1],thread_id='thread-a')\n"
                "state=ledger.load_current_goal()\n"
                "goal=dict(state['goal'])\n"
                "goal['status']=sys.argv[2]\n"
                "Path(sys.argv[3]).write_text('ready',encoding='utf-8')\n"
                "gate=Path(sys.argv[4])\n"
                "while not gate.exists():\n"
                "    time.sleep(0.01)\n"
                "ledger.save_current_goal(goal,expected_revision=state['_ledger_revision']); print('saved')"
            )
            processes = []
            for index, status in enumerate(("complete", "blocked")):
                ready = root / f"ready-{index}"
                process = subprocess.Popen(
                    [sys.executable, "-B", "-c", worker, str(project), status, str(ready), str(gate)],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                processes.append((process, ready))

            deadline = time.time() + 10
            while time.time() < deadline and not all(ready.exists() for _, ready in processes):
                time.sleep(0.01)
            self.assertTrue(all(ready.exists() for _, ready in processes))
            gate.write_text("go", encoding="utf-8")
            results = [process.communicate(timeout=10) + (process.returncode,) for process, _ in processes]

            self.assertEqual(sorted(result[2] for result in results), [0, 1])
            with patch.dict(os.environ, {"UAF_RUNTIME_ROOT": env["UAF_RUNTIME_ROOT"]}, clear=False):
                final_ledger = GoalRuntime(str(project), thread_id="thread-a").ledger
                final_state = final_ledger.load_current_goal()
            self.assertIn(final_state["goal"]["status"], {"complete", "blocked"})
            json.loads(final_ledger.current_goal_path.read_text(encoding="utf-8"))

    def test_goal_ledger_cannot_reopen_terminal_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"UAF_RUNTIME_ROOT": str(Path(tmp) / "runtime")}, clear=False):
                project = Path(tmp) / "project"
                project.mkdir()
                runtime = GoalRuntime(str(project))
                started = runtime.start(
                    objective="Keep terminal state immutable.",
                    success_criteria=["focused tests pass"],
                    evidence_required=["focused tests passed"],
                )
                runtime.add_evidence(
                    [
                        observed_test(
                            started["goal"]["metadata"]["scope"],
                            runtime.evidence_producer,
                        )
                    ]
                )
                closed = runtime.close()
                reopened = deepcopy(closed["goal"])
                reopened["status"] = "active"

                with self.assertRaisesRegex(ValueError, "terminal goal"):
                    runtime.ledger.save_current_goal(reopened)

    def test_required_goal_rejects_empty_completion_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(
                os.environ,
                {
                    "UAF_RUNTIME_ROOT": str(Path(tmp) / "runtime"),
                    "UAF_PROJECT_MARKDOWN": "0",
                },
                clear=False,
            ):
                runtime = GoalRuntime(tmp)
                with self.assertRaisesRegex(ValueError, "success criteria"):
                    runtime.start(
                        objective="Incomplete goal",
                        success_criteria=[],
                        evidence_required=["tests passed"],
                    )
                with self.assertRaisesRegex(ValueError, "evidence requirements"):
                    runtime.start(
                        objective="Incomplete goal",
                        success_criteria=["tests pass"],
                        evidence_required=[],
                    )

    def test_backend_policy_defaults_to_ledger_and_requires_host_authorization(self):
        self.assertEqual(resolve_goal_backend({})["goal_backend"], "kh_ledger")
        unauthorized = resolve_goal_backend(
            {
                "goal_backend_preference": "host_goal",
                "host_goal_available": True,
                "host_goal_authorized": False,
            }
        )
        self.assertEqual(unauthorized["goal_backend"], "kh_ledger")
        authorized = resolve_goal_backend(
            {
                "goal_backend_preference": "host_goal",
                "host_goal_available": True,
                "host_goal_authorized": True,
            }
        )
        self.assertEqual(authorized["goal_backend"], "host_goal")

    def test_module_cli_and_skill_demo_publish_the_exact_runtime_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            env = os.environ.copy()
            env["UAF_RUNTIME_ROOT"] = str(root / "runtime")
            env["UAF_PROJECT_MARKDOWN"] = "0"
            started = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "src.orchestration.goal_runtime",
                    "start",
                    "--project",
                    str(project),
                    "--objective",
                    "Exercise the Goal CLI.",
                    "--success-criterion",
                    "the CLI runs",
                    "--evidence-required",
                    "cli run passed",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            payload = json.loads(started.stdout)
            self.assertEqual(payload["command"], "start")
            self.assertEqual(payload["goal_backend"], "kh_ledger")

            demo = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "skills/goal_state_harness/scripts/demo.py",
                    "--output-dir",
                    str(root / "demo"),
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            demo_payload = json.loads(demo.stdout)
            self.assertEqual(
                demo_payload["goal_runtime_cli"]["module"],
                "python -m src.orchestration.goal_runtime",
            )
            self.assertEqual(demo_payload["goal_backend_policy"]["automatic_default"], "kh_ledger")
            runtime_demo = demo_payload["runtime_demo"]
            self.assertEqual(runtime_demo["success"]["start_status"], "active")
            self.assertTrue(runtime_demo["success"]["closed"])
            self.assertEqual(runtime_demo["success"]["final_status"], "complete")
            self.assertEqual(
                runtime_demo["failures"]["asserted_text_close"],
                "rejected",
            )
            self.assertEqual(
                runtime_demo["failures"]["single_blocker_close"],
                "rejected",
            )

    def test_cli_lifecycle_works_across_separate_processes_with_captured_command_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            command_result = root / "focused-tests.json"
            command_result.write_text(
                json.dumps(
                    {
                        "command": "python -m unittest tests.test_goal_runtime",
                        "command_id": "focused-tests-1",
                        "exit_code": 0,
                        "stdout": "focused tests passed",
                        "stderr": "",
                    }
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["UAF_RUNTIME_ROOT"] = str(root / "runtime")
            env["UAF_PROJECT_MARKDOWN"] = "0"

            def run_cli(*args, check=True):
                return subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        "-m",
                        "src.orchestration.goal_runtime",
                        *args,
                        "--project",
                        str(project),
                        "--thread-id",
                        "thread-a",
                        "--task-id",
                        "task-a",
                    ],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=check,
                )

            started = run_cli(
                "start",
                "--objective",
                "Exercise the durable Goal CLI lifecycle.",
                "--success-criterion",
                "focused tests pass",
                "--evidence-required",
                "focused tests passed",
            )
            captured = run_cli(
                "capture-evidence",
                "--evidence-type",
                "test",
                "--evidence-key",
                "focused tests passed",
                "--command-result-file",
                str(command_result),
            )
            evaluated = run_cli("evaluate")
            closed = run_cli("close")

            self.assertEqual(json.loads(started.stdout)["status"], "active")
            captured_payload = json.loads(captured.stdout)
            self.assertEqual(captured_payload["captured_evidence"]["observation"], "observed")
            self.assertEqual(
                captured_payload["captured_evidence"]["external_authenticity"],
                "unverified",
            )
            self.assertTrue(json.loads(evaluated.stdout)["ready_to_close"])
            self.assertTrue(json.loads(closed.stdout)["closed"])
            self.assertEqual(json.loads(closed.stdout)["status"], "complete")


if __name__ == "__main__":
    unittest.main()
