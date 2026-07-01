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

        self.assertEqual(audit.total_skills, 41)
        self.assertEqual(audit.coverage["total_skills"], 41)
        self.assertTrue(rows["token-optimizer"]["required"])
        self.assertEqual(rows["token-optimizer"]["token_optimizer_status"], "blocked")
        self.assertIn("no runtime optimizer", rows["token-optimizer"]["token_optimizer_status_reason"])
        self.assertTrue(rows["goal-state-harness"]["required"])
        self.assertIn("token-optimizer", audit.coverage["required_missing_skill_names"])
        self.assertTrue(any(issue["skill"] == "token-optimizer" for issue in audit.issues))
        self.assertTrue(any(issue["status"] == "blocked" for issue in audit.issues))

    def test_subagent_without_token_optimizer_decision_is_blocked(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "multi_agent_v1.spawn_agent",
                        "arguments": json.dumps({"message": "blind user-style task"}),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": json.dumps({"agent_id": "agent-a"}),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "Subagent returned a useful answer, so this is done.",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertEqual(audit.postmortem["subagent_summary"]["spawned"], 1)
        self.assertTrue(rows["token-optimizer"]["required"])
        self.assertEqual(rows["token-optimizer"]["required_reason"], "subagent packets/transcripts require a token decision")
        self.assertEqual(rows["token-optimizer"]["token_optimizer_status"], "blocked")
        self.assertIn("subagent was spawned", rows["token-optimizer"]["token_optimizer_status_reason"])
        self.assertIn(("token-optimizer", "blocked"), issues)

    def test_subagent_considered_not_needed_requires_explicit_token_decision(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": json.dumps(
                            {
                                "token_optimizer_status": "considered_not_needed",
                                "token_optimizer_provider": "kh",
                                "not_used_reason": "Subagent packet and transcript stayed below the configured threshold.",
                                "decision_source": "subagent preflight",
                            }
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "multi_agent_v1.spawn_agent",
                        "arguments": json.dumps({"message": "blind user-style task"}),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": json.dumps({"agent_id": "agent-a"}),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertEqual(rows["token-optimizer"]["token_optimizer_status"], "considered_not_needed")
        self.assertNotIn(("token-optimizer", "blocked"), issues)

    def test_subagent_considered_not_needed_without_not_used_reason_is_blocked(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": json.dumps(
                            {
                                "token_optimizer_status": "considered_not_needed",
                                "token_optimizer_provider": "kh",
                                "decision_source": "subagent preflight",
                            }
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "multi_agent_v1.spawn_agent",
                        "arguments": json.dumps({"message": "blind user-style task"}),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": json.dumps({"agent_id": "agent-a"}),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertEqual(rows["token-optimizer"]["token_optimizer_status"], "blocked")
        self.assertIn(("token-optimizer", "blocked"), issues)

    def test_subagent_considered_not_needed_with_status_reason_only_is_blocked(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": json.dumps(
                            {
                                "token_optimizer_status": "considered_not_needed",
                                "token_optimizer_provider": "kh",
                                "token_optimizer_status_reason": "The packet is short.",
                                "decision_source": "subagent preflight",
                            }
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "multi_agent_v1.spawn_agent",
                        "arguments": json.dumps({"message": "blind user-style task"}),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": json.dumps({"agent_id": "agent-a"}),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertEqual(rows["token-optimizer"]["token_optimizer_status"], "blocked")
        self.assertIn(("token-optimizer", "blocked"), issues)

    def test_parallel_wrapper_subagent_tools_are_counted(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "multi_tool_use.parallel",
                        "arguments": json.dumps(
                            {
                                "tool_uses": [
                                    {
                                        "recipient_name": "multi_agent_v1.spawn_agent",
                                        "parameters": {"message": "blind user-style task"},
                                    },
                                    {
                                        "recipient_name": "multi_agent_v1.close_agent",
                                        "parameters": {"target": "agent-a"},
                                    },
                                ]
                            }
                        ),
                    },
                }
            ]
        )

        audit = analyze_session_skills(path)

        self.assertEqual(audit.postmortem["subagent_summary"]["spawned"], 1)
        self.assertEqual(audit.postmortem["subagent_summary"]["closed"], 1)

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

    def test_sql_output_before_host_local_sql_formatting_is_flagged_without_brainstorm_noise(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": (
                            "SELECT *\n"
                            "FROM BA011T\n"
                            "WHERE MAINCD = 'DZ010'\n\n"
                            "SELECT *\n"
                            "FROM BA011T\n"
                            "WHERE MAINCD = 'DZ011'\n\n"
                            "\uc774\ubbf8\uc9c0\ucc98\ub7fc \ub300\ubd84\ub958 \uc911\ubd84\ub958\ud574\uc11c "
                            "\uc21c\uc11c\ub85c \uc870\ud68c\ub418\ub3c4\ub85d \ud558\uace0\uc2f6\uac70\ub4e0?"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "```sql\nSELECT A.SUBCD\nFROM BA011T AS A\nWHERE A.MAINCD = 'DZ010';\n```",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertTrue(rows["sql-formatting-style-harness"]["required"])
        self.assertIn(("sql-formatting", "missing_before_sql_output"), issues)
        self.assertNotIn("brainstorming-harness", audit.coverage["required_missing_skill_names"])
        self.assertNotIn("host-agent-orchestration", audit.coverage["required_missing_skill_names"])
        self.assertNotIn("parallel-orchestration-harness", audit.coverage["required_missing_skill_names"])
        self.assertNotIn("subagent-review-pipeline", audit.coverage["required_missing_skill_names"])

    def test_front_door_json_sql_words_do_not_require_sql_style_harness(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "immediate_next_skills": ["brainstorming-harness"],
            "selected_not_executed_skills": ["brainstorming-harness"],
            "execution_gate": {
                "can_execute": False,
                "blocked_actions": [
                    "Get-Content",
                    "source_reads",
                    "implementation",
                    "analysis_output",
                    "verification",
                ],
                "reason": "brainstorming-harness was selected before execution.",
            },
        }
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": (
                            r"C:\Users\KONEIT\Desktop\Jang\SKillsTest\UpgradeBlind_20260630_B "
                            "\ud3f4\ub354\uc5d0 \uc2e0\uaddc \uc7ac\uace0 \uc785\ucd9c\uace0 \uad00\ub9ac "
                            "\ub300\uc2dc\ubcf4\ub4dc \uac1c\ubc1c\ud574\uc918."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {"type": "function_call_output", "output": json.dumps(front_door_output)},
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": (
                            "Before implementation, I have not inspected or modified target files.\n\n"
                            "**Objective/operator**\n"
                            "The inventory operator needs a dashboard for inbound, outbound, and on-hand stock.\n\n"
                            "**Workflow boundary**\n"
                            "The first workflow covers inbound registration, outbound registration, stock status, "
                            "and safety-stock alerts; ERP sync and approval workflow are non-goals.\n\n"
                            "**Success criteria / constraints**\n"
                            "The result should make shortages visible, keep transaction history traceable, and stay "
                            "local until storage requirements are approved.\n\n"
                            "**Operating options with tradeoffs**\n"
                            "1. Ledger-only option: fastest, but weak for warehouse/location control.\n"
                            "2. Location-stock option: better operating visibility, but needs warehouse data.\n"
                            "3. Lot/serial option: strongest traceability, but too heavy for a first cut.\n\n"
                            "**Required records/data**\n"
                            "Required data includes item code, item name, warehouse, quantity, transaction type, "
                            "transaction date, operator, reason, and safety stock.\n\n"
                            "**Recommendation**\n"
                            "I recommend choosing the location-stock option only if warehouse/location data is "
                            "actually available; otherwise start with ledger-only.\n\n"
                            "**Open questions**\n"
                            "Which stock level must be controlled first, and should returns or adjustments be in scope?\n\n"
                            "Please approve or confirm the direction before I implement."
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}

        self.assertFalse(rows["sql-formatting-style-harness"]["required"])
        self.assertNotIn("sql-formatting-style-harness", audit.coverage["required_missing_skill_names"])
        self.assertFalse(
            any(
                issue["skill"] == "brainstorming-harness"
                and issue["status"] == "immediate_next_skill_not_applied"
                for issue in audit.issues
            )
        )

    def test_thin_visible_brainstorming_is_flagged_even_if_it_has_options(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "immediate_next_skills": ["brainstorming-harness"],
            "selected_not_executed_skills": ["brainstorming-harness"],
            "execution_gate": {
                "can_execute": False,
                "reason": "brainstorming-harness was selected before execution.",
            },
        }
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": (
                            r"C:\Users\KONEIT\Desktop\Jang\SKillsTest\UpgradeBlind_20260630_B "
                            "folder needs a new inventory dashboard."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {"type": "function_call_output", "output": json.dumps(front_door_output)},
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": (
                            "I have not modified files yet.\n\n"
                            "Objective/operator: inventory operator dashboard.\n"
                            "Workflow boundary: inbound, outbound, and stock status.\n"
                            "Options:\n"
                            "1. Ledger-only.\n"
                            "2. Location stock.\n"
                            "Which option should I use?"
                        ),
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
            ),
            audit.issues,
        )
        self.assertTrue(
            any(
                issue["skill"] == "brainstorming-harness"
                and issue["status"] == "immediate_next_skill_not_applied"
                for issue in audit.issues
            ),
            audit.issues,
        )

    def test_korean_thin_visible_brainstorming_is_flagged(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "immediate_next_skills": ["brainstorming-harness"],
            "selected_not_executed_skills": ["brainstorming-harness"],
            "execution_gate": {
                "can_execute": False,
                "reason": "brainstorming-harness was selected before execution.",
            },
        }
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": (
                            r"C:\Users\KONEIT\Desktop\Jang\SKillsTest\UpgradeBlind_20260630_B "
                            "\ud3f4\ub354\uc5d0 \uc2e0\uaddc \uc7ac\uace0 \uc785\ucd9c\uace0 \uad00\ub9ac "
                            "\ub300\uc2dc\ubcf4\ub4dc \uac1c\ubc1c\ud574\uc918."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {"type": "function_call_output", "output": json.dumps(front_door_output)},
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": (
                            "\uad6c\ud604 \uc804\uc5d0 \ubc29\ud5a5\uc744 \uba3c\uc800 \uc815\ud558\uaca0\uc2b5\ub2c8\ub2e4.\n\n"
                            "\ubaa9\ud45c/\uc6b4\uc601\uc790: \uc7ac\uace0 \ub2f4\ub2f9\uc790\uc6a9 \ub300\uc2dc\ubcf4\ub4dc.\n"
                            "\uc5c5\ubb34 \ubc94\uc704: \uc785\uace0, \ucd9c\uace0, \ud604\uc7ac\uace0 \uc870\ud68c.\n"
                            "\uc120\ud0dd\uc9c0:\n"
                            "1. \ub2e8\uc21c \uc218\ubd88\uc7a5\ud615\n"
                            "2. \ucc3d\uace0/\uc704\uce58 \uad00\ub9ac\ud615\n\n"
                            "\uc5b4\ub290 \ubc29\ud5a5\uc73c\ub85c \uac08\uae4c\uc694?"
                        ),
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
            ),
            audit.issues,
        )
        self.assertTrue(
            any(
                issue["skill"] == "brainstorming-harness"
                and issue["status"] == "immediate_next_skill_not_applied"
                for issue in audit.issues
            ),
            audit.issues,
        )

    def test_stored_procedure_generation_before_sql_formatting_is_flagged(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": (
                            "Begin Tran\n"
                            "   EXEC UP_SYS_SYSTEMCHECKLIST_SAVE @p_WorkType = 'LIST', @XML_DATA = '<ROOT />'\n"
                            "Rollback\n\n"
                            "이 저장 프로시저 하나 만들어줄래? KH SAVE프로시저 양식으로 하고 "
                            "DEV000T에 저장되면 되고 IF EXISTS 해서 RAISERROR 발생하게 해줘."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": (
                            "```sql\n"
                            "CREATE PROCEDURE [dbo].[UP_SYS_SYSTEMCHECKLIST_SAVE]\n"
                            "    @WORKTYPE VARCHAR(20) = NULL\n"
                            "AS\n"
                            "BEGIN\n"
                            "    INSERT INTO @TMP (GBN, ID, QCCODE)\n"
                            "    SELECT A.GBN, A.ID, A.QCCODE\n"
                            "    FROM OPENXML(@DOC_ID, '/ROOT/DataTable', 1) A;\n"
                            "END\n"
                            "```"
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertTrue(rows["sql-formatting-style-harness"]["required"])
        self.assertIn(("sql-formatting", "missing_before_sql_output"), issues)

    def test_sql_output_scope_does_not_require_development_orchestration_noise(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": (
                            "SELECT * FROM BA011T WHERE MAINCD = 'DZ010'\n"
                            "\uc774\ubbf8\uc9c0\ucc98\ub7fc \uc21c\uc11c\ub85c "
                            "\uc870\ud68c\ub418\ub3c4\ub85d \ud558\uace0\uc2f6\uac70\ub4e0?"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "A reviewer would say this is verified with fixes.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "```sql\nSELECT A.SUBCD\nFROM BA011T A\nORDER BY A.SUBCD;\n```",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertIn("sql-formatting-style-harness", audit.coverage["required_missing_skill_names"])
        self.assertNotIn("quality-gates-harness", audit.coverage["required_missing_skill_names"])
        self.assertNotIn("review-gate-harness", audit.coverage["required_missing_skill_names"])
        self.assertNotIn("host-agent-orchestration", audit.coverage["required_missing_skill_names"])
        self.assertNotIn("parallel-orchestration-harness", audit.coverage["required_missing_skill_names"])

    def test_sql_formatting_mention_only_does_not_suppress_missing_before_sql_output(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": (
                            "SELECT * FROM BA011T WHERE MAINCD = 'DZ010'\n"
                            "\uc815\ub9ac\ud574\uc11c \ub2ec\ub77c"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "I should use sql-formatting first.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "```sql\nSELECT A.SUBCD\nFROM BA011T A;\n```",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertIn(("sql-formatting", "missing_before_sql_output"), issues)

    def test_sql_formatting_front_door_route_suppresses_missing_before_sql_output(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": [],
            "skill_status_summary": {},
            "plugin_route": {
                "route": "single",
                "controller": {
                    "provider_id": "sql-formatting",
                    "capability": "sql_formatting",
                },
            },
        }
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": (
                            "SELECT * FROM BA011T WHERE MAINCD = 'DZ010'\n"
                            "\uc815\ub9ac\ud574\uc11c \ub2ec\ub77c"
                        ),
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
                        "type": "message",
                        "role": "assistant",
                        "content": "```sql\nSELECT A.SUBCD\nFROM BA011T A;\n```",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertNotIn(("sql-formatting", "missing_before_sql_output"), issues)
        self.assertIn(("sql-formatting-style-harness", "missing_sql_formatting_style_verifier"), issues)
        self.assertEqual(
            rows["sql-formatting-style-harness"]["acceptance"]["status"],
            "missing_application",
        )


    def test_sql_formatting_route_passes_when_style_verifier_runs_before_output(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["sql-formatting-style-harness"],
            "plugin_route": {
                "route": "single",
                "controller": {
                    "provider_id": "sql-formatting",
                    "capability": "sql_formatting",
                },
            },
        }
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "SELECT * FROM BA011T WHERE MAINCD = 'DZ010'\nformat this SQL",
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
                        "type": "function_call_output",
                        "output": json.dumps(
                            {
                                "skill": "sql-formatting-style-harness",
                                "status": "passed",
                                "source": "src.skills.sql_formatting_style.verify_sql_formatting_style",
                                "mechanical_checks": {"literal_preservation": "passed"},
                                "style_contract_source": "host-local sql-formatting",
                                "token_optimizer_status": "passthrough",
                            }
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "```sql\nSELECT A.SUBCD\nFROM BA011T A;\n```",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertNotIn(("sql-formatting", "missing_before_sql_output"), issues)
        self.assertNotIn(("sql-formatting-style-harness", "missing_sql_formatting_style_verifier"), issues)

    def test_sql_formatting_style_verifier_call_without_output_does_not_pass(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["sql-formatting-style-harness"],
            "plugin_route": {
                "route": "single",
                "controller": {
                    "provider_id": "sql-formatting",
                    "capability": "sql_formatting",
                },
            },
        }
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "SELECT * FROM BA011T WHERE MAINCD = 'DZ010'\nformat this SQL",
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
                        "type": "function_call",
                        "name": "verify_sql_formatting_style",
                        "arguments": json.dumps({"skill": "sql-formatting-style-harness"}),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "```sql\nSELECT A.SUBCD\nFROM BA011T A;\n```",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertNotIn(("sql-formatting", "missing_before_sql_output"), issues)
        self.assertIn(("sql-formatting-style-harness", "missing_sql_formatting_style_verifier"), issues)
        self.assertEqual(
            rows["sql-formatting-style-harness"]["acceptance"]["status"],
            "missing_outputs",
        )
        self.assertIn(
            "sql_passthrough",
            rows["sql-formatting-style-harness"]["acceptance"]["missing_outputs"],
        )

    def test_sql_formatting_route_requires_style_verifier_before_db_write(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["sql-formatting-style-harness"],
            "plugin_route": {
                "route": "single",
                "controller": {
                    "provider_id": "sql-formatting",
                    "capability": "sql_formatting",
                },
            },
        }
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": (
                            "CREATE PROC [dbo].[UP_SYS_TEST_SAVE]\n"
                            "    @p_WorkType VARCHAR(20) = NULL\n"
                            "AS\n"
                            "BEGIN\n"
                            "    SELECT 1\n"
                            "END\n"
                            "정리해서 적용해줘"
                        ),
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
                        "type": "function_call",
                        "name": "mssql_run_sql_query",
                        "arguments": json.dumps(
                            {
                                "query": (
                                    "CREATE OR ALTER PROCEDURE [dbo].[UP_SYS_TEST_SAVE]\n"
                                    "    @p_WorkType VARCHAR(20) = NULL\n"
                                    "AS\n"
                                    "BEGIN\n"
                                    "    SELECT 1\n"
                                    "END\n"
                                )
                            }
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertIn(("sql-formatting-style-harness", "missing_sql_formatting_style_verifier"), issues)

    def test_failed_sql_formatting_style_verifier_before_output_is_flagged(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["sql-formatting-style-harness"],
            "plugin_route": {
                "route": "single",
                "controller": {
                    "provider_id": "sql-formatting",
                    "capability": "sql_formatting",
                },
            },
        }
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "SELECT * FROM BA011T WHERE MAINCD = 'DZ010'\nformat this SQL",
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
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": r"Get-Content C:\Users\KONEIT\.codex\skills\sql-formatting\SKILL.md",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": json.dumps(
                            {
                                "skill": "sql-formatting-style-harness",
                                "status": "failed",
                                "source": "src.skills.sql_formatting_style.verify_sql_formatting_style",
                                "mechanical_checks": {
                                    "status": "blocked",
                                    "style_issues": [{"code": "join_condition_indentation"}],
                                },
                                "style_contract_source": "host-local sql-formatting",
                            }
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "```sql\nSELECT A.SUBCD\nFROM BA011T A;\n```",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertIn(
            ("sql-formatting-style-harness", "sql_formatting_style_verifier_failed_before_output"),
            issues,
        )

    def test_sql_formatting_provider_snapshot_only_does_not_suppress_missing_before_sql_output(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": [],
            "skill_status_summary": {},
            "plugin_route": {
                "route": "single",
                "controller": {
                    "provider_id": "kh",
                    "capability": "workflow_control",
                },
            },
            "available_providers_snapshot": [
                {
                    "provider_id": "sql-formatting",
                    "capability": "sql_formatting",
                }
            ],
        }
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": (
                            "SELECT * FROM BA011T WHERE MAINCD = 'DZ010'\n"
                            "\uc815\ub9ac\ud574\uc11c \ub2ec\ub77c"
                        ),
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
                        "type": "message",
                        "role": "assistant",
                        "content": "```sql\nSELECT A.SUBCD\nFROM BA011T A;\n```",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertIn(("sql-formatting", "missing_before_sql_output"), issues)

    def test_direct_sql_formatting_uses_host_skill_without_front_door_overclassification(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": (
                            "<environment_context>\n"
                            "  <cwd>C:\\Users\\KONEIT\\Documents\\Codex</cwd>\n"
                            "  <shell>powershell</shell>\n"
                            "</environment_context>"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": (
                            "Below SQL should only be formatted; do not change logic.\n"
                            "IF EXISTS (SELECT 1 FROM DE000T A INNER JOIN @TMP B ON A.ID=B.ID AND A.QCCODE=B.QCCODE)\n"
                            "BEGIN RAISERROR('이미 확인완료된 프로그램입니다.', 16, 1); RETURN; END"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": r"Get-Content C:\Users\KONEIT\.codex\skills\sql-formatting\SKILL.md",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": (
                            "```sql\n"
                            "IF EXISTS (\n"
                            "             SELECT 1\n"
                            "             FROM DE000T A\n"
                            "                    INNER JOIN @TMP B\n"
                            "                            ON A.ID = B.ID\n"
                            "                            AND A.QCCODE = B.QCCODE\n"
                            "            )\n"
                            "BEGIN\n"
                            "    RAISERROR('이미 확인완료된 프로그램입니다.', 16, 1);\n"
                            "    RETURN;\n"
                            "END\n"
                            "```"
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertNotIn(("always-on-front-door", "missing_front_door"), issues)
        self.assertNotIn(("sql-formatting", "missing_before_sql_output"), issues)
        self.assertIn(("sql-formatting-style-harness", "missing_sql_formatting_style_verifier"), issues)

    def test_front_door_prompt_set_content_is_not_implementation_activity(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "$promptPath = Join-Path $env:TEMP \"kh-front-door-prompt.txt\"\n"
                            "Set-Content -LiteralPath $promptPath -Value @'\n"
                            "SELECT * FROM BA011T WHERE MAINCD = 'DZ010'\n"
                            "'@ -Encoding UTF8\n"
                            "python \"C:\\Users\\KONEIT\\.codex\\plugins\\cache\\kh-uaf-marketplace\\kh-uaf\\2.9.76\\skills\\always_on_front_door\\scripts\\front_door.py\" --prompt-file $promptPath --summary"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": json.dumps(
                            {
                                "front_door_status": "ok",
                                "runtime_applied_skills": [
                                    "always-on-front-door",
                                    "automatic-intake-harness",
                                    "plugin-composition-policy",
                                    "request-complexity-router",
                                    "skill-catalog",
                                ],
                                "selected_not_executed_skills": [],
                                "skill_status_summary": {},
                            }
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertNotIn("host-agent-orchestration", audit.coverage["required_missing_skill_names"])
        self.assertNotIn("parallel-orchestration-harness", audit.coverage["required_missing_skill_names"])
        self.assertNotIn("subagent-review-pipeline", audit.coverage["required_missing_skill_names"])
        self.assertNotIn("role-execution-audit-harness", audit.coverage["required_missing_skill_names"])

    def test_always_on_front_door_skill_read_delay_is_flagged(self):
        path = self.write_session(
            [
                {
                    "timestamp": "2026-06-11T01:24:31.000Z",
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "Get-Content -Path "
                            "'C:\\Users\\KONEIT\\.codex\\plugins\\cache\\kh-uaf-marketplace\\"
                            "kh-uaf\\2.9.67\\skills\\always_on_front_door\\SKILL.md'"
                        ),
                    },
                },
                {
                    "timestamp": "2026-06-11T01:26:45.000Z",
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "python C:\\Users\\KONEIT\\.codex\\plugins\\cache\\kh-uaf-marketplace\\"
                            "kh-uaf\\2.9.67\\skills\\always_on_front_door\\scripts\\front_door.py "
                            "--prompt-file prompt.txt --project C:\\work --host codex --summary"
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "always-on-front-door"
                and issue["status"] == "front_door_bootstrap_delay"
                and issue["elapsed_seconds"] == 134.0
                for issue in audit.issues
            )
        )

    def test_large_command_output_reasoning_delay_is_flagged(self):
        path = self.write_session(
            [
                {
                    "timestamp": "2026-06-11T01:30:25.000Z",
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": (
                            "Exit code: 124 Wall time: 10.3 seconds Total output lines: 1050 "
                            "Output: command timed out after 10284 milliseconds ..."
                        ),
                    },
                },
                {
                    "timestamp": "2026-06-11T01:32:10.000Z",
                    "type": "response_item",
                    "payload": {
                        "type": "agent_message",
                        "message": "The output was too long, now narrowing the search.",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "command-output-harness"
                and issue["status"] == "large_output_reasoning_delay"
                and issue["elapsed_seconds"] == 105.0
                for issue in audit.issues
            )
        )

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

    def test_memory_topic_mention_is_not_global_import_approval(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Review memory scope and global-memory boundary behavior.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "Select-String -Path 'C:\\Users\\KONEIT\\.codex\\memories\\MEMORY.md' -Pattern 'dashboard'",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "memory-state-harness"
                and issue["status"] == "global_memory_lookup_without_scope_approval"
                for issue in audit.issues
            )
        )

    def test_explicit_session_id_does_not_approve_global_memory_lookup(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "019e8078-4bde-7813-a1db-5025a3881511 session id logs read and analyze.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "Select-String -Path 'C:\\Users\\KONEIT\\.codex\\memories\\MEMORY.md' -Pattern '019e8078'",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertIn(("memory-state-harness", "global_memory_lookup_without_scope_approval"), issues)

    def test_explicit_session_id_allows_session_log_lookup_not_memory_index(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "019e8078-4bde-7813-a1db-5025a3881511 session id logs read and analyze.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "Select-String -Path 'C:\\Users\\KONEIT\\.codex\\sessions\\2026\\05\\27\\"
                            "rollout-2026-05-27T15-15-52-019e6813-407c-77e1-9975-a6246025d57e.jsonl' "
                            "-Pattern '019e8078'"
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertNotIn(("memory-state-harness", "global_memory_lookup_without_scope_approval"), issues)

    def test_memory_scope_decision_does_not_approve_global_memory_lookup(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": json.dumps(
                            {
                                "skill": "memory-state-harness",
                                "status": "applied",
                                "memory_scope_decision": {
                                    "scope": "project/chat",
                                    "host_global_codex_memory": "external",
                                },
                            }
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "Select-String -Path 'C:\\Users\\KONEIT\\.codex\\memories\\MEMORY.md' -Pattern 'MaxWidth'",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertIn(("memory-state-harness", "global_memory_lookup_without_scope_approval"), issues)

    def test_false_memory_import_approval_does_not_approve_global_memory_lookup(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": json.dumps(
                            {
                                "skill": "memory-state-harness",
                                "status": "applied",
                                "memory_import_approved": False,
                                "parent_memory_access_approved": False,
                            }
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "Select-String -Path 'C:\\Users\\KONEIT\\.codex\\memories\\MEMORY.md' -Pattern 'MaxWidth'",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertIn(("memory-state-harness", "global_memory_lookup_without_scope_approval"), issues)

    def test_plain_approval_marker_explanation_does_not_approve_global_memory_lookup(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "The field memory_import_approved must be true before using global memory.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "Select-String -Path 'C:\\Users\\KONEIT\\.codex\\memories\\MEMORY.md' -Pattern 'MaxWidth'",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertIn(("memory-state-harness", "global_memory_lookup_without_scope_approval"), issues)

    def test_later_global_memory_request_does_not_retroactively_approve_prior_lookup(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "Select-String -Path 'C:\\Users\\KONEIT\\.codex\\memories\\MEMORY.md' -Pattern 'MaxWidth'",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Now read and reuse my Codex MEMORY.md notes.",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertIn(("memory-state-harness", "global_memory_lookup_without_scope_approval"), issues)

    def test_prior_global_memory_request_allows_later_lookup(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Read and reuse my Codex MEMORY.md notes for this diagnosis.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "Select-String -Path 'C:\\Users\\KONEIT\\.codex\\memories\\MEMORY.md' -Pattern 'MaxWidth'",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertNotIn(("memory-state-harness", "global_memory_lookup_without_scope_approval"), issues)

    def test_global_memory_citation_requires_explicit_scope_request(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": (
                            "Done.\n\n"
                            "<oai-mem-citation>\n"
                            "<citation_entries>\n"
                            "MEMORY.md:51-81|note=[old PR300500 context]\n"
                            "</citation_entries>\n"
                            "<rollout_ids>\n"
                            "019efc9e-7b19-7573-8618-94d5829f5696\n"
                            "</rollout_ids>\n"
                            "</oai-mem-citation>"
                        ),
                    },
                }
            ]
        )

        audit = analyze_session_skills(path)
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertIn(("memory-state-harness", "global_memory_citation_without_scope_approval"), issues)

    def test_developer_memory_citation_example_is_not_global_memory_leak(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "developer",
                        "content": (
                            "Citation format example:\n"
                            "<oai-mem-citation>\n"
                            "<citation_entries>\n"
                            "MEMORY.md:51-81|note=[example only]\n"
                            "</citation_entries>\n"
                            "<rollout_ids>\n"
                            "</rollout_ids>\n"
                            "</oai-mem-citation>"
                        ),
                    },
                }
            ]
        )

        audit = analyze_session_skills(path)
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertNotIn(("memory-state-harness", "global_memory_citation_without_scope_approval"), issues)

    def test_passive_tool_output_memory_citation_example_is_not_global_memory_leak(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "Get-Content -Path 'C:\\kh\\skills\\memory_state_harness\\SKILL.md'",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": (
                            "Example only:\n"
                            "<oai-mem-citation>\n"
                            "<citation_entries>\n"
                            "MEMORY.md:51-81|note=[example only]\n"
                            "</citation_entries>\n"
                            "<rollout_ids>\n"
                            "</rollout_ids>\n"
                            "</oai-mem-citation>"
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertNotIn(("memory-state-harness", "global_memory_citation_without_scope_approval"), issues)

    def test_structured_memory_citation_requires_explicit_scope_request(self):
        path = self.write_session(
            [
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "agent_message",
                        "message": "Done.",
                        "phase": "final_answer",
                        "memory_citation": {
                            "entries": [
                                {
                                    "path": "MEMORY.md",
                                    "lineStart": 51,
                                    "lineEnd": 81,
                                    "note": "old PR300500 context",
                                }
                            ],
                            "rolloutIds": ["019efc9e-7b19-7573-8618-94d5829f5696"],
                        },
                    },
                }
            ]
        )

        audit = analyze_session_skills(path)
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertIn(("memory-state-harness", "global_memory_citation_without_scope_approval"), issues)

    def test_task_complete_memory_citation_requires_explicit_scope_request(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": (
                            "Done.\n\n"
                            "<oai-mem-citation>\n"
                            "<citation_entries>\n"
                            "MEMORY.md:51-81|note=[old PR300500 context]\n"
                            "</citation_entries>\n"
                            "<rollout_ids>\n"
                            "</rollout_ids>\n"
                            "</oai-mem-citation>"
                        ),
                    },
                }
            ]
        )

        audit = analyze_session_skills(path)
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertIn(("memory-state-harness", "global_memory_citation_without_scope_approval"), issues)

    def test_explicit_memory_md_request_allows_global_memory_citation(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Read and reuse my Codex MEMORY.md notes for this diagnosis.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": (
                            "Done.\n\n"
                            "<oai-mem-citation>\n"
                            "<citation_entries>\n"
                            "MEMORY.md:51-81|note=[requested memory]\n"
                            "</citation_entries>\n"
                            "<rollout_ids>\n"
                            "</rollout_ids>\n"
                            "</oai-mem-citation>"
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        issues = {(issue["skill"], issue["status"]) for issue in audit.issues}

        self.assertNotIn(("memory-state-harness", "global_memory_citation_without_scope_approval"), issues)

    def test_new_project_global_static_memory_shortcut_is_flagged_even_if_front_door_misroutes(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["token-optimizer", "workflow-usability-harness"],
            "execution_gate": {
                "status": "execution_allowed_after_selected_skill_setup",
                "can_execute": True,
                "blocked_actions": [],
            },
        }
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": (
                            r"C:\Users\KONEIT\Desktop\Jang\asdfasdf "
                            "\uc774 \uacbd\ub85c\uc5d0 \uc77c\uc815,\ud68c\uc758\ub85d\uc744 "
                            "\uc815\ub9ac\ud558\ub294 \uc6f9 \ud648\ud398\uc774\uc9c0\ub97c "
                            "\ud558\ub098 \ub9cc\ub4e4\uace0\uc2f6\ub124 pdf\ub97c \uc62c\ub9ac\uba74 "
                            "pdf\uc758 \ub0b4\uc6a9\uc774 \uadf8\ub300\ub85c \uc800\uc7a5\ub418\uace0 \ud558\ub294"
                        ),
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
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "Select-String -Path 'C:\\Users\\KONEIT\\.codex\\memories\\MEMORY.md' "
                            "-Pattern 'static-web-local-verification|index.html'"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "Get-Content -Path "
                            "'C:\\Users\\KONEIT\\.codex\\memories\\skills\\static-web-local-verification\\SKILL.md'"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "New-Item -ItemType Directory -Force -Path 'work\\asdfasdf-schedule-site'",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "memory-state-harness"
                and issue["status"] == "global_memory_shortcut_without_brainstorm_gate"
                and issue["severity"] == "P0"
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
                        "type": "function_call_output",
                        "output": json.dumps(
                            {
                                "runtime_token_optimization": {
                                    "status": "used",
                                    "source": "src.orchestration.runtime_token_optimizer.optimize_workflow_task_results",
                                    "estimated_tokens_saved": 2000,
                                    "actual_tokens_saved": 2000,
                                    "actual_usage_scope": "actual_optimizer_input_output_payload",
                                    "token_count_method": "deterministic_local_estimate_chars_div_4",
                                    "token_count_is_estimate": True,
                                    "billing_tokens_available": False,
                                },
                                "workflow_usability_auto": {
                                    "status": "applied",
                                    "handler": "apply_workflow_usability_runtime",
                                },
                                "memory": {
                                    "source": "src.orchestration.runtime_memory",
                                    "memory_scope": "project/chat",
                                    "memory_context": True,
                                    "memory_candidates_recorded": True,
                                },
                                "goal": {
                                    "source": "GoalState",
                                    "goal_ledger": "complete",
                                    "evidence_required": "complete",
                                    "progress": "progress.json",
                                },
                            },
                            ensure_ascii=False,
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

    def test_assistant_only_token_optimizer_claim_is_not_runtime_application(self):
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
                            "I used src.orchestration.runtime_token_optimizer.optimize_workflow_task_results "
                            "and produced runtime_token_optimization with estimated_tokens_saved=2000."
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}

        self.assertNotEqual(rows["token-optimizer"]["status"], "applied")
        self.assertEqual(rows["token-optimizer"]["acceptance"]["status"], "missing_application")
        self.assertIn("token-optimizer", audit.coverage["required_missing_skill_names"])

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

    def test_read_only_diff_output_with_token_telemetry_shape_does_not_count_as_runtime_application(self):
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
                        "arguments": json.dumps({"command": "git diff -- src/skills/token_optimizer.py"}),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": json.dumps(
                            {
                                "runtime_token_optimization": {
                                    "status": "used",
                                    "actual_tokens_saved": 2000,
                                    "actual_usage_scope": "actual_optimizer_input_output_payload",
                                    "billing_tokens_available": False,
                                }
                            }
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}

        self.assertNotEqual(rows["token-optimizer"]["status"], "applied")
        self.assertEqual(rows["token-optimizer"]["acceptance"]["status"], "missing_application")
        self.assertIn("token-optimizer", audit.coverage["required_missing_skill_names"])

    def test_plain_rg_output_with_token_telemetry_shape_does_not_count_as_runtime_application(self):
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
                        "arguments": json.dumps({"command": "rg \"actual_tokens_saved\" src"}),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": json.dumps(
                            {
                                "runtime_token_optimization": {
                                    "status": "used",
                                    "actual_tokens_saved": 2000,
                                    "actual_usage_scope": "actual_optimizer_input_output_payload",
                                    "billing_tokens_available": False,
                                }
                            }
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}

        self.assertNotEqual(rows["token-optimizer"]["status"], "applied")
        self.assertEqual(rows["token-optimizer"]["acceptance"]["status"], "missing_application")
        self.assertIn("token-optimizer", audit.coverage["required_missing_skill_names"])

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
        self.assertIn("skill_status_counts", summary["aggregate"])
        self.assertIn("verdict_counts", summary["aggregate"])

    def test_summary_exposes_user_readable_skill_usage_accounting(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 250_000},
                            "last_token_usage": {"input_tokens": 140_000},
                            "model_context_window": 200_000,
                        },
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "Large implementation continued after reading token-optimizer docs but no runtime token evidence was recorded.",
                    },
                },
            ]
        )

        summary = summarize_session_skill_audits([path])
        usage = summary["audits"][0]["usage_summary"]

        self.assertIn(usage["verdict"], {"failed_p0", "failed_p1", "issues_found"})
        self.assertIn("runtime_applied_skills", usage)
        self.assertIn("selected_not_executed_skills", usage)
        self.assertIn("inspected_only_skills", usage)
        self.assertIn("required_missing_or_unaccepted", usage)
        self.assertEqual(usage["token_optimizer"]["runtime_status"], "blocked")
        self.assertIn("no runtime optimizer", usage["token_optimizer"]["runtime_status_reason"])
        self.assertIn(
            "token-optimizer",
            {row["name"] for row in usage["required_missing_or_unaccepted"]},
        )

    def test_summary_dedupes_immediate_next_failures_with_occurrence_count(self):
        front_door = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["workflow-usability-harness"],
            "immediate_next_skills": ["workflow-usability-harness"],
            "skill_status_summary": {
                "workflow-usability-harness": {
                    "status": "pending_immediate_execution",
                }
            },
        }
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": json.dumps(front_door),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "functions.shell_command",
                        "arguments": json.dumps({"command": "Get-ChildItem"}),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": json.dumps(front_door),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "functions.shell_command",
                        "arguments": json.dumps({"command": "Get-ChildItem"}),
                    },
                },
            ]
        )

        usage = summarize_session_skill_audits([path])["audits"][0]["usage_summary"]
        misses = [
            item
            for item in usage["immediate_next_not_applied"]
            if item["skill"] == "workflow-usability-harness"
            and item["expected_order"] == ["workflow-usability-harness"]
        ]

        self.assertEqual(len(misses), 1)
        self.assertEqual(misses[0]["occurrences"], 2)

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

    def test_goal_required_task_complete_without_goal_state_is_p0_issue(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "request-complexity-router",
            ],
            "selected_not_executed_skills": ["goal-state-harness", "development-lifecycle-harness"],
            "skill_status_summary": {
                "goal-state-harness": {
                    "status": "selected",
                    "evidence_note": "Large work requires GoalState before completion.",
                }
            },
            "execution_gate": {"can_execute": True},
        }
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 70_000},
                            "last_token_usage": {"input_tokens": 120_000},
                            "model_context_window": 200_000,
                        },
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
                        "type": "message",
                        "role": "assistant",
                        "content": "I implemented the requested workflow and verified it.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": "Completed the implementation and pushed the changes.",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        rows = {row["name"]: row for row in audit.skills}

        self.assertTrue(rows["goal-state-harness"]["required"])
        self.assertNotEqual(rows["goal-state-harness"]["acceptance"]["status"], "passed")
        self.assertTrue(
            any(
                issue["skill"] == "goal-state-harness"
                and issue["status"] == "missing_terminal_goal_state"
                and issue["severity"] == "P0"
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

    def test_unilateral_brainstorm_decision_is_flagged_before_approval(self):
        target = "C:\\Users\\KONEIT\\Desktop\\Jang\\SKillsTest\\RetestAutoRoute_20260604_G"
        front_door_output = {
            "front_door_status": "ok",
            "selected_not_executed_skills": ["brainstorming-harness"],
            "recommended_skills": ["always-on-front-door", "brainstorming-harness"],
            "execution_gate": {"status": "blocked_until_brainstorming_handoff", "can_execute": False},
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
                            "\ubaa9\uc801/\uc6b4\uc601\uc790: \uc7ac\uace0 \ub2f4\ub2f9\uc790\uc6a9 \ub300\uc2dc\ubcf4\ub4dc.\n"
                            "\uc5c5\ubb34 \ubc94\uc704: \uc785\uace0, \ucd9c\uace0, \uc870\uc815, \uc548\uc804\uc7ac\uace0.\n"
                            "1. \ub2e8\uc21c \uc7a5\ubd80\ud615\n2. \uc704\uce58 \uc7ac\uace0\ud615\n3. LOT/\uc2dc\ub9ac\uc5bc\ud615\n"
                            "\ucd94\ucc9c: 2\ubc88 \uc704\uce58 \uc7ac\uace0\ud615\uc73c\ub85c \uac00\uaca0\uc2b5\ub2c8\ub2e4.\n"
                            "\ud544\uc694 \ub370\uc774\ud130: \ud488\ubaa9, \uc704\uce58, \uc218\ub7c9.\n"
                            "HTML + CSS + JavaScript\ub85c \uad6c\ud604\ud574\ub3c4 \ub420\uae4c\uc694?"
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "brainstorming-harness"
                and issue["status"] == "unilateral_brainstorm_decision"
                and "premature_implementation_stack_choice" in issue.get("matched_markers", [])
                for issue in audit.issues
            )
        )

    def test_execution_approval_question_is_flagged_before_brainstorm_choice(self):
        target = "C:\\Users\\KONEIT\\Desktop\\Jang\\SKillsTest\\RetestAutoRoute_20260604_H"
        front_door_output = {
            "front_door_status": "ok",
            "selected_not_executed_skills": ["brainstorming-harness"],
            "recommended_skills": ["always-on-front-door", "brainstorming-harness"],
            "execution_gate": {"status": "blocked_until_brainstorming_handoff", "can_execute": False},
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
                            "\ucd94\ucc9c \ubc29\ud5a5\n"
                            "1\ucc28 \uac1c\ubc1c\uc740 \ub2e8\uc21c \uc218\ubd88\uc7a5\ud615 + \uc548\uc804\uc7ac\uace0 \uc54c\ub9bc + \ucd5c\uadfc \uc785\ucd9c\uace0 \ub0b4\uc5ed\uc73c\ub85c \uac00\ub294 \uac83\uc744 \ucd94\ucc9c\ud569\ub2c8\ub2e4.\n"
                            "\uc6b4\uc601 \ubaa8\ub378 \uc120\ud0dd\uc9c0\n"
                            "1. \ub2e8\uc21c \uc218\ubd88\uc7a5\ud615\n"
                            "2. \uc704\uce58 \uc7ac\uace0\ud615\n"
                            "3. LOT/\uc2dc\ub9ac\uc5bc\ud615\n"
                            "\ud655\uc778 \uc9c8\ubb38\n"
                            "\ucd94\ucc9c \ubc29\ud5a5\uc778 \ub2e8\uc21c \uc218\ubd88\uc7a5\ud615 \ub300\uc2dc\ubcf4\ub4dc\ub85c \ubc14\ub85c \uad6c\ud604\ud574\ub3c4 \ub420\uae4c\uc694?\n"
                            "\uc2b9\uc778\ud574\uc8fc\uc2dc\uba74 \uc9c0\uc815\ud558\uc2e0 C:\\Users\\KONEIT\\Desktop\\Jang\\SKillsTest\\RetestAutoRoute_20260604_H "
                            "\ud3f4\ub354\uc5d0 \ud654\uba74 \ud30c\uc77c\uc744 \uc0dd\uc131\ud574\uc11c \uac1c\ubc1c\ud558\uaca0\uc2b5\ub2c8\ub2e4."
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "brainstorming-harness"
                and issue["status"] == "unilateral_brainstorm_decision"
                and "premature_execution_approval_question" in issue.get("matched_markers", [])
                for issue in audit.issues
            ),
            audit.issues,
        )

    def test_option_choice_followed_by_file_write_is_flagged(self):
        target = "C:\\Users\\KONEIT\\Desktop\\Jang\\SKillsTest\\RetestAutoRoute_20260604_I"
        front_door_output = {
            "front_door_status": "ok",
            "selected_not_executed_skills": ["brainstorming-harness"],
            "recommended_skills": ["always-on-front-door", "brainstorming-harness"],
            "execution_gate": {"status": "blocked_until_brainstorming_handoff", "can_execute": False},
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
                            "\uc6b4\uc601 \ubaa8\ub378 \uc120\ud0dd\uc9c0\n"
                            "1. \ub2e8\uc21c \uc7ac\uace0 \uc6d0\uc7a5\ud615\n"
                            "2. \uc704\uce58 \uad00\ub9ac\ud615\n"
                            "3. \ub85c\ud2b8/\uc2dc\ub9ac\uc5bc\ud615\n"
                            "\uc5b4\ub5a4 \uc6b4\uc601 \ubaa8\ub378\ub85c \uc9c4\ud589\ud560\uae4c\uc694?"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "1\ubc88 \ub2e8\uc21c \uc7ac\uace0 \uc6d0\uc7a5\ud615\uc73c\ub85c \uc9c4\ud589\ud574\uc918.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "apply_patch",
                        "arguments": "*** Begin Patch\n*** Add File: RetestAutoRoute_20260604_I/index.html\n+<html></html>\n*** End Patch",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "brainstorming-harness"
                and issue["status"] == "option_choice_treated_as_execution_approval"
                and issue["severity"] == "P0"
                for issue in audit.issues
            ),
            audit.issues,
        )

    def test_option_choice_followed_by_implementation_scope_lock_is_flagged(self):
        target = "C:\\Users\\KONEIT\\Desktop\\Jang\\SKillsTest\\RetestAutoRoute_20260604_K"
        front_door_output = {
            "front_door_status": "ok",
            "selected_not_executed_skills": ["brainstorming-harness"],
            "recommended_skills": ["always-on-front-door", "brainstorming-harness"],
            "execution_gate": {"status": "blocked_until_brainstorming_handoff", "can_execute": False},
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
                            "\uc5b4\ub5a4 \uc6b4\uc601 \ubaa8\ub378\ub85c \uc7a1\uc744\uae4c\uc694? "
                            "1\ubc88 \ub2e8\uc21c \uc218\ubd88\uc7a5, 2\ubc88 \uc704\uce58 \uad00\ub9ac, 3\ubc88 LOT/\uc2dc\ub9ac\uc5bc."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "1\ubc88\uc73c\ub85c \uc9c4\ud589",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": (
                            "1\ubc88 \ub2e8\uc21c \uc218\ubd88\uc7a5 \ubaa8\ub378\ub85c \ud655\uc815\ud588\uc2b5\ub2c8\ub2e4.\n\n"
                            "\uad6c\ud604 \ubc94\uc704\ub294 \uc774\ub807\uac8c \uc7a1\uaca0\uc2b5\ub2c8\ub2e4.\n\n"
                            "- \uc0c1\ub2e8 KPI: \ucd1d \ud488\ubaa9\uc218, \ud604\uc7ac\uace0 \ud569\uacc4, \uae08\uc77c \uc785\uace0, \uae08\uc77c \ucd9c\uace0\n"
                            "- \uc785\ucd9c\uace0 \uc785\ub825: \ud488\ubaa9, \uad6c\ubd84, \uc218\ub7c9, \uc77c\uc790, \ub2f4\ub2f9\uc790\n"
                            "- \uc800\uc7a5 \ubc29\uc2dd: \ube0c\ub77c\uc6b0\uc800 localStorage\n\n"
                            f"\uc774 \ubc94\uc704\ub85c {target} \uacbd\ub85c\uc5d0 \uc0c8 \ud3f4\ub354\ub97c \ub9cc\ub4e4\uace0 \ub300\uc2dc\ubcf4\ub4dc \ud30c\uc77c\uc744 \uc0dd\uc131\ud574\ub3c4 \ub420\uae4c\uc694?"
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "brainstorming-harness"
                and issue["status"] == "option_choice_treated_as_scope_approval"
                and issue["severity"] == "P0"
                for issue in audit.issues
            ),
            audit.issues,
        )

    def test_absolute_target_workspace_staging_is_flagged_even_without_relative_target_folder(self):
        target = "C:\\Users\\KONEIT\\Desktop\\Jang\\SKillsTest\\RetestAutoRoute_20260604_M"
        path = self.write_subagent_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": f"{target} folder에서 inventory dashboard develop.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "No files have been created yet. Reply proceed to start implementation.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "proceed",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "apply_patch",
                        "arguments": "*** Begin Patch\n*** Add File: index.html\n+<html></html>\n*** End Patch",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": (
                            f"Final folder not placed yet: {target}\n"
                            "Staging copy has 3 files in current workspace: index.html, styles.css, app.js."
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "guard-policy-harness"
                and issue["status"] == "target_path_substitution"
                and issue["severity"] == "P0"
                and any("workspace" in sample.lower() for sample in issue.get("samples", []))
                for issue in audit.issues
            ),
            audit.issues,
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

    def test_main_implementation_without_orchestration_decision_is_flagged(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": [
                "host-agent-orchestration",
                "subagent-review-pipeline",
                "parallel-orchestration-harness",
                "role-execution-audit-harness",
            ],
            "skill_status_summary": {
                "host-agent-orchestration": {"status": "skipped_with_rationale"},
                "subagent-review-pipeline": {"status": "skipped_with_rationale"},
                "parallel-orchestration-harness": {"status": "skipped_with_rationale"},
                "role-execution-audit-harness": {"status": "skipped_with_rationale"},
            },
        }
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Create an inventory dashboard in C:\\work\\InventoryTest.",
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
                        "type": "function_call",
                        "name": "apply_patch",
                        "arguments": "*** Begin Patch\n*** Add File: index.html\n+<div></div>\n*** End Patch",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "host-agent-orchestration"
                and issue["status"] == "missing_orchestration_decision"
                for issue in audit.issues
            )
        )
        self.assertTrue(
            any(
                issue["skill"] == "subagent-review-pipeline"
                and issue["status"] == "missing_orchestration_decision"
                for issue in audit.issues
            )
        )
        self.assertTrue(
            any(
                issue["skill"] == "parallel-orchestration-harness"
                and issue["status"] == "missing_parallel_strategy"
                for issue in audit.issues
            )
        )
        self.assertTrue(
            any(
                issue["skill"] == "role-execution-audit-harness"
                and issue["status"] == "missing_role_execution_audit"
                for issue in audit.issues
            )
        )

    def test_main_single_controller_with_parallel_and_role_rationale_satisfies_orchestration_audit(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": [
                "host-agent-orchestration",
                "subagent-review-pipeline",
                "parallel-orchestration-harness",
                "role-execution-audit-harness",
            ],
            "skill_status_summary": {
                "host-agent-orchestration": {"status": "skipped_with_rationale"},
                "subagent-review-pipeline": {"status": "skipped_with_rationale"},
                "parallel-orchestration-harness": {"status": "skipped_with_rationale"},
                "role-execution-audit-harness": {"status": "skipped_with_rationale"},
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
                        "content": (
                            "host_runtime=codex-main; nested_subagents_available=true; "
                            "subagent_strategy=single-controller because this is a tiny single file task "
                            "with a shared-state write set; parallel_strategy_decision=sequential with rationale; "
                            "role_execution_audit.status=skipped because no independent role artifact is useful."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "apply_patch",
                        "arguments": "*** Begin Patch\n*** Add File: index.html\n+<div></div>\n*** End Patch",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertFalse(
            any(
                issue["status"]
                in {
                    "missing_orchestration_decision",
                    "missing_parallel_strategy",
                    "missing_role_execution_audit",
                }
                for issue in audit.issues
            )
        )

    def test_parallel_strategy_parallel_without_fan_in_evidence_is_flagged(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": [
                "host-agent-orchestration",
                "subagent-review-pipeline",
                "parallel-orchestration-harness",
                "role-execution-audit-harness",
            ],
            "skill_status_summary": {
                "host-agent-orchestration": {"status": "skipped_with_rationale"},
                "subagent-review-pipeline": {"status": "skipped_with_rationale"},
                "parallel-orchestration-harness": {"status": "skipped_with_rationale"},
                "role-execution-audit-harness": {"status": "skipped_with_rationale"},
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
                        "content": (
                            "host_runtime=codex-main; nested_subagents_available=true; "
                            "subagent_strategy=dispatch; parallel_strategy_decision=parallel; "
                            "role_execution_audit.status=passed."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "apply_patch",
                        "arguments": "*** Begin Patch\n*** Add File: index.html\n+<div></div>\n*** End Patch",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "parallel-orchestration-harness"
                and issue["status"] == "missing_parallel_strategy"
                for issue in audit.issues
            )
        )

    def test_parallel_strategy_parallel_with_only_workflow_dispatch_result_is_flagged(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": ["always-on-front-door", "automatic-intake-harness"],
            "selected_not_executed_skills": ["parallel-orchestration-harness"],
            "skill_status_summary": {
                "parallel-orchestration-harness": {"status": "skipped_with_rationale"}
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
                        "content": (
                            "parallel_strategy_decision=parallel; WorkflowDispatchResult status=success."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "apply_patch",
                        "arguments": "*** Begin Patch\n*** Add File: index.html\n+<div></div>\n*** End Patch",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "parallel-orchestration-harness"
                and issue["status"] == "missing_parallel_strategy"
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

    def test_bare_single_controller_without_rationale_does_not_satisfy_strategy_audit(self):
        path = self.write_subagent_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "subagent_strategy=single-controller",
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
                        "type": "function_call_output",
                        "output": json.dumps(
                            {
                                "front_door_status": "ok",
                                "runtime_applied_skills": ["always-on-front-door"],
                                "selected_not_executed_skills": [],
                                "skill_status_summary": {
                                    "always-on-front-door": {
                                        "status": "applied",
                                        "application_mode": "runtime",
                                    }
                                },
                            }
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
                        "type": "function_call_output",
                        "output": json.dumps(
                            {
                                "front_door_status": "ok",
                                "runtime_applied_skills": ["always-on-front-door"],
                                "selected_not_executed_skills": [],
                                "skill_status_summary": {
                                    "always-on-front-door": {
                                        "status": "applied",
                                        "application_mode": "runtime",
                                    }
                                },
                            }
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
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": ["always-on-front-door"],
            "selected_not_executed_skills": [],
            "skill_status_summary": {
                "always-on-front-door": {"status": "applied", "application_mode": "runtime"}
            },
        }
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
                        "type": "function_call_output",
                        "output": json.dumps(front_door_output),
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

    def test_front_door_command_without_success_output_does_not_count_as_evidence(self):
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

        self.assertTrue(
            any(
                issue["skill"] == "always-on-front-door"
                and issue["status"] == "missing_front_door"
                for issue in audit.issues
            )
        )

    def test_custom_tool_front_door_output_counts_as_front_door_evidence(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": ["always-on-front-door"],
            "selected_not_executed_skills": [],
            "skill_status_summary": {
                "always-on-front-door": {"status": "applied", "application_mode": "runtime"}
            },
        }
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
                        "type": "custom_tool_call",
                        "name": "shell_command",
                        "input": "python -m src.orchestration.kh_front_door --summary",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "custom_tool_call_output",
                        "output": json.dumps(front_door_output),
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

    def test_front_door_error_output_does_not_count_as_front_door_evidence(self):
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
                        "type": "function_call_output",
                        "output": json.dumps(
                            {
                                "front_door_status": "error",
                                "runtime_applied_skills": [],
                                "selected_not_executed_skills": [],
                                "skill_status_summary": {},
                            }
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

    def test_skill_local_front_door_wrapper_counts_as_front_door_evidence(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": ["always-on-front-door"],
            "selected_not_executed_skills": [],
            "skill_status_summary": {
                "always-on-front-door": {"status": "applied", "application_mode": "runtime"}
            },
        }
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
                        "type": "function_call_output",
                        "output": json.dumps(front_door_output),
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
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "immediate_next_skills": ["brainstorming-harness"],
            "recommended_skills": ["always-on-front-door", "brainstorming-harness"],
            "selected_not_executed_skills": [],
            "execution_gate": {
                "status": "blocked_until_brainstorming_handoff",
                "can_execute": False,
            },
        }
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
        self.assertTrue(
            any(
                issue["skill"] == "brainstorming-harness"
                and issue["status"] == "target_folder_inspection_before_brainstorm_handoff"
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

    def test_immediate_next_skill_requires_followup_runtime_evidence(self):
        front_door_output = {
            "front_door_status": "ok",
            "classification": {"complexity": "medium", "domain": "software"},
            "plugin_route": {"route": "single", "controller": "kh"},
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["workflow-usability-harness"],
            "immediate_next_skills": ["workflow-usability-harness"],
            "skill_status_summary": {
                "workflow-usability-harness": {
                    "status": "selected",
                    "evidence_note": "Must be applied next.",
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
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": r"Get-Content C:\kh\skills\workflow_usability_harness\SKILL.md",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": "# Workflow Usability Harness\nRead-only instructions mention workflow_usability_auto.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "I read workflow-usability-harness and will inspect the project now.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {"type": "task_complete", "last_agent_message": "Done."},
                },
            ]
        )

        audit = analyze_session_skills(path)

        issue = next(
            issue
            for issue in audit.issues
            if issue["skill"] == "workflow-usability-harness"
            and issue["status"] == "immediate_next_skill_not_applied"
        )
        self.assertEqual(issue["severity"], "P0")
        self.assertIn("SKILL.md/support-file read", issue["action"])

    def test_front_door_blocked_large_work_flags_db_write_after_skill_reads(self):
        front_door_output = {
            "front_door_status": "ok",
            "classification": {
                "complexity": "heavy",
                "domain": "software",
                "recommended_execution": "role_dag",
            },
            "plugin_route": {"route": "single", "controller": "kh"},
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
                "token-optimizer",
            ],
            "selected_not_executed_skills": ["verification-before-completion-harness"],
            "immediate_next_skills": [
                "goal-state-harness",
                "workflow-usability-harness",
                "host-agent-orchestration",
                "parallel-orchestration-harness",
            ],
            "skill_status_summary": {
                "goal-state-harness": {"status": "pending_immediate_execution"},
                "workflow-usability-harness": {"status": "pending_immediate_execution"},
                "host-agent-orchestration": {"status": "pending_immediate_execution"},
                "parallel-orchestration-harness": {"status": "pending_immediate_execution"},
            },
            "execution_gate": {
                "status": "blocked_until_large_work_preflight",
                "can_execute": False,
                "required_before_execution": [
                    "goal-state-harness",
                    "large_work_orchestration_bundle",
                    "workspace_strategy",
                    "token_optimizer_status",
                    "subagent_strategy_with_rationale",
                    "parallel_strategy_decision_with_rationale",
                    "verification_plan",
                ],
                "blocked_actions": ["broad_source_exploration", "implementation", "db_writes"],
            },
            "execution_authorization": {
                "status": "blocked_by_execution_gate",
                "must_stop_before_execution": True,
                "can_execute_now": False,
                "pending_immediate_next_skills": [
                    "goal-state-harness",
                    "workflow-usability-harness",
                    "host-agent-orchestration",
                    "parallel-orchestration-harness",
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
                            r"Get-Content C:\Users\KONEIT\.codex\plugins\cache\kh-uaf-marketplace"
                            r"\kh-uaf\2.9.93\skills\workflow_usability_harness\SKILL.md"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "mssql_run_sql_query",
                        "arguments": json.dumps(
                            {
                                "query": (
                                    "ALTER PROCEDURE [dbo].[UP_SYS_TEST_SAVE]\n"
                                    "AS\nBEGIN\n    SELECT 1\nEND"
                                )
                            }
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        issue = next(
            issue
            for issue in audit.issues
            if issue["skill"] == "always-on-front-door"
            and issue["status"] == "front_door_execution_gate_bypassed"
        )

        self.assertEqual(issue["severity"], "P0")
        self.assertEqual(issue["gate_status"], "blocked_until_large_work_preflight")
        self.assertIn("db_writes", issue["blocked_actions"])
        self.assertIn("ALTER PROCEDURE", issue["first_blocked_work"])

    def test_front_door_large_work_gate_requires_full_preflight_not_shallow_markers(self):
        front_door_output = {
            "front_door_status": "ok",
            "classification": {
                "complexity": "heavy",
                "domain": "software",
                "recommended_execution": "role_dag",
            },
            "plugin_route": {"route": "single", "controller": "kh"},
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["verification-before-completion-harness"],
            "immediate_next_skills": [
                "goal-state-harness",
                "workflow-usability-harness",
                "host-agent-orchestration",
                "parallel-orchestration-harness",
            ],
            "execution_gate": {
                "status": "blocked_until_large_work_preflight",
                "can_execute": False,
                "required_before_execution": [
                    "goal-state-harness",
                    "large_work_orchestration_bundle",
                    "skill_statuses",
                    "workspace_strategy",
                    "token_optimizer_status",
                    "token_optimizer_status_reason",
                    "host_runtime",
                    "nested_subagents_available_or_not_applicable",
                    "subagent_strategy_with_rationale",
                    "parallel_strategy_decision_with_rationale",
                    "role_execution_audit.status_or_pre_role_skip",
                    "guard_policy_or_rollback_strategy",
                    "verification_plan",
                    "immediate_next_skills_applied_skipped_or_blocked",
                    "same_turn_immediate_skill_evidence",
                ],
                "blocked_actions": ["broad_source_exploration", "implementation"],
            },
            "execution_authorization": {
                "status": "blocked_by_execution_gate",
                "must_stop_before_execution": True,
                "can_execute_now": False,
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
                        "type": "function_call_output",
                        "output": (
                            "large_work_orchestration_bundle workspace_strategy token_optimizer_status "
                            "subagent_strategy goal-state-harness workflow-usability-harness "
                            "host-agent-orchestration parallel-orchestration-harness"
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "rg -n token src/orchestration/request_classifier.py",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "always-on-front-door"
                and issue["status"] == "front_door_execution_gate_bypassed"
                for issue in audit.issues
            )
        )

    def test_front_door_large_work_gate_releases_with_full_preflight_evidence(self):
        front_door_output = {
            "front_door_status": "ok",
            "classification": {
                "complexity": "heavy",
                "domain": "software",
                "recommended_execution": "role_dag",
            },
            "plugin_route": {"route": "single", "controller": "kh"},
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["verification-before-completion-harness"],
            "immediate_next_skills": [
                "goal-state-harness",
                "workflow-usability-harness",
                "host-agent-orchestration",
                "parallel-orchestration-harness",
            ],
            "execution_gate": {
                "status": "blocked_until_large_work_preflight",
                "can_execute": False,
                "required_before_execution": [
                    "goal-state-harness",
                    "large_work_orchestration_bundle",
                    "skill_statuses",
                    "workspace_strategy",
                    "token_optimizer_status",
                    "token_optimizer_status_reason",
                    "host_runtime",
                    "nested_subagents_available_or_not_applicable",
                    "subagent_strategy_with_rationale",
                    "parallel_strategy_decision_with_rationale",
                    "role_execution_audit.status_or_pre_role_skip",
                    "guard_policy_or_rollback_strategy",
                    "verification_plan",
                    "immediate_next_skills_applied_skipped_or_blocked",
                    "same_turn_immediate_skill_evidence",
                ],
                "blocked_actions": ["broad_source_exploration", "implementation"],
            },
            "execution_authorization": {
                "status": "blocked_by_execution_gate",
                "must_stop_before_execution": True,
                "can_execute_now": False,
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
                        "type": "function_call_output",
                        "output": (
                            "large_work_orchestration_bundle=recorded skill_statuses=recorded "
                            "workspace_strategy=current-checkout token_optimizer_status=considered_not_needed "
                            "token_optimizer_status_reason=no-large-output host_runtime=codex "
                            "nested_subagents_available=false subagent_strategy=single-controller "
                            "because shared-state requested files are coupled. "
                            "parallel_strategy_decision=sequential because shared-state risk. "
                            "role_execution_audit.status=skipped because no independent role artifact is useful. "
                            "guard_policy=do-not-revert rollback policy=no revert. "
                            "verification_plan=pytest-focused-tests. "
                            "goal-state-harness status=applied evidence objective goal. "
                            "workflow-usability-harness status=skipped_with_rationale reason=short-run. "
                            "host-agent-orchestration status=skipped_with_rationale reason=single-controller. "
                            "parallel-orchestration-harness status=skipped_with_rationale reason=sequential."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "rg -n token src/orchestration/request_classifier.py",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertFalse(
            any(
                issue["skill"] == "always-on-front-door"
                and issue["status"] == "front_door_execution_gate_bypassed"
                for issue in audit.issues
            )
        )

    def test_immediate_next_skill_support_reference_output_is_not_runtime_evidence(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["workflow-usability-harness"],
            "immediate_next_skills": ["workflow-usability-harness"],
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
                        "arguments": r"Get-Content C:\kh\skills\workflow_usability_harness\references\usage.md",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": (
                            "# Workflow Usability Harness Usage\n"
                            "Runtime auto mode performs apply_workflow_usability_runtime and progress_panel."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {"type": "task_complete", "last_agent_message": "Done."},
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "workflow-usability-harness"
                and issue["status"] == "immediate_next_skill_not_applied"
                for issue in audit.issues
            )
        )

    def test_immediate_next_skill_runtime_evidence_after_source_work_is_too_late(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["workflow-usability-harness"],
            "immediate_next_skills": ["workflow-usability-harness"],
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
                        "arguments": r"Get-Content C:\work\src\app.py",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": (
                            "workflow-usability-harness applied: workflow_usability_auto=true, "
                            "progress_panel rendered."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {"type": "task_complete", "last_agent_message": "Done."},
                },
            ]
        )

        audit = analyze_session_skills(path)

        issue = next(
            issue
            for issue in audit.issues
            if issue["skill"] == "workflow-usability-harness"
            and issue["status"] == "immediate_next_skill_not_applied"
        )
        self.assertIn(r"Get-Content C:\work\src\app.py", issue["order_break_sample"])
        self.assertIn("Work continued", issue["reason"])

    def test_apply_patch_before_immediate_evidence_is_flagged(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["workflow-usability-harness"],
            "immediate_next_skills": ["workflow-usability-harness"],
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
                        "type": "custom_tool_call",
                        "name": "apply_patch",
                        "input": "*** Begin Patch\n*** Update File: app.py\n+print('x')\n*** End Patch",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {"type": "task_complete", "last_agent_message": "Done."},
                },
            ]
        )

        audit = analyze_session_skills(path)

        issue = next(
            issue
            for issue in audit.issues
            if issue["skill"] == "workflow-usability-harness"
            and issue["status"] == "immediate_next_skill_not_applied"
        )
        self.assertIn("apply_patch", issue["order_break_sample"])

    def test_immediate_next_skills_must_preserve_front_door_order(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["goal-state-harness", "workflow-usability-harness"],
            "immediate_next_skills": ["goal-state-harness", "workflow-usability-harness"],
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
                        "type": "function_call_output",
                        "output": json.dumps(
                            {
                                "skill": "workflow-usability-harness",
                                "status": "applied",
                                "application_mode": "runtime",
                                "evidence": ["progress_panel"],
                            }
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "thread_goal_updated",
                        "goal": {"status": "active", "objective": "review immediate skills"},
                    },
                },
                {
                    "type": "response_item",
                    "payload": {"type": "task_complete", "last_agent_message": "Done."},
                },
            ]
        )

        audit = analyze_session_skills(path)

        issue = next(
            issue
            for issue in audit.issues
            if issue["skill"] == "workflow-usability-harness"
            and issue["status"] == "immediate_next_skill_order_violation"
        )
        self.assertIn("goal-state-harness", issue["reason"])
        self.assertEqual(issue["expected_order"], ["goal-state-harness", "workflow-usability-harness"])

    def test_assistant_self_claim_does_not_apply_immediate_skill(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["workflow-usability-harness"],
            "immediate_next_skills": ["workflow-usability-harness"],
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
                        "content": (
                            "workflow-usability-harness applied: workflow_usability_auto=true, "
                            "progress_panel rendered, session_start_context captured."
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {"type": "task_complete", "last_agent_message": "Done."},
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "workflow-usability-harness"
                and issue["status"] == "immediate_next_skill_not_applied"
                for issue in audit.issues
            )
        )

    def test_assistant_json_self_claim_does_not_apply_immediate_skill(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["workflow-usability-harness"],
            "immediate_next_skills": ["workflow-usability-harness"],
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
                        "content": json.dumps(
                            {
                                "skill": "workflow-usability-harness",
                                "status": "applied",
                                "application_mode": "runtime",
                                "evidence": ["progress_panel"],
                            }
                        ),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {"type": "task_complete", "last_agent_message": "Done."},
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "workflow-usability-harness"
                and issue["status"] == "immediate_next_skill_not_applied"
                for issue in audit.issues
            )
        )

    def test_immediate_blocked_negation_is_not_blocked_evidence(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["workflow-usability-harness"],
            "immediate_next_skills": ["workflow-usability-harness"],
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
                        "content": "workflow-usability-harness is not blocked yet; blocked_actions was reviewed.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {"type": "task_complete", "last_agent_message": "Done."},
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "workflow-usability-harness"
                and issue["status"] == "immediate_next_skill_not_applied"
                for issue in audit.issues
            )
        )

    def test_event_msg_task_complete_escalates_immediate_missing_to_p0(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["workflow-usability-harness"],
            "immediate_next_skills": ["workflow-usability-harness"],
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
                    "type": "event_msg",
                    "payload": {"type": "task_complete", "last_agent_message": "Done."},
                },
            ]
        )

        audit = analyze_session_skills(path)

        issue = next(
            issue
            for issue in audit.issues
            if issue["skill"] == "workflow-usability-harness"
            and issue["status"] == "immediate_next_skill_not_applied"
        )
        self.assertEqual(issue["severity"], "P0")


    def test_immediate_applied_echo_output_is_not_runtime_evidence(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["workflow-usability-harness"],
            "immediate_next_skills": ["workflow-usability-harness"],
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
                        "type": "function_call_output",
                        "output": "workflow-usability-harness status=applied runtime evidence",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {"type": "task_complete", "last_agent_message": "Done."},
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "workflow-usability-harness"
                and issue["status"] == "immediate_next_skill_not_applied"
                for issue in audit.issues
            )
        )

    def test_global_codex_memory_lookup_requires_explicit_scope_request(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Create a small local dashboard in this folder.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "Select-String -Path 'C:\\Users\\KONEIT\\.codex\\memories\\MEMORY.md' -Pattern 'dashboard'",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "memory-state-harness"
                and issue["status"] == "global_memory_lookup_without_scope_approval"
                for issue in audit.issues
            )
        )

    def test_immediate_next_skill_passes_with_runtime_evidence(self):
        front_door_output = {
            "front_door_status": "ok",
            "classification": {"complexity": "medium", "domain": "software"},
            "plugin_route": {"route": "single", "controller": "kh"},
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["workflow-usability-harness"],
            "immediate_next_skills": ["workflow-usability-harness"],
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
                        "type": "function_call_output",
                        "output": json.dumps(
                            {
                                "skill": "workflow-usability-harness",
                                "status": "applied",
                                "application_mode": "runtime",
                                "evidence": ["progress_panel", "session_start_context"],
                                "artifacts": [".kh/development/run/state/host_panel.codex.json"],
                            }
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertFalse(
            any(
                issue["skill"] == "workflow-usability-harness"
                and issue["status"] == "immediate_next_skill_not_applied"
                for issue in audit.issues
            )
        )

    def test_thread_goal_updated_applies_goal_state_immediate_skill(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["goal-state-harness"],
            "immediate_next_skills": ["goal-state-harness"],
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
                    "type": "event_msg",
                    "payload": {
                        "type": "thread_goal_updated",
                        "goal": {"status": "active", "objective": "audit KH usage"},
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertFalse(
            any(
                issue["skill"] == "goal-state-harness"
                and issue["status"].startswith("immediate_next_skill")
                for issue in audit.issues
            )
        )

    def test_immediate_next_skill_passes_with_skipped_rationale(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["token-optimizer"],
            "immediate_next_skills": ["token-optimizer"],
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
                        "type": "function_call_output",
                        "output": (
                            "token-optimizer status=skipped skipped_with_rationale "
                            "reason=short focused audit output, no large command output or transcript was processed."
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertFalse(
            any(
                issue["skill"] == "token-optimizer"
                and issue["status"].startswith("immediate_next_skill")
                for issue in audit.issues
            )
        )

    def test_immediate_next_skill_passes_with_blocked_reason(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["workflow-usability-harness"],
            "immediate_next_skills": ["workflow-usability-harness"],
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
                        "type": "function_call_output",
                        "output": (
                            "workflow-usability-harness status=blocked blocked_reason=host progress "
                            "state API unavailable in this read-only review. recovery=retry when host "
                            "progress state API is available."
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertFalse(
            any(
                issue["skill"] == "workflow-usability-harness"
                and issue["status"].startswith("immediate_next_skill")
                for issue in audit.issues
            )
        )

    def test_immediate_blocked_without_recovery_is_not_blocked_evidence(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["workflow-usability-harness"],
            "immediate_next_skills": ["workflow-usability-harness"],
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
                        "content": "workflow-usability-harness status=blocked blocked_reason=unavailable.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {"type": "task_complete", "last_agent_message": "Done."},
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "workflow-usability-harness"
                and issue["status"] == "immediate_next_skill_not_applied"
                for issue in audit.issues
            )
        )

    def test_assistant_blocked_self_claim_does_not_apply_immediate_skill(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["workflow-usability-harness"],
            "immediate_next_skills": ["workflow-usability-harness"],
        }
        for content in [
            "workflow-usability-harness status=blocked blocked_reason=missing host panel recovery=retry later",
            json.dumps(
                {
                    "skill": "workflow-usability-harness",
                    "status": "blocked",
                    "blocked_reason": "missing host panel",
                    "recovery": "retry later",
                }
            ),
        ]:
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
                        "payload": {"type": "message", "role": "assistant", "content": content},
                    },
                    {
                        "type": "response_item",
                        "payload": {"type": "task_complete", "last_agent_message": "Done."},
                    },
                ]
            )

            audit = analyze_session_skills(path)

            self.assertTrue(
                any(
                    issue["skill"] == "workflow-usability-harness"
                    and issue["status"] == "immediate_next_skill_not_applied"
                    for issue in audit.issues
                )
            )

    def test_immediate_missing_with_user_refinement_and_completion_is_p0(self):
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
            "selected_not_executed_skills": ["workflow-usability-harness"],
            "immediate_next_skills": ["workflow-usability-harness"],
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
                        "arguments": r"rg -n RowStyle C:\work\app.cs",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "그럼 그 방향으로 더 봐봐",
                    },
                },
                {
                    "type": "event_msg",
                    "payload": {"type": "task_complete", "last_agent_message": "Done."},
                },
            ]
        )

        audit = analyze_session_skills(path)

        issue = next(
            issue
            for issue in audit.issues
            if issue["skill"] == "workflow-usability-harness"
            and issue["status"] == "immediate_next_skill_not_applied"
        )
        self.assertEqual(issue["severity"], "P0")


if __name__ == "__main__":
    unittest.main()
