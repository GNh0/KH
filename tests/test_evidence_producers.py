import unittest

from src.contracts import WorkflowTaskResult
from src.orchestration.evidence_producers import (
    collect_metadata_evidence,
    command_result_evidence,
    qa_result_evidence,
    review_result_evidence,
)
from src.tasks.workflows import _task_result_evidence


class EvidenceProducerTests(unittest.TestCase):
    def test_command_result_evidence_emits_custom_key_for_success(self):
        record = command_result_evidence(
            command="python -m unittest",
            exit_code=0,
            evidence_key="Tests Passed",
        )

        self.assertEqual(record.status, "passed")
        self.assertEqual(record.evidence, ["tests passed"])
        self.assertEqual(record.metadata["command"], "python -m unittest")
        self.assertEqual(record.metadata["exit_code"], 0)

    def test_failed_command_result_records_details_without_granting_evidence(self):
        record = command_result_evidence(
            command="python -m unittest",
            exit_code=1,
            evidence_key="tests passed",
            stderr="failed",
        )

        self.assertEqual(record.status, "failed")
        self.assertEqual(record.evidence, [])
        self.assertEqual(record.metadata["stderr"], "failed")

    def test_review_and_qa_records_emit_goal_evidence_keys(self):
        review = review_result_evidence(
            role="code-quality-reviewer",
            passed=True,
            evidence_key="review passed",
        )
        qa = qa_result_evidence(
            passed=True,
            evidence_key="qa passed",
            checks=["unit tests"],
        )

        self.assertEqual(review.evidence, ["review passed"])
        self.assertEqual(qa.evidence, ["qa passed"])
        self.assertEqual(qa.metadata["checks"], ["unit tests"])

    def test_collect_metadata_evidence_reads_flat_and_record_evidence(self):
        metadata = {
            "evidence": [" Design Doc "],
            "evidence_records": [
                command_result_evidence(
                    command="python -m unittest",
                    exit_code=0,
                    evidence_key="Tests Passed",
                ).to_dict(),
                {"evidence": ["QA Passed", ""]},
            ],
        }

        self.assertEqual(
            collect_metadata_evidence(metadata),
            ["design doc", "tests passed", "qa passed"],
        )

    def test_workflow_task_evidence_consumes_producer_records(self):
        task_result = WorkflowTaskResult(
            task_id="task_main_py",
            file_name="main.py",
            role="implementer",
            status="success",
            metadata={
                "evidence_records": [
                    command_result_evidence(
                        command="python -m unittest",
                        exit_code=0,
                        evidence_key="tests passed",
                    ).to_dict()
                ]
            },
        )

        self.assertEqual(_task_result_evidence([task_result]), ["tests passed"])


if __name__ == "__main__":
    unittest.main()
