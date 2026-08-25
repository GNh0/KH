import ast
import gc
import hashlib
import inspect
import json
import os
import pickle
import subprocess
import sys
import tempfile
import tracemalloc
import unittest
from pathlib import Path
from unittest import mock

from src.orchestration import session_postmortem as postmortem_module
from src.orchestration import session_skill_audit as audit_module
from src.orchestration.kh_front_door import build_kh_front_door
from src.orchestration.session_postmortem import analyze_codex_session_jsonl
from src.orchestration.session_skill_audit import analyze_session_skills


REPO_ROOT = Path(__file__).resolve().parents[1]
STREAMING_DIAGNOSTICS_KEY = "session_event_index_diagnostics"
EXPECTED_REDUCER_COUNT = 31
MAX_INTEGRITY_SAMPLES = 8


def _write_deserialization_marker(path):
    Path(path).write_text("executed", encoding="utf-8")
    return {"tampered": True}


class _ExecutablePicklePayload:
    def __init__(self, marker_path):
        self.marker_path = marker_path

    def __reduce__(self):
        return (_write_deserialization_marker, (self.marker_path,))


FROZEN_EMPTY_AUDIT_GOLDEN = json.loads(
    r'''
{
  "coverage": {
    "active_or_considered_skills": 0,
    "observed_skills": 0,
    "required_accepted": 0,
    "required_applied": 0,
    "required_applied_skill_names": [],
    "required_considered_or_better": 0,
    "required_missing_evidence": 0,
    "required_missing_skill_names": [],
    "required_skills": 0,
    "required_unaccepted": 0,
    "required_unaccepted_skill_names": [],
    "required_with_evidence": 0,
    "runtime_applied_skill_names": [],
    "runtime_applied_skills": 0,
    "total_skills": 0
  },
  "issues": [],
  "path": "<SESSION>",
  "postmortem": {
    "archive_guard": {
      "archive_directive_count": 0,
      "archive_directives": [],
      "latest_archive_line": 0,
      "reasons": [],
      "status": "passed",
      "user_archive_request_count": 0,
      "user_archive_requests": []
    },
    "assistant_stop_guard": {
      "active_stop_events": [],
      "assistant_claims_stop": false,
      "final_stop_messages": [],
      "latest_goal_status": "",
      "reasons": [],
      "status": "passed",
      "stop_event_count": 0,
      "task_complete_count": 0
    },
    "completion_guard": {
      "final_claims_completion": false,
      "latest_goal_status": "",
      "reasons": [],
      "status": "passed",
      "task_complete_count": 0
    },
    "recommended_actions": [],
    "resume_guard": {
      "implementation_tools_after_resume": [],
      "large_work_bundle_after_resume": 0,
      "latest_resume_line": 0,
      "reasons": [],
      "resume_request_count": 0,
      "runtime_token_evidence_after_resume": 0,
      "session_start_context_after_resume": 0,
      "status": "passed"
    },
    "review_status": "pending",
    "scope_completion_delta": {
      "completed_markers": [],
      "missing_markers": [],
      "objective_markers": [],
      "partial_milestone_claimed": false,
      "status": "passed"
    },
    "subagent_summary": {
      "closed": 0,
      "closed_while_running": 0,
      "reviewer_mentions": 0,
      "spawned": 0,
      "timed_out": 0
    },
    "token_gate": {
      "checked": false,
      "context_ratio_threshold": 0.5,
      "cumulative_threshold_tokens": 200000,
      "max_context_ratio": 0.0,
      "max_last_input_tokens": 0,
      "max_total_tokens": 0,
      "model_context_window": 0,
      "reasons": [],
      "required": false,
      "threshold_tokens": 50000
    },
    "token_optimizer_evidence": {
      "blocked_reason_records": 0,
      "considered_not_needed_records": 0,
      "explicit_passthrough_records": 0,
      "explicit_usage_records": 0,
      "front_door_runtime_provenance": {
        "external_authenticity": "unverified",
        "note": "The audit proves ordered host call/output correlation, identity, boundary, correlation, and packet-hash consistency; it cannot prove file-level cryptographic authenticity.",
        "status": "structural_jsonl_correlation_only"
      },
      "front_door_runtime_receipts": 0,
      "runtime_calls": 0,
      "skill_doc_reads": 0,
      "status_mentions": 0,
      "structured_used_records": 0
    },
    "token_optimizer_status": "not_checked",
    "token_optimizer_status_reason": "no runtime token-optimizer receipt",
    "user_stop_guard": {
      "continued_tool_calls": [],
      "continued_work_messages": [],
      "goal_context_after_stop": 0,
      "latest_goal_status_after_stop": "",
      "latest_stop_line": 0,
      "reasons": [],
      "status": "passed",
      "stop_request_count": 0,
      "terminal_goal_updates_after_stop": 0
    },
    "verification_claim_guard": {
      "failed_verification_count": 0,
      "failures": [],
      "final_report_mentions_failure": false,
      "status": "passed"
    }
  },
  "session_id": "golden-session",
  "skills": [],
  "total_skills": 0,
  "usage_summary": {
    "acceptance_counts": {},
    "immediate_next_not_applied": [],
    "inspected_only_skills": [],
    "mentioned_only_skills": [],
    "pb_migration_evidence": {
      "authoritative_style_source": "none",
      "claimed_unverified": [],
      "completion_claims": {},
      "completion_requested": false,
      "contextual": false,
      "draft_validated": false,
      "duplicate_call_ids": [],
      "front_door_history": [],
      "invalid_verifier_invocations": [],
      "last_write_index": -1,
      "missing_outputs": [
        "packaged_profile",
        "csharp_verification",
        "designer_verification",
        "sp_verification",
        "sql_binding_release"
      ],
      "output_evidence": {
        "build_verification": [],
        "csharp_verification": [],
        "database_verification": [],
        "deployment_verification": [],
        "designer_layout_verification": [],
        "designer_verification": [],
        "manual_qa": [],
        "packaged_profile": [],
        "project_inclusion_verification": [],
        "sp_verification": [],
        "sql_binding_release": []
      },
      "relevant_writes": [],
      "required": false,
      "required_outputs": [
        "packaged_profile",
        "csharp_verification",
        "designer_verification",
        "sp_verification",
        "sql_binding_release"
      ],
      "routed": false,
      "satisfied_outputs": [],
      "style_application_status": "blocked_missing_packaged_fixed_profile_receipt",
      "targets_extractable": false,
      "verified_correction_indexes": [],
      "verifier_attempted": false,
      "verifier_call_ids": [],
      "verifier_completed": false,
      "verifier_executed": false,
      "verifier_receipts": [],
      "written_targets": []
    },
    "recommended_actions": [],
    "required_missing_or_unaccepted": [],
    "runtime_applied_skills": [],
    "selected_not_executed_skills": [],
    "session_event_index_diagnostics": {
      "check_count": 26,
      "finalized_reducer_count": 31,
      "original_passes": 1,
      "reducer_count": 31,
      "reducer_finalize_count": 31,
      "registered_reducer_count": 31,
      "retained_record_count": 0,
      "source_bytes_read": "<FILE_SIZE>",
      "source_open_count": 1,
      "source_passes": 1
    },
    "sql_formatting_evidence": {
      "action_kind": "",
      "binding_errors": [],
      "final_response_bound": false,
      "formatter_application_proven": false,
      "provider_inspected": false,
      "provider_selected": false,
      "required": false,
      "states": [],
      "status": "not_required",
      "verification_id": "",
      "verified_before_output": false,
      "verifier_evidence_unbound": false,
      "verifier_executed": false,
      "verifier_failed": false,
      "verifier_pending": false
    },
    "status_counts": {},
    "subagent_summary": {
      "closed": 0,
      "closed_while_running": 0,
      "reviewer_mentions": 0,
      "spawned": 0,
      "timed_out": 0
    },
    "token_optimizer": {
      "acceptance_status": "",
      "required": false,
      "runtime_status": "not_checked",
      "runtime_status_reason": "no runtime token-optimizer receipt",
      "skill_row_status": "absent",
      "token_gate": {
        "checked": false,
        "context_ratio_threshold": 0.5,
        "cumulative_threshold_tokens": 200000,
        "max_context_ratio": 0.0,
        "max_last_input_tokens": 0,
        "max_total_tokens": 0,
        "model_context_window": 0,
        "reasons": [],
        "required": false,
        "threshold_tokens": 50000
      }
    },
    "verdict": "passed"
  }
}
'''
)


class SessionSkillAuditStreamingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.front_door_receipt = build_kh_front_door(
            "What is 1 + 1?",
            project=REPO_ROOT,
        ).to_micro_summary_dict()

    def write_session(self, events, *, session_id="session-audit"):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)

        def bind(value):
            if isinstance(value, str):
                return value.replace("{session_cwd}", root.as_posix())
            if isinstance(value, list):
                return [bind(item) for item in value]
            if isinstance(value, dict):
                return {key: bind(item) for key, item in value.items()}
            return value

        bound_events = [bind(event) for event in events]
        self.authenticate_general_tool_pairs(bound_events)
        path = root / "session.jsonl"
        records = [
            {
                "type": "session_meta",
                "payload": {
                    "id": session_id,
                    "thread_id": session_id,
                    "cwd": str(root),
                },
            },
            *bound_events,
        ]
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            for record in records:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        return path

    @staticmethod
    def authenticate_general_tool_pairs(events):
        calls = {}
        outputs = {}
        for event in events:
            if event.get("type") != "response_item":
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            call_id = str(
                payload.get("call_id") or payload.get("tool_call_id") or ""
            ).strip()
            payload_type = str(payload.get("type") or "")
            if not call_id:
                continue
            if payload_type in {"function_call", "custom_tool_call"}:
                calls.setdefault(call_id, []).append(payload)
            elif payload_type in {"function_call_output", "custom_tool_call_output"}:
                outputs.setdefault(call_id, []).append(payload)

        provenance_keys = {
            "boundary_id",
            "call_packet_sha256",
            "correlation_id",
            "host",
            "origin",
            "packet_hash",
            "packet_sha256",
            "source",
            "tool_identity",
        }
        for call_id in set(calls) & set(outputs):
            if len(calls[call_id]) != 1 or len(outputs[call_id]) != 1:
                continue
            call = calls[call_id][0]
            output = outputs[call_id][0]
            if any(key in call or key in output for key in provenance_keys):
                continue
            tool_identity = str(call.get("name") or "").strip().lower()
            if not audit_module._is_allowed_general_tool_identity(tool_identity):
                continue
            boundary_id = f"runtime-boundary-{call_id}"
            call.update(
                {
                    "source": "codex_host",
                    "host": "codex",
                    "tool_identity": tool_identity,
                    "correlation_id": call_id,
                    "boundary_id": boundary_id,
                }
            )
            call["packet_sha256"] = audit_module._general_tool_packet_sha256(call)
            output.update(
                {
                    "source": "codex_host",
                    "host": "codex",
                    "tool_identity": tool_identity,
                    "correlation_id": call_id,
                    "boundary_id": boundary_id,
                    "call_packet_sha256": call["packet_sha256"],
                }
            )
            output["packet_sha256"] = audit_module._general_tool_packet_sha256(
                output
            )

    @staticmethod
    def front_door_call(call_id, *, boundary_id=None):
        boundary_id = boundary_id or f"front-door-boundary-{call_id}"
        return {
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "shell_command",
                "call_id": call_id,
                "source": "codex_host",
                "host": "codex",
                "tool_identity": "shell_command",
                "correlation_id": call_id,
                "boundary_id": boundary_id,
                "arguments": (
                    "python -m src.orchestration.kh_front_door "
                    "--prompt \"Inspect this module.\" --micro-summary"
                ),
            },
        }

    @staticmethod
    def front_door_output(
        receipt,
        call_id,
        *,
        boundary_id=None,
        exit_code=0,
    ):
        boundary_id = boundary_id or f"front-door-boundary-{call_id}"
        packet = json.loads(json.dumps(receipt))
        packet_hash = hashlib.sha256(
            json.dumps(
                {
                    key: value
                    for key, value in packet.items()
                    if key not in {"packet_sha256", "packet_hash"}
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return {
            "type": "response_item",
            "payload": {
                "type": "function_call_output",
                "call_id": call_id,
                "source": "codex_host",
                "host": "codex",
                "tool_identity": "shell_command",
                "correlation_id": call_id,
                "boundary_id": boundary_id,
                "packet_sha256": packet_hash,
                "output": f"Exit code: {exit_code}\n{json.dumps(receipt)}",
            },
        }

    @staticmethod
    def memory_import_directive(
        action="approve",
        *,
        project="{session_cwd}",
        conversation_id="session-audit",
    ):
        approved = action == "approve"
        directive = {
            "claim_kind": "kh_memory_import_approval",
            "action": action,
            "memory_import_approved": approved,
            "approval_state": "approved" if approved else "revoked",
            "scope": "host-global",
            "project": project,
            "conversation_id": conversation_id,
        }
        return {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": json.dumps(directive, ensure_ascii=False),
            },
        }

    @staticmethod
    def memory_read_event():
        return {
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "shell_command",
                "arguments": (
                    "Select-String -Path "
                    "'C:\\Users\\KONEIT\\.codex\\memories\\MEMORY.md' "
                    "-Pattern 'scope'"
                ),
            },
        }

    @staticmethod
    def issue_projection(audit):
        return [
            (issue.get("skill"), issue.get("status"), issue.get("severity"))
            for issue in audit.issues
        ]

    def test_exact_reducer_registration_and_finalization_are_reported(self):
        reducer_names = tuple(getattr(audit_module, "_AUDIT_REDUCER_NAMES", ()))
        self.assertEqual(len(reducer_names), EXPECTED_REDUCER_COUNT)
        self.assertEqual(len(set(reducer_names)), EXPECTED_REDUCER_COUNT)

        path = self.write_session([])
        diagnostics = analyze_session_skills(path).usage_summary[
            STREAMING_DIAGNOSTICS_KEY
        ]
        registered = diagnostics.get(
            "registered_reducer_count",
            diagnostics.get("reducer_count"),
        )
        finalized = diagnostics.get(
            "finalized_reducer_count",
            diagnostics.get("reducer_finalize_count"),
        )

        self.assertEqual(registered, EXPECTED_REDUCER_COUNT)
        self.assertEqual(
            finalized,
            EXPECTED_REDUCER_COUNT,
            "all 31 registered reducers must be finalized exactly once",
        )

    def test_source_is_opened_and_consumed_exactly_once(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Inspect the current audit.",
                    },
                }
            ]
        )
        file_size = path.stat().st_size
        original_open = Path.open
        source_open_count = 0

        def counting_open(path_object, *args, **kwargs):
            nonlocal source_open_count
            if path_object == path:
                source_open_count += 1
            return original_open(path_object, *args, **kwargs)

        with mock.patch.object(Path, "open", new=counting_open):
            audit = analyze_session_skills(path)

        diagnostics = audit.usage_summary[STREAMING_DIAGNOSTICS_KEY]
        self.assertEqual(source_open_count, 1)
        self.assertEqual(diagnostics["source_open_count"], 1)
        self.assertEqual(diagnostics["source_passes"], 1)
        self.assertEqual(diagnostics["source_bytes_read"], file_size)

    def test_stage_telemetry_is_measured_bounded_and_opt_in(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Inspect parser stage telemetry.",
                    },
                }
            ]
        )
        index = audit_module._build_session_event_index(
            path,
            collect_stage_telemetry=True,
        )
        self.addCleanup(index.close)

        self.assertNotIn("stage_telemetry", index.diagnostics())
        diagnostics = index.diagnostics(include_stage_telemetry=True)
        telemetry = diagnostics["stage_telemetry"]
        expected_seconds = {
            "source_read_seconds",
            "decode_json_seconds",
            "event_consume_seconds",
            "feature_extract_seconds",
            "event_store_seconds",
            "reducer_consume_seconds",
            "downstream_seconds",
            "stream_seconds",
            "reducer_finalize_seconds",
            "correlation_finalize_seconds",
            "analysis_finalize_seconds",
            "seal_seconds",
            "finalize_seconds",
        }
        self.assertEqual(set(telemetry), expected_seconds | {"source_line_count", "event_count"})
        for key in expected_seconds:
            self.assertIs(type(telemetry[key]), float)
            self.assertGreater(telemetry[key], 0.0, key)
        self.assertEqual(telemetry["source_line_count"], 2)
        self.assertEqual(telemetry["event_count"], 1)
        self.assertLessEqual(len(telemetry), 16)

    def test_stage_telemetry_zero_only_for_unexercised_event_stages(self):
        path = self.write_session([])
        index = audit_module._build_session_event_index(
            path,
            collect_stage_telemetry=True,
        )
        self.addCleanup(index.close)

        telemetry = index.diagnostics(include_stage_telemetry=True)["stage_telemetry"]
        self.assertEqual(telemetry["source_line_count"], 1)
        self.assertEqual(telemetry["event_count"], 0)
        for key in {
            "source_read_seconds",
            "decode_json_seconds",
            "event_consume_seconds",
            "downstream_seconds",
            "stream_seconds",
            "reducer_finalize_seconds",
            "correlation_finalize_seconds",
            "analysis_finalize_seconds",
            "seal_seconds",
            "finalize_seconds",
        }:
            self.assertGreater(telemetry[key], 0.0, key)
        for key in {
            "feature_extract_seconds",
            "event_store_seconds",
            "reducer_consume_seconds",
        }:
            self.assertEqual(telemetry[key], 0.0, key)

    def test_multiple_immediate_claims_use_one_ordered_correlation_replay(self):
        receipt = json.loads(json.dumps(self.front_door_receipt))
        receipt["immediate_next_skills"] = ["goal-state-harness"]
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Inspect the first goal boundary.",
                    },
                },
                self.front_door_call("ordered-claim-1"),
                self.front_door_output(receipt, "ordered-claim-1"),
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Inspect the second goal boundary.",
                    },
                },
                self.front_door_call("ordered-claim-2"),
                self.front_door_output(receipt, "ordered-claim-2"),
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": "Inspection ended.",
                    },
                },
            ]
        )
        built_indexes = []
        original_builder = audit_module._build_session_event_index

        def tracked_builder(session_path):
            index = original_builder(session_path)
            built_indexes.append(index)
            return index

        with mock.patch.object(
            audit_module,
            "_build_session_event_index",
            side_effect=tracked_builder,
        ):
            audit = analyze_session_skills(path)

        self.assertEqual(len(built_indexes), 1)
        self.assertEqual(
            built_indexes[0].payload_events._ordered_correlation_replay_count,
            1,
        )
        self.assertEqual(
            built_indexes[0].payload_events._ordered_correlation_claim_count,
            2,
        )

    def test_protocol_candidates_use_one_narrow_correlation_replay(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "validate_large_work_orchestration_bundle",
                        "call_id": "protocol-bundle",
                        "arguments": json.dumps(
                            {
                                "bundle": {
                                    "parallel_strategy_decision": (
                                        "sequential because the shared-state write set is coupled"
                                    ),
                                    "skill_statuses": {
                                        "role-execution-audit-harness": {
                                            "status": "considered_not_needed",
                                            "evidence_note": "No independent role artifact is useful.",
                                        }
                                    },
                                }
                            }
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "call_id": "protocol-bundle",
                        "output": json.dumps(
                            {
                                "valid": True,
                                "missing": [],
                                "evidence": ["parallel_strategy_decision"],
                            }
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "audit_role_execution",
                        "call_id": "protocol-role-audit",
                        "arguments": "{}",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "call_id": "protocol-role-audit",
                        "output": json.dumps(
                            {
                                "status": "passed",
                                "evidence": ["role-wave-1"],
                                "checks": [
                                    {
                                        "name": "role-execution-audit",
                                        "summary": {
                                            "execution_model": "dag-asyncio-role-waves",
                                            "parallel_wave_count": 1,
                                        },
                                    }
                                ],
                            }
                        ),
                    },
                },
            ]
        )
        index = audit_module._build_session_event_index(path)
        self.addCleanup(index.close)
        token = audit_module._SESSION_EVENT_INDEX.set(index)
        try:
            evidence = audit_module._validated_orchestration_artifacts(path)
        finally:
            audit_module._SESSION_EVENT_INDEX.reset(token)

        self.assertEqual(
            index.payload_events._connection.execute(
                "SELECT COUNT(*) FROM orchestration_protocol_calls"
            ).fetchone()[0],
            2,
        )
        self.assertEqual(
            index.payload_events._protocol_correlation_replay_count,
            1,
        )
        self.assertEqual(
            evidence,
            {"parallel_strategy": True, "role_execution_audit": True},
        )

    def test_no_compact_jsonl_spool_is_created(self):
        path = self.write_session([])
        original_named_temporary_file = tempfile.NamedTemporaryFile
        requested_suffixes = []

        def tracking_named_temporary_file(*args, **kwargs):
            requested_suffixes.append(str(kwargs.get("suffix", "")))
            return original_named_temporary_file(*args, **kwargs)

        with mock.patch.object(
            audit_module.tempfile,
            "NamedTemporaryFile",
            side_effect=tracking_named_temporary_file,
        ):
            analyze_session_skills(path)

        self.assertNotIn(".jsonl", requested_suffixes)

    def test_disk_backed_compatibility_view_does_not_retain_records_list(self):
        source = inspect.getsource(audit_module)
        tree = ast.parse(source)
        retained_record_attributes = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or node.name != "DiskBackedSessionEvents":
                continue
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.Attribute)
                    and isinstance(child.value, ast.Name)
                    and child.value.id == "self"
                    and child.attr == "_records"
                ):
                    retained_record_attributes.append(child.lineno)

        self.assertEqual(
            retained_record_attributes,
            [],
            "DiskBackedSessionEvents._records retains the full projected stream",
        )

    def test_ten_thousand_malformed_boundaries_keep_count_and_eight_samples(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "malformed-10k.jsonl"
        malformed = (
            '{"type":"response_item","payload":{"type":"message",'
            '"role":"user","content":"hidden boundary"}\n'
        )
        with path.open("w", encoding="utf-8", newline="") as stream:
            stream.write(
                json.dumps(
                    {
                        "type": "session_meta",
                        "payload": {"id": "malformed-10k", "cwd": tmp.name},
                    }
                )
                + "\n"
            )
            for _ in range(10_000):
                stream.write(malformed)

        audit = analyze_session_skills(path)
        issue = next(
            item
            for item in audit.issues
            if item.get("integrity_code") == "malformed_task_boundary"
        )

        self.assertEqual(issue["occurrences"], 10_000)
        self.assertLessEqual(len(issue["samples"]), MAX_INTEGRITY_SAMPLES)
        self.assertLessEqual(
            len(issue["sample_line_numbers"]),
            MAX_INTEGRITY_SAMPLES,
        )

    def test_duplicate_call_boundary_and_packet_hashes_fail_closed(self):
        receipt = self.front_door_receipt
        duplicate_call = [
            self.front_door_call("duplicate-call"),
            self.front_door_call("duplicate-call"),
            self.front_door_output(receipt, "duplicate-call"),
        ]
        duplicate_boundary = [
            self.front_door_call("boundary-1", boundary_id="shared-boundary"),
            self.front_door_output(
                receipt,
                "boundary-1",
                boundary_id="shared-boundary",
            ),
            self.front_door_call("boundary-2", boundary_id="shared-boundary"),
            self.front_door_output(
                receipt,
                "boundary-2",
                boundary_id="shared-boundary",
            ),
        ]
        duplicate_packet_hash = [
            self.front_door_call("packet-1"),
            self.front_door_output(receipt, "packet-1"),
            self.front_door_call("packet-2"),
            self.front_door_output(receipt, "packet-2"),
        ]

        for label, events in {
            "call_id": duplicate_call,
            "boundary_id": duplicate_boundary,
            "packet_hash": duplicate_packet_hash,
        }.items():
            with self.subTest(label=label):
                path = self.write_session(events)
                audit = analyze_session_skills(path)
                evidence = audit.postmortem["token_optimizer_evidence"]
                self.assertEqual(evidence["front_door_runtime_receipts"], 0)
                self.assertFalse(
                    any(
                        item.get("status") == "accepted"
                        for item in audit.usage_summary["pb_migration_evidence"][
                            "front_door_history"
                        ]
                    )
                )

    def test_output_before_call_mismatch_and_failed_output_fail_closed(self):
        receipt = self.front_door_receipt
        cases = {
            "output_before_call": [
                self.front_door_output(receipt, "ordered"),
                self.front_door_call("ordered"),
            ],
            "call_id_mismatch": [
                self.front_door_call("call-side"),
                self.front_door_output(receipt, "output-side"),
            ],
            "boundary_mismatch": [
                self.front_door_call("boundary-mismatch"),
                self.front_door_output(
                    receipt,
                    "boundary-mismatch",
                    boundary_id="different-boundary",
                ),
            ],
            "failed_output": [
                self.front_door_call("failed-output"),
                self.front_door_output(
                    receipt,
                    "failed-output",
                    exit_code=1,
                ),
            ],
        }
        for label, events in cases.items():
            with self.subTest(label=label):
                path = self.write_session(events)
                audit = analyze_session_skills(path)
                self.assertEqual(
                    audit.postmortem["token_optimizer_evidence"][
                        "front_door_runtime_receipts"
                    ],
                    0,
                )

    def test_user_correction_supersedes_repeated_assistant_assumption_in_order(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "The export requires `retired_flag`.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": (
                            "Correction: use `canonical_flag`, not `retired_flag`; "
                            "the earlier requirement is invalid."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "I kept `retired_flag` because it is still required.",
                    },
                },
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": "The export is complete.",
                    },
                },
            ]
        )

        issue = next(
            item
            for item in analyze_session_skills(path).issues
            if item.get("status") == "invalidated_user_correction_repeated"
        )
        self.assertEqual(issue["severity"], "P0")
        self.assertEqual(issue["invalidated_claims"], ["retired_flag"])
        self.assertIn("canonical_flag", issue["correction"])
        self.assertIn("retired_flag", issue["repetition"])

    def test_memory_approval_is_scope_bound_authenticated_and_revocable(self):
        unauthorized_statuses = {
            "global_memory_lookup_without_scope_approval",
            "global_memory_shortcut_without_brainstorm_gate",
            "cross_chat_memory_leak",
            "global_memory_citation_without_scope_approval",
        }

        def unauthorized(audit):
            return any(
                issue.get("skill") == "memory-state-harness"
                and issue.get("status") in unauthorized_statuses
                for issue in audit.issues
            )

        standalone = analyze_session_skills(
            self.write_session(
                [self.memory_import_directive(), self.memory_read_event()]
            )
        )
        self.assertFalse(unauthorized(standalone))

        runtime_events = [
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "approve_memory_import",
                    "call_id": "memory-approval-runtime",
                    "arguments": json.dumps({"scope": "host-global"}),
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call_output",
                    "call_id": "memory-approval-runtime",
                    "output": json.dumps(
                        {
                            "memory_import_approval": {
                                "claim_kind": "kh_memory_import_approval",
                                "action": "approve",
                                "memory_import_approved": True,
                                "approval_state": "approved",
                                "application_status": "applied",
                                "scope": "host-global",
                                "project": "{session_cwd}",
                                "conversation_id": "session-audit",
                            }
                        }
                    ),
                },
            },
            self.memory_read_event(),
        ]
        authenticated = analyze_session_skills(self.write_session(runtime_events))
        self.assertFalse(unauthorized(authenticated))

        for label, directives in {
            "wrong_project": [
                self.memory_import_directive(project="C:/wrong-project")
            ],
            "wrong_conversation": [
                self.memory_import_directive(conversation_id="other-session")
            ],
            "revoked": [
                self.memory_import_directive(),
                self.memory_import_directive("revoke"),
            ],
        }.items():
            with self.subTest(label=label):
                audit = analyze_session_skills(
                    self.write_session([*directives, self.memory_read_event()])
                )
                self.assertTrue(unauthorized(audit))

    def test_representative_public_output_matches_golden_semantics(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": (
                            "Finish model training, backtest, DB persistence, "
                            "and dashboard."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "thread_goal_updated",
                        "goal": {
                            "status": "active",
                            "objective": (
                                "Finish model training, backtest, DB persistence, "
                                "and dashboard."
                            ),
                        },
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "call_id": "golden-build",
                        "arguments": "python -m unittest tests.test_model",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "call_id": "golden-build",
                        "output": "Exit code: 1\nFAILED (failures=1)",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": (
                            "Initial dashboard scaffold completed and verified."
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        direct_postmortem = analyze_codex_session_jsonl(path).to_dict()
        postmortem_keys = {
            "archive_guard",
            "assistant_stop_guard",
            "completion_guard",
            "recommended_actions",
            "resume_guard",
            "review_status",
            "scope_completion_delta",
            "subagent_summary",
            "token_gate",
            "token_optimizer_status",
            "token_optimizer_status_reason",
            "user_stop_guard",
            "verification_claim_guard",
        }
        for key in sorted(postmortem_keys):
            with self.subTest(postmortem_key=key):
                self.assertEqual(
                    audit.postmortem[key],
                    direct_postmortem[key],
                )
        self.assertEqual(audit.postmortem["completion_guard"]["status"], "blocked")
        self.assertEqual(
            audit.postmortem["verification_claim_guard"]["status"],
            "blocked",
        )
        self.assertEqual(
            audit.postmortem["scope_completion_delta"]["missing_markers"],
            ["model_training", "backtest", "db_persistence"],
        )
        self.assertEqual(
            self.issue_projection(audit),
            [
                ("always-on-front-door", "absent", "P1"),
                ("automatic-intake-harness", "absent", "P1"),
                ("command-output-harness", "absent", "P1"),
                ("harness-evaluator", "absent", "P1"),
                ("plugin-composition-policy", "absent", "P1"),
                ("qa-gate-harness", "absent", "P1"),
                ("quality-gates-harness", "absent", "P1"),
                ("request-complexity-router", "absent", "P1"),
                ("skill-catalog", "absent", "P1"),
                ("verification-before-completion-harness", "absent", "P1"),
                ("always-on-front-door", "missing_front_door", "P1"),
                ("goal-state-harness", "blocked", "P1"),
                ("verification-before-completion-harness", "blocked", "P1"),
                ("context-state-harness", "blocked", "P1"),
                ("goal-state-harness", "missing_terminal_goal_state", "P0"),
            ],
        )
        self.assertEqual(
            audit.postmortem["token_optimizer_evidence"][
                "front_door_runtime_provenance"
            ],
            {
                "status": "structural_jsonl_correlation_only",
                "external_authenticity": "unverified",
                "note": (
                    "The audit proves ordered host call/output correlation, "
                    "identity, boundary, correlation, and packet-hash consistency; "
                    "it cannot prove file-level cryptographic authenticity."
                ),
            },
        )

    def test_large_middle_only_semantics_match_standalone_postmortem(self):
        edge_noise = " " * (70 * 1024)

        def middle_only(text):
            return edge_noise + text + edge_noise

        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": middle_only("Do not continue until approval."),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "agent_message",
                        "message": middle_only(
                            "I will continue implementing and run tests."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": middle_only("Resume the task and continue."),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "agent_message",
                        "message": middle_only(
                            "session_start_context runtime_token_optimization "
                            "large_work_orchestration_bundle token-optimizer "
                            "goal-state-harness api_key=middle-only-secret"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "call_id": "middle-only-command",
                        "arguments": json.dumps(
                            {
                                "command": middle_only(
                                    "python -m unittest tests.test_middle_only"
                                )
                            }
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": middle_only(
                            "All requested work completed and verified."
                        ),
                    },
                },
            ],
            session_id="middle-only-semantics",
        )

        standalone = analyze_codex_session_jsonl(path)
        extracted_features = []
        original_extractor = audit_module.extract_postmortem_event_features

        def capture_features(*args, **kwargs):
            features = original_extractor(*args, **kwargs)
            extracted_features.append(features)
            return features

        with mock.patch.object(
            audit_module,
            "extract_postmortem_event_features",
            side_effect=capture_features,
        ) as extractor:
            index = audit_module._build_session_event_index(path)
        self.addCleanup(index.close)
        shared = index.postmortem

        self.assertEqual(extractor.call_count, 6)
        self.assertEqual(len(extracted_features), 6)
        for features in extracted_features:
            self.assertFalse(hasattr(features, "text"))
            self.assertFalse(hasattr(features, "lowered"))
            self.assertLessEqual(len(features.sample_220), 223)
            self.assertLessEqual(len(features.sample_260), 263)
            self.assertIsInstance(features.audit_features.reducer_matches, tuple)
        self.assertEqual(shared.to_dict(), standalone.to_dict())
        self.assertEqual(standalone.user_stop_guard["stop_request_count"], 1)
        self.assertEqual(
            len(standalone.user_stop_guard["continued_work_messages"]),
            1,
        )
        self.assertEqual(standalone.resume_guard["status"], "passed")
        self.assertEqual(standalone.resume_guard["resume_request_count"], 1)
        self.assertEqual(standalone.completion_guard["status"], "blocked")
        self.assertEqual(len(standalone.secret_findings), 1)
        self.assertIn("goal-state-harness", standalone.skills_observed)
        self.assertIn("token-optimizer", standalone.skills_observed)
        self.assertEqual(len(standalone.verification_commands), 1)

    def test_duplicate_records_are_integrity_only_in_standalone_and_shared_paths(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "thread_goal_updated",
                        "goal": {"status": "active", "objective": "Trusted objective."},
                    },
                }
            ],
            session_id="trusted-session",
        )
        duplicate_lines = [
            '{"type":"session_meta","payload":{"id":"old","id":"new","cwd":"D:/poison"}}',
            (
                '{"type":"response_item","payload":{"type":"thread_goal_updated",'
                '"goal":{"status":"active","status":"complete","objective":"poison"}}}'
            ),
            (
                '{"type":"response_item","payload":{"type":"task_complete",'
                '"last_agent_message":"All completed.","marker":"old","marker":"new"}}'
            ),
            (
                '{"type":"response_item","payload":{"type":"message","role":"user",'
                '"content":"hello","content":"Stop now."}}'
            ),
        ]
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            for line in duplicate_lines:
                stream.write(line + "\n")

        standalone_original = postmortem_module.extract_postmortem_event_features
        with mock.patch.object(
            postmortem_module,
            "extract_postmortem_event_features",
            side_effect=standalone_original,
        ) as standalone_extractor:
            standalone = analyze_codex_session_jsonl(path)

        audit_original = audit_module.extract_postmortem_event_features
        with mock.patch.object(
            audit_module,
            "extract_postmortem_event_features",
            side_effect=audit_original,
        ) as audit_extractor, mock.patch.object(
            postmortem_module,
            "extract_postmortem_event_features",
            side_effect=standalone_original,
        ) as shared_postmortem_extractor:
            index = audit_module._build_session_event_index(path)
        self.addCleanup(index.close)
        shared = index.postmortem

        self.assertEqual(standalone_extractor.call_count, 2)
        self.assertEqual(audit_extractor.call_count, 1)
        self.assertEqual(shared_postmortem_extractor.call_count, 1)
        self.assertEqual(index.diagnostics()["retained_record_count"], 1)
        self.assertEqual(shared.to_dict(), standalone.to_dict())
        self.assertEqual(standalone.session_id, "trusted-session")
        self.assertEqual(standalone.completion_guard["latest_goal_status"], "active")
        self.assertEqual(standalone.completion_guard["task_complete_count"], 0)
        self.assertEqual(standalone.user_stop_guard["stop_request_count"], 0)
        self.assertEqual(standalone.input_integrity["duplicate_key_count"], 4)
        self.assertEqual(standalone.input_integrity["duplicate_key_line_count"], 4)
        self.assertEqual(standalone.input_integrity["valid_event_count"], 2)

        audit = analyze_session_skills(path)
        issues = [
            issue
            for issue in audit.issues
            if issue.get("integrity_code") == "duplicate_json_key"
        ]
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["issue_type"], "input_integrity")
        self.assertTrue(issues[0]["blocking"])
        self.assertEqual(issues[0]["severity"], "P0")
        self.assertEqual(issues[0]["occurrences"], 4)
        self.assertEqual(issues[0]["sample_line_numbers"], [3, 4, 5, 6])

    def test_synthetic_24_mib_stream_has_bounded_python_retention(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "synthetic-24mib.jsonl"
        blob = "x" * (64 * 1024)
        record = json.dumps(
            {
                "type": "response_item",
                "payload": {"type": "debug_blob", "blob": blob},
            },
            separators=(",", ":"),
        ) + "\n"
        with path.open("w", encoding="utf-8", newline="") as stream:
            for _ in range(384):
                stream.write(record)
        file_size = path.stat().st_size
        self.assertGreaterEqual(file_size, 24 * 1024 * 1024)

        gc.collect()
        tracemalloc.start()
        audit = analyze_session_skills(path)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        diagnostics = audit.usage_summary[STREAMING_DIAGNOSTICS_KEY]

        self.assertEqual(diagnostics["source_open_count"], 1)
        self.assertEqual(diagnostics["source_passes"], 1)
        self.assertEqual(diagnostics["source_bytes_read"], file_size)
        self.assertNotIn("retained_record_bytes", diagnostics)
        self.assertLess(peak, 12 * 1024 * 1024)

    def test_sparse_large_records_do_not_accumulate_full_records(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "sparse-large-records.jsonl"
        blob = "z" * (8 * 1024 * 1024)
        with path.open("w", encoding="utf-8", newline="") as stream:
            for index in range(3):
                stream.write(
                    json.dumps(
                        {
                            "type": "response_item",
                            "payload": {
                                "type": "debug_blob",
                                "index": index,
                                "blob": blob,
                            },
                        },
                        separators=(",", ":"),
                    )
                    + "\n"
                )
        del blob
        file_size = path.stat().st_size

        gc.collect()
        tracemalloc.start()
        audit = analyze_session_skills(path)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        diagnostics = audit.usage_summary[STREAMING_DIAGNOSTICS_KEY]

        self.assertEqual(diagnostics["source_bytes_read"], file_size)
        self.assertNotIn("retained_record_bytes", diagnostics)
        self.assertLess(peak, 64 * 1024 * 1024)

    def test_generic_events_are_scalar_only_and_text_is_stored_once(self):
        events = audit_module.DiskBackedSessionEvents()
        self.addCleanup(events.close)
        events.append(
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "shell_command",
                    "call_id": "scalar-call",
                    "arguments": "python -m unittest tests.test_scalar",
                },
            },
            source_line=1,
        )
        events.begin_text_records()
        events.append_text_record(
            0,
            audit_module.SessionTextRecord(
                text="shell_command python -m unittest tests.test_scalar",
                payload_type="function_call",
                call_id="scalar-call",
                name="shell_command",
                arguments="python -m unittest tests.test_scalar",
            ),
        )
        events.seal_text_records()

        event_columns = {
            str(row[1])
            for row in events._connection.execute("PRAGMA table_info(events)")
        }
        self.assertTrue(
            {"record", "payload_json", "source_sha256"}.isdisjoint(event_columns)
        )
        self.assertEqual(
            events._connection.execute(
                "SELECT COUNT(*) FROM retained_json"
            ).fetchone()[0],
            0,
            "generic call/message events must not retain canonical payload JSON",
        )
        stored_text, stored_arguments = events._connection.execute(
            "SELECT text, arguments FROM text_records WHERE record_seq = 0"
        ).fetchone()
        self.assertEqual(stored_text, "")
        self.assertEqual(
            stored_arguments,
            "python -m unittest tests.test_scalar",
        )

    def test_catalog_candidate_buckets_match_exhaustive_literal_semantics(self):
        skills = [
            {
                "name": "alpha-observation-harness",
                "relative_path": "alpha_observation_harness/SKILL.md",
            },
            {
                "name": "token-optimizer",
                "relative_path": "token_optimizer/SKILL.md",
            },
        ]
        catalog_index = audit_module._build_catalog_observation_index(skills)
        probes = [
            "plain unrelated text",
            "escaped \\n and whitespace only",
            "prefix ation-harness without the complete skill name",
            "{\"message\":\"token optimizer words without the marker\"}",
        ]
        probes.extend(
            f"prefix\t{needle}\n suffix"
            for needle in catalog_index.candidate_needles
        )
        for probe in probes:
            with self.subTest(probe=probe[:80]):
                lowered = probe.lower()
                expected = any(
                    needle in lowered
                    for needle in catalog_index.candidate_needles
                )
                self.assertEqual(
                    audit_module._has_catalog_candidate(lowered, catalog_index),
                    expected,
                )
                for buckets, owners in (
                    (catalog_index.candidate_buckets, catalog_index.alias_owners),
                    (catalog_index.candidate_buckets, catalog_index.runtime_owners),
                ):
                    expected_owners = {
                        owner
                        for needle, needle_owners in owners.items()
                        if needle in lowered
                        for owner in needle_owners
                    }
                    self.assertEqual(
                        audit_module._catalog_owner_hits(
                            lowered,
                            buckets,
                            owners,
                        ),
                        expected_owners,
                    )

    def test_bounded_text_accumulator_lowercase_reuse_is_semantically_exact(self):
        values = [
            "token-optimizer considered_not_needed",
            "İ" * 20 + " middle " + "verification" + "İ" * 20,
            "plain text",
        ]
        baseline = audit_module._BoundedTextAccumulator(item_limit=24)
        optimized = audit_module._BoundedTextAccumulator(item_limit=24)
        for value in values:
            baseline.add(value)
            optimized.add(value, lowered=value.lower())
        self.assertEqual(baseline.render(), optimized.render())
        self.assertEqual(baseline.first, optimized.first)
        self.assertEqual(baseline.signals, optimized.signals)
        self.assertEqual(baseline.signal_count, optimized.signal_count)

    def test_scalar_analysis_is_extracted_in_pass_with_one_catalog_replay(self):
        skills = [
            {
                "name": "token-optimizer",
                "relative_path": "token_optimizer/SKILL.md",
            }
        ]
        events = audit_module.DiskBackedSessionEvents(skills)
        self.addCleanup(events.close)
        payload = {
            "type": "message",
            "role": "user",
            "content": "Format this SQL: SELECT * FROM dbo.T; token-optimizer considered_not_needed",
        }
        events.append(
            {"type": "response_item", "payload": payload},
            source_line=1,
        )
        events.begin_text_records()
        events.append_text_record(
            0,
            audit_module.SessionTextRecord(
                text=payload["content"],
                payload_type="message",
                role="user",
            ),
            lowered=payload["content"].lower(),
        )
        self.assertEqual(
            events._connection.execute(
                "SELECT sql_requirement FROM text_records WHERE record_seq = 0"
            ).fetchone()[0],
            1,
        )
        self.assertEqual(
            events._connection.execute(
                "SELECT is_sql_output_request FROM events WHERE seq = 0"
            ).fetchone()[0],
            1,
        )

        statements = []
        events._connection.set_trace_callback(statements.append)
        try:
            events.finalize_analysis_summary()
        finally:
            events._connection.set_trace_callback(None)
        catalog_selects = [
            statement
            for statement in statements
            if statement.lstrip().upper().startswith("SELECT")
            and "catalog_candidate_records" in statement
        ]
        self.assertEqual(len(catalog_selects), 1)
        self.assertFalse(
            any(
                statement.lstrip().upper().startswith("SELECT")
                and "FROM text_records\n" in statement
                and "catalog_candidate_records" not in statement
                for statement in statements
            )
        )
        summary = events.analysis_summary()
        self.assertIn("SELECT * FROM dbo.T", summary["sql_scope_text"])
        self.assertGreater(
            summary["catalog_observations"]["token-optimizer"]["mentions"],
            0,
        )

    def test_corrupt_retained_json_is_rejected_without_deserialization(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        marker = Path(tmp.name) / "deserialization-executed.txt"
        events = audit_module.DiskBackedSessionEvents()
        self.addCleanup(events.close)
        events.append(
            {
                "type": "response_item",
                "payload": {
                    "type": "thread_goal_updated",
                    "goal": {"status": "active", "objective": "safe"},
                },
            },
            source_line=1,
        )
        events.seal()
        malicious_blob = pickle.dumps(
            _ExecutablePicklePayload(str(marker)),
            protocol=5,
        )
        events._connection.execute(
            "UPDATE retained_json SET data_json = ? WHERE event_seq = 0",
            (audit_module.sqlite3.Binary(malicious_blob),),
        )
        events._connection.commit()

        rejected = False
        try:
            list(events.iter_payloads(payload_types=("thread_goal_updated",)))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            rejected = True

        self.assertFalse(
            marker.exists(),
            "tampered retained JSON executed during decoding",
        )
        self.assertTrue(
            rejected,
            "tampered retained JSON bytes must be rejected fail-closed",
        )

    def test_retained_json_allowlist_preserves_scalar_provenance(self):
        events = audit_module.DiskBackedSessionEvents()
        self.addCleanup(events.close)
        events.append(
            {
                "type": "response_item",
                "payload": {
                    "type": "thread_goal_updated",
                    "source": "codex",
                    "status": "active",
                    "goal": {"status": "active", "objective": "safe"},
                    "info": {"reason": "resume"},
                    "memory_citation": {"scope": "project"},
                },
            },
            source_line=1,
        )
        events.seal()

        fact_kind, data_json = events._connection.execute(
            "SELECT fact_kind, data_json FROM retained_json WHERE event_seq = 0"
        ).fetchone()
        self.assertEqual(fact_kind, "goal+memory")
        self.assertEqual(
            sorted(json.loads(data_json)),
            ["goal", "info", "memory_citation"],
        )
        _, payload = next(
            events.iter_payloads(payload_types=("thread_goal_updated",))
        )
        self.assertEqual(payload["source"], "codex")
        self.assertEqual(payload["status"], "active")
        self.assertEqual(payload["goal"]["objective"], "safe")
        self.assertEqual(payload["memory_citation"], {"scope": "project"})

    def test_retained_json_rejects_valid_json_scalar_overwrite(self):
        events = audit_module.DiskBackedSessionEvents()
        self.addCleanup(events.close)
        events.append(
            {
                "type": "response_item",
                "payload": {
                    "type": "thread_goal_updated",
                    "source": "codex",
                    "status": "active",
                    "goal": {"status": "active", "objective": "safe"},
                },
            },
            source_line=1,
        )
        events.seal()
        events._connection.execute(
            "UPDATE retained_json SET data_json = ? WHERE event_seq = 0",
            (
                json.dumps(
                    {
                        "goal": {"status": "active", "objective": "safe"},
                        "source": "attacker",
                        "status": "failed",
                    }
                ),
            ),
        )
        events._connection.commit()

        with self.assertRaisesRegex(ValueError, "unexpected retained JSON keys"):
            list(events.iter_payloads(payload_types=("thread_goal_updated",)))

    def test_retained_json_rejects_fact_kind_and_payload_type_mismatch(self):
        events = audit_module.DiskBackedSessionEvents()
        self.addCleanup(events.close)
        events.append(
            {
                "type": "response_item",
                "payload": {
                    "type": "thread_goal_updated",
                    "goal": {"status": "active", "objective": "safe"},
                },
            },
            source_line=1,
        )
        events.seal()
        with self.assertRaises(audit_module.sqlite3.IntegrityError):
            events._connection.execute(
                "UPDATE retained_json SET fact_kind = 'unexpected' WHERE event_seq = 0"
            )
        events._connection.rollback()
        events._connection.execute(
            "UPDATE events SET payload_type = 'message' WHERE seq = 0"
        )
        events._connection.commit()

        with self.assertRaisesRegex(
            ValueError,
            "only valid for thread_goal_updated",
        ):
            list(events.iter_payloads(payload_types=("message",)))

    def test_retained_json_rejects_duplicate_allowed_keys(self):
        events = audit_module.DiskBackedSessionEvents()
        self.addCleanup(events.close)
        events.append(
            {
                "type": "response_item",
                "payload": {
                    "type": "thread_goal_updated",
                    "goal": {"status": "active", "objective": "safe"},
                },
            },
            source_line=1,
        )
        events.seal()
        events._connection.execute(
            "UPDATE retained_json SET data_json = ? WHERE event_seq = 0",
            ('{"goal":{"status":"active"},"goal":{"status":"complete"}}',),
        )
        events._connection.commit()

        with self.assertRaises(audit_module.DuplicateJsonKeyError):
            list(events.iter_payloads(payload_types=("thread_goal_updated",)))

    def test_constructor_connect_and_schema_failures_remove_partial_database(self):
        original_named_temporary_file = tempfile.NamedTemporaryFile
        original_connect = audit_module.sqlite3.connect

        class ConnectionProxy:
            def __init__(self, connection):
                self.connection = connection
                self.closed = False

            def execute(self, *args, **kwargs):
                return self.connection.execute(*args, **kwargs)

            def executescript(self, *args, **kwargs):
                raise RuntimeError("forced schema failure")

            def close(self):
                self.closed = True
                return self.connection.close()

            def __getattr__(self, name):
                return getattr(self.connection, name)

        for failure_kind in ("connect", "schema"):
            with self.subTest(failure_kind=failure_kind):
                tmp = tempfile.TemporaryDirectory()
                self.addCleanup(tmp.cleanup)
                created_paths = []
                proxies = []

                def tracked_named_temporary_file(*args, **kwargs):
                    kwargs["dir"] = tmp.name
                    handle = original_named_temporary_file(*args, **kwargs)
                    created_paths.append(Path(handle.name))
                    return handle

                def failing_connect(path):
                    if failure_kind == "connect":
                        raise RuntimeError("forced connect failure")
                    proxy = ConnectionProxy(original_connect(path))
                    proxies.append(proxy)
                    return proxy

                try:
                    with mock.patch.object(
                        audit_module.tempfile,
                        "NamedTemporaryFile",
                        side_effect=tracked_named_temporary_file,
                    ), mock.patch.object(
                        audit_module.sqlite3,
                        "connect",
                        side_effect=failing_connect,
                    ):
                        with self.assertRaisesRegex(
                            RuntimeError,
                            f"forced {failure_kind} failure",
                        ):
                            audit_module.DiskBackedSessionEvents()

                    self.assertEqual(len(created_paths), 1)
                    with self.subTest(
                        failure_kind=failure_kind,
                        check="database_removed",
                    ):
                        self.assertFalse(
                            created_paths[0].exists(),
                            f"{failure_kind} failure leaked the partial database",
                        )
                    if failure_kind == "schema":
                        with self.subTest(
                            failure_kind=failure_kind,
                            check="connection_closed",
                        ):
                            self.assertTrue(
                                proxies[0].closed,
                                "schema failure left the SQLite connection open",
                            )
                finally:
                    for proxy in proxies:
                        if not proxy.closed:
                            proxy.close()
                    for path in created_paths:
                        try:
                            path.unlink()
                        except FileNotFoundError:
                            pass

    def test_success_and_analysis_exception_remove_streaming_artifacts(self):
        path = self.write_session([])
        original_named_temporary_file = tempfile.NamedTemporaryFile

        for scenario in ("success", "analysis_exception"):
            with self.subTest(scenario=scenario):
                artifact_root = tempfile.TemporaryDirectory()
                self.addCleanup(artifact_root.cleanup)
                created_paths = []

                def tracked_named_temporary_file(*args, **kwargs):
                    kwargs["dir"] = artifact_root.name
                    handle = original_named_temporary_file(*args, **kwargs)
                    created_paths.append(Path(handle.name))
                    return handle

                patches = [
                    mock.patch.object(
                        audit_module.tempfile,
                        "NamedTemporaryFile",
                        side_effect=tracked_named_temporary_file,
                    )
                ]
                if scenario == "analysis_exception":
                    patches.append(
                        mock.patch.object(
                            audit_module,
                            "_analyze_session_skills_impl",
                            side_effect=RuntimeError("forced analysis failure"),
                        )
                    )
                with patches[0]:
                    if len(patches) == 2:
                        with patches[1], self.assertRaisesRegex(
                            RuntimeError,
                            "forced analysis failure",
                        ):
                            analyze_session_skills(path)
                    else:
                        analyze_session_skills(path)

                self.assertTrue(created_paths)
                self.assertEqual(
                    [item for item in created_paths if item.exists()],
                    [],
                    f"{scenario} leaked streaming artifacts",
                )

    def test_subprocess_analysis_exit_leaves_no_streaming_artifact(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        session_path = root / "subprocess-session.jsonl"
        session_path.write_text(
            json.dumps(
                {
                    "type": "session_meta",
                    "payload": {
                        "id": "subprocess-cleanup",
                        "cwd": str(root),
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        child_temp = root / "child-temp"
        child_temp.mkdir()
        code = (
            "from src.orchestration.session_skill_audit import "
            "analyze_session_skills; "
            f"analyze_session_skills({str(session_path)!r})"
        )
        environment = dict(os.environ)
        environment.update(
            {
                "TEMP": str(child_temp),
                "TMP": str(child_temp),
                "TMPDIR": str(child_temp),
            }
        )

        result = subprocess.run(
            [sys.executable, "-B", "-c", code],
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(
            list(child_temp.glob("kh-session-audit-*")),
            [],
            "the subprocess left a streaming database behind at exit",
        )

    def test_reducers_publish_consume_finalize_and_output_evidence(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Inspect reducer behavior.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": "Inspection complete.",
                    },
                },
            ]
        )
        audit = analyze_session_skills(path)
        diagnostics = audit.usage_summary[STREAMING_DIAGNOSTICS_KEY]
        reducer_evidence = diagnostics.get("reducer_evidence")

        self.assertIsInstance(
            reducer_evidence,
            list,
            "streaming diagnostics must expose per-reducer behavioral evidence",
        )
        self.assertEqual(len(reducer_evidence), EXPECTED_REDUCER_COUNT)
        self.assertEqual(
            {item["name"] for item in reducer_evidence},
            set(audit_module._AUDIT_REDUCER_NAMES),
        )
        for item in reducer_evidence:
            with self.subTest(reducer=item["name"]):
                self.assertEqual(item["consume_count"], 2)
                self.assertEqual(item["finalize_count"], 1)
                self.assertTrue(item["finalized"])
                self.assertIn("output", item)
                self.assertIsNotNone(item["output"])

    def test_adversarial_repeated_events_have_bounded_1k_to_10k_growth(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)

        def write_adversarial(path, event_count):
            with path.open("w", encoding="utf-8", newline="") as stream:
                stream.write(
                    json.dumps(
                        {
                            "type": "session_meta",
                            "payload": {
                                "id": path.stem,
                                "thread_id": path.stem,
                                "cwd": str(root),
                            },
                        },
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                for index in range(event_count):
                    pair = index // 3
                    phase = index % 3
                    if phase == 0:
                        event = {
                            "type": "response_item",
                            "payload": {
                                "type": "message",
                                "role": "user",
                                "content": "Stop this task now.",
                            },
                        }
                    elif phase == 1:
                        event = {
                            "type": "response_item",
                            "payload": {
                                "type": "function_call",
                                "name": "shell_command",
                                "call_id": f"front-door-{pair}",
                                "source": "codex_host",
                                "host": "codex",
                                "tool_identity": "shell_command",
                                "correlation_id": f"front-door-{pair}",
                                "boundary_id": f"boundary-{pair}",
                                "arguments": (
                                    "python -m src.orchestration.kh_front_door "
                                    "--prompt \"Inspect.\" --micro-summary"
                                ),
                            },
                        }
                    else:
                        event = {
                            "type": "response_item",
                            "payload": {
                                "type": "function_call_output",
                                "call_id": f"front-door-{pair}",
                                "source": "codex_host",
                                "host": "codex",
                                "tool_identity": "shell_command",
                                "correlation_id": f"front-door-{pair}",
                                "boundary_id": f"boundary-{pair}",
                                "packet_sha256": hashlib.sha256(
                                    f"packet-{pair}".encode("ascii")
                                ).hexdigest(),
                                "output": (
                                    "Exit code: 0\n"
                                    '{"front_door_status":"ok",'
                                    '"token_optimizer":{"status":'
                                    '"considered_not_needed"}}'
                                ),
                            },
                        }
                    stream.write(
                        json.dumps(event, separators=(",", ":")) + "\n"
                    )

        def measure(path):
            audit = analyze_session_skills(path)
            output = audit.to_dict()
            seen = set()

            def deep_size(value):
                identity = id(value)
                if identity in seen:
                    return 0
                seen.add(identity)
                size = sys.getsizeof(value)
                if isinstance(value, dict):
                    size += sum(
                        deep_size(key) + deep_size(item)
                        for key, item in value.items()
                    )
                elif isinstance(value, (list, tuple, set, frozenset)):
                    size += sum(deep_size(item) for item in value)
                return size

            retained_bytes = deep_size(output)
            serialized_bytes = len(
                json.dumps(
                    output,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            return retained_bytes, serialized_bytes

        small_path = root / "adversarial-1k.jsonl"
        large_path = root / "adversarial-10k.jsonl"
        write_adversarial(small_path, 1_000)
        write_adversarial(large_path, 10_000)
        small_retained, small_output = measure(small_path)
        large_retained, large_output = measure(large_path)

        with self.subTest(metric="retained_python_bytes"):
            self.assertLessEqual(
                large_retained - small_retained,
                2 * 1024 * 1024,
                "retained Python output grew with the adversarial event corpus",
            )
        with self.subTest(metric="serialized_public_output_bytes"):
            self.assertLessEqual(
                large_output - small_output,
                512 * 1024,
                "public audit output retained an adversarial corpus",
            )

    def test_pipeline_retains_no_full_corpus_under_any_attribute_name(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "attribute-corpus.jsonl"
        event_count = 257
        with path.open("w", encoding="utf-8", newline="") as stream:
            for index in range(event_count):
                stream.write(
                    json.dumps(
                        {
                            "type": "response_item",
                            "payload": {
                                "type": "debug_blob",
                                "marker": f"corpus-marker-{index}",
                            },
                        },
                        separators=(",", ":"),
                    )
                    + "\n"
                )

        pipeline = audit_module.AuditStreamPipeline(path)
        self.addCleanup(pipeline.close)
        list(pipeline.stream())
        index = pipeline.finalize()
        offenders = []
        seen = set()

        def inspect_value(value, location, depth=0):
            if depth > 8:
                return
            identity = id(value)
            if identity in seen:
                return
            seen.add(identity)
            if isinstance(value, dict):
                if len(value) >= event_count:
                    offenders.append((location, type(value).__name__, len(value)))
                for key, item in value.items():
                    inspect_value(item, f"{location}[{key!r}]", depth + 1)
                return
            if isinstance(value, (list, tuple, set, frozenset)):
                if len(value) >= event_count:
                    offenders.append((location, type(value).__name__, len(value)))
                for offset, item in enumerate(value):
                    inspect_value(item, f"{location}[{offset}]", depth + 1)
                return
            attributes = getattr(value, "__dict__", None)
            if isinstance(attributes, dict):
                for name, item in attributes.items():
                    inspect_value(item, f"{location}.{name}", depth + 1)

        inspect_value(pipeline, "pipeline")
        inspect_value(index, "index")
        self.assertEqual(
            offenders,
            [],
            "a Python attribute retained a collection as large as the corpus",
        )
        self.assertLessEqual(index.retained_memory_bytes, 512 * 1024)

    def test_complete_public_output_matches_independent_frozen_golden(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "golden-session.jsonl"
        path.write_text(
            json.dumps(
                {
                    "type": "session_meta",
                    "payload": {
                        "id": "golden-session",
                        "thread_id": "golden-session",
                        "cwd": "<ROOT>",
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

        with mock.patch.object(
            audit_module,
            "collect_packaged_skills",
            return_value={"skills": []},
        ):
            actual = analyze_session_skills(path).to_dict()
        actual["path"] = "<SESSION>"
        actual["usage_summary"][STREAMING_DIAGNOSTICS_KEY][
            "source_bytes_read"
        ] = "<FILE_SIZE>"

        def assert_frozen(actual_value, expected_value, location):
            with self.subTest(path=f"{location}.__type__"):
                self.assertIs(type(actual_value), type(expected_value))
            if isinstance(expected_value, dict):
                with self.subTest(path=f"{location}.__keys__"):
                    self.assertEqual(
                        sorted(actual_value),
                        sorted(expected_value),
                    )
                for key in sorted(actual_value.keys() & expected_value.keys()):
                    assert_frozen(
                        actual_value[key],
                        expected_value[key],
                        f"{location}.{key}",
                    )
                return
            if isinstance(expected_value, list):
                with self.subTest(path=f"{location}.__len__"):
                    self.assertEqual(len(actual_value), len(expected_value))
                for index, (actual_item, expected_item) in enumerate(
                    zip(actual_value, expected_value)
                ):
                    assert_frozen(
                        actual_item,
                        expected_item,
                        f"{location}[{index}]",
                    )
                return
            with self.subTest(path=location):
                self.assertEqual(actual_value, expected_value)

        assert_frozen(actual, FROZEN_EMPTY_AUDIT_GOLDEN, "audit")


if __name__ == "__main__":
    unittest.main()
