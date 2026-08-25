import gc
import json
import tempfile
import tracemalloc
import unittest
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from src.orchestration import session_postmortem as postmortem_module


class SessionPostmortemBoundedStateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    @staticmethod
    def _response(payload):
        return {"type": "response_item", "payload": payload}

    def _write_adversarial_session(self, event_count):
        path = self.root / f"bounded-{event_count}.jsonl"
        cycle = [
            self._response(
                {"type": "message", "role": "user", "content": "Stop."}
            ),
            self._response(
                {"type": "agent_message", "message": "Continue implementation now."}
            ),
            self._response(
                {"type": "function_call", "name": "write_file", "arguments": "{}"}
            ),
            self._response(
                {
                    "type": "task_complete",
                    "last_agent_message": (
                        "Work stopped. ::archive{reason=\"bounded-state test\"}"
                    ),
                }
            ),
            self._response(
                {
                    "type": "message",
                    "role": "user",
                    "content": "archive this conversation",
                }
            ),
            self._response(
                {
                    "type": "message",
                    "role": "user",
                    "content": "resume implementation",
                }
            ),
            self._response(
                {"type": "function_call", "name": "apply_patch", "arguments": "{}"}
            ),
            self._response(
                {
                    "type": "function_call_output",
                    "output": "Exit code: 1\nFAILED bounded verification",
                }
            ),
        ]
        records = [
            {
                "type": "session_meta",
                "payload": {"id": f"bounded-{event_count}", "cwd": "D:/bounded"},
            },
            self._response(
                {
                    "type": "thread_goal_updated",
                    "goal": {"status": "active", "objective": "Bound retained state."},
                }
            ),
        ]
        cycle_count = (event_count - len(records)) // len(cycle)
        for _ in range(cycle_count):
            records.extend(cycle)
        while len(records) < event_count:
            records.append(
                self._response(
                    {"type": "debug_blob", "index": len(records), "blob": "x" * 32}
                )
            )

        with path.open("w", encoding="utf-8", newline="\n") as stream:
            for record in records:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        return path, cycle_count

    @staticmethod
    def _capture_bounded_states(path):
        captured = {}
        original_user_stop = postmortem_module._build_user_stop_guard
        original_assistant_stop = postmortem_module._build_assistant_stop_guard
        original_archive = postmortem_module._build_archive_guard
        original_resume = postmortem_module._build_resume_guard
        original_verification = postmortem_module._build_verification_claim_guard

        def capture_user_stop(state, goal_state):
            captured["user_stop"] = state
            return original_user_stop(state, goal_state)

        def capture_assistant_stop(goal_state, task_count, final_messages, state):
            captured["assistant_stop"] = state
            return original_assistant_stop(
                goal_state,
                task_count,
                final_messages,
                state,
            )

        def capture_archive(state):
            captured["archive"] = state
            return original_archive(state)

        def capture_resume(state, token_gate):
            captured["resume"] = state
            return original_resume(state, token_gate)

        def capture_verification(state, final_message_state):
            captured["verification"] = state
            return original_verification(state, final_message_state)

        with mock.patch.object(
            postmortem_module,
            "_build_user_stop_guard",
            side_effect=capture_user_stop,
        ), mock.patch.object(
            postmortem_module,
            "_build_assistant_stop_guard",
            side_effect=capture_assistant_stop,
        ), mock.patch.object(
            postmortem_module,
            "_build_archive_guard",
            side_effect=capture_archive,
        ), mock.patch.object(
            postmortem_module,
            "_build_resume_guard",
            side_effect=capture_resume,
        ), mock.patch.object(
            postmortem_module,
            "_build_verification_claim_guard",
            side_effect=capture_verification,
        ):
            result = postmortem_module.analyze_codex_session_jsonl(path)
        return result, captured

    def _measure_retained_state(self, event_count):
        path, cycle_count = self._write_adversarial_session(event_count)
        gc.collect()
        tracemalloc.start()
        result, captured = self._capture_bounded_states(path)
        gc.collect()
        retained, _ = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return result, captured, cycle_count, retained

    def test_1k_vs_10k_events_keep_exact_counts_and_bounded_retained_state(self):
        small = self._measure_retained_state(1_000)
        large = self._measure_retained_state(10_000)

        for result, states, cycle_count, _ in (small, large):
            with self.subTest(line_count=result.line_count):
                self.assertEqual(result.line_count, int(result.session_id.rsplit("-", 1)[1]))

                self.assertEqual(states["user_stop"]["request_count"], cycle_count)
                self.assertEqual(
                    states["user_stop"]["continued_tool_call_count"], cycle_count
                )
                self.assertEqual(
                    states["user_stop"]["continued_work_message_count"], cycle_count
                )
                self.assertEqual(
                    len(states["user_stop"]["continued_tool_call_samples"]), 10
                )
                self.assertEqual(
                    len(states["user_stop"]["continued_work_message_samples"]), 10
                )

                self.assertEqual(states["assistant_stop"]["event_count"], cycle_count)
                self.assertEqual(
                    states["assistant_stop"]["active_event_count"], cycle_count
                )
                self.assertEqual(len(states["assistant_stop"]["event_samples"]), 5)
                self.assertEqual(
                    len(states["assistant_stop"]["active_event_samples"]), 5
                )

                self.assertEqual(states["archive"]["directive_count"], cycle_count)
                self.assertEqual(states["archive"]["user_request_count"], cycle_count)
                self.assertEqual(len(states["archive"]["directive_samples"]), 5)
                self.assertEqual(len(states["archive"]["user_request_samples"]), 5)

                self.assertEqual(states["resume"]["request_count"], cycle_count)
                self.assertEqual(states["resume"]["implementation_tool_count"], cycle_count)
                self.assertEqual(
                    len(states["resume"]["implementation_tool_samples"]), 10
                )

                self.assertEqual(states["verification"]["count"], cycle_count)
                self.assertEqual(len(states["verification"]["samples"]), 10)

                self.assertEqual(result.user_stop_guard["stop_request_count"], cycle_count)
                self.assertEqual(result.assistant_stop_guard["stop_event_count"], cycle_count)
                self.assertEqual(
                    result.archive_guard["archive_directive_count"], cycle_count
                )
                self.assertEqual(
                    result.archive_guard["user_archive_request_count"], cycle_count
                )
                self.assertEqual(
                    result.resume_guard["resume_request_count"], cycle_count
                )
                self.assertEqual(
                    result.verification_claim_guard["failed_verification_count"],
                    cycle_count,
                )

                self.assertEqual(
                    result.user_stop_guard["latest_stop_line"],
                    3 + 8 * (cycle_count - 1),
                )
                self.assertEqual(
                    result.archive_guard["latest_archive_line"],
                    6 + 8 * (cycle_count - 1),
                )
                self.assertEqual(
                    result.resume_guard["latest_resume_line"],
                    8 + 8 * (cycle_count - 1),
                )
                self.assertEqual(
                    result.user_stop_guard["continued_tool_calls"][0]["line"], 5
                )
                self.assertEqual(
                    result.assistant_stop_guard["active_stop_events"][0]["line"], 6
                )
                self.assertEqual(
                    result.resume_guard["implementation_tools_after_resume"][0]["line"],
                    9,
                )

        small_result, _, _, small_retained = small
        large_result, _, _, large_retained = large
        self.assertLessEqual(large_retained, small_retained + 512 * 1024)
        small_size = len(json.dumps(small_result.to_dict(), ensure_ascii=False))
        large_size = len(json.dumps(large_result.to_dict(), ensure_ascii=False))
        self.assertLessEqual(large_size, small_size + 4_096)

    def test_event_stream_matches_standalone_bounded_analysis(self):
        path, _ = self._write_adversarial_session(1_000)
        standalone = postmortem_module.analyze_codex_session_jsonl(path).to_dict()

        def envelopes():
            with path.open("r", encoding="utf-8", newline="") as stream:
                for line_number, raw_text in enumerate(stream, start=1):
                    yield SimpleNamespace(
                        source_line=line_number,
                        raw_text=raw_text,
                        event=json.loads(raw_text),
                        duplicate_keys=(),
                        parse_error="",
                    )

        shared_stream = postmortem_module.analyze_codex_session_jsonl(
            path,
            event_stream=envelopes(),
        ).to_dict()

        self.assertEqual(shared_stream, standalone)

    def test_giant_unicode_scalar_metadata_is_byte_bounded_before_retention(self):
        giant = "한" * 100_000
        events = [
            {
                "type": "session_meta",
                "payload": {"id": giant, "cwd": giant},
            },
            self._response({"type": giant, "role": giant}),
            self._response(
                {
                    "type": "thread_goal_updated",
                    "goal": {"status": giant, "objective": giant},
                }
            ),
            self._response(
                {
                    "type": "function_call",
                    "role": giant,
                    "name": giant,
                    "arguments": json.dumps(
                        {"command": "python -m unittest " + giant},
                        ensure_ascii=False,
                    ),
                }
            ),
            self._response(
                {
                    "type": "task_complete",
                    "last_agent_message": giant,
                }
            ),
            self._response(
                {
                    "type": "function_call_output",
                    "output": "Exit code: 1\nFAILED verification " + giant,
                }
            ),
        ]
        features = [
            postmortem_module.extract_postmortem_event_features(event, line_number)
            for line_number, event in enumerate(events, start=1)
        ]

        def retained_strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                for item in value.values():
                    yield from retained_strings(item)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    yield from retained_strings(item)

        for feature in features:
            for retained in retained_strings(asdict(feature)):
                self.assertLessEqual(
                    len(retained.encode("utf-8", errors="replace")),
                    postmortem_module.MAX_POSTMORTEM_SCALAR_BYTES,
                )

        session, unknown, goal, call, completion, output = features
        self.assertLessEqual(len(session.session_id.encode("utf-8")), 4_096)
        self.assertLessEqual(len(session.cwd.encode("utf-8")), 4_096)
        self.assertLessEqual(len(unknown.payload_type.encode("utf-8")), 256)
        self.assertLessEqual(len(unknown.role.encode("utf-8")), 128)
        self.assertLessEqual(len(goal.goal_status.encode("utf-8")), 256)
        self.assertLessEqual(len(goal.goal_objective.encode("utf-8")), 2_048)
        self.assertLessEqual(len(call.role.encode("utf-8")), 128)
        self.assertLessEqual(len(call.call_name.encode("utf-8")), 512)
        self.assertLessEqual(len(call.call_sample_260.encode("utf-8")), 260)
        self.assertLessEqual(len(call.verification_command.encode("utf-8")), 4_096)
        self.assertLessEqual(len(completion.sample_220.encode("utf-8")), 220)
        self.assertLessEqual(len(completion.sample_260.encode("utf-8")), 260)
        failure = dict(output.verification_failure)
        self.assertLessEqual(len(failure["sample"].encode("utf-8")), 300)


if __name__ == "__main__":
    unittest.main()
