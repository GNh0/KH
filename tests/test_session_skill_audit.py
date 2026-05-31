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

    def test_audit_covers_full_kh_skill_catalog_and_flags_required_omissions(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 80_000},
                            "last_token_usage": {"input_tokens": 20_000},
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

        self.assertEqual(audit.total_skills, 38)
        self.assertEqual(audit.coverage["total_skills"], 38)
        self.assertTrue(rows["token-optimizer"]["required"])
        self.assertTrue(rows["goal-state-harness"]["required"])
        self.assertIn("token-optimizer", audit.coverage["required_missing_skill_names"])
        self.assertTrue(any(issue["skill"] == "token-optimizer" for issue in audit.issues))
        self.assertTrue(any(issue["status"] == "blocked" for issue in audit.issues))

    def test_audit_counts_runtime_token_memory_and_workflow_evidence_as_applied(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 80_000},
                            "last_token_usage": {"input_tokens": 20_000},
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
                            "last_token_usage": {"input_tokens": 20_000},
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
                            "last_token_usage": {"input_tokens": 20_000},
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

    def test_resume_guard_failure_is_skill_audit_issue(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 80_000},
                            "last_token_usage": {"input_tokens": 30_000},
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


if __name__ == "__main__":
    unittest.main()
