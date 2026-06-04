import json
import tempfile
import unittest
from pathlib import Path

from src.orchestration.session_skill_audit import (
    analyze_session_skills,
    summarize_session_skill_audits,
)


class SessionSkillAuditTests(unittest.TestCase):
    def write_session(self, events):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "session.jsonl"
        lines = [
            json.dumps(
                {
                    "type": "session_meta",
                    "payload": {
                        "id": "session-audit",
                        "cwd": str(Path(tmp.name)),
                    },
                }
            )
        ]
        lines.extend(json.dumps(event) for event in events)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def write_subagent_session(self, events):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "session.jsonl"
        lines = [
            json.dumps(
                {
                    "type": "session_meta",
                    "payload": {
                        "id": "session-audit-subagent",
                        "cwd": str(Path(tmp.name)),
                        "thread_source": "subagent",
                        "source": {"subagent": {"thread_spawn": {"parent_thread_id": "parent"}}},
                    },
                }
            )
        ]
        lines.extend(json.dumps(event) for event in events)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def test_audit_covers_full_kh_skill_catalog_and_flags_required_omissions(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 80_000},
                            "last_token_usage": {"input_tokens": 120_000},
                            "model_context_window": 200_000,
                        },
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "Large implementation continued without progress.json, GoalState, or token runtime evidence.",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}

        self.assertEqual(audit.total_skills, 40)
        self.assertEqual(audit.coverage["total_skills"], 40)
        self.assertTrue(rows["token-optimizer"]["required"])
        self.assertTrue(rows["goal-state-harness"]["required"])
        self.assertIn("token-optimizer", audit.coverage["required_missing_skill_names"])
        self.assertTrue(any(issue["skill"] == "token-optimizer" for issue in audit.issues))
        self.assertTrue(any(issue["status"] == "blocked" for issue in audit.issues))

    def test_front_door_worktree_skill_name_does_not_force_snapshot_requirement(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["worktree-isolation-harness"],
            "skill_status_summary": {
                "worktree-isolation-harness": {
                    "status": "skipped_with_rationale",
                    "evidence_note": "Selected for later only; no git or worktree command ran.",
                }
            },
        }
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": json.dumps(front_door_output),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "Created two new markdown deliverables in an empty folder. No source files were modified.",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}

        self.assertFalse(rows["snapshot-state-harness"]["required"])
        self.assertFalse(rows["worktree-isolation-harness"]["required"])
        self.assertNotIn("snapshot-state-harness", audit.coverage["required_missing_skill_names"])

    def test_actual_git_worktree_flow_requires_snapshot_requirement(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "I ran git worktree add for implementation, changed files, and prepared git commit evidence.",
                    },
                }
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}

        self.assertTrue(rows["worktree-isolation-harness"]["required"])
        self.assertTrue(rows["snapshot-state-harness"]["required"])

    def test_front_door_architect_skill_name_does_not_force_architecture_requirement(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["architect-pipeline"],
            "skill_status_summary": {
                "architect-pipeline": {
                    "status": "skipped_with_rationale",
                    "evidence_note": "Selected for later only.",
                }
            },
        }
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": json.dumps(front_door_output),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "Created a business definition and process-flow document in an empty folder.",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}

        self.assertFalse(rows["architect-pipeline"]["required"])
        self.assertNotIn("architect-pipeline", audit.coverage["required_missing_skill_names"])

    def test_front_door_selected_brainstorming_blocks_same_turn_implementation(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["brainstorming-harness"],
            "skill_status_summary": {
                "brainstorming-harness": {
                    "status": "skipped_with_rationale",
                    "evidence_note": "Selected for the workflow after front-door routing.",
                }
            },
            "execution_gate": {
                "status": "blocked_until_brainstorming_handoff",
                "can_execute": False,
                "blocked_actions": ["MEMORY.md_lookup", "implementation"],
            },
        }
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": json.dumps(front_door_output),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "New-Item -ItemType Directory -Path Dashboard -Force",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "brainstorming-harness"
                and issue["status"] == "brainstorming_execution_gate_bypassed"
                and issue["severity"] == "P1"
                for issue in audit.issues
            )
        )

    def test_brainstorm_gate_blocks_global_codex_memory_lookup(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["brainstorming-harness"],
            "skill_status_summary": {
                "brainstorming-harness": {
                    "status": "skipped_with_rationale",
                    "evidence_note": "Selected for the workflow after front-door routing.",
                }
            },
            "execution_gate": {
                "status": "blocked_until_brainstorming_handoff",
                "can_execute": False,
                "blocked_actions": [
                    "MEMORY.md_lookup",
                    "global_codex_MEMORY.md",
                    "cross_chat_or_subagent_memory",
                    "implementation",
                ],
            },
        }
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": json.dumps(front_door_output),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "Select-String -Path 'C:\\Users\\KONEIT\\.codex\\memories\\MEMORY.md' "
                            "-Pattern 'dashboard|static-web-local-verification'"
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "memory-state-harness"
                and issue["status"] == "cross_chat_memory_leak"
                and issue["severity"] == "P1"
                for issue in audit.issues
            )
        )

    def test_actual_architecture_work_requires_architect_pipeline(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "I prepared a technical spec and system design for the service architecture.",
                    },
                }
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}

        self.assertTrue(rows["architect-pipeline"]["required"])

    def test_audit_counts_runtime_token_memory_and_workflow_evidence_as_applied(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 80_000},
                            "last_token_usage": {"input_tokens": 120_000},
                            "model_context_window": 200_000,
                        },
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": (
                            "workflow_usability_auto applied apply_workflow_usability_runtime, "
                            "src.orchestration.runtime_token_optimizer.optimize_workflow_task_results "
                            "produced runtime_token_optimization with estimated_tokens_saved=2000, "
                            "src.orchestration.runtime_memory resolved memory_scope=project/chat "
                            "and recorded memory_context plus memory_candidates_recorded, "
                            "GoalState goal_ledger evidence_required complete, progress.json written."
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}

        self.assertEqual(rows["token-optimizer"]["status"], "applied")
        self.assertEqual(rows["token-optimizer"]["acceptance"]["status"], "passed")
        self.assertEqual(rows["memory-state-harness"]["status"], "applied")
        self.assertEqual(rows["memory-state-harness"]["acceptance"]["status"], "passed")
        self.assertEqual(rows["workflow-usability-harness"]["status"], "applied")
        self.assertEqual(rows["goal-state-harness"]["status"], "applied")
        self.assertNotIn("token-optimizer", audit.coverage["required_missing_skill_names"])

    def test_passive_skill_docs_do_not_count_as_runtime_application(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 80_000},
                            "last_token_usage": {"input_tokens": 120_000},
                            "model_context_window": 200_000,
                        },
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "Get-Content -Path skills\\token_optimizer\\SKILL.md",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": (
                            "# Token Optimizer\n"
                            "Docs mention runtime_token_optimization and estimated_tokens_saved."
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}

        self.assertEqual(rows["token-optimizer"]["status"], "inspected")
        self.assertEqual(rows["token-optimizer"]["acceptance"]["status"], "missing_application")
        self.assertTrue(
            any(
                issue["skill"] == "token-optimizer"
                and issue["status"] == "inspected"
                for issue in audit.issues
            )
        )

    def test_applied_memory_harness_requires_scope_and_record_outputs(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": (
                            "persistent memory is needed, and memory-state-harness was used, "
                            "but no output artifact was produced."
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}

        self.assertTrue(rows["memory-state-harness"]["required"])
        self.assertEqual(rows["memory-state-harness"]["status"], "applied")
        self.assertEqual(rows["memory-state-harness"]["acceptance"]["status"], "missing_outputs")
        self.assertIn("memory_scope", rows["memory-state-harness"]["acceptance"]["missing_outputs"])
        self.assertTrue(
            any(
                issue["skill"] == "memory-state-harness"
                and issue["status"] == "missing_outputs"
                for issue in audit.issues
            )
        )

    def test_summary_aggregates_issues_by_skill(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 80_000},
                            "last_token_usage": {"input_tokens": 120_000},
                            "model_context_window": 200_000,
                        },
                    },
                }
            ]
        )

        summary = summarize_session_skill_audits([path])

        self.assertEqual(summary["session_count"], 1)
        self.assertGreater(summary["aggregate"]["issue_count"], 0)
        self.assertIn("token-optimizer", summary["aggregate"]["issues_by_skill"])

    def test_postmortem_guard_failures_are_skill_audit_issues(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "thread_goal_updated",
                        "goal": {
                            "objective": "Build complete app",
                            "status": "active",
                        },
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": "Done and verified.",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "goal-state-harness"
                and issue["status"] == "blocked"
                for issue in audit.issues
            )
        )

    def test_user_stop_guard_failure_is_p0_skill_audit_issue(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "thread_goal_updated",
                        "goal": {"objective": "Build complete app", "status": "active"},
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "goal 멈추라고",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "apply_patch",
                        "arguments": "*** Begin Patch\n*** End Patch",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "goal-state-harness"
                and issue["severity"] == "P0"
                and "user stop request" in issue["reason"]
                for issue in audit.issues
            )
        )

    def test_assistant_stop_guard_failure_is_p0_skill_audit_issue(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "thread_goal_updated",
                        "goal": {"objective": "Build complete app", "status": "active"},
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": "\uc791\uc5c5 \uc911\ub2e8\ud569\ub2c8\ub2e4. \uc784\uc2dc \ud30c\uc77c\ub9cc \uc788\uc2b5\ub2c8\ub2e4.",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "goal-state-harness"
                and issue["severity"] == "P0"
                and "without terminal GoalState evidence" in issue["reason"]
                for issue in audit.issues
            )
        )

    def test_unsolicited_archive_directive_is_p0_skill_audit_issue(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": (
                            "\uc911\ub2e8\ud558\uace0 \uc885\ub8cc\ud569\ub2c8\ub2e4.\n"
                            "::archive{reason=\"User requested to end conversation\"}"
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertEqual(audit.postmortem["archive_guard"]["status"], "blocked")
        self.assertTrue(
            any(
                issue["skill"] == "workflow-usability-harness"
                and issue["severity"] == "P0"
                and "::archive" in issue["reason"]
                for issue in audit.issues
            )
        )

    def test_subagent_shallow_brainstorm_and_relative_target_substitution_are_flagged(self):
        target = "C:\\Users\\KONEIT\\Desktop\\Jang\\SKillsTest\\RetestAutoRoute_20260604_D"
        front_door_output = {
            "front_door_status": "ok",
            "selected_not_executed_skills": ["brainstorming-harness", "host-agent-orchestration"],
            "recommended_skills": ["always-on-front-door", "brainstorming-harness", "host-agent-orchestration"],
            "execution_gate": {"status": "blocked_until_brainstorming_handoff", "can_execute": False},
            "required_next_actions": [
                "When running inside a host subagent, record nested_subagents_available and subagent_strategy=dispatch|single-controller|review-only|blocked before implementation."
            ],
        }
        path = self.write_subagent_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": f"{target} \ud3f4\ub354\uc5d0\uc11c \uc7ac\uace0 \uc785\ucd9c\uace0 \uad00\ub9ac \ub300\uc2dc\ubcf4\ub4dc \uac1c\ubc1c\ud574\uc918.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": json.dumps(front_door_output),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": (
                            "\uc7ac\uace0 \uc785\ucd9c\uace0 \ub300\uc2dc\ubcf4\ub4dc\ub294 \uc0c1\ud488 \ub2f4\ub2f9\uc790\uc640 "
                            "\uad00\ub9ac\uc790\uac00 \uc785\uace0/\ucd9c\uace0\ub97c \ubcf4\ub294 \ubc29\ud5a5\uc785\ub2c8\ub2e4.\n"
                            "1. \ub2e8\uc21c \uc6d0\uc7a5\ud615\n2. \uc704\uce58 \uad00\ub9ac\ud615\n3. LOT \uad00\ub9ac\ud615\n"
                            "\ucd94\ucc9c\uc740 1\ubc88\uc785\ub2c8\ub2e4. 1\ubc88\uc73c\ub85c \uc9c4\ud589\ud574\ub3c4 \ub420\uae4c\uc694?"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "1\ubc88\uc73c\ub85c \uc9c4\ud589\ud574.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "apply_patch",
                        "arguments": "*** Begin Patch\n*** Add File: RetestAutoRoute_20260604_D/index.html\n+<html></html>\n*** End Patch",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "brainstorming-harness"
                and issue["status"] == "shallow_visible_brainstorming"
                and "required_records_data" in issue.get("missing_markers", [])
                for issue in audit.issues
            )
        )
        self.assertTrue(
            any(
                issue["skill"] == "guard-policy-harness"
                and issue["status"] == "target_path_substitution"
                and issue["severity"] == "P0"
                for issue in audit.issues
            )
        )
        self.assertTrue(
            any(
                issue["skill"] == "host-agent-orchestration"
                and issue["status"] == "missing_subagent_strategy"
                for issue in audit.issues
            )
        )

    def test_resume_guard_failure_is_skill_audit_issue(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 80_000},
                            "last_token_usage": {"input_tokens": 120_000},
                            "model_context_window": 200_000,
                        },
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "resume and continue the implementation",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "apply_patch",
                        "arguments": "*** Begin Patch\n*** End Patch",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertEqual(audit.postmortem["resume_guard"]["status"], "blocked")
        self.assertTrue(
            any(
                issue["skill"] == "workflow-usability-harness"
                and issue["status"] == "blocked"
                and "resume/restart" in issue["reason"]
                for issue in audit.issues
            )
        )

    def test_timed_out_subagent_flags_host_role_and_subagent_skills(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "create_agent",
                        "arguments": "{\"prompt\":\"implement task\"}",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": "{\"timed_out\": true}",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertIn(("host-agent-orchestration", "blocked"), issues)
        self.assertIn(("role-execution-audit-harness", "blocked"), issues)
        self.assertIn(("subagent-review-pipeline", "blocked"), issues)

    def test_korean_product_request_without_brainstorm_handoff_is_flagged(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": r"C:\work\OpsProduct 폴더에 운영지원 제품 개발해줘.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "python C:\\kh\\skills\\always_on_front_door\\scripts\\front_door.py "
                            "--prompt \"운영지원 제품 개발해줘\" --summary"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "request_user_input",
                        "arguments": "{\"questions\":[{\"question\":\"제품 방향은?\"}]}",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "1번으로 진행해.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "apply_patch",
                        "arguments": "*** Begin Patch\n*** Add File: index.html\n+<h1>Ops</h1>\n*** End Patch",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}

        self.assertTrue(rows["brainstorming-harness"]["required"])
        self.assertTrue(
            any(
                issue["skill"] == "brainstorming-harness"
                and issue["status"] == "missing_brainstorm_handoff"
                and issue["severity"] == "P1"
                for issue in audit.issues
            )
        )

    def test_subagent_implementation_without_strategy_rationale_is_flagged(self):
        path = self.write_subagent_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Build an operations support product in this folder.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "python C:\\kh\\skills\\always_on_front_door\\scripts\\front_door.py "
                            "--prompt \"Build an operations support product\" --summary"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "apply_patch",
                        "arguments": "*** Begin Patch\n*** Add File: app.js\n+console.log('ok')\n*** End Patch",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "host-agent-orchestration"
                and issue["status"] == "missing_subagent_strategy"
                for issue in audit.issues
            )
        )
        self.assertTrue(
            any(
                issue["skill"] == "subagent-review-pipeline"
                and issue["status"] == "missing_subagent_strategy"
                for issue in audit.issues
            )
        )

    def test_subagent_single_controller_rationale_satisfies_strategy_audit(self):
        path = self.write_subagent_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Build an operations support product in this folder.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": (
                            "host-agent-orchestration resolved host_runtime=codex-subagent; "
                            "subagent_strategy=single-controller because nested subagents are unavailable "
                            "and the write set is shared."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "apply_patch",
                        "arguments": "*** Begin Patch\n*** Add File: app.js\n+console.log('ok')\n*** End Patch",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertFalse(
            any(
                issue["status"] == "missing_subagent_strategy"
                for issue in audit.issues
            )
        )

    def test_developer_skill_inventory_does_not_count_as_observed_usage(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "developer",
                        "content": (
                            "Available skills: token-optimizer, goal-state-harness, "
                            "parallel-orchestration-harness, subagent-review-pipeline."
                        ),
                    },
                }
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}

        self.assertEqual(audit.coverage["observed_skills"], 0)
        self.assertEqual(rows["token-optimizer"]["status"], "absent")
        self.assertEqual(rows["goal-state-harness"]["status"], "absent")
        self.assertEqual(rows["parallel-orchestration-harness"]["status"], "absent")

    def test_skill_doc_and_catalog_outputs_do_not_count_as_runtime_usage(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": (
                            "Exit code: 0\n"
                            "---\n"
                            "name: parallel-orchestration-harness\n"
                            "description: Use when a task needs bounded parallel worker execution.\n"
                            "---\n"
                            "# Parallel Orchestration Harness\n"
                            "## Support files\n"
                            "## UAF implementation targets\n"
                            "- src.orchestration.role_orchestrator\n"
                            "parallel_wave_count fan-in fan-out"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": (
                            "adapter_contract_harness command_output_harness "
                            "parallel_orchestration_harness request_complexity_router "
                            "subagent_review_pipeline workflow_usability_harness"
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}

        self.assertEqual(rows["parallel-orchestration-harness"]["status"], "inspected")
        self.assertEqual(rows["subagent-review-pipeline"]["status"], "inspected")
        self.assertEqual(audit.coverage["runtime_applied_skills"], 0)

    def test_stale_kh_cache_skill_read_failure_is_audit_issue(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": (
                            "Exit code: 1\n"
                            "Get-Content : 'C:\\Users\\KONEIT\\.codex\\plugins\\cache\\"
                            "kh-uaf-marketplace\\kh-uaf\\2.9.25\\skills\\parallel_orchestration_harness\\SKILL.md' "
                            "경로는 존재하지 않으므로 찾을 수 없습니다."
                        ),
                    },
                }
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "skill-catalog"
                and issue["status"] == "stale_skill_cache_path"
                and issue["severity"] == "P1"
                for issue in audit.issues
            )
        )

    def test_kh_plugin_request_requires_front_door_before_source_work(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Use the KH plugin for this source analysis.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "Get-ChildItem -Recurse -Filter *.cs",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "always-on-front-door"
                and issue["status"] == "missing_front_door"
                and issue["severity"] == "P1"
                for issue in audit.issues
            )
        )

    def test_korean_kh_request_requires_front_door_before_source_work(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "이 폴더 작업은 KH 플러그인을 사용해서 처리해줘.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "Get-Content -Path .\\Program.cs -TotalCount 120",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "always-on-front-door"
                and issue["status"] == "missing_front_door"
                and issue["severity"] == "P1"
                for issue in audit.issues
            )
        )

    def test_ordinary_non_trivial_request_requires_automatic_intake_before_source_work(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Build a small HTML todo tool in this folder and verify it.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "Get-ChildItem -Recurse -Filter *.html",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "always-on-front-door"
                and issue["status"] == "missing_front_door"
                and issue["severity"] == "P1"
                for issue in audit.issues
            )
        )

    def test_kh_active_directive_carries_to_later_ordinary_work(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "앞으로 KH 스킬,하네스를 적극적으로 활용해서 작업해줘.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "간단한 월별 KPI 대시보드를 만들어줘.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "Get-ChildItem -Recurse -Filter *.html",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "always-on-front-door"
                and issue["status"] == "missing_front_door"
                and issue["trigger_kind"] == "kh_active_directive"
                and issue["kh_active_directive"]
                for issue in audit.issues
            )
        )

    def test_kh_active_directive_detects_real_korean_usage_phrase(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": (
                            "\uc55e\uc73c\ub85c \uc774 \ub300\ud654\uc5d0\uc11c\ub294 KH "
                            "\uc2a4\ud0ac/\ud558\ub124\uc2a4\ub97c \uc801\uadf9\uc801\uc73c\ub85c "
                            "\uc368\uc11c \uc791\uc5c5\ud574\uc918."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": (
                            "C:\\Users\\KONEIT\\Desktop\\Jang\\SKillsTest\\Carryover "
                            "\ud3f4\ub354\uc5d0 \uc791\uc740 KPI \ub300\uc2dc\ubcf4\ub4dc\ub97c "
                            "\ub9cc\ub4e4\uc5b4\uc918."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "Test-Path -LiteralPath 'C:\\Users\\KONEIT\\Desktop\\Jang\\SKillsTest\\Carryover'",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "always-on-front-door"
                and issue["status"] == "missing_front_door"
                and issue["trigger_kind"] == "kh_active_directive"
                and issue["kh_active_directive"]
                for issue in audit.issues
            )
        )

    def test_kh_active_directive_passes_when_later_front_door_runs_first(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "앞으로 KH 스킬,하네스를 적극적으로 활용해서 작업해줘.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "간단한 월별 KPI 대시보드를 만들어줘.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "python -m src.orchestration.kh_front_door "
                            "--prompt \"간단한 월별 KPI 대시보드를 만들어줘.\" --summary"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "Get-ChildItem -Recurse -Filter *.html",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertFalse(
            any(
                issue["skill"] == "always-on-front-door"
                and issue["status"] == "missing_front_door"
                and issue.get("trigger_kind") == "kh_active_directive"
                for issue in audit.issues
            )
        )

    def test_skill_catalog_or_doc_read_does_not_satisfy_front_door_order(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Use the KH plugin for this source analysis.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "python -m src.skills.uaf_skill_catalog --list",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": (
                            "---\n"
                            "name: always-on-front-door\n"
                            "description: Use when any non-trivial request should be handled first.\n"
                            "---\n"
                            "# Always On Front Door\n"
                            "Required outputs include front_door_status and runtime_applied_skills."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": (
                            "plugin_composition selected KH as controller, "
                            "request_complexity classification=medium, "
                            "skill_application bundle recorded considered_not_needed entries."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "Get-ChildItem -Recurse -Filter *.cs",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "always-on-front-door"
                and issue["status"] == "missing_front_door"
                for issue in audit.issues
            )
        )

    def test_non_bootstrap_kh_skill_read_before_front_door_is_a_miss(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Build a small static KPI dashboard and verify it.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "Get-Content -Path 'C:\\Users\\KONEIT\\.codex\\plugins\\cache\\"
                            "kh-uaf-marketplace\\kh-uaf\\2.9.34\\skills\\qa_gate_harness\\SKILL.md'"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "python -m src.orchestration.kh_front_door "
                            "--prompt \"Build a small static KPI dashboard and verify it.\" --summary"
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "always-on-front-door"
                and issue["status"] == "missing_front_door"
                and "qa_gate_harness" in issue["first_work"]
                for issue in audit.issues
            )
        )

    def test_kh_plugin_request_passes_when_front_door_runs_first(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Use the KH plugin for this source analysis.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "python -m src.orchestration.kh_front_door "
                            "--prompt \"Use the KH plugin for this source analysis.\" --summary"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": (
                            "plugin_composition selected KH as controller, "
                            "request_complexity classification=medium, "
                            "skill_application bundle recorded considered_not_needed entries."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "Get-ChildItem -Recurse -Filter *.cs",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertFalse(
            any(
                issue["skill"] == "always-on-front-door"
                and issue["status"] == "missing_front_door"
                for issue in audit.issues
            )
        )

    def test_browser_storage_direction_does_not_require_qa_gate(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": (
                            "C:\\work\\InventoryDirection 폴더에서 재고 입출고 관리 "
                            "대시보드 개발해줘."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "python -B -m src.orchestration.kh_front_door "
                            "--prompt \"재고 입출고 관리 대시보드 개발해줘.\" --summary"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": (
                            "추천 방향은 정적 로컬 대시보드입니다. 데이터는 우선 "
                            "브라우저 localStorage에 저장하고 CSV 내보내기를 넣는 방식이 "
                            "가장 빠릅니다. 이 방향으로 진행해도 될까요?"
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertFalse(
            any(
                issue["skill"] == "qa-gate-harness"
                and "browser or local app QA appeared" in issue["reason"]
                for issue in audit.issues
            )
        )

    def test_browser_verification_still_requires_qa_gate(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Build a dashboard and verify it in the browser.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "python -B -m src.orchestration.kh_front_door "
                            "--prompt \"Build a dashboard and verify it in the browser.\" --summary"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "I opened the browser and verified the localhost dashboard screen.",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}

        self.assertTrue(rows["qa-gate-harness"]["required"])

    def test_kh_front_door_command_counts_as_front_door_evidence(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Use the KH plugin for this source analysis.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "python -m src.orchestration.kh_front_door "
                            "--prompt \"Use the KH plugin for this source analysis.\" --summary"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "Get-ChildItem -Recurse -Filter *.cs",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertFalse(
            any(
                issue["skill"] == "always-on-front-door"
                and issue["status"] == "missing_front_door"
                for issue in audit.issues
            )
        )
        self.assertIn("runtime_applied_skills", audit.coverage)

    def test_skill_local_front_door_wrapper_counts_as_front_door_evidence(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Build an operations support product in this folder.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "python C:\\kh\\skills\\always_on_front_door\\scripts\\front_door.py "
                            "--prompt \"Build an operations support product in this folder.\" --summary"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "Get-ChildItem -Path .",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertFalse(
            any(
                issue["skill"] == "always-on-front-door"
                and issue["status"] == "missing_front_door"
                for issue in audit.issues
            )
        )

    def test_always_on_skill_read_does_not_count_as_front_door_runtime(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Build an operations support product in this folder.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "Get-Content C:\\kh\\skills\\always_on_front_door\\SKILL.md"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "Get-ChildItem -Path C:\\work\\new-product",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "python C:\\kh\\skills\\always_on_front_door\\scripts\\front_door.py "
                            "--prompt \"Build an operations support product in this folder.\" --summary"
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "always-on-front-door"
                and issue["status"] == "missing_front_door"
                for issue in audit.issues
            )
        )

    def test_memory_quick_pass_batched_with_always_on_read_is_a_front_door_miss(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": (
                            "C:\\Users\\KONEIT\\Desktop\\Jang\\SKillsTest\\BlindProductRequest "
                            "folder needs an operations support product built."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "Get-Content -Path 'C:\\Users\\KONEIT\\.codex\\plugins\\cache\\"
                            "kh-uaf-marketplace\\kh-uaf\\2.9.40\\skills\\always_on_front_door\\SKILL.md'"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "Select-String -Path 'C:\\Users\\KONEIT\\.codex\\memories\\MEMORY.md' "
                            "-Pattern 'SKillsTest|KH|BlindProductRequest'"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "python C:\\Users\\KONEIT\\.codex\\plugins\\cache\\kh-uaf-marketplace\\"
                            "kh-uaf\\2.9.40\\skills\\always_on_front_door\\scripts\\front_door.py "
                            "--prompt \"operations support product\" --summary"
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "always-on-front-door"
                and issue["status"] == "missing_front_door"
                and "memory.md" in issue["first_work"].lower()
                for issue in audit.issues
            )
        )

    def test_sibling_run_read_is_cross_scope_context_leak(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": (
                            r"C:\Users\KONEIT\Desktop\Jang\SKillsTest\BrainstormAutoRoute_20260601_F "
                            "folder needs independent brainstorming."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "python -m src.orchestration.kh_front_door "
                            "--prompt \"independent brainstorming\" --summary"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            r"rg -n ""추천|리스크"" "
                            r"'C:\Users\KONEIT\Desktop\Jang\SKillsTest\BrainstormAutoRoute_20260601_E'"
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "guard-policy-harness"
                and issue["status"] == "cross_scope_context_leak"
                and "BrainstormAutoRoute_20260601_E" in " ".join(issue.get("samples", []))
                for issue in audit.issues
            )
        )

    def test_exact_target_read_is_not_cross_scope_context_leak(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": (
                            r"C:\Users\KONEIT\Desktop\Jang\SKillsTest\BrainstormAutoRoute_20260601_F "
                            "folder needs independent brainstorming."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "python -m src.orchestration.kh_front_door "
                            "--prompt \"independent brainstorming\" --summary"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            r"Get-ChildItem -LiteralPath "
                            r"'C:\Users\KONEIT\Desktop\Jang\SKillsTest\BrainstormAutoRoute_20260601_F'"
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertFalse(
            any(
                issue["skill"] == "guard-policy-harness"
                and issue["status"] == "cross_scope_context_leak"
                for issue in audit.issues
            )
        )

    def test_kh_front_door_output_from_plugin_cache_counts_as_runtime_status_split(self):
        front_door_output = {
            "front_door_status": "ok",
            "classification": {"complexity": "heavy", "domain": "software"},
            "plugin_route": {"route": "single", "controller": "kh"},
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["verification-before-completion-harness"],
            "skill_status_summary": {
                "always-on-front-door": {"status": "applied", "application_mode": "runtime"},
                "automatic-intake-harness": {"status": "applied", "application_mode": "runtime"},
                "plugin-composition-policy": {"status": "applied", "application_mode": "runtime"},
                "request-complexity-router": {"status": "applied", "application_mode": "runtime"},
                "skill-catalog": {"status": "applied", "application_mode": "runtime"},
            },
            "skill_source": {
                "skills_dir": r"C:\Users\KONEIT\.codex\plugins\cache\kh-uaf-marketplace\kh-uaf\2.9.30\skills"
            },
        }
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": r"C:\work\app 폴더에 정적 대시보드를 만들고 검증해줘.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": json.dumps(front_door_output),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}

        self.assertEqual(rows["always-on-front-door"]["acceptance"]["status"], "passed")
        self.assertEqual(rows["automatic-intake-harness"]["acceptance"]["status"], "passed")
        self.assertIn("plugin-composition-policy", audit.coverage["runtime_applied_skill_names"])
        self.assertIn("request-complexity-router", audit.coverage["runtime_applied_skill_names"])
        self.assertIn("skill-catalog", audit.coverage["runtime_applied_skill_names"])
        self.assertFalse(
            any(
                issue["skill"] in {"always-on-front-door", "automatic-intake-harness"}
                and issue["status"] == "missing_outputs"
                for issue in audit.issues
            )
        )


if __name__ == "__main__":
    unittest.main()
