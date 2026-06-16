import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.orchestration.kh_front_door import build_kh_front_door
from src.skills.sql_formatting_style import (
    build_powerbuilder_sql_validation_plan,
    extract_powerbuilder_sql_fragments,
    resolve_style_contract_source,
    validate_powerbuilder_output_dir,
    verify_sql_formatting_style,
)
from src.skills.uaf_skill_catalog import collect_packaged_skills, read_packaged_skill


FIXTURES = Path(__file__).parent / "fixtures" / "sql_formatting" / "c_kone110"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class SqlFormattingStyleHarnessTests(unittest.TestCase):
    def test_verifier_passes_preserved_c_kone110_style_sql(self):
        result = verify_sql_formatting_style(
            _fixture("original_select.sql"),
            _fixture("formatted_select.sql"),
        )

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.metadata["mechanical_checks"]["status"], "passed")
        self.assertEqual(result.metadata["semantic_checks"]["status"], "not_proven")
        self.assertEqual(result.metadata["token_optimizer_status"], "passthrough")

    def test_verifier_blocks_literal_comment_predicate_or_else_changes(self):
        result = verify_sql_formatting_style(
            _fixture("original_select.sql"),
            _fixture("formatted_changed_literal.sql"),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 1)
        issues = result.metadata["mechanical_checks"]["preservation_issues"]
        codes = {issue["code"] for issue in issues}
        self.assertIn("string_literals_changed", codes)
        self.assertIn("korean_literals_changed", codes)
        self.assertIn("comments_changed", codes)
        self.assertIn("predicates_changed", codes)
        self.assertIn("arbitrary_else_added", codes)

    def test_verifier_blocks_style_shape_failures_without_literal_changes(self):
        result = verify_sql_formatting_style(
            _fixture("original_select.sql"),
            _fixture("formatted_bad_style.sql"),
        )

        self.assertFalse(result.success)
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["style_issues"]
        }
        self.assertIn("select_column_missing_leading_comma", codes)
        self.assertIn("join_indentation", codes)
        self.assertIn("join_condition_indentation", codes)
        self.assertIn("case_not_parenthesized", codes)

    def test_verifier_blocks_retained_ba011t_scalar_lookup(self):
        formatted = (
            "CREATE OR ALTER PROCEDURE [DBO].[SP_DEMO_SELECT]\n"
            "      @WORKTYPE    VARCHAR(20) = NULL\n"
            "    , @ORGDIV      VARCHAR(2)  = NULL\n"
            "AS\n"
            "BEGIN\n"
            "    SET NOCOUNT ON\n"
            "\n"
            "    SELECT A.ORDNUM\n"
            "         , DBO.F_BA011T_FIND_SUBNM('DE001', A.STATUS, 'Y') AS STATUSNM\n"
            "         , (CASE WHEN A.CHKYN = 'Y' THEN '?뺤씤' END) AS CHKYNM\n"
            "         , A.QTY * A.PRICE AS AMT\n"
            "    FROM DE100T A\n"
            "        LEFT OUTER JOIN DE110T B\n"
            "                     ON A.ORDNUM = B.ORDNUM\n"
            "                     AND A.ORDSEQ = B.ORDSEQ\n"
            "    WHERE A.ORGDIV = @ORGDIV\n"
            "      AND A.STATUS = '吏꾪뻾'\n"
            "--AND A.STATUS = '蹂대쪟'\n"
            "END\n"
        )

        result = verify_sql_formatting_style(_fixture("original_select.sql"), formatted)

        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 1)
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["style_issues"]
        }
        self.assertIn("ba011t_scalar_lookup_retained", codes)

    def test_verifier_allows_lowercase_powerbuilder_host_variables(self):
        original = (
            "select a.col_a, b.col_b,\n"
            "case when a.flag_yn='Y' then '<KOREAN_LITERAL>' end flag_nm,\n"
            "dbo.F_BA011T_FIND_SUBNM('CD001',a.status_cd,'Y') status_nm\n"
            "from t_main a\n"
            "left outer join t_flow b on a.key_col=b.key_col and a.seq=b.seq\n"
            "where a.date_col between :ls_frdt and :ls_todt\n"
            "and a.status_cd like :ls_status ;\n"
            "--and a.flag_yn='Y'\n"
        )
        formatted = (
            "SELECT A.COL_A\n"
            "     , B.COL_B\n"
            "     , (CASE WHEN A.FLAG_YN = 'Y' THEN '<KOREAN_LITERAL>' END) AS FLAG_NM\n"
            "     , ISNULL(C.SUBNM, '') AS STATUS_NM\n"
            "FROM T_MAIN A\n"
            "        LEFT OUTER JOIN T_FLOW B\n"
            "                     ON A.KEY_COL = B.KEY_COL\n"
            "                     AND A.SEQ = B.SEQ\n"
            "\n"
            "        LEFT OUTER JOIN BA011T C\n"
            "                     ON C.MAINCD = 'CD001'\n"
            "                     AND A.STATUS_CD = C.SUBCD\n"
            "                     AND C.USEYN = 'Y'\n"
            "WHERE A.DATE_COL BETWEEN :ls_frdt AND :ls_todt\n"
            "  AND A.STATUS_CD LIKE :ls_status;\n"
            "--AND A.FLAG_YN = 'Y'\n"
        )

        result = verify_sql_formatting_style(original, formatted)

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["mechanical_checks"]["status"], "passed")

    def test_powerbuilder_update_host_variable_semicolon_spacing_is_preserved(self):
        original = _fixture("pbl_update_semicolon_space.original.sql")
        formatted = _fixture("pbl_update_semicolon_space.formatted.sql")

        result = verify_sql_formatting_style(original, formatted)

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["mechanical_checks"]["status"], "passed")

    def test_powerbuilder_delete_host_variable_semicolon_spacing_is_preserved(self):
        original = _fixture("pbl_delete_semicolon_space.original.sql")
        formatted = _fixture("pbl_delete_semicolon_space.formatted.sql")

        result = verify_sql_formatting_style(original, formatted)

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["mechanical_checks"]["status"], "passed")

    def test_verifier_allows_alias_only_comment_update(self):
        original = (
            "SELECT A.STATUS\n"
            "FROM DE100T A\n"
            "WHERE A.STATUS = '진행'\n"
            "--AND a.status = '보류'\n"
        )
        formatted = original.replace("--AND a.status", "--AND A.STATUS")

        result = verify_sql_formatting_style(original, formatted)

        self.assertTrue(result.success, result.to_dict())

    def test_verifier_blocks_uncommenting_commented_condition(self):
        original = (
            "SELECT A.STATUS\n"
            "FROM DE100T A\n"
            "WHERE A.STATUS = '진행'\n"
            "--AND a.status = '보류'\n"
        )
        formatted = original.replace("--AND a.status", "AND A.STATUS")

        result = verify_sql_formatting_style(original, formatted)

        self.assertFalse(result.success)
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["preservation_issues"]
        }
        self.assertIn("comments_changed", codes)
        self.assertIn("predicates_changed", codes)

    def test_verifier_blocks_korean_business_text_change_inside_comment(self):
        original = (
            "SELECT A.STATUS\n"
            "FROM DE100T A\n"
            "WHERE A.STATUS = '진행'\n"
            "--AND a.status = '보류'\n"
        )
        formatted = original.replace("--AND a.status = '보류'", "--AND A.STATUS = '취소'")

        result = verify_sql_formatting_style(original, formatted)

        self.assertFalse(result.success)
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["preservation_issues"]
        }
        self.assertIn("string_literals_changed", codes)
        self.assertIn("korean_literals_changed", codes)
        self.assertIn("comments_changed", codes)

    def test_style_contract_source_records_host_local_hash_when_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_path = Path(tmp) / "SKILL.md"
            skill_path.write_text("host sql-formatting contract\n", encoding="utf-8")

            source = resolve_style_contract_source(skill_path)

        self.assertTrue(source["available"])
        self.assertEqual(source["path"], str(skill_path))
        self.assertRegex(source["sha256"], r"^[0-9a-f]{64}$")

    def test_packaged_skill_is_registered_and_readable(self):
        catalog = collect_packaged_skills()
        names = {skill["name"] for skill in catalog["skills"]}

        self.assertIn("sql-formatting-style-harness", names)
        content = read_packaged_skill("sql-formatting-style-harness")
        self.assertIn("host-local `sql-formatting`", content)
        self.assertIn("verify_sql_formatting_style", content)

    def test_demo_script_outputs_harness_result_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            demo_path = Path("skills") / "sql_formatting_style_harness" / "scripts" / "demo.py"
            completed = subprocess.run(
                [sys.executable, str(demo_path), "--output-dir", tmp],
                capture_output=True,
                encoding="utf-8",
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["skill"], "sql-formatting-style-harness")
        self.assertEqual(payload["success_case"]["contract_type"], "HarnessResult")
        self.assertEqual(payload["blocked_or_failure_case"]["contract_type"], "HarnessResult")

    def test_powerbuilder_fixture_extracts_sql_fragments_without_source_writes(self):
        fragments = extract_powerbuilder_sql_fragments(
            _fixture("powerbuilder_sample.sru"),
            source_name="powerbuilder_sample.sru",
        )

        self.assertEqual([fragment["keyword"] for fragment in fragments], ["UPDATE", "SELECT"])
        self.assertTrue(all(fragment["token_optimizer_status"] == "passthrough" for fragment in fragments))
        self.assertIn("진행", fragments[0]["sql_text"])

    def test_powerbuilder_validation_plan_keeps_gwerp_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_powerbuilder_sql_validation_plan(
                pbl_root=r"C:\GWERP",
                output_dir=tmp,
            )

        self.assertEqual(plan["status"], "planned")
        self.assertIn(r"C:\GWERP", plan["write_boundary"]["forbidden"])
        self.assertIn("bounded hook", plan["current_pass_scope"])

    def test_powerbuilder_output_guard_blocks_gwerp_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard = validate_powerbuilder_output_dir(
                source_root=tmp,
                output_dir=r"C:\GWERP\probe-output",
            )

        self.assertFalse(guard["allowed"])
        self.assertIn(str(Path(r"C:\GWERP").resolve()), guard["violations"])

    def test_powerbuilder_probe_blocks_source_root_output_without_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_root = Path(tmp) / "pb_source"
            source_root.mkdir()
            (source_root / "sample.sru").write_bytes(
                "SELECT * FROM DE100T WHERE STATUS = '진행';\n".encode("cp949")
            )
            output_dir = source_root / "probe_output"
            probe_path = Path("skills") / "sql_formatting_style_harness" / "scripts" / "powerbuilder_sql_probe.py"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(probe_path),
                    "--source-root",
                    str(source_root),
                    "--output-dir",
                    str(output_dir),
                ],
                capture_output=True,
                encoding="utf-8",
                text=True,
            )

            self.assertEqual(completed.returncode, 2, completed.stdout)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "blocked")
            self.assertFalse(payload["artifact_written"])
            self.assertFalse(output_dir.exists())

    def test_front_door_composes_sql_formatting_with_verifier_for_heavy_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skills" / "sql-formatting"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: sql-formatting\n"
                "description: Use when formatting, cleaning, standardizing, or refactoring SQL/T-SQL.\n"
                "---\n"
                "# SQL Formatting\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"CODEX_HOME": tmp}):
                result = build_kh_front_door(
                    "Use sql-formatting to refactor every SQL file in this project, run verification, and prepare evidence.",
                    project=Path(tmp),
                    host="codex",
                )

        payload = result.to_dict()
        self.assertEqual(payload["plugin_route"]["controller"]["provider_id"], "sql-formatting")
        self.assertIn("sql-formatting-style-harness", payload["recommended_skills"])
        self.assertIn("sql-formatting-style-harness", payload["skill_statuses"])

    def test_front_door_does_not_select_verifier_for_mention_only_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skills" / "sql-formatting"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: sql-formatting\n"
                "description: Use when formatting, cleaning, standardizing, or refactoring SQL/T-SQL.\n"
                "---\n"
                "# SQL Formatting\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"CODEX_HOME": tmp}):
                result = build_kh_front_door(
                    "Review whether KH hides other skills such as `sql-formatting`; this is a risk example, not a SQL formatting request.",
                    project=Path(tmp),
                    host="codex",
                )

        payload = result.to_dict()
        self.assertNotIn("sql-formatting-style-harness", payload["recommended_skills"])


if __name__ == "__main__":
    unittest.main()
