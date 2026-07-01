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
        self.assertIn("localized_literals_changed", codes)
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

    def test_verifier_blocks_wide_insert_select_one_column_per_line(self):
        original = (
            "INSERT INTO SA130T\n"
            "(\n"
            "    ORGDIV, ORDNUM, ORDSEQ, PORSEQ\n"
            "  , PRNTITEMCD, SPECNUM, CHLDITEMCD, CHLDITEMNM\n"
            "  , DWGNO, CHLDQTY, CHLDUNIT, DOGUB\n"
            ")\n"
            "SELECT @ORGDIV, A.ORDNUM, A.ORDSEQ, A.PORSEQ\n"
            "     , A.PRNTITEMCD, A.SPECNUM, A.CHLDITEMCD, A.CHLDITEMNM\n"
            "     , A.DWGNO, A.CHLDQTY, A.CHLDUNIT, A.DOGUB\n"
            "FROM SA130T A\n"
            "WHERE A.ORGDIV = @ORGDIV;\n"
        )
        formatted = (
            "INSERT INTO SA130T (\n"
            "      ORGDIV\n"
            "    , ORDNUM\n"
            "    , ORDSEQ\n"
            "    , PORSEQ\n"
            "    , PRNTITEMCD\n"
            "    , SPECNUM\n"
            "    , CHLDITEMCD\n"
            "    , CHLDITEMNM\n"
            "    , DWGNO\n"
            "    , CHLDQTY\n"
            "    , CHLDUNIT\n"
            "    , DOGUB\n"
            ")\n"
            "SELECT @ORGDIV\n"
            "     , A.ORDNUM\n"
            "     , A.ORDSEQ\n"
            "     , A.PORSEQ\n"
            "     , A.PRNTITEMCD\n"
            "     , A.SPECNUM\n"
            "     , A.CHLDITEMCD\n"
            "     , A.CHLDITEMNM\n"
            "     , A.DWGNO\n"
            "     , A.CHLDQTY\n"
            "     , A.CHLDUNIT\n"
            "     , A.DOGUB\n"
            "FROM SA130T A\n"
            "WHERE A.ORGDIV = @ORGDIV;\n"
        )

        result = verify_sql_formatting_style(original, formatted)

        self.assertFalse(result.success)
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["style_issues"]
        }
        self.assertIn("insert_select_single_column_per_line", codes)

    def test_verifier_blocks_outer_query_internal_t_alias(self):
        original = (
            "SELECT A.ORDNUM\n"
            "     , A.ORDSEQ\n"
            "FROM SA110T A\n"
            "WHERE A.ORGDIV = @ORGDIV;\n"
        )
        formatted = (
            "SELECT T.ORDNUM\n"
            "     , T.ORDSEQ\n"
            "FROM SA110T T\n"
            "WHERE T.ORGDIV = @ORGDIV;\n"
        )

        result = verify_sql_formatting_style(original, formatted)

        self.assertFalse(result.success)
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["style_issues"]
        }
        self.assertIn("outer_query_uses_derived_table_internal_alias", codes)

    def test_verifier_blocks_ad_hoc_outer_aliases(self):
        original = (
            "SELECT A.ORDNUM\n"
            "     , B.CUSTNM\n"
            "FROM SA100T A\n"
            "        LEFT OUTER JOIN BA020T B\n"
            "                     ON A.CUSTCD = B.CUSTCD;\n"
        )
        formatted = (
            "SELECT TT.ORDNUM\n"
            "     , YY.CUSTNM\n"
            "FROM SA100T TT\n"
            "        LEFT OUTER JOIN BA020T YY\n"
            "                     ON TT.CUSTCD = YY.CUSTCD;\n"
        )

        result = verify_sql_formatting_style(original, formatted)

        self.assertFalse(result.success)
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["style_issues"]
        }
        self.assertIn("ad_hoc_outer_alias", codes)

    def test_verifier_blocks_derived_table_outer_internal_alias(self):
        original = (
            "SELECT A.ORDNUM\n"
            "     , B.CNT\n"
            "FROM SA100T A\n"
            "        LEFT OUTER JOIN (\n"
            "            SELECT T.ORDNUM\n"
            "                 , COUNT(*) AS CNT\n"
            "            FROM SA110T T\n"
            "            GROUP BY T.ORDNUM\n"
            "        ) B\n"
            "                     ON A.ORDNUM = B.ORDNUM;\n"
        )
        formatted = (
            "SELECT A.ORDNUM\n"
            "     , T.CNT\n"
            "FROM SA100T A\n"
            "        LEFT OUTER JOIN (\n"
            "            SELECT T.ORDNUM\n"
            "                 , COUNT(*) AS CNT\n"
            "            FROM SA110T T\n"
            "            GROUP BY T.ORDNUM\n"
            "        ) T\n"
            "                     ON A.ORDNUM = T.ORDNUM;\n"
        )

        result = verify_sql_formatting_style(original, formatted)

        self.assertFalse(result.success)
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["style_issues"]
        }
        self.assertIn("outer_query_uses_derived_table_internal_alias", codes)

    def test_verifier_allows_raw_table_qualifier_in_independent_statement(self):
        sql = (
            "SELECT A.ORDNUM\n"
            "FROM SA110T A\n"
            "WHERE A.ORGDIV = @ORGDIV;\n"
            "\n"
            "SELECT SA110T.ORDNUM\n"
            "FROM SA110T\n"
            "WHERE SA110T.ORGDIV = @ORGDIV;\n"
        )

        result = verify_sql_formatting_style(sql, sql)

        self.assertTrue(result.success, result.to_dict())

    def test_verifier_blocks_grouped_insert_target_with_vertical_select_values(self):
        original = (
            "INSERT INTO SA130T\n"
            "(\n"
            "      ORGDIV                  , ORDNUM                  , ORDSEQ                  , PORSEQ\n"
            "    , PRNTITEMCD              , SPECNUM                 , CHLDITEMCD              , CHLDITEMNM\n"
            ")\n"
            "SELECT @ORGDIV                , A4.ORDNUM               , A4.ORDSEQ               , A4.PORSEQ\n"
            "     , A4.PRNTITEMCD          , A4.SPECNUM              , A4.CHLDITEMCD           , A4.CHLDITEMNM\n"
            "FROM SA130T A4;\n"
        )
        formatted = (
            "INSERT INTO SA130T\n"
            "(\n"
            "      ORGDIV                  , ORDNUM                  , ORDSEQ                  , PORSEQ\n"
            "    , PRNTITEMCD              , SPECNUM                 , CHLDITEMCD              , CHLDITEMNM\n"
            ")\n"
            "SELECT @ORGDIV\n"
            "     , A4.ORDNUM\n"
            "     , A4.ORDSEQ\n"
            "     , A4.PORSEQ\n"
            "     , A4.PRNTITEMCD\n"
            "     , A4.SPECNUM\n"
            "     , A4.CHLDITEMCD\n"
            "     , A4.CHLDITEMNM\n"
            "FROM SA130T A4;\n"
        )

        result = verify_sql_formatting_style(original, formatted)

        self.assertFalse(result.success)
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["style_issues"]
        }
        self.assertIn("insert_select_value_list_verticalized", codes)

    def test_verifier_blocks_korean_comment_mojibake_damage(self):
        original = (
            "SELECT A.ORDNUM\n"
            "     , A.SIZSEQ /* \ub3c4\uba74\ud655\uc815\uc720\ubb34 */\n"
            "FROM SA110T A\n"
            "WHERE A.ORGDIV = @ORGDIV;\n"
        )
        formatted = (
            "SELECT A.ORDNUM\n"
            "     , A.SIZSEQ /* ???? */\n"
            "FROM SA110T A\n"
            "WHERE A.ORGDIV = @ORGDIV;\n"
        )

        result = verify_sql_formatting_style(original, formatted)

        self.assertFalse(result.success)
        preservation_codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["preservation_issues"]
        }
        self.assertIn("localized_text_damaged", preservation_codes)

    def test_verifier_allows_wide_insert_select_grouped_layout(self):
        grouped = (
            "INSERT INTO SA130T\n"
            "(\n"
            "      ORGDIV                  , ORDNUM                  , ORDSEQ                  , PORSEQ\n"
            "    , PRNTITEMCD              , SPECNUM                 , CHLDITEMCD              , CHLDITEMNM\n"
            "    , DWGNO                   , CHLDQTY                 , CHLDUNIT                , DOGUB\n"
            ")\n"
            "SELECT @ORGDIV                , A.ORDNUM                , A.ORDSEQ                , A.PORSEQ\n"
            "     , A.PRNTITEMCD           , A.SPECNUM               , A.CHLDITEMCD            , A.CHLDITEMNM\n"
            "     , A.DWGNO                , A.CHLDQTY               , A.CHLDUNIT              , A.DOGUB\n"
            "FROM SA130T A\n"
            "WHERE A.ORGDIV = @ORGDIV;\n"
        )

        result = verify_sql_formatting_style(grouped, grouped)

        self.assertTrue(result.success, result.to_dict())

    def test_verifier_blocks_join_conditions_not_deep_enough_inside_if_exists(self):
        bad_block = (
            "        IF EXISTS (\n"
            "                    SELECT 1\n"
            "                    FROM DEV000T A\n"
            "                            INNER JOIN @TMP B\n"
            "                                    ON A.ID = B.ID\n"
            "                                    AND A.QCCODE = B.QCCODE\n"
            "                    --WHERE ISNULL(B.GBN, '') <> 'DEL'\n"
            "                  )\n"
            "        BEGIN\n"
            "            RAISERROR('이미 확인완료된 프로그램입니다.', 16, 1);\n"
            "            RETURN;\n"
            "        END\n"
        )

        result = verify_sql_formatting_style(bad_block, bad_block)

        self.assertFalse(result.success)
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["style_issues"]
        }
        self.assertIn("join_condition_indentation", codes)

    def test_verifier_allows_grouped_insert_with_wrapped_long_expression(self):
        grouped = (
            "INSERT INTO SA130T\n"
            "(\n"
            "      ORGDIV                  , ORDNUM                  , ORDSEQ                  , PORSEQ\n"
            "    , PRNTITEMCD              , SPECNUM                 , CHLDITEMCD              , CHLDITEMNM\n"
            ")\n"
            "SELECT @ORGDIV                , A4.ORDNUM               , A4.ORDSEQ\n"
            "     , ISNULL(A4.MAXPORSEQ, 0)\n"
            "       + ROW_NUMBER() OVER (\n"
            "                            PARTITION BY A4.ORDNUM, A4.ORDSEQ\n"
            "                            ORDER BY A4.SEQ\n"
            "                           )\n"
            "     , A4.PRNTITEMCD          , A4.SPECNUM              , A4.CHLDITEMCD           , A4.CHLDITEMNM\n"
            "FROM SA130T A4\n"
            "WHERE A4.ORGDIV = @ORGDIV;\n"
        )

        result = verify_sql_formatting_style(grouped, grouped)

        self.assertTrue(result.success, result.to_dict())

    def test_verifier_blocks_new_cte_introduction_by_default(self):
        original = (
            "SELECT A.ORDNUM\n"
            "     , SUM(B.QTY) AS QTY\n"
            "FROM SA100T A\n"
            "        LEFT OUTER JOIN SA110T B\n"
            "                     ON A.ORDNUM = B.ORDNUM\n"
            "WHERE A.ORGDIV = @ORGDIV\n"
            "GROUP BY A.ORDNUM;\n"
        )
        formatted = (
            "WITH ORDER_QTY AS (\n"
            "    SELECT B.ORDNUM\n"
            "         , SUM(B.QTY) AS QTY\n"
            "    FROM SA110T B\n"
            "    GROUP BY B.ORDNUM\n"
            ")\n"
            "SELECT A.ORDNUM\n"
            "     , C.QTY\n"
            "FROM SA100T A\n"
            "        LEFT OUTER JOIN ORDER_QTY C\n"
            "                     ON A.ORDNUM = C.ORDNUM\n"
            "WHERE A.ORGDIV = @ORGDIV;\n"
        )

        result = verify_sql_formatting_style(original, formatted)

        self.assertFalse(result.success)
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["style_issues"]
        }
        self.assertIn("cte_introduced_without_reason", codes)

    def test_verifier_blocks_new_temp_table_introduction_by_default(self):
        original = (
            "SELECT A.ORDNUM\n"
            "     , A.CUSTCD\n"
            "FROM SA100T A\n"
            "WHERE A.ORGDIV = @ORGDIV;\n"
        )
        formatted = (
            "SELECT A.ORDNUM\n"
            "     , A.CUSTCD\n"
            "INTO #ORDER_WORK\n"
            "FROM SA100T A\n"
            "WHERE A.ORGDIV = @ORGDIV;\n"
            "\n"
            "SELECT A.ORDNUM\n"
            "     , A.CUSTCD\n"
            "FROM #ORDER_WORK A;\n"
        )

        result = verify_sql_formatting_style(original, formatted)

        self.assertFalse(result.success)
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["style_issues"]
        }
        self.assertIn("temp_table_introduced_without_reason", codes)

    def test_verifier_allows_existing_cte_and_temp_table_to_remain(self):
        sql = (
            "WITH ORDER_QTY AS (\n"
            "    SELECT T.ORDNUM\n"
            "         , SUM(T.QTY) AS QTY\n"
            "    FROM #ORDER_WORK T\n"
            "    GROUP BY T.ORDNUM\n"
            ")\n"
            "SELECT A.ORDNUM\n"
            "     , A.QTY\n"
            "FROM ORDER_QTY A;\n"
        )

        result = verify_sql_formatting_style(sql, sql)

        self.assertTrue(result.success, result.to_dict())

    def test_verifier_blocks_cte_column_list_introduction(self):
        original = (
            "SELECT A.ORDNUM\n"
            "     , A.QTY\n"
            "FROM SA110T A\n"
            "WHERE A.ORGDIV = @ORGDIV;\n"
        )
        formatted = (
            "WITH ORDER_QTY (ORDNUM, QTY) AS (\n"
            "    SELECT A.ORDNUM\n"
            "         , A.QTY\n"
            "    FROM SA110T A\n"
            "    WHERE A.ORGDIV = @ORGDIV\n"
            ")\n"
            "SELECT A.ORDNUM\n"
            "     , A.QTY\n"
            "FROM ORDER_QTY A;\n"
        )

        result = verify_sql_formatting_style(original, formatted)

        self.assertFalse(result.success)
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["style_issues"]
        }
        self.assertIn("cte_introduced_without_reason", codes)

    def test_verifier_blocks_cte_after_begin_introduction(self):
        original = (
            "CREATE OR ALTER PROCEDURE DBO.SP_SAMPLE_SELECT\n"
            "      @ORGDIV VARCHAR(2) = NULL\n"
            "AS\n"
            "BEGIN\n"
            "    SELECT A.ORDNUM\n"
            "    FROM SA110T A\n"
            "    WHERE A.ORGDIV = @ORGDIV;\n"
            "END\n"
        )
        formatted = (
            "CREATE OR ALTER PROCEDURE DBO.SP_SAMPLE_SELECT\n"
            "      @ORGDIV VARCHAR(2) = NULL\n"
            "AS\n"
            "BEGIN\n"
            "    WITH ORDER_QTY AS (\n"
            "        SELECT A.ORDNUM\n"
            "        FROM SA110T A\n"
            "        WHERE A.ORGDIV = @ORGDIV\n"
            "    )\n"
            "    SELECT A.ORDNUM\n"
            "    FROM ORDER_QTY A;\n"
            "END\n"
        )

        result = verify_sql_formatting_style(original, formatted)

        self.assertFalse(result.success)
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["style_issues"]
        }
        self.assertIn("cte_introduced_without_reason", codes)

    def test_verifier_does_not_treat_nolock_as_cte(self):
        sql = (
            "SELECT A.ORDNUM\n"
            "FROM SA100T A WITH (NOLOCK)\n"
            "WHERE A.ORGDIV = @ORGDIV;\n"
        )

        result = verify_sql_formatting_style(sql, sql)

        self.assertTrue(result.success, result.to_dict())

    def test_verifier_ignores_cte_and_temp_markers_inside_literals_and_comments(self):
        sql = (
            "SELECT 'WITH ORDER_QTY AS (' AS SAMPLE_TEXT\n"
            "     , '#ORDER_WORK' AS TEMP_NAME\n"
            "FROM SA100T A\n"
            "WHERE A.ORGDIV = @ORGDIV\n"
            "-- SELECT * INTO #ORDER_WORK FROM SA100T\n"
        )

        result = verify_sql_formatting_style(sql, sql)

        self.assertTrue(result.success, result.to_dict())

    def test_verifier_allows_new_cte_with_recorded_exception_reason(self):
        original = (
            "SELECT A.ORDNUM\n"
            "FROM SA110T A\n"
            "WHERE A.ORGDIV = @ORGDIV\n"
        )
        formatted = (
            "WITH ORDER_BASE AS (\n"
            "    SELECT A.ORDNUM\n"
            "    FROM SA110T A\n"
            "    WHERE A.ORGDIV = @ORGDIV\n"
            ")\n"
            "SELECT A.ORDNUM\n"
            "FROM ORDER_BASE A;\n"
        )

        result = verify_sql_formatting_style(
            original,
            formatted,
            cte_temp_table_reason="explicit user request to show the same logic as a CTE variant",
        )

        self.assertTrue(result.success, result.to_dict())
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["style_issues"]
        }
        self.assertIn("cte_exception_reason_recorded", codes)

    def test_verifier_rejects_vague_cte_exception_reason(self):
        original = (
            "SELECT A.ORDNUM\n"
            "FROM SA110T A\n"
            "WHERE A.ORGDIV = @ORGDIV\n"
        )
        formatted = (
            "WITH ORDER_BASE AS (\n"
            "    SELECT A.ORDNUM\n"
            "    FROM SA110T A\n"
            "    WHERE A.ORGDIV = @ORGDIV\n"
            ")\n"
            "SELECT A.ORDNUM\n"
            "FROM ORDER_BASE A;\n"
        )

        result = verify_sql_formatting_style(
            original,
            formatted,
            cte_temp_table_reason="looks cleaner",
        )

        self.assertFalse(result.success)
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["style_issues"]
        }
        self.assertIn("cte_introduced_without_reason", codes)

    def test_verifier_blocks_added_cte_when_original_already_has_one(self):
        original = (
            "WITH BASE AS (\n"
            "    SELECT A.ORDNUM\n"
            "    FROM SA110T A\n"
            "    WHERE A.ORGDIV = @ORGDIV\n"
            ")\n"
            "SELECT A.ORDNUM\n"
            "FROM BASE A;\n"
        )
        formatted = (
            "WITH BASE AS (\n"
            "    SELECT A.ORDNUM\n"
            "    FROM SA110T A\n"
            "    WHERE A.ORGDIV = @ORGDIV\n"
            "), EXTRA AS (\n"
            "    SELECT A.ORDNUM\n"
            "    FROM SA120T A\n"
            ")\n"
            "SELECT A.ORDNUM\n"
            "FROM BASE A;\n"
        )

        result = verify_sql_formatting_style(original, formatted)

        self.assertFalse(result.success)
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["style_issues"]
        }
        self.assertIn("cte_introduced_without_reason", codes)

    def test_verifier_rejects_negated_exception_reason(self):
        original = (
            "SELECT A.ORDNUM\n"
            "FROM SA110T A\n"
            "WHERE A.ORGDIV = @ORGDIV\n"
        )
        formatted = (
            "WITH ORDER_BASE AS (\n"
            "    SELECT A.ORDNUM\n"
            "    FROM SA110T A\n"
            "    WHERE A.ORGDIV = @ORGDIV\n"
            ")\n"
            "SELECT A.ORDNUM\n"
            "FROM ORDER_BASE A;\n"
        )

        result = verify_sql_formatting_style(
            original,
            formatted,
            cte_temp_table_reason="not explicit, just cleaner for readability",
        )

        self.assertFalse(result.success)
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["style_issues"]
        }
        self.assertIn("cte_introduced_without_reason", codes)

    def test_verifier_rejects_negated_performance_exception_reason(self):
        original = (
            "SELECT A.ORDNUM\n"
            "FROM SA110T A\n"
            "WHERE A.ORGDIV = @ORGDIV\n"
        )
        formatted = (
            "WITH ORDER_BASE AS (\n"
            "    SELECT A.ORDNUM\n"
            "    FROM SA110T A\n"
            "    WHERE A.ORGDIV = @ORGDIV\n"
            ")\n"
            "SELECT A.ORDNUM\n"
            "FROM ORDER_BASE A;\n"
        )

        result = verify_sql_formatting_style(
            original,
            formatted,
            cte_temp_table_reason="no measured performance evidence, just cleaner",
        )

        self.assertFalse(result.success)
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["style_issues"]
        }
        self.assertIn("cte_introduced_without_reason", codes)

    def test_verifier_allows_temp_table_select_into_with_recorded_exception_reason(self):
        original = (
            "SELECT A.ORDNUM\n"
            "     , A.CUSTCD\n"
            "FROM SA100T A\n"
            "WHERE A.ORGDIV = @ORGDIV\n"
        )
        formatted = (
            "SELECT A.ORDNUM\n"
            "     , A.CUSTCD\n"
            "INTO #ORDER_WORK\n"
            "FROM SA100T A\n"
            "WHERE A.ORGDIV = @ORGDIV\n"
        )

        result = verify_sql_formatting_style(
            original,
            formatted,
            cte_temp_table_reason="large intermediate result needs indexing/statistics before repeated reuse",
        )

        self.assertTrue(result.success, result.to_dict())
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["style_issues"]
        }
        self.assertIn("temp_table_exception_reason_recorded", codes)

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
        self.assertIn("localized_literals_changed", codes)
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
        self.assertTrue(
            any("SQL PRE-OUTPUT GATE" in action for action in payload["required_next_actions"])
        )

    def test_front_door_adds_sql_pre_output_gate_for_generated_stored_procedure(self):
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
                    "Begin Tran\n"
                    "EXEC UP_SYS_SYSTEMCHECKLIST_SAVE @p_WorkType = 'LIST', @XML_DATA = '<ROOT />'\n"
                    "Rollback\n"
                    "SAVE procedure with IF EXISTS and RAISERROR.",
                    project=Path(tmp),
                    host="codex",
                )

        payload = result.to_dict()
        self.assertEqual(payload["plugin_route"]["route"], "hybrid")
        self.assertTrue(
            any(role["provider_id"] == "sql-formatting" for role in payload["plugin_route"]["assistants"])
        )
        self.assertIn("sql-formatting-style-harness", payload["recommended_skills"])
        self.assertTrue(
            any("SQL PRE-OUTPUT GATE" in action for action in payload["required_next_actions"])
        )

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
