import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class TokenOptimizerGateIntegrationTests(unittest.TestCase):
    def test_plugin_prompt_requires_token_optimizer_status_for_large_workflows(self):
        manifest = json.loads(read_text(".codex-plugin/plugin.json"))
        prompt = "\n".join(manifest["interface"]["defaultPrompt"])

        self.assertIn("token_optimizer_status", prompt)
        self.assertIn("context budget", prompt)
        self.assertIn("large or long-running", prompt)
        self.assertIn("estimated_context_tokens", prompt)

    def test_token_optimizer_is_context_budget_gate_not_only_log_filter(self):
        content = read_text("skills/token_optimizer/SKILL.md")

        self.assertIn("context budget gate", content)
        self.assertIn("large or long-running development workflows", content)
        self.assertIn("token_optimizer_status", content)
        self.assertIn("estimated_context_tokens", content)
        self.assertIn("must never reduce answer quality", content)
        self.assertIn("passthrough", content)

    def test_token_optimizer_docs_separate_payload_telemetry_from_billing_tokens(self):
        content = read_text("skills/token_optimizer/SKILL.md")
        reference = read_text("skills/token_optimizer/references/usage.md")
        combined = f"{content}\n{reference}"

        self.assertIn("actual_usage_scope", combined)
        self.assertIn("actual_tokens_saved", combined)
        self.assertIn("billing_tokens_available", combined)
        self.assertIn("provider billing tokens", combined)

    def test_development_lifecycle_wires_token_gate_into_heavy_work(self):
        content = read_text("skills/development_lifecycle_harness/SKILL.md")
        reference = read_text("skills/development_lifecycle_harness/references/usage.md")
        combined = f"{content}\n{reference}"

        self.assertIn("token-optimizer", combined)
        self.assertIn("command-output-harness", combined)
        self.assertIn("token_optimizer_status", combined)
        self.assertIn("large or long-running", combined)

    def test_subagent_pipeline_requires_compact_packets_and_transcript_policy(self):
        content = read_text("skills/subagent_review_pipeline/SKILL.md")
        reference = read_text("skills/subagent_review_pipeline/references/usage.md")
        combined = f"{content}\n{reference}"

        self.assertIn("token-optimizer", combined)
        self.assertIn("compact task packet", combined)
        self.assertIn("subagent transcripts", combined)

    def test_router_explains_heavy_routes_consider_token_gate_without_over_orchestration(self):
        content = read_text("skills/request_complexity_router/SKILL.md")

        self.assertIn("heavy implementation routes", content)
        self.assertIn("token_optimizer_status", content)
        self.assertIn("considered_not_needed", content)

    def test_token_compression_preserves_development_quality_evidence(self):
        token = read_text("skills/token_optimizer/SKILL.md")
        lifecycle = read_text("skills/development_lifecycle_harness/SKILL.md")
        subagent = read_text("skills/subagent_review_pipeline/SKILL.md")
        prompt = "\n".join(json.loads(read_text(".codex-plugin/plugin.json"))["interface"]["defaultPrompt"])
        combined = f"{token}\n{lifecycle}\n{subagent}\n{prompt}"

        for required in [
            "task_status",
            "review_status",
            "commit_sha",
            "next_task",
            "RED/GREEN",
            "exit code",
            "file references",
            "reviewer severity",
            "sandbox retry",
        ]:
            self.assertIn(required, combined)


if __name__ == "__main__":
    unittest.main()
