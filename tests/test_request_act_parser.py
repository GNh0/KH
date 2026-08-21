import time
import unicodedata
import unittest

from src.orchestration.request_act_parser import parse_request_act


class RequestActParserTests(unittest.TestCase):
    def test_sql_payload_is_separate_from_trailing_outer_execution(self):
        analysis = parse_request_act(
            "Format this SQL: DELETE FROM T; execute it against production."
        )

        self.assertEqual([span.kind for span in analysis.payload_spans], ["sql"])
        self.assertNotIn("delete from t", analysis.outer_text.lower())
        self.assertIn("execute it against production", analysis.outer_text.lower())
        self.assertTrue(analysis.outer_database_execution)
        self.assertTrue(analysis.authorized_high_impact_destructive)

    def test_fenced_alias_delete_is_sql_and_trailing_execution_remains_outer(self):
        analysis = parse_request_act(
            "Review this T-SQL:\n```tsql\nDELETE A FROM Accounts A WHERE A.Disabled = 1\n```\n"
            "Then run it against live."
        )

        self.assertEqual([span.kind for span in analysis.payload_spans], ["sql"])
        self.assertTrue(analysis.sql_payload_is_destructive)
        self.assertIn("run it against live", analysis.outer_text.lower())
        self.assertTrue(analysis.outer_database_execution)
        self.assertTrue(analysis.authorized_high_impact_destructive)

    def test_sql_without_semicolon_stops_before_outer_execution_clause(self):
        analysis = parse_request_act(
            "Format this SQL: DELETE A FROM Orders A WHERE A.Cancelled = 1 "
            "then execute it against staging"
        )

        self.assertTrue(analysis.has_sql_payload)
        self.assertNotIn("execute it", analysis.payload_spans[0].text.lower())
        self.assertIn("execute it against staging", analysis.outer_text.lower())
        self.assertTrue(analysis.outer_database_execution)

    def test_negated_clause_does_not_negate_sequence_continuation(self):
        analysis = parse_request_act(
            "Do not alter the draft; after review, deploy the current application."
        )

        self.assertEqual(len(analysis.clauses), 2)
        self.assertTrue(analysis.clauses[0].negated)
        self.assertFalse(analysis.clauses[0].authorized)
        self.assertEqual(analysis.clauses[1].connector, "sequence")
        self.assertTrue(analysis.clauses[1].authorized)
        self.assertIn("execute", analysis.clauses[1].action_classes)

    def test_korean_adversative_continuation_preserves_outer_command(self):
        analysis = parse_request_act(
            "초안은 수정하지 말고, 검토 후 현재 앱을 배포해 주세요."
        )

        self.assertTrue(analysis.clauses[0].negated)
        self.assertFalse(analysis.clauses[0].authorized)
        self.assertTrue(analysis.clauses[-1].authorized)
        self.assertIn("execute", analysis.clauses[-1].action_classes)

    def test_approval_context_accepts_only_literal_boolean_true(self):
        prompt = "Accepted. Carry out the current patch."

        approved = parse_request_act(prompt, {"execution_approved": True})
        string_value = parse_request_act(prompt, {"execution_approved": "true"})
        integer_value = parse_request_act(prompt, {"execution_approved": 1})

        self.assertIs(approved.context_execution_approved, True)
        self.assertFalse(approved.unresolved_referential_mutation)
        self.assertIsNone(string_value.context_execution_approved)
        self.assertTrue(string_value.unresolved_referential_mutation)
        self.assertIsNone(integer_value.context_execution_approved)
        self.assertTrue(integer_value.unresolved_referential_mutation)

    def test_negated_and_questioned_approval_block_followup_authorization(self):
        for prompt in (
            "This is not approved. Proceed with the current patch.",
            "Is the patch approved? Proceed with the current patch.",
        ):
            with self.subTest(prompt=prompt):
                analysis = parse_request_act(
                    prompt,
                    {"execution_approved": True},
                )
                self.assertTrue(analysis.approval_blocked)
                self.assertTrue(analysis.unresolved_referential_mutation)

    def test_pending_approval_language_blocks_followup_authorization(self):
        for prompt in (
            "Approval is still pending. Proceed with the current patch.",
            "승인 대기 중입니다. 현재 패치를 반영해 주세요.",
        ):
            with self.subTest(prompt=prompt):
                analysis = parse_request_act(prompt, {"execution_approved": True})
                self.assertTrue(analysis.approval_blocked)
                self.assertTrue(analysis.unresolved_referential_mutation)

    def test_arbitrary_adverb_destructive_imperative_uses_action_and_scope(self):
        analysis = parse_request_act(
            "Permanently delete all production customer records."
        )
        clause = analysis.clauses[0]

        self.assertTrue(clause.authorized)
        self.assertIn("destructive", clause.action_classes)
        self.assertIn("database", clause.target_classes)
        self.assertEqual(clause.scopes & {"all", "production"}, {"all", "production"})
        self.assertTrue(analysis.authorized_high_impact_destructive)

    def test_unknown_high_impact_predicates_fail_closed_by_scope_and_speech_act(self):
        prompts = (
            "Please irreversibly obliterate every production Kubernetes namespace.",
            "Kindly vaporize all cloud resources in the live environment.",
            "운영 쿠버네티스 네임스페이스를 전부 초토화해 주세요.",
        )

        for prompt in prompts:
            with self.subTest(prompt=prompt):
                analysis = parse_request_act(prompt)
                self.assertTrue(analysis.authorized_high_impact_destructive)

    def test_readonly_source_question_does_not_request_credential_access(self):
        analysis = parse_request_act(
            "Inspect whether the current source reads credentials during authentication; "
            "report only and do not edit."
        )

        self.assertTrue(analysis.readonly_inspection)
        self.assertFalse(analysis.has_mutation_authorization)
        self.assertFalse(analysis.credential_access_requested)

    def test_quoted_advisory_destructive_language_is_nonexecuting(self):
        analysis = parse_request_act(
            'Explain why "drop the production database" requires approval; '
            "do not execute it."
        )

        self.assertFalse(analysis.has_mutation_authorization)
        self.assertTrue(analysis.nonexecuting_destructive_discussion)

    def test_curly_quoted_korean_wording_with_nonexecution_is_advisory(self):
        analysis = parse_request_act(
            "문구 “운영 네임스페이스를 전부 초토화해”가 왜 위험한지 설명만 해줘. "
            "실행 요청은 아니야."
        )

        self.assertFalse(analysis.has_mutation_authorization)
        self.assertTrue(analysis.nonexecuting_destructive_discussion)

    def test_decomposed_korean_is_normalized_before_classification(self):
        prompt = unicodedata.normalize(
            "NFD",
            "운영 쿠버네티스 네임스페이스를 전부 초토화해 주세요.",
        )
        analysis = parse_request_act(prompt)

        self.assertEqual(analysis.text, unicodedata.normalize("NFKC", prompt))
        self.assertTrue(analysis.authorized_high_impact_destructive)

    def test_many_literal_spans_are_merged_with_bounded_runtime(self):
        prompt = "Explain only: " + " ".join(
            f"`sample_{index}`" for index in range(5000)
        )

        started = time.perf_counter()
        analysis = parse_request_act(prompt)
        elapsed = time.perf_counter() - started

        self.assertEqual(len(analysis.payload_spans), 5000)
        self.assertLess(elapsed, 2.5)

    def test_named_noncritical_file_removal_is_governed_not_high_impact(self):
        analysis = parse_request_act(
            "Remove the named local file temp_notes.txt from this project."
        )

        self.assertTrue(analysis.has_mutation_authorization)
        self.assertIn("named_file", analysis.clauses[0].scopes)
        self.assertFalse(analysis.authorized_high_impact_destructive)


if __name__ == "__main__":
    unittest.main()
