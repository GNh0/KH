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

    def test_runtime_mutation_verb_families_are_centrally_authorized(self):
        cases = {
            "Set the KH plugin to 2.9.145.": "set",
            "Switch the KH plugin to 2.9.145.": "switch",
            "Downgrade the KH plugin to 2.9.143.": "downgrade",
            "Sync the KH plugin.": "sync",
            "Pin the KH plugin to 2.9.145.": "pin",
            "Upgrade the KH plugin.": "upgrade",
            "Install the KH plugin.": "install",
        }

        for prompt, expected_verb in cases.items():
            with self.subTest(prompt=prompt):
                analysis = parse_request_act(prompt)
                clause = analysis.clauses[0]
                self.assertIn(expected_verb, clause.action_verbs)
                self.assertTrue(clause.mutating)
                self.assertTrue(clause.authorized)
                self.assertTrue(analysis.has_mutation_authorization)

    def test_bring_up_to_date_distinguishes_mutation_from_status_report(self):
        mutation = parse_request_act("Bring the KH plugin up to date.")
        report = parse_request_act("Bring me up to date on the KH plugin.")

        self.assertEqual(mutation.clauses[0].action_verbs, ("update",))
        self.assertTrue(mutation.has_mutation_authorization)
        self.assertEqual(report.clauses[0].action_verbs, ("report",))
        self.assertFalse(report.has_mutation_authorization)

    def test_runtime_mutation_negation_and_advice_are_not_authorization(self):
        prompts = (
            "Do not downgrade the KH plugin.",
            "Never switch the KH plugin version.",
            "How do I sync the KH plugin?",
            "Should we pin the KH plugin to 2.9.145?",
        )

        for prompt in prompts:
            with self.subTest(prompt=prompt):
                analysis = parse_request_act(prompt)
                self.assertTrue(any(clause.mutating for clause in analysis.clauses))
                self.assertFalse(analysis.has_mutation_authorization)

    def test_korean_completed_runtime_action_is_state_not_authorization(self):
        status = parse_request_act(
            "\uc5c5\ub370\uc774\ud2b8 \ub410\ub294\uc9c0 \ud655\uc778 \uc880"
        )
        command = parse_request_act("\uc5c5\ub370\uc774\ud2b8\ud574\uc918")

        self.assertTrue(status.clauses[0].mutating)
        self.assertFalse(status.has_mutation_authorization)
        self.assertTrue(command.has_mutation_authorization)

    def test_semantic_versions_are_not_misread_as_named_files(self):
        semantic_version = parse_request_act("Set the KH plugin to 2.9.145.")
        source_file = parse_request_act("Check the version in package.json.")

        self.assertNotIn("named_file", semantic_version.clauses[0].scopes)
        self.assertIn("named_file", source_file.clauses[0].scopes)

    def test_explicit_kh_target_is_inherited_only_by_runtime_sequence(self):
        downgrade = parse_request_act(
            "KH가 최신인지 확인한 뒤 2.9.143으로 내려줘."
        )
        readonly = parse_request_act(
            "KH는 업데이트하지 말고 설치된 버전만 알려줘."
        )
        unrelated = parse_request_act(
            "Check KH plugin version, then update the inventory dashboard."
        )

        self.assertEqual(downgrade.clauses[-1].semantic_target, "kh")
        self.assertTrue(downgrade.clauses[-1].runtime_related)
        self.assertEqual(readonly.clauses[-1].semantic_target, "kh")
        self.assertTrue(readonly.clauses[-1].runtime_related)
        self.assertEqual(unrelated.clauses[-1].semantic_target, "other")
        self.assertFalse(unrelated.clauses[-1].runtime_related)

    def test_version_mutation_back_binds_to_explicit_kh_clarification(self):
        analysis = parse_request_act(
            "2.9.145로 바꿔줘. 내가 말한 대상은 KH 플러그인이야."
        )

        self.assertEqual(analysis.clauses[0].semantic_target, "kh")
        self.assertTrue(analysis.clauses[0].runtime_related)

    def test_runtime_mutation_phrase_and_korean_command_families(self):
        cases = (
            ("Roll back the KH plugin to 2.9.143.", "rollback"),
            ("Roll the KH plugin back to 2.9.143.", "rollback"),
            ("KH \ud50c\ub7ec\uadf8\uc778\uc744 2.9.145\ub85c \uc124\uc815\ud574\uc918.", "\uc124\uc815"),
            ("KH \ud50c\ub7ec\uadf8\uc778 \ubc84\uc804\uc744 2.9.145\ub85c \ub9de\ucdb0\uc918.", "\ub9de\ucdb0"),
            ("KH \ud50c\ub7ec\uadf8\uc778 \ubc84\uc804\uc744 \ubc14\uafd4\uc918.", "\ubc14\uafd4"),
            ("KH \ud50c\ub7ec\uadf8\uc778 \ubc84\uc804\uc744 2.9.143\uc73c\ub85c \ub0b4\ub824\uc918.", "\ub0b4\ub824"),
            ("KH \ud50c\ub7ec\uadf8\uc778 \ubc84\uc804\uc744 \uc62c\ub824\uc918.", "\uc62c\ub824"),
            ("KH \ud50c\ub7ec\uadf8\uc778 \ubc84\uc804\uc744 \uace0\uc815\ud574\uc918.", "\uace0\uc815"),
            ("KH \ud50c\ub7ec\uadf8\uc778\uc744 \ub3d9\uae30\ud654\ud574\uc918.", "\ub3d9\uae30\ud654"),
        )

        for prompt, expected_verb in cases:
            with self.subTest(prompt=prompt):
                analysis = parse_request_act(prompt)
                self.assertIn(expected_verb, analysis.clauses[0].action_verbs)
                self.assertTrue(analysis.has_mutation_authorization)

    def test_conditional_and_sequenced_mutation_is_authorized_by_parser(self):
        prompts = (
            "Check the KH plugin version and if stale, upgrade it.",
            "Check the KH plugin version; afterward upgrade it.",
            "Check the KH plugin version. Upgrade it later.",
        )

        for prompt in prompts:
            with self.subTest(prompt=prompt):
                analysis = parse_request_act(prompt)
                self.assertTrue(analysis.has_mutation_authorization)
                self.assertTrue(
                    any(clause.authorized and clause.mutating for clause in analysis.clauses)
                )

    def test_modal_negation_and_nominal_action_words_do_not_authorize(self):
        prompts = (
            "Could you not upgrade the KH plugin?",
            "Commit messages should be clear.",
            "Upgrade notes are missing.",
            "What is a set?",
            "\uc5c5\ub370\uc774\ud2b8\ub77c\ub294 \ub2e8\uc5b4 \ub73b\uc744 \uc124\uba85\ud574\uc918.",
            "\uc124\uce58 \ubbf8\uc220\uc774\ub780 \ubb34\uc5c7\uc778\uac00?",
            "\ucc98\ub9ac \uc131\ub2a5\uc774 \ub290\ub9ac\ub2e4.",
            "\uc124\uc815 \uac12\uc774 \uc774\uc0c1\ud558\ub2e4.",
            "\uc5c5\ub370\uc774\ud2b8 \ub0b4\uc6a9\uc774 \ub204\ub77d\ub410\ub2e4.",
        )

        for prompt in prompts:
            with self.subTest(prompt=prompt):
                analysis = parse_request_act(prompt)
                self.assertFalse(analysis.has_mutation_authorization)

        for prompt in prompts[1:]:
            with self.subTest(contract="nominal", prompt=prompt):
                analysis = parse_request_act(prompt)
                self.assertFalse(any(clause.mutating for clause in analysis.clauses))

    def test_referential_korean_polite_mutation_remains_unresolved_without_context(self):
        analysis = parse_request_act(
            "\uadf8 \uc5c5\ub370\uc774\ud2b8 \ucc98\ub9ac\ud574\uc8fc\uc2e4 \uc218 \uc788\uc744\uae4c\uc694?"
        )

        self.assertTrue(analysis.has_mutation_authorization)
        self.assertTrue(analysis.clauses[0].referential_target)
        self.assertTrue(analysis.unresolved_referential_mutation)

    def test_parenthesized_conditional_connectors_preserve_mutation_authorization(self):
        prompts = (
            "Check the KH plugin version and, if stale, upgrade it.",
            "Check the KH plugin version and (if stale) upgrade it.",
            "Check the KH plugin version and, only if stale, upgrade it.",
            "Check the KH plugin version and (only if stale) upgrade it.",
        )

        for prompt in prompts:
            with self.subTest(prompt=prompt):
                analysis = parse_request_act(prompt)
                self.assertTrue(analysis.has_mutation_authorization)
                self.assertEqual(len(analysis.clauses), 2)

    def test_stable_domain_concepts_and_negated_lookups_are_non_mutating(self):
        conceptual = (
            "Explain installation art.",
            "Explain the concept of installation art.",
            "\uc124\uce58 \ubbf8\uc220\uc758 \uac1c\ub150\uc744 \uc124\uba85\ud574\uc918.",
        )
        for prompt in conceptual:
            with self.subTest(contract="conceptual", prompt=prompt):
                analysis = parse_request_act(prompt)
                self.assertFalse(analysis.has_mutation_authorization)

        for prompt in (
            "Do not check the KH plugin version.",
            "Do not verify whether Git is installed.",
            "Do not read the version from package.json.",
        ):
            with self.subTest(contract="negative-lookup", prompt=prompt):
                analysis = parse_request_act(prompt)
                self.assertFalse(analysis.has_mutation_authorization)
                self.assertTrue(all(clause.negated for clause in analysis.clauses))

    def test_runtime_and_source_mutation_inflections_are_authorized(self):
        prompts = (
            "Synchronize the installed KH plugin with codex-runtime.",
            "Revert KH UAF to 2.9.143 and keep it there.",
            "Make the KH marketplace package current.",
            "KH \ud50c\ub7ec\uadf8\uc778\uc744 2.9.145 \ubc84\uc804\uc73c\ub85c \uc804\ud658\ud574\uc918.",
            "\uc124\uce58\ub41c KH\ub97c 2.9.145 \ub9b4\ub9ac\uc2a4\ub85c \ub9de\ucdb0 \ub194.",
            "KH\ub97c 2.9.143\uc73c\ub85c \ub0b4\ub824\ub194.",
            "Revise the KH README installation paragraph.",
            "Extend the KH classifier test file with a negation case.",
            "KH README\uc758 \uc624\ud504\ub77c\uc778 \uc124\uce58 \uc608\uc2dc\ub97c \ubc14\ub85c\uc7a1\uc544\uc918.",
            "KH \ubd84\ub958\uae30 \ud14c\uc2a4\ud2b8 \ud30c\uc77c\uc5d0 \ubd80\uc815\ubb38 \ucf00\uc774\uc2a4\ub97c \ub123\uc5b4\uc918.",
        )

        for prompt in prompts:
            with self.subTest(prompt=prompt):
                self.assertTrue(parse_request_act(prompt).has_mutation_authorization)

    def test_passive_installed_status_is_not_mutation_authorization(self):
        analysis = parse_request_act(
            "Can you verify whether the installed KH package is already at 2.9.145?"
        )

        self.assertFalse(analysis.has_mutation_authorization)

    def test_decimal_values_do_not_become_runtime_versions(self):
        cases = (
            "Should I update my portfolio target to 60.0% equities?",
            "Upgrade Kubernetes to 1.30.",
            "Change this SQL constant to 2.0.",
        )

        for prompt in cases:
            with self.subTest(prompt=prompt):
                analysis = parse_request_act(prompt)
                self.assertFalse(any(clause.runtime_related for clause in analysis.clauses))

    def test_unrelated_following_mutation_does_not_inherit_prior_runtime_target(self):
        analysis = parse_request_act(
            "Check the Python runtime version. Then update the invoice total to 2.0."
        )

        self.assertEqual(len(analysis.clauses), 2)
        self.assertTrue(analysis.clauses[0].runtime_related)
        self.assertFalse(analysis.clauses[1].runtime_related)
        self.assertEqual(analysis.clauses[1].semantic_target, "other")


if __name__ == "__main__":
    unittest.main()
