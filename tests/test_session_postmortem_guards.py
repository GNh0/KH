import json
import tempfile
import unittest
from pathlib import Path

from src.orchestration.development_progress import (
    DevelopmentRunProgress,
    DevelopmentTaskProgress,
    derive_review_status,
    validate_development_progress,
)
from src.orchestration.session_postmortem import (
    analyze_codex_session_jsonl,
    redact_sensitive_text,
    render_session_postmortem,
)
from src.orchestration.windows_dev_server import build_streamlit_launch_plan


class SessionPostmortemGuardTests(unittest.TestCase):
    def write_session(self, events):
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "rollout.jsonl"
        path.write_text(
            "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n",
            encoding="utf-8",
        )
        self.addCleanup(tmp.cleanup)
        return path

    def test_active_goal_completion_guard_blocks_partial_scaffold_stop(self):
        path = self.write_session(
            [
                {
                    "type": "session_meta",
                    "payload": {"id": "session-1", "cwd": "D:/Coding/DeepLStock"},
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "thread_goal_updated",
                        "goal": {
                            "status": "active",
                            "objective": (
                                "Complete MVP: data collection, feature generation, model training, backtest, "
                                "paper trading, DB persistence, dashboard, and bot monitoring."
                            ),
                        },
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": (
                            "The first MVP scaffold is implemented and pushed to GitHub. "
                            "It includes a Streamlit dashboard and a DB repository skeleton."
                        ),
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.completion_guard["status"], "blocked")
        self.assertEqual(postmortem.scope_completion_delta["status"], "blocked")
        self.assertIn("model_training", postmortem.scope_completion_delta["missing_markers"])
        self.assertTrue(
            any("Do not emit task_complete" in action for action in postmortem.recommended_actions)
        )
        self.assertIn("Completion guard: blocked", render_session_postmortem(postmortem))

    def test_verification_claim_guard_blocks_unreported_browser_failure(self):
        path = self.write_session(
            [
                {
                    "type": "session_meta",
                    "payload": {"id": "session-2", "cwd": "D:/Coding/DeepLStock"},
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": '{"ok":false,"error":"Error: Module not found: playwright"}',
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": "Verification completed. Streamlit HTTP 200 confirmed.",
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.verification_claim_guard["status"], "blocked")
        self.assertEqual(postmortem.verification_claim_guard["failed_verification_count"], 1)
        self.assertTrue(
            any("Report failed or unavailable verification" in action for action in postmortem.recommended_actions)
        )

    def test_user_stop_guard_blocks_goal_context_reactivation_and_extra_patch(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "thread_goal_updated",
                        "goal": {"status": "active", "objective": "Finish a large workflow."},
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "작업한거까지 체크하고 goal멈추라니까?"}],
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "update_plan",
                        "arguments": json.dumps({"plan": []}),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "thread_goal_updated",
                        "goal": {"status": "active", "objective": "Finish a large workflow."},
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "<goal_context>Continue working toward the active thread goal.</goal_context>"}],
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "다시 이어서 구현을 진행하겠습니다."}],
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

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.user_stop_guard["status"], "blocked")
        self.assertIn("user_stop_left_goal_active", postmortem.user_stop_guard["reasons"])
        self.assertIn("goal_context_reactivated_after_user_stop", postmortem.user_stop_guard["reasons"])
        self.assertIn("tool_call_after_user_stop", postmortem.user_stop_guard["reasons"])
        self.assertIn("work_continuation_after_user_stop", postmortem.user_stop_guard["reasons"])
        self.assertTrue(
            any("User stop/cancel requests override goal_context" in action for action in postmortem.recommended_actions)
        )
        self.assertTrue(
            any("ignore automated goal_context until a fresh user resume" in action for action in postmortem.recommended_actions)
        )
        self.assertIn("User stop guard: blocked", render_session_postmortem(postmortem))

    def test_user_stop_guard_allows_status_check_then_blocked_goal(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "thread_goal_updated",
                        "goal": {"status": "active", "objective": "Finish a large workflow."},
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "작업 해놓은거 까지 체크하고 일단 스탑하자"}],
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": json.dumps({"command": "git status --short --branch"}),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "thread_goal_updated",
                        "goal": {
                            "status": "blocked",
                            "objective": "Finish a large workflow.",
                            "blocked_reason": "user_requested_stop",
                        },
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": "Stopped at user request. Goal blocked with user_requested_stop.",
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.user_stop_guard["status"], "passed")
        self.assertEqual(postmortem.user_stop_guard["latest_goal_status_after_stop"], "blocked")
        self.assertEqual(postmortem.user_stop_guard["continued_tool_calls"], [])

    def test_assistant_stop_guard_blocks_active_goal_left_open(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "thread_goal_updated",
                        "goal": {"status": "active", "objective": "Build inventory dashboard."},
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": (
                            "\uc791\uc5c5 \uc911\ub2e8\ud569\ub2c8\ub2e4. "
                            "\ub300\uc0c1 Desktop \ud3f4\ub354\uc5d0\ub294 \uc544\uc9c1 \uc4f0\uc9c0 \uc54a\uc558\uace0 "
                            "\uc784\uc2dc \ud30c\uc77c\ub9cc \uc788\uc2b5\ub2c8\ub2e4."
                        ),
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.assistant_stop_guard["status"], "blocked")
        self.assertIn("assistant_stop_left_goal_active", postmortem.assistant_stop_guard["reasons"])
        self.assertTrue(postmortem.assistant_stop_guard["assistant_claims_stop"])
        self.assertTrue(
            any("stopped/blocked final answer" in action for action in postmortem.recommended_actions)
        )
        self.assertIn("Assistant stop guard: blocked", render_session_postmortem(postmortem))

    def test_assistant_stop_guard_detects_korean_stop_and_archive_without_goal(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": (
                            "\uc911\ub2e8\ud558\uace0 \uc885\ub8cc\ud569\ub2c8\ub2e4.\n\n"
                            "::archive{reason=\"User requested to end conversation\"}"
                        ),
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.assistant_stop_guard["status"], "blocked")
        self.assertIn("assistant_stop_without_terminal_goal", postmortem.assistant_stop_guard["reasons"])
        self.assertTrue(postmortem.assistant_stop_guard["assistant_claims_stop"])
        self.assertEqual(postmortem.archive_guard["status"], "blocked")
        self.assertIn("archive_directive_without_user_request", postmortem.archive_guard["reasons"])
        self.assertIn("Archive guard: blocked", render_session_postmortem(postmortem))

    def test_archive_guard_allows_explicit_user_archive_request(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "\ub300\ud654 \uc885\ub8cc\ud574\uc918.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": "::archive{reason=\"User requested to end conversation\"}",
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.archive_guard["status"], "passed")
        self.assertEqual(postmortem.archive_guard["archive_directive_count"], 1)
        self.assertEqual(postmortem.archive_guard["user_archive_request_count"], 1)

    def test_assistant_stop_guard_allows_terminal_goal(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "thread_goal_updated",
                        "goal": {"status": "active", "objective": "Build inventory dashboard."},
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "thread_goal_updated",
                        "goal": {"status": "blocked", "objective": "Build inventory dashboard."},
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": "Blocked because the requested target path needs approval.",
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.assistant_stop_guard["status"], "passed")
        self.assertEqual(postmortem.assistant_stop_guard["latest_goal_status"], "blocked")

    def test_assistant_stop_guard_blocks_even_if_goal_completes_later(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "thread_goal_updated",
                        "goal": {"status": "active", "objective": "Build inventory dashboard."},
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": "\uc791\uc5c5 \uc911\ub2e8\ud569\ub2c8\ub2e4. \uc784\uc2dc \ud30c\uc77c\ub9cc \uc788\uc2b5\ub2c8\ub2e4.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "thread_goal_updated",
                        "goal": {"status": "complete", "objective": "Build inventory dashboard."},
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.assistant_stop_guard["status"], "blocked")
        self.assertEqual(postmortem.assistant_stop_guard["latest_goal_status"], "complete")
        self.assertEqual(postmortem.assistant_stop_guard["active_stop_events"][0]["goal_status_at_stop"], "active")

    def test_korean_goal_scope_markers_are_detected(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "thread_goal_updated",
                        "goal": {
                            "status": "active",
                            "objective": (
                                "완성형 MVP: 데이터 수집, 피처 생성, 모델 학습, 백테스트, "
                                "페이퍼 트레이딩, DB 저장, 대시보드, 봇 모니터링"
                            ),
                        },
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": "1차 스캐폴드 완료. 대시보드와 DB 저장 골격만 포함.",
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.scope_completion_delta["status"], "blocked")
        self.assertIn("data_collection", postmortem.scope_completion_delta["objective_markers"])
        self.assertIn("paper_trading", postmortem.scope_completion_delta["missing_markers"])

    def test_token_and_secret_gates_are_extracted_from_large_session(self):
        path = self.write_session(
            [
                {"type": "session_meta", "payload": {"id": "session-3", "cwd": "D:/Coding/Stock"}},
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 500_000},
                            "last_token_usage": {"input_tokens": 150_000},
                            "model_context_window": 250_000,
                        },
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": json.dumps(
                            {
                                "command": (
                                    "$env:PGPASSWORD='1111'; "
                                    "python -m unittest tests.test_postgres -v"
                                )
                            }
                        ),
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.token_optimizer_status, "blocked")
        self.assertIn("no runtime optimizer", postmortem.token_optimizer_status_reason)
        self.assertTrue(postmortem.token_gate["required"])
        self.assertEqual(postmortem.secret_findings[0].kind, "pgpassword")
        self.assertIn("PGPASSWORD='***", postmortem.verification_commands[0])

    def test_token_optimizer_doc_read_does_not_count_as_usage(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 60_000},
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
                        "arguments": json.dumps(
                            {
                                "command": (
                                    "Get-Content -Path "
                                    "C:/Users/User/.codex/plugins/cache/kh-uaf/skills/token_optimizer/SKILL.md "
                                    "-TotalCount 140"
                                )
                            }
                        ),
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.token_optimizer_status, "blocked")
        self.assertIn("only the skill documentation was read", postmortem.token_optimizer_status_reason)
        self.assertEqual(postmortem.token_optimizer_evidence["skill_doc_reads"], 1)
        self.assertEqual(postmortem.token_optimizer_evidence["runtime_calls"], 0)
        self.assertTrue(
            any("inspection, not usage" in action for action in postmortem.recommended_actions)
        )
        self.assertIn("Token optimizer reason:", render_session_postmortem(postmortem))

    def test_cumulative_tokens_alone_do_not_force_token_gate(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 450_000},
                            "last_token_usage": {"input_tokens": 56_000},
                            "model_context_window": 258_400,
                        },
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "Short direction-setting answer with no long command output.",
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertFalse(postmortem.token_gate["required"])
        self.assertEqual(postmortem.token_optimizer_status, "considered_not_needed")
        self.assertIn("optimization was not needed", postmortem.token_optimizer_status_reason)


    def test_required_token_gate_accepts_structured_passthrough_decision(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 60_000},
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
                                "skill": "token-optimizer",
                                "token_optimizer_status": "passthrough",
                                "passthrough_reason": "contract-sensitive SQL must preserve exact source text",
                                "provider": "kh",
                                "strategy": "raw_passthrough",
                            }
                        ),
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.token_optimizer_status, "passthrough")
        self.assertIn("explicit passthrough", postmortem.token_optimizer_status_reason)
        self.assertEqual(postmortem.token_optimizer_evidence["explicit_passthrough_records"], 1)

    def test_generic_tool_output_passthrough_string_does_not_satisfy_token_gate(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 60_000},
                            "last_token_usage": {"input_tokens": 120_000},
                            "model_context_window": 200_000,
                        },
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": "token_optimizer_status=passthrough because someone wrote it in a generic tool log",
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.token_optimizer_status, "blocked")
        self.assertEqual(postmortem.token_optimizer_evidence["explicit_passthrough_records"], 0)

    def test_assistant_only_passthrough_claim_does_not_satisfy_token_gate(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 60_000},
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
                        "content": "token_optimizer_status=passthrough because this was contract-sensitive.",
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.token_optimizer_status, "blocked")
        self.assertEqual(postmortem.token_optimizer_evidence["explicit_passthrough_records"], 0)

    def test_token_optimizer_runtime_call_without_structured_output_does_not_count_as_usage(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 60_000},
                            "last_token_usage": {"input_tokens": 40_000},
                            "model_context_window": 200_000,
                        },
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": json.dumps(
                            {
                                "command": (
                                    "python -m src.skills.token_optimizer "
                                    "--log-file logs/test.log --max-lines 40"
                                )
                            }
                        ),
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.token_optimizer_status, "blocked")
        self.assertIn("no structured", postmortem.token_optimizer_status_reason)
        self.assertEqual(postmortem.token_optimizer_evidence["runtime_calls"], 1)

    def test_runtime_token_optimizer_workflow_evidence_counts_as_usage(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 60_000},
                            "last_token_usage": {"input_tokens": 40_000},
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
                                    "estimated_tokens_saved": 12000,
                                    "actual_tokens_saved": 12000,
                                    "actual_usage_scope": "actual_optimizer_input_output_payload",
                                    "token_count_method": "deterministic_local_estimate_chars_div_4",
                                    "token_count_is_estimate": True,
                                    "billing_tokens_available": False,
                                }
                            }
                        ),
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.token_optimizer_status, "used")
        self.assertEqual(postmortem.token_optimizer_evidence["runtime_calls"], 1)
        self.assertEqual(postmortem.token_optimizer_evidence["explicit_usage_records"], 1)

    def test_runtime_token_optimizer_passthrough_report_does_not_count_as_usage(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 60_000},
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
                                    "status": "passthrough",
                                    "token_optimizer_status_reason": (
                                        "Token optimizer not used because content was passed through unchanged."
                                    ),
                                    "not_used_reason": (
                                        "Token optimizer not used because content was passed through unchanged."
                                    ),
                                    "summary": {
                                        "actual_tokens_saved": 0,
                                        "actual_usage_scope": "actual_optimizer_input_output_payload",
                                    },
                                }
                            }
                        ),
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.token_optimizer_status, "passthrough")
        self.assertEqual(postmortem.token_optimizer_evidence["runtime_calls"], 1)
        self.assertEqual(postmortem.token_optimizer_evidence["explicit_usage_records"], 0)
        self.assertEqual(postmortem.token_optimizer_evidence["explicit_passthrough_records"], 1)

    def test_runtime_token_optimizer_blocked_report_does_not_count_as_usage(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 60_000},
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
                                    "status": "blocked",
                                    "token_optimizer_status_reason": (
                                        "Token optimizer not used because optimization was blocked."
                                    ),
                                    "not_used_reason": "Token optimizer not used because optimization was blocked.",
                                    "blocked_reason": "required facts could not be preserved",
                                    "summary": {
                                        "actual_tokens_saved": 0,
                                        "actual_usage_scope": "actual_optimizer_input_output_payload",
                                    },
                                }
                            }
                        ),
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.token_optimizer_status, "blocked")
        self.assertEqual(postmortem.token_optimizer_evidence["runtime_calls"], 1)
        self.assertEqual(postmortem.token_optimizer_evidence["explicit_usage_records"], 0)
        self.assertEqual(postmortem.token_optimizer_evidence["blocked_reason_records"], 1)

    def test_assistant_only_token_optimizer_claim_does_not_count_as_usage(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 60_000},
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
                            "and recorded runtime_token_optimization estimated_tokens_saved=12000."
                        ),
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.token_optimizer_status, "blocked")
        self.assertEqual(postmortem.token_optimizer_evidence["runtime_calls"], 0)
        self.assertEqual(postmortem.token_optimizer_evidence["explicit_usage_records"], 0)

    def test_assistant_only_structured_token_optimizer_claim_does_not_count_as_usage(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 60_000},
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
                        "content": json.dumps(
                            {
                                "runtime_token_optimization": {
                                    "status": "used",
                                    "actual_tokens_saved": 1200,
                                    "actual_usage_scope": "actual_optimizer_input_output_payload",
                                }
                            }
                        ),
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.token_optimizer_status, "blocked")
        self.assertEqual(postmortem.token_optimizer_evidence["runtime_calls"], 0)
        self.assertEqual(postmortem.token_optimizer_evidence["structured_used_records"], 0)
        self.assertEqual(postmortem.token_optimizer_evidence["explicit_usage_records"], 0)

    def test_read_only_token_optimizer_probe_does_not_count_as_usage(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 60_000},
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
                        "arguments": json.dumps(
                            {
                                "command": (
                                    "rg -n \"optimize_workflow_task_results|runtime_token_optimization\" "
                                    "src tests"
                                )
                            }
                        ),
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.token_optimizer_status, "blocked")
        self.assertEqual(postmortem.token_optimizer_evidence["runtime_calls"], 0)

    def test_read_only_diff_output_with_token_telemetry_shape_does_not_count_as_usage(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 60_000},
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
                                    "actual_tokens_saved": 12000,
                                    "actual_usage_scope": "actual_optimizer_input_output_payload",
                                    "billing_tokens_available": False,
                                }
                            }
                        ),
                    },
                },
            ]
        )

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.token_optimizer_status, "blocked")
        self.assertEqual(postmortem.token_optimizer_evidence["runtime_calls"], 0)
        self.assertEqual(postmortem.token_optimizer_evidence["explicit_usage_records"], 0)

    def test_resume_guard_blocks_implementation_without_kh_preflight(self):
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
                        "content": "stop for now",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "Stopped and waiting.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "restart and continue development",
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

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.resume_guard["status"], "blocked")
        self.assertIn("resume_without_session_start_context", postmortem.resume_guard["reasons"])
        self.assertIn("resume_without_runtime_token_optimizer", postmortem.resume_guard["reasons"])
        self.assertIn("resume_without_large_work_skill_bundle", postmortem.resume_guard["reasons"])
        self.assertTrue(
            any("Resume/restart requests must run KH session_start_context" in action for action in postmortem.recommended_actions)
        )
        self.assertIn("Resume guard: blocked", render_session_postmortem(postmortem))

    def test_resume_guard_passes_after_kh_preflight_evidence(self):
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
                        "content": "resume the implementation",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": (
                            "session_start_context restored with build_session_start_context; "
                            "src.orchestration.runtime_token_optimizer.optimize_workflow_task_results "
                            "recorded runtime_token_optimization estimated_tokens_saved=1200; "
                            "large_work_orchestration_bundle selected skill_statuses and skill_transition_handoff."
                        ),
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

        postmortem = analyze_codex_session_jsonl(path)

        self.assertEqual(postmortem.resume_guard["status"], "passed")
        self.assertEqual(postmortem.resume_guard["reasons"], [])

    def test_redaction_preserves_shape_without_secret_value(self):
        text = "DATABASE_URL=postgresql+psycopg2://postgres:1111@127.0.0.1/db"

        redacted = redact_sensitive_text(text)

        self.assertIn("postgresql+psycopg2://postgres:***", redacted)
        self.assertNotIn("1111@127", redacted)

    def test_review_timeout_status_cannot_validate_as_complete(self):
        progress = DevelopmentRunProgress(
            run_id="run-review-timeout",
            objective="Finish a feature.",
            workspace_strategy="project-local-worktree",
            token_optimizer_status="used",
            token_optimizer_status_reason="Token optimizer used; runtime telemetry is available.",
            tasks=[
                DevelopmentTaskProgress(
                    task_id="task-1",
                    title="Implement feature",
                    status="complete",
                    red_status="failed_expected",
                    green_status="passed",
                    spec_review_status="timeout",
                    code_quality_review_status="passed",
                    commit_sha="abc1234",
                )
            ],
        )

        self.assertEqual(derive_review_status(progress.tasks), "review_incomplete")
        result = validate_development_progress(progress)
        self.assertFalse(result["valid"])
        self.assertIn("tasks.task-1.spec_review_status", result["missing"])

    def test_windows_streamlit_launch_plan_normalizes_path_and_health_check(self):
        plan = build_streamlit_launch_plan(
            "D:/Coding/DeepLStock",
            env={"PYTHONPATH": "src", "DASHBOARD_URL": "http://deeplstock-pc:8501"},
            visible=True,
        )

        self.assertEqual(plan.url, "http://127.0.0.1:8501")
        self.assertIn("SetEnvironmentVariable('PATH'", plan.command)
        self.assertIn("-WindowStyle Normal", plan.command)
        self.assertIn("Invoke-WebRequest", plan.health_check_command)
        self.assertIn("normalized_path_environment", plan.evidence)


if __name__ == "__main__":
    unittest.main()
