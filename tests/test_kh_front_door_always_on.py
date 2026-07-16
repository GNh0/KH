import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.orchestration.kh_front_door import SkillSource, build_kh_front_door
from src.orchestration.plugin_composition import compose_plugin_route
from src.orchestration.request_classifier import classify_request
from src.orchestration.session_skill_audit import analyze_session_skills
from src.skills.uaf_skill_catalog import collect_packaged_skills


class AlwaysOnFrontDoorTests(unittest.TestCase):
    def write_session(self, events):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "session.jsonl"
        lines = [
            json.dumps(
                {
                    "type": "session_meta",
                    "payload": {"id": "always-on-front-door-test", "cwd": str(Path(tmp.name))},
                }
            )
        ]
        lines.extend(json.dumps(event) for event in events)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def write_host_sql_formatting_skill(self, codex_home, content=None):
        skill_path = Path(codex_home) / "skills" / "sql-formatting" / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        skill_path.write_text(
            content
            or """---
name: sql-formatting
description: Format SQL and T-SQL while preserving query behavior and semantics.
---

# SQL Formatting

Do not change query behavior or results.
Convert scalar lookups only when their implementation and relational equivalence are verified.
Run the packaged `sql-formatting-style-harness` deterministic verifier and accept only passing output.
""",
            encoding="utf-8",
        )
        return skill_path

    def write_packaged_skill(self, skills_root, skill_name, *, valid=True):
        skill_path = Path(skills_root) / skill_name.replace("-", "_") / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        description = (
            f"Use when the {skill_name} contract is selected."
            if valid
            else "Invalid trigger description."
        )
        skill_path.write_text(
            f"""---
name: {skill_name}
description: {description}
---

# {skill_name}

## KH Entry Contract
Apply only after routing selects this skill.

## Workflow
Run the selected contract.

## Required outputs
Record deterministic evidence.

## Common mistakes
Do not claim unexecuted work.

## UAF implementation targets
- tests
""",
            encoding="utf-8",
        )
        return skill_path

    def test_always_on_front_door_runs_for_ordinary_work_without_kh_terms(self):
        request = "Build a small HTML dashboard in this folder and verify it."
        classification = classify_request(request, {"host": "codex"})
        route = compose_plugin_route(
            request,
            providers=[
                {
                    "provider_id": "kh",
                    "capabilities": ["workflow_control", "memory_goal_resume", "domain_orchestration"],
                }
            ],
            context={"host": "codex"},
        )
        catalog = collect_packaged_skills()
        result = build_kh_front_door(request, project=Path.cwd(), host="codex")
        summary = result.to_summary_dict()

        self.assertEqual(classification.complexity, "heavy")
        self.assertEqual(route.controller.provider_id, "kh")
        self.assertIn("always-on-front-door", {skill["name"] for skill in catalog["skills"]})
        self.assertEqual(summary["front_door_status"], "ok")
        self.assertEqual(
            summary["runtime_applied_skills"],
            [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
                "token-optimizer",
            ],
        )
        self.assertEqual(summary["skill_status_summary"]["token-optimizer"]["status"], "applied")
        self.assertIn("estimated_payload_tokens_before", summary["token_optimizer_decision"])
        self.assertIn("verification-before-completion-harness", summary["selected_not_executed_skills"])

    def test_runtime_front_door_status_defers_host_ordering_claim_to_session_audit(self):
        result = build_kh_front_door("1+1?", project=Path.cwd(), host="codex")

        status = result.skill_statuses["always-on-front-door"]
        evidence_note = status["evidence_note"].lower()
        self.assertEqual(status["status"], "applied")
        self.assertIn("current invocation executed kh intake", evidence_note)
        self.assertIn("ordering requires session audit", evidence_note)
        self.assertNotIn("forced", evidence_note)

    def test_new_korean_web_product_request_blocks_until_brainstorming(self):
        request = (
            r"C:\Users\KONEIT\Desktop\Jang\asdfasdf "
            "\uc774 \uacbd\ub85c\uc5d0 \uc77c\uc815,\ud68c\uc758\ub85d\uc744 "
            "\uc815\ub9ac\ud558\ub294 \uc6f9 \ud648\ud398\uc774\uc9c0\ub97c "
            "\ud558\ub098 \ub9cc\ub4e4\uace0\uc2f6\ub124 pdf\ub97c \uc62c\ub9ac\uba74 "
            "pdf\uc758 \ub0b4\uc6a9\uc774 \uadf8\ub300\ub85c \uc800\uc7a5\ub418\uace0 \ud558\ub294"
        )

        classification = classify_request(request, {"host": "codex"})
        result = build_kh_front_door(
            request,
            project=r"C:\Users\KONEIT\Desktop\Jang\asdfasdf",
            host="codex",
        )
        summary = result.to_summary_dict()

        self.assertEqual(classification.recommended_execution, "skill_read")
        self.assertIn("brainstorming-harness", classification.required_harnesses)
        self.assertFalse(summary["execution_gate"]["can_execute"])
        self.assertEqual(summary["execution_gate"]["status"], "blocked_until_brainstorming_handoff")
        self.assertIn("MEMORY.md_lookup", summary["execution_gate"]["blocked_actions"])
        self.assertIn("brainstorming-harness", summary["immediate_next_skills"])
        self.assertNotIn("brainstorming-harness", summary["selected_not_executed_skills"])

    def test_new_korean_web_product_request_without_pdf_still_brainstorms(self):
        request = (
            r"C:\Users\KONEIT\Desktop\Jang\asdfasdf "
            "\uacbd\ub85c\uc5d0 \uc77c\uc815,\ud68c\uc758\ub85d\uc744 "
            "\uc815\ub9ac\ud558\ub294 \uc6f9 \ud648\ud398\uc774\uc9c0\ub97c "
            "\ud558\ub098 \ub9cc\ub4e4\uace0\uc2f6\ub124"
        )

        classification = classify_request(request, {"host": "codex"})
        result = build_kh_front_door(
            request,
            project=r"C:\Users\KONEIT\Desktop\Jang\asdfasdf",
            host="codex",
        )
        summary = result.to_summary_dict()

        self.assertIn("brainstorming-harness", classification.required_harnesses)
        self.assertFalse(summary["execution_gate"]["can_execute"])

    def test_garbled_path_pdf_project_request_does_not_open_execution_gate(self):
        request = (
            r"C:\Users\KONEIT\Desktop\Jang\asdfasdf "
            "?? ??? ??? ??? ??? pdf?? ?? pdf??? ??? ???"
        )

        classification = classify_request(request, {"host": "codex"})
        result = build_kh_front_door(
            request,
            project=r"C:\Users\KONEIT\Desktop\Jang\asdfasdf",
            host="codex",
        )
        summary = result.to_summary_dict()

        self.assertIn("brainstorming-harness", classification.required_harnesses)
        self.assertFalse(summary["execution_gate"]["can_execute"])
        self.assertIn("global_codex_MEMORY.md", summary["execution_gate"]["blocked_actions"])

    def test_contextual_kh_audit_repair_followup_opens_large_work_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "docs" / "kh").mkdir(parents=True)
            request = (
                "\uc774\uc81c \uadf8\ub7fc \uadf8 \uae30\uc900\uc73c\ub85c "
                "\ub2e4\uc2dc \uc2f9\ub2e4 \ubcf4\uc644\ud558\uc790??"
            )

            result = build_kh_front_door(request, project=project, host="codex")

        summary = result.to_summary_dict()
        self.assertEqual(summary["classification"]["complexity"], "heavy")
        self.assertEqual(summary["classification"]["recommended_execution"], "role_dag")
        self.assertEqual(summary["plugin_route"]["controller"], "kh")
        self.assertEqual(summary["execution_gate"]["status"], "blocked_until_large_work_preflight")
        self.assertIn("goal-state-harness", summary["immediate_next_skills"])
        self.assertIn("workflow-usability-harness", summary["immediate_next_skills"])

    def test_contextual_kh_audit_repair_followup_uses_request_context_without_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            request = (
                "\uc774\uc81c \uadf8\ub7fc \uadf8 \uae30\uc900\uc73c\ub85c "
                "\ub2e4\uc2dc \uc2f9\ub2e4 \ubcf4\uc644\ud558\uc790??"
            )
            result = build_kh_front_door(
                request,
                project=tmp,
                host="codex",
                request_context={
                    "domain": "software",
                    "has_active_artifact": True,
                    "requires_resume": True,
                    "prior_context_kind": "session_audit",
                },
            )

        summary = result.to_summary_dict()
        self.assertEqual(summary["classification"]["complexity"], "heavy")
        self.assertEqual(summary["execution_gate"]["status"], "blocked_until_large_work_preflight")

    def test_front_door_cli_accepts_context_json_for_session_audit_followup(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompt_file = Path(tmp) / "prompt.txt"
            prompt_file.write_text(
                "\uc774\uc81c \uadf8\ub7fc \uadf8 \uae30\uc900\uc73c\ub85c "
                "\ub2e4\uc2dc \uc2f9\ub2e4 \ubcf4\uc644\ud558\uc790??",
                encoding="utf-8",
            )
            context = json.dumps(
                {
                    "domain": "software",
                    "has_active_artifact": True,
                    "requires_resume": True,
                    "prior_context_kind": "session_audit",
                }
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.orchestration.kh_front_door",
                    "--prompt-file",
                    str(prompt_file),
                    "--project",
                    tmp,
                    "--host",
                    "codex",
                    "--context-json",
                    context,
                    "--summary",
                ],
                capture_output=True,
                encoding="utf-8",
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["classification"]["complexity"], "heavy")
        self.assertEqual(payload["execution_gate"]["status"], "blocked_until_large_work_preflight")

    def test_kh_project_marker_does_not_turn_security_fix_into_audit_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "docs" / "kh").mkdir(parents=True)
            result = build_kh_front_door(
                "Fix the SQL injection vulnerability and add regression tests.",
                project=project,
                host="codex",
            )

        classification = result.classification
        self.assertEqual(classification["domain"], "security")
        self.assertIn("security_review", classification["evidence_required"])
        self.assertNotIn("contextual_audit_repair_request", classification["reasons"])

    def test_kh_active_directive_does_not_turn_react_routing_bug_into_audit_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_kh_front_door(
                "Fix the React routing bug in this app.",
                project=tmp,
                host="codex",
                request_context={"kh_active_directive": "active"},
            )

        classification = result.classification
        self.assertEqual(classification["domain"], "software")
        self.assertNotIn("contextual_audit_repair_request", classification["reasons"])

    def test_session_audit_flags_front_door_miss_as_always_on_failure(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Build a small HTML dashboard in this folder and verify it.",
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

        self.assertIn("always-on-front-door", audit.coverage["required_missing_skill_names"])
        self.assertTrue(
            any(
                issue["skill"] == "always-on-front-door"
                and issue["status"] == "missing_front_door"
                and issue["severity"] == "P1"
                for issue in audit.issues
            )
        )

    def test_skill_trigger_does_not_leave_a_triviality_escape_hatch(self):
        repo_root = Path(__file__).resolve().parents[1]
        skill_text = (repo_root / "skills/always_on_front_door/SKILL.md").read_text(
            encoding="utf-8"
        )
        usage_text = (
            repo_root / "skills/always_on_front_door/references/usage.md"
        ).read_text(encoding="utf-8")
        combined = f"{skill_text}\n{usage_text}".lower()

        self.assertNotIn("non-trivial", combined)
        self.assertNotIn("do not use it for clearly light direct answers", combined)
        self.assertIn("every new user request or task", combined)
        self.assertIn("runtime, not the host selector", combined)
        for required_example in [
            "short/simple sql formatting",
            "translation",
            "rewrite",
            "lookup",
            "arithmetic",
        ]:
            with self.subTest(required_example=required_example):
                self.assertIn(required_example, combined)

    def test_minimal_workflow_requires_runtime_output_for_direct_exit(self):
        repo_root = Path(__file__).resolve().parents[1]
        example = (
            repo_root / "skills/always_on_front_door/examples/minimal-workflow.md"
        ).read_text(encoding="utf-8")
        lowered = example.lower()

        self.assertNotIn("explicit blocked/direct rationale", lowered)
        self.assertIn("valid runtime output", lowered)
        self.assertIn("direct", lowered)
        self.assertIn("execution authorization", lowered)

    def test_plugin_manifests_match_the_universal_front_door_trigger(self):
        repo_root = Path(__file__).resolve().parents[1]
        manifest_paths = [
            repo_root / ".codex-plugin/plugin.json",
            repo_root / "plugin.json",
            repo_root / ".agents/plugins/kh-uaf/plugin.json",
        ]
        manifests = [json.loads(path.read_text(encoding="utf-8")) for path in manifest_paths]
        combined = "\n".join(
            json.dumps(manifest, ensure_ascii=False).lower() for manifest in manifests
        )

        self.assertNotIn("non-trivial", combined)
        for manifest in manifests:
            with self.subTest(manifest=manifest["name"]):
                self.assertIn("every new", manifest["description"].lower())
        default_prompt = manifests[0]["interface"]["defaultPrompt"]
        self.assertIn("every new user request", default_prompt[0].lower())

    def test_micro_direct_path_skips_catalog_and_broad_host_skill_discovery(self):
        with (
            mock.patch(
                "src.orchestration.kh_front_door.collect_packaged_skills"
            ) as collect_catalog,
            mock.patch(
                "src.orchestration.kh_front_door._host_local_skill_providers"
            ) as discover_host_skills,
        ):
            result = build_kh_front_door(
                "1+1?",
                project=Path.cwd(),
                host="codex",
                micro=True,
            )

        collect_catalog.assert_not_called()
        discover_host_skills.assert_not_called()
        packet = result.to_micro_summary_dict()
        self.assertEqual(packet["src"]["v"], "2.9.134")
        self.assertEqual(packet["cls"], {"c": "l", "x": "direct"})
        self.assertNotIn("next", packet)

    def test_micro_sql_path_skips_catalog_and_preserves_provider_then_verifier(self):
        with (
            mock.patch(
                "src.orchestration.kh_front_door.collect_packaged_skills"
            ) as collect_catalog,
            mock.patch(
                "src.orchestration.kh_front_door._host_local_skill_providers"
            ) as discover_host_skills,
        ):
            result = build_kh_front_door(
                "Format this SQL: SELECT A.ORDNUM FROM SA220T A",
                project=Path.cwd(),
                host="codex",
                micro=True,
            )

        collect_catalog.assert_not_called()
        discover_host_skills.assert_not_called()
        self.assertEqual(
            result.immediate_next_skills,
            ["sql-formatting", "sql-formatting-style-harness"],
        )

    def test_micro_sql_path_prefers_canonical_host_local_provider(self):
        with tempfile.TemporaryDirectory() as codex_home:
            skill_path = self.write_host_sql_formatting_skill(codex_home)
            with (
                mock.patch.dict("os.environ", {"CODEX_HOME": codex_home}),
                mock.patch(
                    "src.orchestration.kh_front_door._host_local_skill_providers"
                ) as discover_host_skills,
            ):
                result = build_kh_front_door(
                    "Format this SQL: SELECT A.ORDNUM FROM SA220T A",
                    project=Path.cwd(),
                    host="codex",
                    micro=True,
                )

        discover_host_skills.assert_not_called()
        controller = result.plugin_route["controller"]
        self.assertEqual(controller["provider_id"], "sql-formatting")
        self.assertEqual(controller["metadata"]["source"], "host-local-skill")
        self.assertEqual(controller["metadata"]["path"], str(skill_path.resolve()))

    def test_sql_provider_selection_requires_generic_preserving_verified_host_policy(self):
        compatible = """---
name: sql-formatting
description: Format SQL while preserving query behavior and semantics.
---

# SQL Formatting

Do not change query behavior, predicates, expressions, or results.
Convert scalar lookups only when the implementation and relational equivalence are verified.
Run the packaged `sql-formatting-style-harness` deterministic verifier and accept only passing output.

## Examples

For example, `DBO.F_SAMPLE_NAME(...)` and `SAMPLE_LOOKUP_TABLE` are illustrative placeholders.
"""
        cases = [
            ("compatible_generic", compatible, "host-local-skill", None),
            (
                "current_host_shape",
                """---
name: sql-formatting
description: Preserve SQL logic and verified lookup scalar-function-to-join conversions.
---

# SQL Formatting

Do not change query behavior.

## BA011T Name Lookup

`DBO.F_BA011T_FIND_SUBNM(MAINCD, SUBCD, USEYN)` has a verified lookup contract.
When SQL contains this function, replace it with `LEFT OUTER JOIN BA011T` and select `SUBNM`.
""",
                "packaged-kh-skill",
                "concrete_schema_object_mandate",
            ),
            (
                "missing_verifier",
                compatible.replace(
                    "Run the packaged `sql-formatting-style-harness` deterministic verifier and accept only passing output.\n",
                    "",
                ),
                "packaged-kh-skill",
                "missing_packaged_verifier_requirement",
            ),
            (
                "missing_behavior_boundary",
                compatible.replace(
                    "description: Format SQL while preserving query behavior and semantics.",
                    "description: Format SQL for readability.",
                ).replace(
                    "Do not change query behavior, predicates, expressions, or results.",
                    "Keep predicates and expressions readable.",
                ),
                "packaged-kh-skill",
                "missing_behavior_preservation_boundary",
            ),
            (
                "behavior_change_allowed",
                compatible.replace(
                    "Do not change query behavior, predicates, expressions, or results.",
                    "Query behavior changes are permitted when they improve performance.",
                ),
                "packaged-kh-skill",
                "behavior_change_allowed",
            ),
            (
                "unbounded_scalar_join",
                compatible.replace(
                    "Convert scalar lookups only when the implementation and relational equivalence are verified.",
                    "Replace scalar UDF calls with LEFT JOINs for performance.",
                ),
                "packaged-kh-skill",
                "unbounded_scalar_to_join_conversion",
            ),
        ]

        for case_name, content, expected_source, expected_issue in cases:
            for micro in [False, True]:
                with self.subTest(case=case_name, micro=micro), tempfile.TemporaryDirectory() as codex_home:
                    self.write_host_sql_formatting_skill(codex_home, content)
                    with mock.patch.dict("os.environ", {"CODEX_HOME": codex_home}):
                        result = build_kh_front_door(
                            "Format this SQL and preserve its behavior.",
                            project=Path.cwd(),
                            host="codex",
                            micro=micro,
                        )

                controller = result.plugin_route["controller"]
                self.assertEqual(controller["metadata"]["source"], expected_source)
                host_evidence = next(
                    item
                    for item in result.plugin_route["provider_evidence"]
                    if item["source"] == "host-local-skill"
                    and item["provider_id"] == "sql-formatting"
                )
                self.assertEqual(host_evidence["selected"], expected_issue is None)
                self.assertEqual(host_evidence["compatible"], expected_issue is None)
                if expected_issue is not None:
                    self.assertIn(expected_issue, host_evidence["compatibility_issues"])

    def test_micro_sql_path_skips_codex_home_lookup_for_non_codex_hosts(self):
        for host in ["antigravity", "local"]:
            with (
                self.subTest(host=host),
                mock.patch(
                    "src.orchestration.kh_front_door._canonical_host_sql_formatting_provider"
                ) as canonical_lookup,
            ):
                result = build_kh_front_door(
                    "Format this SQL: SELECT A.ORDNUM FROM SA220T A",
                    project=Path.cwd(),
                    host=host,
                    micro=True,
                )

            canonical_lookup.assert_not_called()
            controller = result.plugin_route["controller"]
            self.assertEqual(controller["provider_id"], "sql-formatting")
            self.assertEqual(
                controller["metadata"]["source"],
                "packaged-kh-skill",
            )

    def test_micro_sql_path_uses_packaged_fallback_without_canonical_host_skill(self):
        with tempfile.TemporaryDirectory() as codex_home:
            with (
                mock.patch.dict("os.environ", {"CODEX_HOME": codex_home}),
                mock.patch(
                    "src.orchestration.kh_front_door._host_local_skill_providers"
                ) as discover_host_skills,
            ):
                result = build_kh_front_door(
                    "Format this SQL: SELECT A.ORDNUM FROM SA220T A",
                    project=Path.cwd(),
                    host="codex",
                    micro=True,
                )

        discover_host_skills.assert_not_called()
        controller = result.plugin_route["controller"]
        self.assertEqual(controller["provider_id"], "sql-formatting")
        self.assertEqual(controller["metadata"]["source"], "packaged-kh-skill")
        self.assertEqual(
            result.immediate_next_skills,
            ["sql-formatting", "sql-formatting-style-harness"],
        )

    def test_micro_mode_considers_skill_catalog_without_runtime_application(self):
        result = build_kh_front_door(
            "1+1?",
            project=Path.cwd(),
            host="codex",
            micro=True,
        )
        summary = result.to_summary_dict()

        self.assertNotIn("skill-catalog", summary["runtime_applied_skills"])
        catalog_status = summary["skill_status_summary"]["skill-catalog"]
        self.assertEqual(catalog_status["status"], "skipped_with_rationale")
        self.assertEqual(catalog_status["application_mode"], "considered")
        self.assertIn("Micro routing", catalog_status["evidence_note"])

    def test_invalid_core_skill_blocks_normal_and_micro_without_micro_catalog_scan(self):
        core_skills = [
            "always-on-front-door",
            "automatic-intake-harness",
            "plugin-composition-policy",
            "request-complexity-router",
            "skill-catalog",
            "token-optimizer",
        ]
        with tempfile.TemporaryDirectory() as root:
            skills_root = Path(root) / "skills"
            for skill_name in core_skills:
                self.write_packaged_skill(
                    skills_root,
                    skill_name,
                    valid=skill_name != "automatic-intake-harness",
                )
            source = SkillSource(
                source_type="repo-local",
                root=root,
                skills_dir=str(skills_root),
                exists=True,
            )

            for micro in [False, True]:
                with (
                    self.subTest(micro=micro),
                    mock.patch(
                        "src.orchestration.kh_front_door._select_skill_source",
                        return_value=source,
                    ),
                    mock.patch(
                        "src.orchestration.kh_front_door.collect_packaged_skills",
                        wraps=collect_packaged_skills,
                    ) as collect_catalog,
                ):
                    result = build_kh_front_door(
                        "1+1?",
                        project=Path.cwd(),
                        host="codex",
                        micro=micro,
                    )

                if micro:
                    collect_catalog.assert_not_called()
                else:
                    collect_catalog.assert_called_once_with(str(skills_root))
                self.assertEqual(result.front_door_status, "blocked")
                invalid_status = result.skill_statuses["automatic-intake-harness"]
                self.assertEqual(invalid_status["status"], "blocked")
                self.assertEqual(
                    invalid_status["blocked_reason"],
                    "invalid_packaged_skill",
                )

    def test_invalid_immediate_skill_stays_blocked_in_micro_routing(self):
        skill_names = [
            "always-on-front-door",
            "automatic-intake-harness",
            "plugin-composition-policy",
            "request-complexity-router",
            "skill-catalog",
            "token-optimizer",
            "sql-formatting",
            "sql-formatting-style-harness",
        ]
        with tempfile.TemporaryDirectory() as root:
            skills_root = Path(root) / "skills"
            for skill_name in skill_names:
                self.write_packaged_skill(
                    skills_root,
                    skill_name,
                    valid=skill_name != "sql-formatting-style-harness",
                )
            source = SkillSource(
                source_type="repo-local",
                root=root,
                skills_dir=str(skills_root),
                exists=True,
            )
            providers = [
                {
                    "provider_id": "sql-formatting",
                    "display_name": "SQL Formatting",
                    "capabilities": ["sql_formatting"],
                    "status": "available",
                    "metadata": {"source": "packaged-kh-skill"},
                }
            ]

            with mock.patch(
                "src.orchestration.kh_front_door._select_skill_source",
                return_value=source,
            ):
                result = build_kh_front_door(
                    "Format this SQL: SELECT A.ORDNUM FROM SA220T A",
                    project=Path.cwd(),
                    host="codex",
                    providers=providers,
                    micro=True,
                )

        self.assertIn("sql-formatting-style-harness", result.immediate_next_skills)
        immediate_status = result.skill_statuses["sql-formatting-style-harness"]
        self.assertEqual(immediate_status["status"], "blocked")
        self.assertEqual(immediate_status["blocked_reason"], "invalid_packaged_skill")
        self.assertEqual(result.front_door_status, "blocked")

    def test_micro_validation_blocks_duplicate_selected_name_in_noncanonical_folder(self):
        core_skills = [
            "always-on-front-door",
            "automatic-intake-harness",
            "plugin-composition-policy",
            "request-complexity-router",
            "skill-catalog",
            "token-optimizer",
        ]
        with tempfile.TemporaryDirectory() as root:
            skills_root = Path(root) / "skills"
            for skill_name in core_skills:
                self.write_packaged_skill(skills_root, skill_name)
            selected_skill = skills_root / "automatic_intake_harness" / "SKILL.md"
            duplicate_file = skills_root / "archived-copy-v2" / "SKILL.md"
            duplicate_file.parent.mkdir(parents=True)
            duplicate_file.write_text(
                selected_skill.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            source = SkillSource(
                source_type="repo-local",
                root=root,
                skills_dir=str(skills_root),
                exists=True,
            )

            with mock.patch(
                "src.orchestration.kh_front_door._select_skill_source",
                return_value=source,
            ):
                result = build_kh_front_door(
                    "1+1?",
                    project=Path.cwd(),
                    host="codex",
                    micro=True,
                )

        integrity = result.catalog_summary["skill_integrity"]["automatic-intake-harness"]
        self.assertFalse(integrity["valid"])
        self.assertIn("duplicate_name", {issue["code"] for issue in integrity["issues"]})
        self.assertEqual(result.front_door_status, "blocked")

    def test_same_task_acknowledgement_reuses_valid_front_door(self):
        front_door_call_id = "front-door-same-task"
        front_door_output = {
            "front_door_status": "ok",
            "runtime_applied_skills": ["always-on-front-door"],
            "selected_not_executed_skills": [],
            "classification": {"complexity": "heavy"},
            "plugin_route": {"route": "single", "controller": "kh"},
            "execution_gate": {"can_execute": True, "status": "ok"},
            "immediate_next_skills": [],
        }
        acknowledgements = ["yes", "ok", "응", "네", "ㅇㅇ", "진행", "1번으로 진행해"]

        for acknowledgement in acknowledgements:
            with self.subTest(acknowledgement=acknowledgement):
                path = self.write_session(
                    [
                        {
                            "type": "response_item",
                            "payload": {
                                "type": "message",
                                "role": "user",
                                "content": "Fix the routing bug in this repository.",
                            },
                        },
                        {
                            "type": "response_item",
                            "payload": {
                                "type": "function_call",
                                "name": "shell_command",
                                "call_id": front_door_call_id,
                                "arguments": (
                                    "python -m src.orchestration.kh_front_door "
                                    '--prompt "Fix the routing bug in this repository." '
                                    "--micro-summary"
                                ),
                            },
                        },
                        {
                            "type": "response_item",
                            "payload": {
                                "type": "function_call_output",
                                "call_id": front_door_call_id,
                                "output": f"Exit code: 0\n{json.dumps(front_door_output)}",
                            },
                        },
                        {
                            "type": "response_item",
                            "payload": {
                                "type": "message",
                                "role": "user",
                                "content": acknowledgement,
                            },
                        },
                        {
                            "type": "response_item",
                            "payload": {
                                "type": "function_call",
                                "name": "shell_command",
                                "arguments": "rg -n routing src",
                            },
                        },
                    ]
                )

                audit = analyze_session_skills(path)
                self.assertFalse(
                    any(
                        issue["skill"] == "always-on-front-door"
                        and issue["status"] == "missing_front_door"
                        and issue.get("trigger") == acknowledgement
                        for issue in audit.issues
                    )
                )

    def test_new_work_bearing_request_after_valid_front_door_requires_new_intake(self):
        front_door_output = {
            "front_door_status": "ok",
            "classification": {"complexity": "heavy"},
            "plugin_route": {"route": "single", "controller": "kh"},
            "execution_gate": {"can_execute": True, "status": "ok"},
            "immediate_next_skills": [],
        }
        request = "Also add CSV export to the dashboard."
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Fix the routing bug in this repository.",
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
                        "role": "user",
                        "content": request,
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "rg -n export src",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)
        self.assertTrue(
            any(
                issue["skill"] == "always-on-front-door"
                and issue["status"] == "missing_front_door"
                and issue.get("trigger") == request
                for issue in audit.issues
            )
        )

    def test_short_sql_routes_provider_before_verifier(self):
        requests = [
            "Format this SQL: SELECT A.ORDNUM FROM SA220T A",
            (
                "Only normalize aliases in this SQL: "
                "SELECT A.ORDNUM, B.ITEMCD FROM SA220T A "
                "LEFT JOIN SA100T B ON A.ORDNUM = B.ORDNUM"
            ),
        ]

        for request in requests:
            with self.subTest(request=request):
                summary = build_kh_front_door(
                    request,
                    project=Path.cwd(),
                    host="codex",
                ).to_summary_dict()

                self.assertEqual(summary["plugin_route"]["controller"], "sql-formatting")
                self.assertEqual(
                    summary["immediate_next_skills"],
                    ["sql-formatting", "sql-formatting-style-harness"],
                )
                self.assertTrue(summary["execution_gate"]["can_execute"])

    def test_short_direct_requests_exit_without_unrelated_followup_skills(self):
        requests = [
            "Translate hello to Korean.",
            "Rewrite this sentence: Hello world from me.",
            "What is the capital of France?",
            "1+1?",
        ]

        for request in requests:
            with self.subTest(request=request):
                summary = build_kh_front_door(
                    request,
                    project=Path.cwd(),
                    host="codex",
                ).to_summary_dict()

                self.assertEqual(summary["classification"]["complexity"], "light")
                self.assertEqual(
                    summary["classification"]["recommended_execution"],
                    "direct_answer",
                )
                self.assertEqual(summary["plugin_route"]["route"], "direct")
                self.assertEqual(summary["immediate_next_skills"], [])
                self.assertEqual(summary["selected_not_executed_skills"], [])
                self.assertTrue(summary["execution_gate"]["can_execute"])

    def test_arithmetic_micro_summary_is_low_overhead_direct_exit(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.orchestration.kh_front_door",
                "--prompt",
                "1+1?",
                "--project",
                ".",
                "--host",
                "codex",
                "--micro-summary",
                "--strict-execution-gate",
            ],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            encoding="utf-8",
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["m"], "kh_fd_micro")
        self.assertEqual(payload["cls"], {"c": "l", "x": "direct"})
        self.assertEqual(payload["r"], {"r": "direct"})
        self.assertEqual(payload["g"], {"ok": True, "s": "ok"})
        self.assertNotIn("next", payload)
        self.assertLess(len(completed.stdout.encode("utf-8")), 700)

    def test_session_audit_flags_short_sql_provider_before_front_door(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Format this SQL: SELECT A.ORDNUM FROM SA220T A",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": (
                            "Get-Content C:\\Users\\KONEIT\\.codex\\skills\\"
                            "sql-formatting\\SKILL.md"
                        ),
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertIn("always-on-front-door", audit.coverage["required_missing_skill_names"])
        self.assertTrue(
            any(
                issue["skill"] == "always-on-front-door"
                and issue["status"] == "missing_front_door"
                and issue.get("trigger_kind") == "sql_formatting_request"
                for issue in audit.issues
            )
        )

    def test_session_audit_flags_arithmetic_final_answer_before_front_door(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "1+1?",
                    },
                },
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "agent_message",
                        "message": "2",
                        "phase": "final_answer",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertTrue(
            any(
                issue["skill"] == "always-on-front-door"
                and issue["status"] == "missing_front_door"
                and issue.get("trigger_kind") == "universal_request"
                for issue in audit.issues
            )
        )

    def test_skill_documentation_targets_are_traceable(self):
        repo_root = Path(__file__).resolve().parents[1]
        always_on = repo_root / "skills/always_on_front_door/SKILL.md"
        automatic_intake = repo_root / "skills/automatic_intake_harness/SKILL.md"

        self.assertTrue(always_on.exists())
        self.assertTrue(automatic_intake.exists())
        self.assertIn("src.orchestration.kh_front_door.build_kh_front_door", always_on.read_text(encoding="utf-8"))
        self.assertIn("tests.test_kh_front_door_always_on", always_on.read_text(encoding="utf-8"))

    def test_windows_powershell_51_template_writes_bom_safe_prompt_and_context_json(self):
        repo_root = Path(__file__).resolve().parents[1]
        skill_text = (repo_root / "skills/always_on_front_door/SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("UTF8Encoding($false)", skill_text)
        self.assertIn("ConvertTo-Json -Depth 10", skill_text)
        self.assertIn("--context-file $contextPath", skill_text)


if __name__ == "__main__":
    unittest.main()
