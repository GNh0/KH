import hashlib
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


def _issue_codes(result) -> set[str]:
    codes = set()
    for value in result.metadata.get("mechanical_checks", {}).values():
        if isinstance(value, list):
            codes.update(
                issue["code"]
                for issue in value
                if isinstance(issue, dict) and "code" in issue
            )
    return codes


class SqlFormattingStyleHarnessTests(unittest.TestCase):
    def test_verifier_passes_preserved_c_kone110_style_sql(self):
        original = (
            "select a.order_no, dbo.F_LOOKUP_NAME(a.status_cd) as status_name\n"
            "from order_header a\n"
            "where a.status_cd = N'진행';\n"
        )
        formatted = (
            "SELECT A.ORDER_NO\n"
            "     , DBO.F_LOOKUP_NAME(A.STATUS_CD) AS STATUS_NAME\n"
            "FROM ORDER_HEADER A\n"
            "WHERE A.STATUS_CD = N'진행';\n"
        )

        result = verify_sql_formatting_style(original, formatted)

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.metadata["mechanical_checks"]["status"], "passed")
        self.assertEqual(result.metadata["semantic_checks"]["status"], "not_proven")
        self.assertEqual(result.metadata["token_optimizer_status"], "passthrough")

    def test_verifier_blocks_literal_comment_predicate_or_else_changes(self):
        original = (
            "SELECT A.STATUS_CD\n"
            "     , (CASE WHEN A.ACTIVE = 'Y' THEN N'진행' END) AS STATUS_NAME\n"
            "FROM ORDER_HEADER A\n"
            "WHERE A.ACTIVE = 'Y'\n"
            "-- keep active rows\n"
        )
        changed = (
            "SELECT A.STATUS_CD\n"
            "     , (CASE WHEN A.ACTIVE = 'Y' THEN N'완료' ELSE N'기타' END) AS STATUS_NAME\n"
            "FROM ORDER_HEADER A\n"
            "WHERE A.ACTIVE = 'Y' OR A.LOCKED = 'N'\n"
            "-- changed business rule\n"
        )

        result = verify_sql_formatting_style(original, changed)

        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 1)
        issues = result.metadata["mechanical_checks"]["preservation_issues"]
        codes = {issue["code"] for issue in issues}
        self.assertIn("string_literals_changed", codes)
        self.assertIn("localized_literals_changed", codes)
        self.assertIn("comments_changed", codes)
        self.assertIn("localized_text_damaged", codes)
        self.assertIn("predicates_changed", codes)
        self.assertIn("arbitrary_else_added", codes)

    def test_verifier_blocks_style_shape_failures_without_literal_changes(self):
        bad_style = (
            "SELECT A.ORDER_NO\n"
            "       B.CUSTOMER_NAME\n"
            "     , CASE WHEN A.ACTIVE = 'Y' THEN 'YES' END AS ACTIVE_NAME\n"
            "FROM ORDER_HEADER A\n"
            " LEFT OUTER JOIN CUSTOMER B\n"
            " ON A.CUSTOMER_ID = B.CUSTOMER_ID;\n"
        )

        result = verify_sql_formatting_style(bad_style, bad_style)

        self.assertFalse(result.success)
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["style_issues"]
        }
        self.assertIn("select_column_missing_leading_comma", codes)
        self.assertIn("join_indentation", codes)
        self.assertIn("join_condition_indentation", codes)
        self.assertNotIn("case_not_parenthesized", codes)

    def test_formatting_preserves_original_unparenthesized_case(self):
        sql = (
            "SELECT CASE WHEN A.ACTIVE = 'Y' THEN 'YES' ELSE 'NO' END AS ACTIVE_NAME\n"
            "FROM ORDER_HEADER A;\n"
        )

        result = verify_sql_formatting_style(sql, sql, operation="formatting")

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["formatting_preservation"]["status"], "verified")
        self.assertNotIn("case_not_parenthesized", _issue_codes(result))

    def test_formatting_blocks_parentheses_added_around_case(self):
        original = (
            "SELECT CASE WHEN A.ACTIVE = 'Y' THEN 'YES' ELSE 'NO' END AS ACTIVE_NAME\n"
            "FROM ORDER_HEADER A;\n"
        )
        formatted = (
            "SELECT (CASE WHEN A.ACTIVE = 'Y' THEN 'YES' ELSE 'NO' END) AS ACTIVE_NAME\n"
            "FROM ORDER_HEADER A;\n"
        )

        result = verify_sql_formatting_style(original, formatted, operation="formatting")

        self.assertFalse(result.success, result.to_dict())
        self.assertEqual(result.metadata["formatting_preservation"]["status"], "changed")
        self.assertIn("token_stream_changed", _issue_codes(result))

    def test_generation_requires_parenthesized_case_without_formatting_comparison(self):
        unparenthesized = (
            "SELECT CASE WHEN A.ACTIVE = 'Y' THEN 'YES' ELSE 'NO' END AS ACTIVE_NAME\n"
            "FROM ORDER_HEADER A;\n"
        )
        parenthesized = (
            "SELECT (CASE WHEN A.ACTIVE = 'Y' THEN 'YES' ELSE 'NO' END) AS ACTIVE_NAME\n"
            "FROM ORDER_HEADER A;\n"
        )

        blocked = verify_sql_formatting_style("", unparenthesized, operation="generation")
        accepted = verify_sql_formatting_style("", parenthesized, operation="generation")

        self.assertFalse(blocked.success, blocked.to_dict())
        self.assertIn("case_not_parenthesized", _issue_codes(blocked))
        self.assertEqual(blocked.metadata["formatting_preservation"]["status"], "not_evaluated")
        self.assertTrue(accepted.success, accepted.to_dict())
        self.assertEqual(accepted.metadata["formatting_preservation"]["status"], "not_evaluated")

    def test_verifier_retains_every_scalar_function_for_formatting_only(self):
        formatted = (
            "SELECT A.STATUS\n"
            "     , DBO.F_LOOKUP_NAME(A.STATUS) AS STATUS_NAME\n"
            "FROM DE100T A;\n"
        )
        result = verify_sql_formatting_style(formatted, formatted)

        self.assertTrue(result.success, result.to_dict())
        refactor = result.metadata["semantic_refactor_evidence"]["scalar_function_refactor"]
        self.assertEqual(refactor["status"], "not_requested")
        self.assertEqual(
            refactor["reason"],
            "formatting_preserves_all_scalar_functions",
        )

    def test_verifier_allows_lowercase_powerbuilder_host_variables(self):
        original = (
            "select a.col_a, b.col_b,\n"
            "(case when a.flag_yn='Y' then '<KOREAN_LITERAL>' end) as flag_nm,\n"
            "dbo.F_LOOKUP_NAME(a.status_cd) as status_nm\n"
            "from t_main a\n"
            "left outer join t_flow b on a.key_col=b.key_col and a.seq=b.seq\n"
            "where a.date_col between :ls_frdt and :ls_todt\n"
            "and a.status_cd like :ls_status ;\n"
            "--AND A.FLAG_YN = 'Y'\n"
        )
        formatted = (
            "SELECT A.COL_A\n"
            "     , B.COL_B\n"
            "     , (CASE WHEN A.FLAG_YN = 'Y' THEN '<KOREAN_LITERAL>' END) AS FLAG_NM\n"
            "     , DBO.F_LOOKUP_NAME(A.STATUS_CD) AS STATUS_NM\n"
            "FROM T_MAIN A\n"
            "        LEFT OUTER JOIN T_FLOW B\n"
            "                     ON A.KEY_COL = B.KEY_COL\n"
            "                     AND A.SEQ = B.SEQ\n"
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

    def test_verifier_allows_repeated_lookup_numbered_alias_family(self):
        sql = (
            "SELECT A.ITEMCD\n"
            "     , ISNULL(E1.SUBNM, '') AS MNGITEM1NM\n"
            "     , ISNULL(E2.SUBNM, '') AS OUTINSPECNM\n"
            "FROM SA220T A\n"
            "        LEFT OUTER JOIN CODE_LOOKUP E1\n"
            "                     ON E1.MAINCD = 'MA002'\n"
            "                     AND E1.SUBCD = A.MNGITEM1\n"
            "\n"
            "        LEFT OUTER JOIN CODE_LOOKUP E2\n"
            "                     ON E2.MAINCD = 'MA020'\n"
            "                     AND E2.SUBCD = A.OUTINSPEC;\n"
        )

        result = verify_sql_formatting_style(sql, sql)

        self.assertTrue(result.success, result.to_dict())

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

    def test_verifier_blocks_session_019f45b6_first_answer_text_damage(self):
        original = (
            "SELECT C.USERNM\n"
            "     , A.PAC1     /*\ud300\uc7a5\ud655\uc778*/\n"
            "     , (CASE WHEN A.REMARK LIKE '' THEN '' ELSE '\u25cb' END) AS CMT\n"
            "     , A.ININSPEC /* \uc2b9\uc778\uad6c\ubd84*/\n"
            "     , ISNULL(E.SUBNM, '') AS MNGITEM1NM\n"
            "     , ISNULL(F.SUBNM, '') AS OUTINSPECNM\n"
            "FROM SA220T A\n"
            "        LEFT OUTER JOIN CODE_LOOKUP E\n"
            "                     ON E.MAINCD = 'MA002'\n"
            "                     AND E.SUBCD = A.MNGITEM1\n"
            "\n"
            "        LEFT OUTER JOIN CODE_LOOKUP F\n"
            "                     ON F.MAINCD = 'MA020'\n"
            "                     AND F.SUBCD = A.OUTINSPEC\n"
            "WHERE A.OUTINSPEC LIKE '%' /*\uae30\ud0c0\ucd9c\uace0\uad6c\ubd84*/\n"
            "  AND (CASE WHEN A.ININSPEC = 'Y' THEN 'Y' ELSE 'N' END) LIKE '%' /* \uc2b9\uc778\uc5ec\ubd80 */;\n"
        )
        formatted = (
            "SELECT C.USERNM\n"
            "     , A.PAC1     /*?\u0080?\u03bd\uc19a??/\n"
            "     , (CASE WHEN A.REMARK LIKE '' THEN '' ELSE '?? END) AS CMT\n"
            "     , A.ININSPEC /* ?\ubc40\uc52c援щ텇*/\n"
            "     , ISNULL(E.SUBNM, '') AS MNGITEM1NM\n"
            "     , ISNULL(F.SUBNM, '') AS OUTINSPECNM\n"
            "FROM SA220T A\n"
            "        LEFT OUTER JOIN CODE_LOOKUP E\n"
            "                     ON E.MAINCD = 'MA002'\n"
            "                     AND E.SUBCD = A.MNGITEM1\n"
            "\n"
            "        LEFT OUTER JOIN CODE_LOOKUP F\n"
            "                     ON F.MAINCD = 'MA020'\n"
            "                     AND F.SUBCD = A.OUTINSPEC\n"
            "WHERE A.OUTINSPEC LIKE '%' /*\u6e32\uace0?\u7570\uc395퀬援щ텇*/\n"
            "  AND (CASE WHEN A.ININSPEC = 'Y' THEN 'Y' ELSE 'N' END) LIKE '%' /* ?\ubc40\uc52c?\uc5ec? */;\n"
        )

        result = verify_sql_formatting_style(original, formatted)

        self.assertFalse(result.success)
        output_codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["output_integrity_issues"]
        }
        self.assertEqual(result.metadata["formatter_output_integrity"]["status"], "damaged")
        self.assertIn("unclosed_block_comment", output_codes)

    def test_verifier_blocks_unterminated_string_literal(self):
        original = (
            "SELECT A.ITEMCD\n"
            "     , (CASE WHEN A.REMARK LIKE '' THEN '' ELSE 'OK' END) AS CMT\n"
            "FROM SA220T A;\n"
        )
        formatted = (
            "SELECT A.ITEMCD\n"
            "     , (CASE WHEN A.REMARK LIKE '' THEN '' ELSE '?? END) AS CMT\n"
            "FROM SA220T A;\n"
        )

        result = verify_sql_formatting_style(original, formatted)

        self.assertFalse(result.success)
        output_codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["output_integrity_issues"]
        }
        self.assertEqual(result.metadata["formatter_output_integrity"]["status"], "damaged")
        self.assertIn("unterminated_string_literal", output_codes)

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

    def test_verifier_blocks_where_subquery_inside_if_exists(self):
        cases = [
            (
                "IN",
                "          WHERE A.ORDNUM IN (\n"
                "                              SELECT T.ORDNUM\n"
                "                              FROM @TMP T\n"
                "                             )\n",
            ),
            (
                "EXISTS",
                "          WHERE EXISTS (\n"
                "                        SELECT 1\n"
                "                        FROM @TMP T\n"
                "                        WHERE T.ORDNUM = A.ORDNUM\n"
                "                       )\n",
            ),
            (
                "NOT EXISTS",
                "          WHERE NOT EXISTS (\n"
                "                            SELECT 1\n"
                "                            FROM @TMP T\n"
                "                            WHERE T.ORDNUM = A.ORDNUM\n"
                "                           )\n",
            ),
            (
                "SCALAR",
                "          WHERE A.ORDSEQ = (\n"
                "                            SELECT MAX(T.ORDSEQ)\n"
                "                            FROM @TMP T\n"
                "                           )\n",
            ),
        ]

        for label, predicate in cases:
            with self.subTest(label=label):
                bad_block = (
                    "IF EXISTS (\n"
                    "          SELECT 1\n"
                    "          FROM SA100T A\n"
                    f"{predicate}"
                    "          )\n"
                    "BEGIN\n"
                    "    RAISERROR('Already processed.', 16, 1);\n"
                    "    RETURN;\n"
                    "END\n"
                )

                result = verify_sql_formatting_style(bad_block, bad_block)

                self.assertFalse(result.success)
                codes = {
                    issue["code"]
                    for issue in result.metadata["mechanical_checks"]["style_issues"]
                }
                self.assertIn("if_exists_where_subquery", codes)

    def test_verifier_allows_simple_where_predicate_inside_if_exists(self):
        guard_block = (
            "IF EXISTS (\n"
            "          SELECT 1\n"
            "          FROM SA100T A\n"
            "          WHERE A.ORDNUM = @ORDNUM\n"
            "          )\n"
            "BEGIN\n"
            "    RAISERROR('Already processed.', 16, 1);\n"
            "    RETURN;\n"
            "END\n"
        )

        result = verify_sql_formatting_style(guard_block, guard_block)
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["style_issues"]
        }

        self.assertNotIn("if_exists_where_subquery", codes)

    def test_verifier_does_not_block_derived_table_internal_where_subquery_inside_if_exists(self):
        guard_block = (
            "IF EXISTS (\n"
            "          SELECT 1\n"
            "          FROM (\n"
            "                SELECT T.ORDNUM\n"
            "                FROM SA100T T\n"
            "                WHERE T.ORDSEQ IN (\n"
            "                                      SELECT X.ORDSEQ\n"
            "                                      FROM @TMP X\n"
            "                                     )\n"
            "               ) A\n"
            "          WHERE A.ORDNUM = @ORDNUM\n"
            "          )\n"
            "BEGIN\n"
            "    RAISERROR('Already processed.', 16, 1);\n"
            "    RETURN;\n"
            "END\n"
        )

        result = verify_sql_formatting_style(guard_block, guard_block)
        codes = {
            issue["code"]
            for issue in result.metadata["mechanical_checks"]["style_issues"]
        }

        self.assertNotIn("if_exists_where_subquery", codes)

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

    def test_verifier_blocks_semicolon_prefixed_cte_introduction(self):
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
            ";WITH ORDER_QTY AS (\n"
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

    def test_verifier_records_cte_reason_but_does_not_treat_it_as_preservation_proof(self):
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

        self.assertFalse(result.success, result.to_dict())
        self.assertIn("select_query_count_changed", _issue_codes(result))
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

    def test_verifier_records_temp_table_reason_without_waiving_token_preservation(self):
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

        self.assertFalse(result.success, result.to_dict())
        self.assertIn("token_stream_changed", _issue_codes(result))
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

    def test_verifier_blocks_comment_token_case_updates(self):
        original = (
            "SELECT A.STATUS\n"
            "FROM DE100T A\n"
            "WHERE A.STATUS = '진행'\n"
            "--AND a.status = '보류'\n"
        )
        formatted = original.replace("--AND a.status", "--AND A.STATUS")

        result = verify_sql_formatting_style(original, formatted)

        self.assertFalse(result.success, result.to_dict())
        self.assertIn("comments_changed", _issue_codes(result))

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
        self.assertIn("comments_changed", codes)
        self.assertIn("localized_text_damaged", codes)

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
        description = next(line for line in content.splitlines() if line.startswith("description:"))
        self.assertTrue(description.startswith("description: Use when"))

        fallback = Path("skills/sql_formatting_style_harness/references/style-contract.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Do not apply a universal `= NULL` rule", fallback)
        self.assertIn("only caller-provided inputs are procedure parameters", fallback)
        self.assertIn("Never invent `AUTHOR`", fallback)
        self.assertIn("`DECLARE`/`SET`", fallback)

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

    def test_powerbuilder_validation_plan_has_standalone_fallback_without_local_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_root = Path(tmp) / "pb_source"
            output_dir = Path(tmp) / "probe_output"
            source_root.mkdir()
            plan = build_powerbuilder_sql_validation_plan(
                pbl_root=source_root,
                output_dir=output_dir,
            )

        self.assertEqual(plan["status"], "planned")
        self.assertEqual(plan["export_provider"], "standalone")
        self.assertEqual(plan["pblscripter_path"], "")
        self.assertIn(str(source_root), plan["write_boundary"]["forbidden"])
        self.assertNotIn(r"C:\PblScripter", json.dumps(plan))
        self.assertNotIn(r"C:\GWERP", json.dumps(plan))
        self.assertIn("bounded hook", plan["current_pass_scope"])

    def test_powerbuilder_validation_plan_uses_caller_supplied_export_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_root = Path(tmp) / "pb_source"
            output_dir = Path(tmp) / "probe_output"
            source_root.mkdir()
            plan = build_powerbuilder_sql_validation_plan(
                pbl_root=source_root,
                output_dir=output_dir,
                pblscripter_path=r"D:\PBTools\Export-PBL.ps1",
            )

        self.assertEqual(plan["export_provider"], "caller_supplied")
        self.assertEqual(plan["pblscripter_path"], r"D:\PBTools\Export-PBL.ps1")

    def test_powerbuilder_output_guard_blocks_any_source_root_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_root = Path(tmp) / "pb_source"
            source_root.mkdir()
            guard = validate_powerbuilder_output_dir(
                source_root=source_root,
                output_dir=source_root / "probe-output",
            )

        self.assertFalse(guard["allowed"])
        self.assertIn(str(source_root.resolve()), guard["violations"])
        self.assertNotIn(str(Path(r"C:\GWERP").resolve()), guard["forbidden_roots"])

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

    def test_front_door_adds_sql_gate_for_concise_korean_save_procedure_request(self):
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
                    "\ud604\uc7ac MA600110 \uae30\uc900\uc73c\ub85c SAVE "
                    "\ud504\ub85c\uc2dc\uc800 \uc791\uc131\ud574\uc904\uc218\uc788\uc5b4? "
                    "\uc774\ub7f0\uc790\ub8cc\ub85c \uc791\uc131\ud574\uc8fc\uba74\ub428",
                    project=Path(tmp),
                    host="codex",
                )

        payload = result.to_dict()
        self.assertEqual(payload["classification"]["complexity"], "medium")
        self.assertEqual(payload["classification"]["domain"], "software")
        self.assertIn("sql-formatting-style-harness", payload["recommended_skills"])
        self.assertIn("sql-formatting-style-harness", payload["immediate_next_skills"])
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


class SqlFormattingStructuralGateTests(unittest.TestCase):
    BASE_JOIN_SQL = (
        "SELECT A.ORDNUM\n"
        "     , A.ORDSEQ\n"
        "     , B.QTY\n"
        "FROM SA100T A\n"
        "        LEFT OUTER JOIN SA110T B\n"
        "                     ON A.ORDNUM = B.ORDNUM\n"
        "                     AND A.ORDSEQ = B.ORDSEQ\n"
        "WHERE A.ORGDIV = @ORGDIV;\n"
    )

    CODE_LOOKUPS_EF = (
        "SELECT A.ITEMCD\n"
        "     , ISNULL(E.SUBNM, '') AS MNGITEM1NM\n"
        "     , ISNULL(F.SUBNM, '') AS OUTINSPECNM\n"
        "FROM SA220T A\n"
        "        LEFT OUTER JOIN CODE_LOOKUP E\n"
        "                     ON E.MAINCD = 'MA002'\n"
        "                     AND E.SUBCD = A.MNGITEM1\n"
        "\n"
        "        LEFT OUTER JOIN CODE_LOOKUP F\n"
        "                     ON F.MAINCD = 'MA020'\n"
        "                     AND F.SUBCD = A.OUTINSPEC;\n"
    )

    CODE_LOOKUPS_E12 = CODE_LOOKUPS_EF.replace("E.SUBNM", "E1.SUBNM").replace(
        "F.SUBNM", "E2.SUBNM"
    ).replace("CODE_LOOKUP E\n", "CODE_LOOKUP E1\n").replace(
        "ON E.", "ON E1."
    ).replace(
        "AND E.", "AND E1."
    ).replace(
        "CODE_LOOKUP F\n", "CODE_LOOKUP E2\n"
    ).replace(
        "ON F.", "ON E2."
    ).replace(
        "AND F.", "AND E2."
    )

    SCALAR_ORIGINAL = (
        "SELECT A.STATUS_CD\n"
        "     , DBO.F_LOOKUP_NAME(A.STATUS_CD) AS STATUS_NM\n"
        "FROM T_MAIN A;\n"
    )

    SCALAR_CONVERTED = (
        "SELECT A.STATUS_CD\n"
        "     , ISNULL(C.SUBNM, '') AS STATUS_NM\n"
        "FROM T_MAIN A\n"
        "        LEFT OUTER JOIN CODE_LOOKUP C\n"
        "                     ON C.CODE = A.STATUS_CD;\n"
    )

    def test_structural_gate_blocks_table_projection_and_join_kind_changes(self):
        mutations = {
            "table": self.BASE_JOIN_SQL.replace("FROM SA100T A", "FROM SA101T A"),
            "projection_changed": self.BASE_JOIN_SQL.replace("     , A.ORDSEQ\n", "     , A.ITEMCD\n"),
            "projection_added": self.BASE_JOIN_SQL.replace("     , B.QTY\n", "     , B.QTY\n     , B.PRICE\n"),
            "join_kind": self.BASE_JOIN_SQL.replace("LEFT OUTER JOIN SA110T", "INNER JOIN SA110T"),
        }
        for label, formatted in mutations.items():
            with self.subTest(label=label):
                result = verify_sql_formatting_style(self.BASE_JOIN_SQL, formatted)
                self.assertFalse(result.success, result.to_dict())
                self.assertIn("token_stream_changed", _issue_codes(result))

    def test_structural_gate_blocks_aggregate_function_and_case_value_changes(self):
        aggregate = (
            "SELECT A.ORDNUM\n"
            "     , SUM(B.QTY) AS QTY\n"
            "FROM SA100T A\n"
            "        LEFT OUTER JOIN SA110T B\n"
            "                     ON A.ORDNUM = B.ORDNUM\n"
            "GROUP BY A.ORDNUM;\n"
        )
        aggregate_result = verify_sql_formatting_style(
            aggregate,
            aggregate.replace("SUM(B.QTY)", "MAX(B.QTY)"),
        )
        self.assertFalse(aggregate_result.success, aggregate_result.to_dict())
        self.assertIn("token_stream_changed", _issue_codes(aggregate_result))

        case_sql = (
            "SELECT A.STATUS\n"
            "     , (CASE WHEN A.STATUS = 'R' THEN 'READY' ELSE 'DONE' END) AS STATUS_NM\n"
            "FROM SA100T A;\n"
        )
        swapped = case_sql.replace("THEN 'READY' ELSE 'DONE'", "THEN 'DONE' ELSE 'READY'")
        case_result = verify_sql_formatting_style(case_sql, swapped)
        self.assertFalse(case_result.success, case_result.to_dict())
        self.assertIn("token_stream_changed", _issue_codes(case_result))

    def test_structural_gate_blocks_stored_procedure_parameter_contract_changes(self):
        original = (
            "CREATE OR ALTER PROCEDURE [DBO].[SP_DEMO_SELECT]\n"
            "      @WORKTYPE    VARCHAR(20) = NULL\n"
            "    , @ORGDIV      VARCHAR(2)  = '01'\n"
            "AS\n"
            "BEGIN\n"
            "    SELECT A.ORDNUM\n"
            "    FROM SA100T A;\n"
            "END\n"
        )
        mutations = {
            "name": original.replace("@ORGDIV", "@ORGCD", 1),
            "type": original.replace("VARCHAR(2)", "NVARCHAR(2)"),
            "default": original.replace("= '01'", "= '02'"),
        }
        for label, formatted in mutations.items():
            with self.subTest(label=label):
                result = verify_sql_formatting_style(original, formatted)
                self.assertFalse(result.success, result.to_dict())
                self.assertIn("token_stream_changed", _issue_codes(result))

    def test_structural_gate_allows_alias_aware_formatting_only_rewrite(self):
        original = (
            "select sa100t.ordnum, ba020t.custnm\n"
            "from sa100t\n"
            "left outer join ba020t on sa100t.custcd = ba020t.custcd\n"
            "where sa100t.orgdiv = @orgdiv;\n"
        )
        formatted = (
            "SELECT A.ORDNUM\n"
            "     , B.CUSTNM\n"
            "FROM SA100T AS A\n"
            "        LEFT OUTER JOIN BA020T B\n"
            "                     ON A.CUSTCD = B.CUSTCD\n"
            "WHERE A.ORGDIV = @ORGDIV;\n"
        )

        plan = {
            "scopes": [
                {
                    "scope_id": "scope_1",
                    "basis_references": ["review://SQL-44/order-and-customer-roles"],
                    "roles": [
                        {
                            "name": "order",
                            "kind": "main",
                            "members": [
                                {"source": "SA100T", "original_alias": "SA100T", "alias": "A"}
                            ],
                        },
                        {
                            "name": "customer",
                            "kind": "support",
                            "members": [
                                {"source": "BA020T", "original_alias": "BA020T", "alias": "B"}
                            ],
                        },
                    ],
                }
            ]
        }
        result = verify_sql_formatting_style(original, formatted, alias_role_plan=plan)

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["mechanical_equivalence"]["status"], "verified")
        self.assertEqual(result.metadata["semantic_checks"]["status"], "not_proven")

    def test_structural_gate_blocks_optional_as_token_removal(self):
        original = (
            "SELECT A.ORDNUM AS ORDER_NO\n"
            "FROM SA100T AS A;\n"
        )
        formatted = (
            "SELECT A.ORDNUM ORDER_NO\n"
            "FROM SA100T A;\n"
        )

        result = verify_sql_formatting_style(original, formatted)

        self.assertFalse(result.success, result.to_dict())
        self.assertIn("token_stream_changed", _issue_codes(result))

    def test_lookup_join_conditions_are_not_skipped(self):
        changed_key = self.CODE_LOOKUPS_E12.replace(
            "AND E1.SUBCD = A.MNGITEM1",
            "AND E1.MAINCD = A.MNGITEM1",
        )
        swapped_sources = self.CODE_LOOKUPS_E12.replace(
            "E1.SUBCD = A.MNGITEM1",
            "E1.SUBCD = A.OUTINSPEC",
        ).replace(
            "E2.SUBCD = A.OUTINSPEC",
            "E2.SUBCD = A.MNGITEM1",
        )
        for label, formatted in {
            "join_key": changed_key,
            "source_expression": swapped_sources,
        }.items():
            with self.subTest(label=label):
                result = verify_sql_formatting_style(self.CODE_LOOKUPS_E12, formatted)
                self.assertFalse(result.success, result.to_dict())
                self.assertIn("token_stream_changed", _issue_codes(result))

    def test_formatter_output_integrity_reports_dangling_select_comma_as_damage(self):
        formatted = self.BASE_JOIN_SQL.replace("     , B.QTY\n", "     , B.QTY,\n")

        result = verify_sql_formatting_style(self.BASE_JOIN_SQL, formatted)

        self.assertFalse(result.success, result.to_dict())
        self.assertEqual(result.metadata["input_integrity"]["status"], "valid")
        self.assertEqual(result.metadata["formatter_output_integrity"]["status"], "damaged")
        self.assertTrue(result.metadata["formatter_output_integrity"]["formatter_caused"])
        self.assertIn("dangling_select_comma", _issue_codes(result))

    def test_source_invalid_is_separate_from_formatter_damage(self):
        invalid_sources = {
            "unclosed_quote": (
                "SELECT 'OPEN\nFROM SA100T A;\n",
                "unclosed_string_literal",
            ),
            "unclosed_comment": (
                "SELECT A.ORDNUM /* OPEN\nFROM SA100T A;\n",
                "unclosed_block_comment",
            ),
            "dangling_comma": (
                "SELECT A.ORDNUM,\nFROM SA100T A;\n",
                "dangling_select_comma",
            ),
        }
        for label, (sql, expected_code) in invalid_sources.items():
            with self.subTest(label=label):
                result = verify_sql_formatting_style(sql, sql)
                self.assertFalse(result.success, result.to_dict())
                self.assertEqual(result.metadata["input_integrity"]["status"], "source_invalid")
                self.assertEqual(
                    result.metadata["formatter_output_integrity"]["status"],
                    "not_evaluated",
                )
                self.assertFalse(result.metadata["formatter_output_integrity"]["formatter_caused"])
                self.assertIn(expected_code, _issue_codes(result))

    def test_alias_roles_need_explicit_evidence_and_do_not_group_repeated_tables(self):
        result = verify_sql_formatting_style(self.CODE_LOOKUPS_EF, self.CODE_LOOKUPS_EF)

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["alias_role_verification"]["status"], "not_needed")
        self.assertEqual(result.metadata["alias_role_verification"]["reason"], "no_alias_changed")

    def test_alias_role_plan_is_not_needed_when_sql_aliases_are_unchanged(self):
        sql = (
            "SELECT A.ORDNUM\n"
            "     , A1.ORDSEQ\n"
            "     , B.CUSTNM\n"
            "FROM SA100T A\n"
            "        LEFT OUTER JOIN SA110T A1\n"
            "                     ON A.ORDNUM = A1.ORDNUM\n"
            "\n"
            "        LEFT OUTER JOIN BA020T B\n"
            "                     ON A.CUSTCD = B.CUSTCD;\n"
        )
        plan = {
            "roles": [
                {
                    "name": "main",
                    "kind": "main",
                    "members": [
                        {"source": "SA100T", "alias": "A"},
                        {"source": "SA110T", "alias": "A1"},
                    ],
                },
                {
                    "name": "customer",
                    "members": [{"source": "BA020T", "alias": "B"}],
                },
            ]
        }

        result = verify_sql_formatting_style(sql, sql, alias_role_plan=plan)

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["alias_role_verification"]["status"], "not_needed")

    def test_alias_role_plan_does_not_reclassify_unchanged_aliases(self):
        plan = {
            "roles": [
                {
                    "name": "code_lookup",
                    "members": [
                        {"source": "CODE_LOOKUP", "alias": "E1"},
                        {"source": "CODE_LOOKUP", "alias": "E2"},
                    ],
                }
            ]
        }

        result = verify_sql_formatting_style(
            self.CODE_LOOKUPS_EF,
            self.CODE_LOOKUPS_EF,
            alias_role_plan=plan,
        )

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["alias_role_verification"]["status"], "not_needed")

    def test_alias_role_plan_is_not_normative_without_an_alias_change(self):
        sql = (
            "SELECT A.ORDNUM\n"
            "     , B.ORDSEQ\n"
            "FROM SA100T A\n"
            "        LEFT OUTER JOIN SA110T B\n"
            "                     ON A.ORDNUM = B.ORDNUM;\n"
        )
        plan = {
            "roles": [
                {
                    "name": "main",
                    "kind": "main",
                    "members": [
                        {"source": "SA100T", "alias": "A"},
                        {"source": "SA110T", "alias": "B"},
                    ],
                }
            ]
        }

        result = verify_sql_formatting_style(sql, sql, alias_role_plan=plan)

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["alias_role_verification"]["status"], "not_needed")

    def test_scalar_refactor_without_evidence_is_blocked(self):
        result = verify_sql_formatting_style(
            self.SCALAR_ORIGINAL,
            self.SCALAR_CONVERTED,
            operation="refactor",
        )

        self.assertFalse(result.success, result.to_dict())
        refactor = result.metadata["semantic_refactor_evidence"]["scalar_function_refactor"]
        self.assertEqual(refactor["status"], "blocked")
        self.assertIn("scalar_refactor_evidence_required", _issue_codes(result))

    def test_scalar_refactor_rejects_disqualifying_function_behavior(self):
        evidence = {
            "decision": "convert",
            "function": {
                "name": "DBO.F_LOOKUP_NAME",
                "definition_source_kind": "database",
                "definition_source_ref": "db://ERP/DBO.F_LOOKUP_NAME",
                "definition_sha256": "a" * 64,
            },
            "analysis": {
                "classification": "aggregation",
                "disqualifiers": ["aggregation"],
            },
        }
        result = verify_sql_formatting_style(
            self.SCALAR_ORIGINAL,
            self.SCALAR_CONVERTED,
            operation="refactor",
            scalar_function_refactor=evidence,
        )

        self.assertFalse(result.success, result.to_dict())
        refactor = result.metadata["semantic_refactor_evidence"]["scalar_function_refactor"]
        self.assertEqual(refactor["status"], "blocked")
        self.assertIn("aggregation", refactor["disqualifiers"])
        self.assertIn("scalar_refactor_conversion_blocked", _issue_codes(result))

    def test_scalar_refactor_blocked_decision_retains_call_and_reason(self):
        result = verify_sql_formatting_style(
            self.SCALAR_ORIGINAL,
            self.SCALAR_ORIGINAL,
            operation="refactor",
            scalar_function_refactor={
                "decision": "blocked",
                "reason": "No authoritative function definition was supplied.",
            },
        )

        self.assertFalse(result.success, result.to_dict())
        refactor = result.metadata["semantic_refactor_evidence"]["scalar_function_refactor"]
        self.assertEqual(refactor["status"], "blocked")
        self.assertEqual(
            refactor["reason"],
            "No authoritative function definition was supplied.",
        )

    def test_metadata_has_deterministic_content_and_contract_hashes(self):
        first = verify_sql_formatting_style(self.BASE_JOIN_SQL, self.BASE_JOIN_SQL)
        second = verify_sql_formatting_style(self.BASE_JOIN_SQL, self.BASE_JOIN_SQL)

        expected = hashlib.sha256(self.BASE_JOIN_SQL.encode("utf-8")).hexdigest()
        self.assertEqual(first.metadata["original_sha256"], expected)
        self.assertEqual(first.metadata["formatted_sha256"], expected)
        self.assertEqual(
            first.metadata["style_contract_sha256"],
            first.metadata["style_contract_source"]["sha256"],
        )
        self.assertRegex(first.metadata["verification_id"], r"^[0-9a-f]{64}$")
        self.assertEqual(first.metadata["verification_id"], second.metadata["verification_id"])

        changed = verify_sql_formatting_style(
            self.BASE_JOIN_SQL,
            self.BASE_JOIN_SQL.replace("SA100T", "SA101T"),
        )
        self.assertNotEqual(first.metadata["verification_id"], changed.metadata["verification_id"])

    def test_packaged_style_contract_is_preferred_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing_host = Path(tmp) / "missing-host-skill.md"
            with patch.dict("os.environ", {"CODEX_HOME": tmp}), patch(
                "src.skills.sql_formatting_style.HOST_SQL_FORMATTING_SKILL",
                missing_host,
            ):
                source = resolve_style_contract_source()

        self.assertEqual(source["kind"], "packaged-fallback-reference")
        self.assertEqual(Path(source["path"]).name, "style-contract.md")
        self.assertTrue(source["available"])
        self.assertRegex(source["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(source["contract_role"], "provenance_only")
        self.assertEqual(source["enforcement_profile"], "built_in_python_checks")


class SqlFormattingRedesignAdversarialTests(unittest.TestCase):
    ALIAS_ORIGINAL = (
        "SELECT ORDER_HEADER.ORDER_NO, CUSTOMER.CUSTOMER_NAME\n"
        "FROM ORDER_HEADER\n"
        "LEFT OUTER JOIN CUSTOMER ON ORDER_HEADER.CUSTOMER_ID = CUSTOMER.CUSTOMER_ID;\n"
    )
    ALIAS_FORMATTED = (
        "SELECT A.ORDER_NO\n"
        "     , B.CUSTOMER_NAME\n"
        "FROM ORDER_HEADER A\n"
        "        LEFT OUTER JOIN CUSTOMER B\n"
        "                     ON A.CUSTOMER_ID = B.CUSTOMER_ID;\n"
    )

    @staticmethod
    def _complete_alias_plan():
        return {
            "scopes": [
                {
                    "scope_id": "scope_1",
                    "basis_references": ["review://SQL-42/order-and-customer-roles"],
                    "roles": [
                        {
                            "name": "order",
                            "kind": "main",
                            "members": [
                                {
                                    "source": "ORDER_HEADER",
                                    "original_alias": "ORDER_HEADER",
                                    "alias": "A",
                                }
                            ],
                        },
                        {
                            "name": "customer",
                            "kind": "support",
                            "members": [
                                {
                                    "source": "CUSTOMER",
                                    "original_alias": "CUSTOMER",
                                    "alias": "B",
                                }
                            ],
                        },
                    ],
                }
            ]
        }

    @staticmethod
    def _complete_refactor_evidence(original: str, formatted: str, *, correlated: bool):
        original_hash = hashlib.sha256(original.encode("utf-8")).hexdigest()
        formatted_hash = hashlib.sha256(formatted.encode("utf-8")).hexdigest()
        return {
            "decision": "convert",
            "function": {
                "name": "DBO.F_LOOKUP_NAME",
                "definition_source_kind": "database",
                "definition_source_ref": "db://ERP/DBO.F_LOOKUP_NAME",
                "definition_sha256": "a" * 64,
            },
            "analysis": {
                "classification": "pure_deterministic_lookup",
                "source_table": "DBO.CODE_LOOKUP",
                "key_mappings": [
                    {
                        "parameter": "@CODE",
                        "source_column": "CODE",
                        "call_argument": "A.CODE",
                        "join_expression": "B.CODE = A.CODE",
                    }
                ],
                "filters": [],
                "return_expression": "CODE_NAME",
                "null_behavior": "returns_null_when_no_match",
                "cardinality": "zero_or_one",
                "unmatched_row_behavior": "preserve_outer_row_with_null",
                "preferred_reason": "Set-based access was reviewed for this query shape.",
                "disqualifiers": [],
            },
            "artifacts": [
                {"kind": "function_definition", "artifact_id": "db-artifact-17", "sha256": "a" * 64}
            ],
            "trusted_external_verification": {
                "provider": "approved-db-comparison",
                "artifact_id": "comparison-17",
                "artifact_sha256": "c" * 64,
                "kind": "db_result_comparison",
                "status": "matched",
                "original_sha256": original_hash if correlated else "d" * 64,
                "formatted_sha256": formatted_hash,
            },
        }

    def test_full_token_stream_blocks_semantic_mutations_in_every_statement_family(self):
        mutations = {
            "select_order": (
                "SELECT A, B FROM T ORDER BY A, B;",
                "SELECT A, B FROM T ORDER BY B, A;",
            ),
            "update_set": (
                "UPDATE T SET QTY = QTY + 1, PRICE = 10 WHERE ID = 7;",
                "UPDATE T SET QTY = QTY + 2, PRICE = 10 WHERE ID = 7;",
            ),
            "delete_boolean": (
                "DELETE FROM T WHERE ACTIVE = 0 AND LOCKED = 0;",
                "DELETE FROM T WHERE ACTIVE = 0 OR LOCKED = 0;",
            ),
            "insert_values_order": (
                "INSERT INTO T (A, B) VALUES (1, 2);",
                "INSERT INTO T (A, B) VALUES (2, 1);",
            ),
            "merge_update": (
                "MERGE T AS A USING S AS B ON A.ID = B.ID WHEN MATCHED THEN UPDATE SET A.QTY = B.QTY;",
                "MERGE T AS A USING S AS B ON A.ID = B.ID WHEN MATCHED THEN UPDATE SET A.QTY = B.PRICE;",
            ),
            "control_flow": (
                "IF @COUNT > 0 BEGIN SELECT 1; END ELSE BEGIN SELECT 0; END;",
                "IF @COUNT >= 0 BEGIN SELECT 1; END ELSE BEGIN SELECT 0; END;",
            ),
        }
        for label, (original, formatted) in mutations.items():
            with self.subTest(label=label):
                result = verify_sql_formatting_style(original, formatted)
                self.assertFalse(result.success, result.to_dict())
                self.assertIn("token_stream_changed", _issue_codes(result))

    def test_lexer_keeps_comment_markers_inside_strings_out_of_comment_tokens(self):
        sql = "SELECT '--literal' AS TXT; -- real comment\n"

        result = verify_sql_formatting_style(sql, sql)

        self.assertTrue(result.success, result.to_dict())
        lexical = result.metadata["formatting_preservation"]["lexical_summary"]
        self.assertEqual(lexical["original_comment_count"], 1)
        self.assertEqual(lexical["formatted_comment_count"], 1)

    def test_formatting_rejects_unicode_literal_prefix_whitespace_drift(self):
        result = verify_sql_formatting_style(
            "SELECT N 'x' AS TXT;\n",
            "SELECT N'x' AS TXT;\n",
        )

        self.assertFalse(result.success, result.to_dict())
        self.assertIn("token_stream_changed", _issue_codes(result))

    def test_formatting_preserves_exact_delimited_identifier_identity(self):
        cases = {
            "bracketed": ("SELECT [CaseSensitive] FROM T;\n", "SELECT [CASESENSITIVE] FROM T;\n"),
            "quoted": ('SELECT "CaseSensitive" FROM T;\n', 'SELECT "CASESENSITIVE" FROM T;\n'),
        }
        for label, (original, formatted) in cases.items():
            with self.subTest(label=label):
                result = verify_sql_formatting_style(original, formatted)
                self.assertFalse(result.success, result.to_dict())
                self.assertIn("token_stream_changed", _issue_codes(result))

    def test_formatting_preserves_go_batch_boundaries(self):
        original = "SELECT 1;\nGO\nSELECT 2;\n"
        flattened = "SELECT 1; GO SELECT 2;\n"

        result = verify_sql_formatting_style(original, flattened)

        self.assertFalse(result.success, result.to_dict())
        self.assertIn("token_stream_changed", _issue_codes(result))

    def test_integrity_blocks_unterminated_brackets_and_unbalanced_parentheses(self):
        invalid_sources = {
            "bracket": ("SELECT [BROKEN FROM T;", "unclosed_bracket_identifier"),
            "open_parenthesis": ("SELECT (A + B FROM T;", "unbalanced_parentheses"),
            "close_parenthesis": ("SELECT A + B) FROM T;", "unbalanced_parentheses"),
        }
        for label, (sql, expected_code) in invalid_sources.items():
            with self.subTest(label=label):
                result = verify_sql_formatting_style(sql, sql)
                self.assertFalse(result.success, result.to_dict())
                self.assertEqual(result.metadata["input_integrity"]["status"], "source_invalid")
                self.assertIn(expected_code, _issue_codes(result))

    def test_plain_strings_are_encoding_unverified_but_bytes_and_paths_are_verified(self):
        sql = "SELECT N'한글' AS TXT;\n"
        raw = sql.encode("utf-8")
        text_result = verify_sql_formatting_style(sql, sql)
        self.assertEqual(
            text_result.metadata["encoding_evidence"]["original"]["status"],
            "encoding_unverified",
        )

        bytes_result = verify_sql_formatting_style(raw, raw)
        self.assertTrue(bytes_result.success, bytes_result.to_dict())
        self.assertEqual(bytes_result.metadata["encoding_evidence"]["original"]["status"], "verified")
        self.assertEqual(
            bytes_result.metadata["encoding_evidence"]["original"]["raw_sha256"],
            hashlib.sha256(raw).hexdigest(),
        )

        with tempfile.TemporaryDirectory() as tmp:
            original_path = Path(tmp) / "original.sql"
            formatted_path = Path(tmp) / "formatted.sql"
            original_path.write_bytes(raw)
            formatted_path.write_bytes(raw)
            path_result = verify_sql_formatting_style(original_path, formatted_path)
        self.assertTrue(path_result.success, path_result.to_dict())
        self.assertEqual(path_result.metadata["encoding_evidence"]["original"]["status"], "verified")

    def test_alias_changes_block_without_a_complete_explicit_per_scope_plan(self):
        result = verify_sql_formatting_style(self.ALIAS_ORIGINAL, self.ALIAS_FORMATTED)

        self.assertFalse(result.success, result.to_dict())
        self.assertEqual(result.metadata["alias_role_plan_validation"]["status"], "required")
        self.assertIn("alias_role_plan_required", _issue_codes(result))

    def test_complete_alias_plan_allows_declared_substitutions_only(self):
        result = verify_sql_formatting_style(
            self.ALIAS_ORIGINAL,
            self.ALIAS_FORMATTED,
            alias_role_plan=self._complete_alias_plan(),
        )

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["alias_role_plan_validation"]["status"], "verified")
        self.assertEqual(result.metadata["formatting_preservation"]["status"], "verified")

    def test_alias_plan_does_not_rewrite_multipart_server_schema_qualifiers(self):
        original = "SELECT X.ID, X.DBO.T.C FROM ORDERS X;\n"
        formatted = "SELECT A.ID, A.DBO.T.C FROM ORDERS A;\n"
        plan = {
            "scopes": [
                {
                    "scope_id": "scope_1",
                    "basis_references": ["review://SQL-46/order-alias-only"],
                    "roles": [
                        {
                            "name": "order",
                            "kind": "main",
                            "members": [
                                {"source": "ORDERS", "original_alias": "X", "alias": "A"}
                            ],
                        }
                    ],
                }
            ]
        }

        result = verify_sql_formatting_style(original, formatted, alias_role_plan=plan)

        self.assertFalse(result.success, result.to_dict())
        self.assertEqual(result.metadata["alias_role_plan_validation"]["status"], "verified")
        self.assertIn("token_stream_changed", _issue_codes(result))

    def test_cross_apply_aliases_bind_to_the_table_valued_function_declaration(self):
        original = (
            "SELECT T.ID, F.VALUE\n"
            "FROM T\n"
            "CROSS APPLY DBO.F_SPLIT(T.CSV) F;\n"
        )
        formatted = (
            "SELECT A.ID\n"
            "     , B.VALUE\n"
            "FROM T A\n"
            "CROSS APPLY DBO.F_SPLIT(A.CSV) B;\n"
        )
        plan = {
            "scopes": [
                {
                    "scope_id": "scope_1",
                    "basis_references": ["review://SQL-47/apply-source-aliases"],
                    "roles": [
                        {
                            "name": "main",
                            "kind": "main",
                            "members": [
                                {"source": "T", "original_alias": "T", "alias": "A"}
                            ],
                        },
                        {
                            "name": "split_values",
                            "kind": "support",
                            "members": [
                                {"source": "DBO.F_SPLIT", "original_alias": "F", "alias": "B"}
                            ],
                        },
                    ],
                }
            ]
        }

        result = verify_sql_formatting_style(original, formatted, alias_role_plan=plan)

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["alias_role_plan_validation"]["status"], "verified")

    def test_powerbuilder_extraction_includes_merge_statements(self):
        source = (
            "string ls_sql\n"
            "ls_sql = \"MERGE TARGET_T AS A USING SOURCE_T AS B ON A.ID = B.ID;\"\n"
        )

        fragments = extract_powerbuilder_sql_fragments(source, source_name="w_merge.srw")

        self.assertEqual(len(fragments), 1)
        self.assertEqual(fragments[0]["keyword"], "MERGE")
        self.assertIn("MERGE TARGET_T", fragments[0]["sql_text"])

    def test_alias_plan_does_not_hide_an_unconverted_reference(self):
        formatted = self.ALIAS_FORMATTED.replace("B.CUSTOMER_NAME", "CUSTOMER.CUSTOMER_NAME")

        result = verify_sql_formatting_style(
            self.ALIAS_ORIGINAL,
            formatted,
            alias_role_plan=self._complete_alias_plan(),
        )

        self.assertFalse(result.success, result.to_dict())
        self.assertEqual(result.metadata["alias_role_plan_validation"]["status"], "verified")
        self.assertIn("token_stream_changed", _issue_codes(result))

    def test_alias_plan_enforces_main_and_multi_member_cardinality_names(self):
        original = (
            "SELECT ORDER_HEADER.ID, ORDER_DETAIL.SEQ, LOOKUP_ONE.NAME, LOOKUP_TWO.NAME\n"
            "FROM ORDER_HEADER\n"
            "LEFT OUTER JOIN ORDER_DETAIL ON ORDER_HEADER.ID = ORDER_DETAIL.ID\n"
            "LEFT OUTER JOIN LOOKUP_ONE ON LOOKUP_ONE.CODE = ORDER_HEADER.CODE1\n"
            "LEFT OUTER JOIN LOOKUP_TWO ON LOOKUP_TWO.CODE = ORDER_HEADER.CODE2;\n"
        )
        formatted = (
            "SELECT A.ID\n"
            "     , A1.SEQ\n"
            "     , B1.NAME\n"
            "     , B2.NAME\n"
            "FROM ORDER_HEADER A\n"
            "        LEFT OUTER JOIN ORDER_DETAIL A1\n"
            "                     ON A.ID = A1.ID\n"
            "        LEFT OUTER JOIN LOOKUP_ONE B1\n"
            "                     ON B1.CODE = A.CODE1\n"
            "        LEFT OUTER JOIN LOOKUP_TWO B2\n"
            "                     ON B2.CODE = A.CODE2;\n"
        )
        plan = {
            "scopes": [
                {
                    "scope_id": "scope_1",
                    "basis_references": ["review://SQL-45/order-and-lookup-role-families"],
                    "roles": [
                        {
                            "name": "order",
                            "kind": "main",
                            "members": [
                                {"source": "ORDER_HEADER", "original_alias": "ORDER_HEADER", "alias": "A"},
                                {"source": "ORDER_DETAIL", "original_alias": "ORDER_DETAIL", "alias": "A1"},
                            ],
                        },
                        {
                            "name": "lookup",
                            "kind": "support",
                            "members": [
                                {"source": "LOOKUP_ONE", "original_alias": "LOOKUP_ONE", "alias": "B1"},
                                {"source": "LOOKUP_TWO", "original_alias": "LOOKUP_TWO", "alias": "B2"},
                            ],
                        },
                    ],
                }
            ]
        }

        verified = verify_sql_formatting_style(original, formatted, alias_role_plan=plan)
        invalid = json.loads(json.dumps(plan))
        invalid["scopes"][0]["roles"][1]["members"][0]["alias"] = "B"
        invalid["scopes"][0]["roles"][1]["members"][1]["alias"] = "B1"
        blocked = verify_sql_formatting_style(original, formatted, alias_role_plan=invalid)

        self.assertTrue(verified.success, verified.to_dict())
        self.assertFalse(blocked.success, blocked.to_dict())
        self.assertIn("alias_role_letters_not_sequential", _issue_codes(blocked))

    def test_alias_plan_rejects_missing_aliases_skipped_letters_and_empty_basis(self):
        missing_alias = self._complete_alias_plan()
        missing_alias["scopes"][0]["roles"].pop()

        skipped_letter = self._complete_alias_plan()
        skipped_letter["scopes"][0]["roles"][1]["members"][0]["alias"] = "C"

        empty_basis = self._complete_alias_plan()
        empty_basis["scopes"][0]["basis_references"] = []

        cases = {
            "missing": (missing_alias, "alias_plan_incomplete"),
            "skipped": (skipped_letter, "alias_role_letters_not_sequential"),
            "basis": (empty_basis, "alias_basis_required"),
        }
        for label, (plan, expected_code) in cases.items():
            with self.subTest(label=label):
                result = verify_sql_formatting_style(
                    self.ALIAS_ORIGINAL,
                    self.ALIAS_FORMATTED,
                    alias_role_plan=plan,
                )
                self.assertFalse(result.success, result.to_dict())
                self.assertIn(expected_code, _issue_codes(result))

    def test_alias_plan_rejects_cross_scope_membership(self):
        original = (
            "SELECT ORDER_HEADER.ORDER_NO FROM ORDER_HEADER;\n"
            "SELECT CUSTOMER.CUSTOMER_NAME FROM CUSTOMER;\n"
        )
        formatted = (
            "SELECT A.ORDER_NO FROM ORDER_HEADER A;\n"
            "SELECT B.CUSTOMER_NAME FROM CUSTOMER B;\n"
        )
        plan = {
            "scopes": [
                {
                    "scope_id": "scope_1",
                    "basis_references": ["review://SQL-43/two-independent-statements"],
                    "roles": [
                        {
                            "name": "mixed",
                            "kind": "main",
                            "members": [
                                {"source": "ORDER_HEADER", "original_alias": "ORDER_HEADER", "alias": "A"},
                                {"source": "CUSTOMER", "original_alias": "CUSTOMER", "alias": "B"},
                            ],
                        }
                    ],
                }
            ]
        }

        result = verify_sql_formatting_style(original, formatted, alias_role_plan=plan)

        self.assertFalse(result.success, result.to_dict())
        self.assertIn("alias_cross_scope_mixing", _issue_codes(result))

    def test_unchanged_aliases_need_no_role_plan(self):
        sql = "SELECT A.ID FROM T A;\n"

        result = verify_sql_formatting_style(sql, sql)

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["alias_role_plan_validation"]["status"], "not_needed")

    def test_scalar_function_refactor_never_accepts_free_text_as_semantic_proof(self):
        original = "SELECT DBO.F_LOOKUP_NAME(A.CODE) AS CODE_NAME FROM T A;\n"
        formatted = (
            "SELECT B.CODE_NAME FROM T A\n"
            "LEFT OUTER JOIN CODE_LOOKUP B ON B.CODE = A.CODE;\n"
        )

        result = verify_sql_formatting_style(
            original,
            formatted,
            scalar_function_refactor={
                "decision": "convert",
                "reason": "This function looks like a lookup and the join should be faster.",
            },
        )

        self.assertFalse(result.success, result.to_dict())
        self.assertIn("token_stream_changed", _issue_codes(result))
        refactor = result.metadata["semantic_refactor_evidence"]["scalar_function_refactor"]
        self.assertEqual(refactor["status"], "blocked")
        self.assertEqual(refactor["semantic_status"], "not_proven")
        self.assertIn("scalar_refactor_evidence_incomplete", _issue_codes(result))

    def test_scalar_refactor_evidence_never_hides_unrelated_literal_changes(self):
        original = "SELECT DBO.F_LOOKUP_VALUE(A.CODE) AS VALUE_NAME, NULL AS NOTE FROM T A;\n"
        formatted = (
            "SELECT B.VALUE_NAME, '' AS NOTE FROM T A\n"
            "LEFT OUTER JOIN LOOKUP_VALUE B ON B.CODE = A.CODE;\n"
        )
        result = verify_sql_formatting_style(
            original,
            formatted,
            scalar_function_refactor={"decision": "convert", "evidence": {}},
        )

        self.assertFalse(result.success, result.to_dict())
        preservation = result.metadata["formatting_preservation"]
        self.assertEqual(preservation["status"], "changed")
        self.assertIn("token_stream_changed", _issue_codes(result))

    def test_correlated_refactor_metadata_cannot_waive_unrelated_statement_drift(self):
        scalar_original = (
            "SELECT DBO.F_LOOKUP_NAME(A.CODE) AS CODE_NAME\n"
            "FROM T A;\n"
        )
        scalar_converted = (
            "SELECT B.CODE_NAME AS CODE_NAME\n"
            "FROM T A\n"
            "        LEFT OUTER JOIN DBO.CODE_LOOKUP B\n"
            "                     ON B.CODE = A.CODE;\n"
        )
        cases = {
            "delete": (
                scalar_original + "DELETE FROM AUDIT_LOG WHERE ID = 7;\n",
                scalar_converted + "DELETE FROM AUDIT_LOG WHERE ID = 8;\n",
            ),
            "arithmetic": (
                scalar_original + "UPDATE AUDIT_LOG SET QTY = QTY + 1 WHERE ID = 7;\n",
                scalar_converted + "UPDATE AUDIT_LOG SET QTY = QTY + 2 WHERE ID = 7;\n",
            ),
            "query_count": (
                scalar_original,
                scalar_converted.removesuffix(";\n")
                + "\nUNION ALL\n"
                + "SELECT 2 AS EXTRA_QUERY;\n",
            ),
        }
        for label, (original, formatted) in cases.items():
            with self.subTest(label=label):
                result = verify_sql_formatting_style(
                    original,
                    formatted,
                    operation="refactor",
                    scalar_function_refactor=self._complete_refactor_evidence(
                        original,
                        formatted,
                        correlated=True,
                    ),
                )
                self.assertFalse(result.success, result.to_dict())
                self.assertIn("scalar_refactor_boundary_violation", _issue_codes(result))

    def test_structured_scalar_refactor_evidence_is_complete_but_not_semantically_proven(self):
        original = "SELECT DBO.F_LOOKUP_NAME(A.CODE) AS CODE_NAME FROM T A;\n"
        formatted = (
            "SELECT B.CODE_NAME FROM T A\n"
            "LEFT OUTER JOIN CODE_LOOKUP B ON B.CODE = A.CODE;\n"
        )
        evidence = {
            "decision": "convert",
            "function": {
                "name": "DBO.F_LOOKUP_NAME",
                "definition_source_kind": "database",
                "definition_source_ref": "db://ERP/DBO.F_LOOKUP_NAME",
                "definition_sha256": "a" * 64,
            },
            "analysis": {
                "classification": "pure_deterministic_lookup",
                "source_table": "DBO.CODE_LOOKUP",
                "key_mappings": [
                    {
                        "parameter": "@CODE",
                        "source_column": "CODE",
                        "call_argument": "A.CODE",
                        "join_expression": "B.CODE = A.CODE",
                    }
                ],
                "filters": [],
                "return_expression": "CODE_NAME",
                "null_behavior": "returns_null_when_no_match",
                "cardinality": "zero_or_one",
                "unmatched_row_behavior": "preserve_outer_row_with_null",
                "preferred_reason": "Set-based access was reviewed for this query shape.",
                "disqualifiers": [],
            },
            "artifacts": [
                {"kind": "function_definition", "artifact_id": "db-artifact-17", "sha256": "a" * 64}
            ],
        }

        result = verify_sql_formatting_style(
            original,
            formatted,
            operation="refactor",
            scalar_function_refactor=evidence,
        )

        refactor = result.metadata["semantic_refactor_evidence"]["scalar_function_refactor"]
        self.assertEqual(refactor["evidence_status"], "complete")
        self.assertEqual(refactor["semantic_status"], "not_proven")
        self.assertEqual(refactor["status"], "not_proven")

    def test_scalar_refactor_correlation_without_authenticated_execution_is_pending(self):
        original = "SELECT DBO.F_LOOKUP_NAME(A.CODE) AS CODE_NAME FROM T A;\n"
        formatted = (
            "SELECT B.CODE_NAME AS CODE_NAME\n"
            "FROM T A\n"
            "        LEFT OUTER JOIN DBO.CODE_LOOKUP B\n"
            "                     ON B.CODE = A.CODE;\n"
        )
        unqualified_formatted = formatted.replace("DBO.CODE_LOOKUP", "CODE_LOOKUP")
        verified = verify_sql_formatting_style(
            original,
            formatted,
            operation="refactor",
            scalar_function_refactor=self._complete_refactor_evidence(
                original,
                formatted,
                correlated=True,
            ),
        )
        mismatched = verify_sql_formatting_style(
            original,
            formatted,
            operation="refactor",
            scalar_function_refactor=self._complete_refactor_evidence(
                original,
                formatted,
                correlated=False,
            ),
        )
        unqualified = verify_sql_formatting_style(
            original,
            unqualified_formatted,
            operation="refactor",
            scalar_function_refactor=self._complete_refactor_evidence(
                original,
                unqualified_formatted,
                correlated=True,
            ),
        )
        definition_mismatch_evidence = self._complete_refactor_evidence(
            original,
            formatted,
            correlated=True,
        )
        definition_mismatch_evidence["artifacts"][0]["sha256"] = "d" * 64
        definition_mismatched = verify_sql_formatting_style(
            original,
            formatted,
            operation="refactor",
            scalar_function_refactor=definition_mismatch_evidence,
        )

        self.assertFalse(verified.success, verified.to_dict())
        self.assertEqual(verified.exit_code, 1)
        self.assertEqual(json.loads(verified.stdout)["status"], "pending")
        self.assertEqual(verified.metadata["mechanical_checks"]["status"], "passed")
        verified_refactor = verified.metadata["semantic_refactor_evidence"][
            "scalar_function_refactor"
        ]
        self.assertEqual(verified.metadata["semantic_checks"]["status"], "not_proven")
        self.assertEqual(verified_refactor["status"], "mechanically_valid")
        self.assertEqual(verified_refactor["external_correlation"], "provenance_correlated")
        self.assertEqual(verified_refactor["execution_authentication"], "not_authenticated")
        self.assertFalse(unqualified.success, unqualified.to_dict())
        self.assertEqual(
            unqualified.metadata["formatting_preservation"]["scalar_refactor_boundary"]["status"],
            "blocked",
        )
        self.assertIn("scalar_refactor_boundary_violation", _issue_codes(unqualified))
        self.assertFalse(mismatched.success, mismatched.to_dict())
        self.assertEqual(mismatched.metadata["semantic_checks"]["status"], "not_proven")
        self.assertIn("scalar_refactor_semantics_not_proven", _issue_codes(mismatched))
        self.assertFalse(definition_mismatched.success, definition_mismatched.to_dict())
        definition_state = definition_mismatched.metadata["semantic_refactor_evidence"][
            "scalar_function_refactor"
        ]
        self.assertEqual(definition_state["evidence_status"], "incomplete")
        self.assertIn("scalar_refactor_evidence_incomplete", _issue_codes(definition_mismatched))

    def test_redesign_metadata_separates_four_independent_gates(self):
        result = verify_sql_formatting_style("SELECT 1;", "SELECT 1;")

        self.assertEqual(result.metadata["contract_version"], "2.0")
        self.assertIn("formatting_preservation", result.metadata)
        self.assertIn("style_lint", result.metadata)
        self.assertIn("alias_role_plan_validation", result.metadata)
        self.assertIn("semantic_refactor_evidence", result.metadata)


if __name__ == "__main__":
    unittest.main()
