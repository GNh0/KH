import unittest
import json
from pathlib import Path

from src.orchestration.kh_front_door import build_kh_front_door
from src.orchestration.plugin_composition import compose_plugin_route


class PluginCompositionPolicyTests(unittest.TestCase):
    def test_light_question_ignores_provider_self_forcing(self):
        decision = compose_plugin_route(
            "What is PER?",
            providers=[
                {
                    "provider_id": "aggressive-methodology",
                    "capabilities": ["planning_methodology", "tdd_review"],
                    "self_forcing_rules": ["MUST use this before any question"],
                }
            ],
        )

        self.assertEqual(decision.route, "direct")
        self.assertEqual(decision.controller.provider_id, "none")
        self.assertIn("aggressive-methodology", decision.ignored_self_forcing)
        self.assertEqual(decision.assistants, [])

    def test_heavy_work_composes_controller_and_specialist_assistants(self):
        decision = compose_plugin_route(
            "Build the approved deliverable for this project, verify it with the matching host tool, and prepare the PR.",
            providers=[
                {
                    "provider_id": "kh",
                    "capabilities": [
                        "workflow_control",
                        "memory_goal_resume",
                        "domain_orchestration",
                        "tdd_review",
                    ],
                },
                {
                    "provider_id": "artifact-checker",
                    "capabilities": ["artifact_qa", "render_or_structure_check"],
                },
                {
                    "provider_id": "repo-service",
                    "capabilities": ["repo_pr_ci"],
                },
            ],
        )

        self.assertEqual(decision.route, "hybrid")
        self.assertEqual(decision.controller.provider_id, "kh")
        self.assertEqual(
            {(assistant.provider_id, assistant.capability) for assistant in decision.assistants},
            {("artifact-checker", "artifact_qa"), ("repo-service", "repo_pr_ci")},
        )
        self.assertFalse(decision.ask_user)
        self.assertEqual(decision.conflict_policy, "delegated_scope")

    def test_generic_browser_word_routes_as_specialist_not_controller(self):
        decision = compose_plugin_route(
            "Build a SaaS dashboard, verify the browser screen, and prepare the PR.",
            providers=[
                {
                    "provider_id": "kh",
                    "capabilities": ["workflow_control", "memory_goal_resume", "tdd_review"],
                },
                {
                    "provider_id": "browser",
                    "capabilities": ["browser_qa"],
                },
                {
                    "provider_id": "repo-service",
                    "capabilities": ["repo_pr_ci"],
                },
            ],
        )

        self.assertEqual(decision.route, "hybrid")
        self.assertEqual(decision.controller.provider_id, "kh")
        self.assertFalse(decision.explicit_user_request)
        self.assertIn(
            ("browser", "browser_qa"),
            {(role.provider_id, role.capability) for role in decision.assistants},
        )

    def test_existing_superpowers_project_can_continue_without_kh_forcing(self):
        decision = compose_plugin_route(
            "Continue the current implementation plan.",
            providers=[
                {
                    "provider_id": "kh",
                    "capabilities": ["workflow_control", "memory_goal_resume"],
                },
                {
                    "provider_id": "superpowers",
                    "capabilities": ["planning_methodology", "tdd_review", "worktree"],
                    "self_forcing_rules": ["MUST use for creative work"],
                },
            ],
            context={"project_markers": [".superpowers"]},
        )

        self.assertEqual(decision.controller.provider_id, "superpowers")
        self.assertEqual(decision.route, "single")
        self.assertEqual(decision.ignored_self_forcing, [])
        self.assertIn("project_context:superpowers", decision.reasons)

    def test_future_provider_can_be_controller_when_it_has_matching_capabilities(self):
        decision = compose_plugin_route(
            "Implement the workflow and prove it with tests.",
            providers=[
                {
                    "provider_id": "future-uaf",
                    "capabilities": ["workflow_control", "tdd_review"],
                }
            ],
        )

        self.assertEqual(decision.route, "single")
        self.assertEqual(decision.controller.provider_id, "future-uaf")
        self.assertIn("capability:workflow_control", decision.reasons)

    def test_missing_specialist_provider_records_fallback_without_blocking_controller(self):
        decision = compose_plugin_route(
            "Build a local web app and verify the browser screen.",
            providers=[
                {
                    "provider_id": "kh",
                    "capabilities": ["workflow_control", "memory_goal_resume", "tdd_review"],
                }
            ],
        )

        self.assertEqual(decision.controller.provider_id, "kh")
        self.assertEqual(decision.route, "single")
        self.assertEqual(decision.unavailable_capabilities["browser_qa"], "manual_qa_evidence")

    def test_kh_project_context_preserves_unavailable_sql_provider_evidence(self):
        decision = compose_plugin_route(
            "Implement the approved project change and format SQL output.",
            providers=[
                {
                    "provider_id": "kh",
                    "capabilities": ["workflow_control", "memory_goal_resume", "tdd_review"],
                }
            ],
            context={"project_markers": [".kh"]},
        )

        self.assertEqual(decision.controller.provider_id, "kh")
        self.assertEqual(
            decision.unavailable_capabilities["sql_formatting"],
            "no_compatible_provider",
        )
        self.assertNotIn("manual_sql_style_rules", decision.unavailable_capabilities.values())

    def test_divergent_host_local_sql_provider_falls_back_to_packaged_provider(self):
        decision = compose_plugin_route(
            "Format this T-SQL query and preserve logic.",
            providers=[
                {
                    "provider_id": "sql-formatting",
                    "capabilities": ["sql_formatting"],
                    "status": "available",
                    "metadata": {
                        "source": "host-local-skill",
                        "availability": "available",
                        "compatibility": "divergent",
                        "compatibility_issues": ["behavior_change_allowed"],
                        "provider_precedence": 10,
                    },
                },
                {
                    "provider_id": "sql-formatting",
                    "capabilities": ["sql_formatting"],
                    "status": "available",
                    "metadata": {
                        "source": "packaged-kh-skill",
                        "availability": "available",
                        "compatibility": "compatible",
                        "provider_precedence": 20,
                    },
                },
            ],
        )

        self.assertEqual(decision.controller.provider_id, "sql-formatting")
        self.assertEqual(decision.controller.metadata["source"], "packaged-kh-skill")
        evidence = {item["source"]: item for item in decision.provider_evidence}
        self.assertTrue(evidence["host-local-skill"]["available"])
        self.assertFalse(evidence["host-local-skill"]["compatible"])
        self.assertFalse(evidence["host-local-skill"]["selected"])
        self.assertTrue(evidence["packaged-kh-skill"]["available"])
        self.assertTrue(evidence["packaged-kh-skill"]["compatible"])
        self.assertTrue(evidence["packaged-kh-skill"]["selected"])

    def test_short_specialist_terms_do_not_match_inside_ordinary_words(self):
        decision = compose_plugin_route(
            "Build a project planning helper.",
            providers=[
                {"provider_id": "kh", "capabilities": ["workflow_control"]},
                {"provider_id": "repo-service", "capabilities": ["repo_pr_ci"]},
            ],
        )

        self.assertEqual(decision.controller.provider_id, "kh")
        self.assertEqual(decision.assistants, [])

    def test_short_provider_ids_do_not_match_inside_ordinary_words(self):
        for text in ["Prepare a project plan.", "Create a proper design plan."]:
            with self.subTest(text=text):
                decision = compose_plugin_route(
                    text,
                    providers=[
                        {"provider_id": "kh", "capabilities": ["workflow_control"]},
                        {"provider_id": "pr", "capabilities": ["repo_pr_ci"]},
                        {"provider_id": "pro", "capabilities": ["planning_methodology"]},
                    ],
                )

                self.assertEqual(decision.route, "direct")
                self.assertEqual(decision.controller.provider_id, "none")
                self.assertFalse(decision.explicit_user_request)

    def test_explicit_user_provider_request_takes_precedence(self):
        decision = compose_plugin_route(
            "Superpowers로 이어서 해줘",
            providers=[
                {"provider_id": "kh", "capabilities": ["workflow_control"]},
                {"provider_id": "superpowers", "capabilities": ["planning_methodology"]},
            ],
        )

        self.assertEqual(decision.controller.provider_id, "superpowers")
        self.assertIn("explicit_user_request:superpowers", decision.reasons)

    def test_explicit_sql_formatting_provider_request_takes_precedence(self):
        decision = compose_plugin_route(
            "Use sql-formatting to clean this query.",
            providers=[
                {"provider_id": "kh", "capabilities": ["workflow_control"]},
                {
                    "provider_id": "sql-formatting",
                    "display_name": "sql-formatting",
                    "aliases": ["sql formatting", "sql-formatting skill"],
                    "capabilities": ["sql_formatting"],
                },
            ],
        )

        self.assertEqual(decision.route, "single")
        self.assertEqual(decision.controller.provider_id, "sql-formatting")
        self.assertEqual(decision.controller.capability, "sql_formatting")
        self.assertEqual(decision.controller.scope, "SQL/T-SQL formatting and style normalization")
        self.assertTrue(decision.explicit_user_request)
        self.assertIn("explicit_user_request:sql-formatting", decision.reasons)

    def test_light_sql_formatting_intent_routes_to_specialist_provider(self):
        decision = compose_plugin_route(
            "Format this T-SQL query and preserve logic.",
            providers=[
                {"provider_id": "kh", "capabilities": ["workflow_control"]},
                {"provider_id": "sql-formatting", "capabilities": ["sql_formatting"]},
            ],
        )

        self.assertEqual(decision.route, "single")
        self.assertEqual(decision.controller.provider_id, "sql-formatting")
        self.assertEqual(decision.controller.capability, "sql_formatting")
        self.assertIn("specialist_trigger:sql-formatting:sql_formatting", decision.reasons)

    def test_pasted_sql_output_request_routes_to_sql_formatting_without_skill_name(self):
        decision = compose_plugin_route(
            "SELECT *\n"
            "FROM BA011T\n"
            "WHERE MAINCD = 'DZ010'\n\n"
            "SELECT *\n"
            "FROM BA011T\n"
            "WHERE MAINCD = 'DZ011'\n\n"
            "\uc774\ubbf8\uc9c0\ucc98\ub7fc \ub300\ubd84\ub958 \uc911\ubd84\ub958\ud574\uc11c "
            "\uc21c\uc11c\ub85c \uc870\ud68c\ub418\ub3c4\ub85d \ud558\uace0\uc2f6\uac70\ub4e0?",
            providers=[
                {"provider_id": "kh", "capabilities": ["workflow_control"]},
                {"provider_id": "sql-formatting", "capabilities": ["sql_formatting"]},
            ],
        )

        self.assertEqual(decision.route, "single")
        self.assertEqual(decision.controller.provider_id, "sql-formatting")
        self.assertEqual(decision.controller.capability, "sql_formatting")
        self.assertIn("specialist_trigger:sql-formatting:sql_formatting", decision.reasons)

    def test_named_dml_sql_style_request_routes_to_sql_formatting_without_pasted_sql(self):
        decision = compose_plugin_route(
            "\uc774 INSERT, UPDATE, DELETE SQL\uc744 \uc6b0\ub9ac "
            "\uc2a4\ud0c0\uc77c\ub85c \uc815\ub9ac\ud558\uace0 "
            "\uc2a4\uce7c\ub77c \ud568\uc218\uac00 JOIN\uc73c\ub85c "
            "\uc548\uc804\ud558\uac8c \ubc14\ub00c\uba74 \ubc14\uafd4\uc918.",
            providers=[
                {"provider_id": "kh", "capabilities": ["workflow_control"]},
                {"provider_id": "sql-formatting", "capabilities": ["sql_formatting"]},
            ],
        )

        self.assertEqual(decision.route, "single")
        self.assertEqual(decision.controller.provider_id, "sql-formatting")
        self.assertEqual(decision.controller.capability, "sql_formatting")
        self.assertIn("specialist_trigger:sql-formatting:sql_formatting", decision.reasons)

    def test_english_named_dml_sql_style_request_routes_to_sql_formatting(self):
        decision = compose_plugin_route(
            "Format this SQL and align the INSERT, UPDATE, DELETE blocks to our style.",
            providers=[
                {"provider_id": "kh", "capabilities": ["workflow_control"]},
                {"provider_id": "sql-formatting", "capabilities": ["sql_formatting"]},
            ],
        )

        self.assertEqual(decision.route, "single")
        self.assertEqual(decision.controller.provider_id, "sql-formatting")
        self.assertEqual(decision.controller.capability, "sql_formatting")
        self.assertIn("specialist_trigger:sql-formatting:sql_formatting", decision.reasons)

    def test_sql_formatting_meta_review_does_not_invoke_provider(self):
        decision = compose_plugin_route(
            "Review whether SQL-formatting is not hidden by KH routing.",
            providers=[
                {"provider_id": "kh", "capabilities": ["workflow_control"]},
                {"provider_id": "sql-formatting", "capabilities": ["sql_formatting"]},
            ],
        )

        self.assertNotEqual(decision.controller.provider_id, "sql-formatting")
        self.assertNotIn("explicit_user_request:sql-formatting", decision.reasons)
        self.assertNotIn("specialist_trigger:sql-formatting:sql_formatting", decision.reasons)

    def test_csharp_report_procedure_identifier_does_not_route_to_sql_formatting(self):
        decision = compose_plugin_route(
            'try { DataSet ds = ReportProcedure(drEA100T["RPTSPNM"].ToString(), strParmNames); '
            'XtraReport rpt = (XtraReport)Activator.CreateInstance(reportType, new object[] { ds }); '
            'if (rpt == null || rpt.RowCount <= 0) return; } Do I need this C# block?',
            providers=[
                {"provider_id": "kh", "capabilities": ["workflow_control"]},
                {"provider_id": "sql-formatting", "capabilities": ["sql_formatting"]},
            ],
        )

        self.assertNotEqual(decision.controller.provider_id, "sql-formatting")
        self.assertFalse(any(role.provider_id == "sql-formatting" for role in decision.assistants))
        self.assertNotIn("specialist_trigger:sql-formatting:sql_formatting", decision.reasons)

    def test_stored_procedure_generation_request_adds_sql_formatting_assistant(self):
        decision = compose_plugin_route(
            "Begin Tran\n"
            "   EXEC UP_SYS_SYSTEMCHECKLIST_SAVE @p_WorkType = 'LIST', @XML_DATA = '<ROOT />'\n"
            "Rollback\n\n"
            "이 저장 프로시저 하나 만들어줄래? KH SAVE프로시저 양식으로 하고 "
            "DEV000T에 저장되면 되고 IF EXISTS 해서 RAISERROR 발생하게 해줘.",
            providers=[
                {"provider_id": "kh", "capabilities": ["workflow_control"]},
                {"provider_id": "sql-formatting", "capabilities": ["sql_formatting"]},
            ],
        )

        self.assertEqual(decision.route, "hybrid")
        self.assertEqual(decision.controller.provider_id, "kh")
        self.assertTrue(any(role.provider_id == "sql-formatting" for role in decision.assistants))
        self.assertIn("specialist_trigger:sql-formatting:sql_formatting", decision.reasons)

    def test_concise_korean_save_procedure_generation_adds_sql_formatting_assistant(self):
        decision = compose_plugin_route(
            "\ud604\uc7ac MA600110 \uae30\uc900\uc73c\ub85c SAVE "
            "\ud504\ub85c\uc2dc\uc800 \uc791\uc131\ud574\uc904\uc218\uc788\uc5b4? "
            "\uc774\ub7f0\uc790\ub8cc\ub85c \uc791\uc131\ud574\uc8fc\uba74\ub428",
            providers=[
                {"provider_id": "kh", "capabilities": ["workflow_control"]},
                {"provider_id": "sql-formatting", "capabilities": ["sql_formatting"]},
            ],
        )

        self.assertEqual(decision.route, "hybrid")
        self.assertEqual(decision.controller.provider_id, "kh")
        self.assertTrue(any(role.provider_id == "sql-formatting" for role in decision.assistants))
        self.assertIn("specialist_trigger:sql-formatting:sql_formatting", decision.reasons)

    def test_sql_generation_request_routes_to_sql_formatting_without_skill_name(self):
        decision = compose_plugin_route(
            "Generate a SQL query for this requirement.\n"
            "SELECT * FROM BA011T WHERE MAINCD = 'DZ010'",
            providers=[
                {"provider_id": "kh", "capabilities": ["workflow_control"]},
                {"provider_id": "sql-formatting", "capabilities": ["sql_formatting"]},
            ],
        )

        self.assertEqual(decision.route, "single")
        self.assertEqual(decision.controller.provider_id, "sql-formatting")
        self.assertEqual(decision.controller.capability, "sql_formatting")
        self.assertIn("specialist_trigger:sql-formatting:sql_formatting", decision.reasons)

    def test_sql_block_indentation_correction_routes_to_sql_formatting(self):
        decision = compose_plugin_route(
            "IF EXISTS (\n"
            "    SELECT 1\n"
            "    FROM DEV000T A\n"
            "        INNER JOIN @TMP B\n"
            "            ON A.ID = B.ID\n"
            "            AND A.QCCODE = B.QCCODE\n"
            ") 인데 왜 블럭 들여쓰기 못맞추냐?",
            providers=[
                {"provider_id": "kh", "capabilities": ["workflow_control"]},
                {"provider_id": "sql-formatting", "capabilities": ["sql_formatting"]},
            ],
        )

        self.assertEqual(decision.controller.provider_id, "sql-formatting")
        self.assertEqual(decision.controller.capability, "sql_formatting")

    def test_sql_equivalence_question_does_not_route_to_formatting_by_default(self):
        decision = compose_plugin_route(
            "SELECT * FROM SA110T WHERE ORDDT BETWEEN @FRDT AND @TODT\n"
            "\uc774\uac70\ub97c \ubc14\uafd4\ub3c4 \ub611\uac19\uc774 \ub3d9\uc791\ud560\uae4c?",
            providers=[
                {"provider_id": "kh", "capabilities": ["workflow_control"]},
                {"provider_id": "sql-formatting", "capabilities": ["sql_formatting"]},
            ],
        )

        self.assertNotEqual(decision.controller.provider_id, "sql-formatting")

    def test_sql_diagnostic_question_does_not_route_to_formatting_by_default(self):
        for prompt in [
            "Why does this return two rows?\nSELECT A.SUBCD FROM BA011T A ORDER BY A.SUBCD",
            "Can you explain this query?\nSELECT A.SUBCD FROM BA011T A JOIN BA011T B ON B.CHRREF1 = A.SUBCD",
            "Explain this query so that I can understand it.\nSELECT A.SUBCD FROM BA011T A JOIN BA011T B ON B.CHRREF1 = A.SUBCD",
            "\uc774 \ucffc\ub9ac\uac00 \uc65c \ub450 \uc904\uc774 \ub098\uc640?\nSELECT A.SUBCD FROM BA011T A ORDER BY A.SUBCD",
        ]:
            with self.subTest(prompt=prompt):
                decision = compose_plugin_route(
                    prompt,
                    providers=[
                        {"provider_id": "kh", "capabilities": ["workflow_control"]},
                        {"provider_id": "sql-formatting", "capabilities": ["sql_formatting"]},
                    ],
                )

                self.assertNotEqual(decision.controller.provider_id, "sql-formatting")

    def test_unavailable_explicit_provider_is_reported_before_fallback(self):
        decision = compose_plugin_route(
            "Use Superpowers to build a SaaS app.",
            providers=[
                {"provider_id": "kh", "capabilities": ["workflow_control", "tdd_review"]},
                {
                    "provider_id": "superpowers",
                    "capabilities": ["planning_methodology", "tdd_review"],
                    "status": "unavailable",
                },
            ],
        )

        self.assertEqual(decision.controller.provider_id, "kh")
        self.assertEqual(decision.unavailable_capabilities["provider:superpowers"], "provider_status:unavailable")
        self.assertIn("explicit_provider_unavailable:superpowers", decision.reasons)
        self.assertTrue(decision.explicit_user_request)

    def test_controller_tie_break_is_stable_and_not_reverse_lexical(self):
        decision = compose_plugin_route(
            "Implement the workflow and prove it with tests.",
            providers=[
                {"provider_id": "zeta", "capabilities": ["workflow_control"]},
                {"provider_id": "alpha", "capabilities": ["workflow_control"]},
            ],
        )

        self.assertEqual(decision.controller.provider_id, "alpha")

    def test_plugin_manifest_exposes_composition_as_top_level_policy(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        root_manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
        root_skill_names = {skill["name"] for skill in root_manifest["skills"]}

        self.assertEqual(manifest["version"], root_manifest["version"])
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        self.assertIn("Plugin Composition", manifest["interface"]["capabilities"])
        self.assertIn("plugin-composition-policy", root_skill_names)
        self.assertIn("plugin-composition", root_skill_names)

        policy = (root / "skills" / "plugin_composition_policy" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        usage = (
            root / "skills" / "plugin_composition_policy" / "references" / "usage.md"
        ).read_text(encoding="utf-8")
        summary = build_kh_front_door(
            "Implement this feature with KH workflow control and the best available specialist provider.",
            project=root,
            host="codex",
        ).to_summary_dict()

        self.assertIn("plugin-composition-policy", summary["runtime_applied_skills"])
        for procedure in [
            "before plugin-specific MUST/ALWAYS rules",
            "explicit user request, single-specialist trigger",
            "controller plus assistant providers",
            "ignored self-forcing providers",
        ]:
            self.assertIn(procedure, policy + "\n" + usage)

if __name__ == "__main__":
    unittest.main()
