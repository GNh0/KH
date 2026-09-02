import hashlib
import hmac
import tempfile
import unittest
from pathlib import Path

from src.skills.csharp_designer_style import verify_csharp_edit_contract
from src.skills.sql_formatting_style import (
    _full_replace_pairs,
    _runtime_receipt_payload,
    bind_sql_alias_role_plan,
    normalize_sql_join_layout,
    verify_sql_formatting_style,
)


ROOT = Path(__file__).resolve().parents[1]


def issue_codes(result):
    return {
        item["code"]
        for item in result.metadata.get("mechanical_checks", {}).get("style_issues", [])
    }


def preservation_issue_codes(result):
    return {
        item["code"]
        for item in result.metadata.get("mechanical_checks", {}).get(
            "preservation_issues",
            [],
        )
    }


class CSharpSqlHarnessRegressionTests(unittest.TestCase):
    @staticmethod
    def _candidate_bound_alias_plan(sql):
        return bind_sql_alias_role_plan(
            sql,
            {
                "scopes": [
                    {
                        "scope_id": "scope_1",
                        "basis_references": [
                            {
                                "kind": "reviewer_approved_business_role",
                                "source": "review://SQL-GENERATION/main-and-detail-roles",
                                "reviewer_approved": True,
                                "role_names": ["main", "detail"],
                            }
                        ],
                        "roles": [
                            {
                                "name": "main",
                                "kind": "main",
                                "members": [
                                    {
                                        "source": "ORDER_HEADER",
                                        "original_alias": "A",
                                        "alias": "A",
                                    }
                                ],
                            },
                            {
                                "name": "detail",
                                "kind": "support",
                                "members": [
                                    {
                                        "source": "CUSTOMER",
                                        "original_alias": "B",
                                        "alias": "B",
                                    }
                                ],
                            },
                        ],
                    }
                ]
            },
        )

    @staticmethod
    def _ba035t_tmp_bound_alias_plan(sql):
        return bind_sql_alias_role_plan(
            sql,
            {
                "scopes": [
                    {
                        "scope_id": "scope_1",
                        "basis_references": [
                            {
                                "kind": "reviewer_approved_business_role",
                                "source": "review://SQL-GENERATION/ba035t-tmp-roles",
                                "reviewer_approved": True,
                                "role_names": ["target", "input"],
                            }
                        ],
                        "roles": [
                            {
                                "name": "target",
                                "kind": "main",
                                "members": [
                                    {
                                        "source": "BA035T",
                                        "original_alias": "A",
                                        "alias": "A",
                                    }
                                ],
                            },
                            {
                                "name": "input",
                                "kind": "support",
                                "members": [
                                    {
                                        "source": "@tmp",
                                        "original_alias": "B",
                                        "alias": "B",
                                    }
                                ],
                            },
                        ],
                    }
                ]
            },
        )

    def test_csharp_skill_routes_generation_and_modification(self):
        skill = (ROOT / "skills/csharp_designer_style_harness/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("generating, modifying, or reviewing", skill)

    def test_csharp_guard_blocks_invented_grid_commit_and_whole_table_loop(self):
        original = """
private void SaveCommand()
{
    CallSaveProcedure();
}
"""
        candidate = """
private void SaveCommand()
{
    gvwList.PostEditor();
    gvwList.UpdateCurrentRow();
    foreach (DataRow row in dtDetail.Rows)
    {
        row["PARENT_KEY"] = btnParent.Text;
    }
    NormalizeDetailKeys();
    CallSaveProcedure();
}

private void NormalizeDetailKeys()
{
}
"""
        result = verify_csharp_edit_contract(original, candidate)
        codes = {item["code"] for item in result.metadata["issues"]}
        self.assertFalse(result.success)
        self.assertIn("invented_edit_commit_call", codes)
        self.assertIn("invented_whole_table_row_rewrite", codes)
        self.assertNotIn("invented_helper_method", codes)

    def test_csharp_guard_blocks_common_whole_table_row_sources(self):
        row_sources = (
            "ds.Tables[0].Rows",
            "dtMACList.Select()",
            "dtMACList.Rows.Cast<DataRow>()",
        )
        for row_source in row_sources:
            with self.subTest(row_source=row_source):
                candidate = f"""
private void btnSave_Click(object sender, EventArgs e)
{{
    foreach (DataRow row in {row_source})
    {{
        row["ITEMCD"] = btnITEMCD.Text;
    }}
}}
"""
                result = verify_csharp_edit_contract("", candidate)
                codes = {item["code"] for item in result.metadata["issues"]}
                self.assertIn("invented_whole_table_row_rewrite", codes)

    def test_csharp_guard_allows_read_only_loop_and_ignores_examples_in_comments_and_strings(self):
        candidate = r'''
private void btnSave_Click(object sender, EventArgs e)
{
    foreach (DataRow row in ds.Tables[0].Rows)
    {
        string itemcd = Convert.ToString(row["ITEMCD"]);
    }

    // foreach (DataRow row in dtMACList.Rows) { row["ITEMCD"] = "X"; }
    string example = "foreach (DataRow row in dtMACList.Select()) { row[\"ITEMCD\"] = \"X\"; }";
}
'''
        result = verify_csharp_edit_contract("", candidate)
        self.assertTrue(result.success, result.to_dict())

    def test_csharp_guard_does_not_block_ordinary_new_helpers(self):
        candidate = """
private bool IsReady()
{
    return btnITEMCD.EditValue != null;
}

private string CurrentItemCode() => Convert.ToString(btnITEMCD.EditValue);
"""
        result = verify_csharp_edit_contract("", candidate)
        self.assertTrue(result.success, result.to_dict())

    def test_csharp_guard_blocks_transaction_save_invocation_downgrade(self):
        original = '''
private bool SaveData()
{
    return dbClient.ExecSPTrn("sp_SAMPLE_SAVE", parameters);
}
'''
        candidate = original.replace("ExecSPTrn", "ExecSP")

        result = verify_csharp_edit_contract(original, candidate)
        codes = {item["code"] for item in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("transaction_save_invocation_downgraded", codes)

    def test_csharp_guard_blocks_arbitrary_target_local_method_removal(self):
        original = '''
private void SaveCommand()
{
    ApplyRowState(currentRow);
}

private void ApplyRowState(DataRow row)
{
    row.AcceptChanges();
}
'''
        candidate = '''
private void SaveCommand()
{
}
'''

        result = verify_csharp_edit_contract(original, candidate)
        removed = [
            item
            for item in result.metadata["issues"]
            if item["code"] == "target_local_helper_removed"
        ]

        self.assertFalse(result.success)
        self.assertEqual(1, len(removed), result.metadata["issues"])
        self.assertEqual(
            "ApplyRowState`0(DataRow)",
            removed[0]["evidence"]["signature"],
        )

    def test_csharp_guard_excludes_event_override_and_generated_lifecycle_removal(self):
        original = '''
private void btnSave_Click(object sender, EventArgs e)
{
}

protected override void OnLoad(EventArgs e)
{
    base.OnLoad(e);
}

private void InitializeComponent()
{
}
'''

        result = verify_csharp_edit_contract(original, "")

        self.assertTrue(result.success, result.to_dict())

    def test_sql_generation_blocks_not_in_where_subquery(self):
        candidate = """
SELECT A.ITEMCD
FROM ITEM_MASTER A
WHERE A.ITEMCD NOT IN (SELECT B.ITEMCD FROM BLOCKED_ITEM B);
"""
        result = verify_sql_formatting_style("", candidate, operation="generation")
        self.assertFalse(result.success)
        self.assertIn("where_subquery_introduced", issue_codes(result))
        self.assertEqual(
            1,
            result.metadata["style_lint"]["where_subquery_policy"]["introduced_not_in_count"],
        )

    def test_if_exists_layout_is_token_column_based_and_normalized_with_join_rules(self):
        malformed = (
            "    IF EXISTS (\n"
            "          SELECT 1\n"
            "       FROM ORDER_HEADER A\n"
            "             INNER JOIN CUSTOMER B\n"
            "                ON A.CUSTOMER_ID = B.CUSTOMER_ID\n"
            "                  AND B.ACTIVE_YN = 'Y'\n"
            "         WHERE A.ACTIVE_YN = 'Y'\n"
            "       )\n"
            "      BEGIN\n"
            "        RETURN;\n"
            "      END\n"
        )
        plan = self._candidate_bound_alias_plan(malformed)

        invalid = verify_sql_formatting_style(
            malformed,
            malformed,
            alias_role_plan=plan,
        )
        normalized = normalize_sql_join_layout(malformed)
        repaired = verify_sql_formatting_style(
            malformed,
            normalized,
            alias_role_plan=plan,
        )
        lines = normalized.splitlines()
        open_column = lines[0].index("(")
        join_column = lines[3].index("JOIN")

        self.assertIn("if_exists_parenthesis_alignment_invalid", issue_codes(invalid))
        self.assertIn("if_exists_inner_start_alignment_invalid", issue_codes(invalid))
        self.assertIn("if_exists_inner_clause_alignment_invalid", issue_codes(invalid))
        self.assertIn("if_exists_begin_alignment_invalid", issue_codes(invalid))
        self.assertEqual(open_column + 1, lines[1].index("SELECT"))
        self.assertEqual(open_column + 1, lines[2].index("FROM"))
        self.assertEqual(open_column + 1, lines[6].index("WHERE"))
        self.assertEqual(open_column, lines[7].index(")"))
        self.assertEqual(lines[0].index("IF"), lines[8].index("BEGIN"))
        self.assertEqual(join_column + 2, lines[4].index("ON"))
        self.assertEqual(join_column + 2, lines[5].index("AND"))
        self.assertTrue(repaired.success, repaired.to_dict())

        inline = (
            "IF EXISTS (SELECT 1 FROM HEADER_TABLE A "
            "WHERE A.ID = @ID) BEGIN\n"
            "    RETURN;\n"
            "END\n"
        )
        normalized_inline = normalize_sql_join_layout(inline)
        inline_lines = normalized_inline.splitlines()
        inline_open_column = inline_lines[0].index("(")
        inline_result = verify_sql_formatting_style(inline, normalized_inline)

        self.assertEqual(inline_open_column + 1, inline_lines[1].index("SELECT"))
        self.assertEqual(inline_open_column + 1, inline_lines[2].index("FROM"))
        self.assertEqual(inline_open_column + 1, inline_lines[3].index("WHERE"))
        self.assertEqual(inline_open_column, inline_lines[4].index(")"))
        self.assertEqual(inline_lines[0].index("IF"), inline_lines[5].index("BEGIN"))
        self.assertTrue(inline_result.success, inline_result.to_dict())

    def test_multiline_predicate_exists_layout_is_normalized_without_false_positives(self):
        cases = {
            "WHERE": (
                "SELECT A.ID\n"
                "FROM HEADER_TABLE A\n"
                "WHERE EXISTS (\n"
                "      SELECT 1\n"
                "      FROM DETAIL_TABLE\n"
                "      WHERE DETAIL_TABLE.ID = A.ID\n"
                "  );\n"
            ),
            "HAVING": (
                "SELECT A.ID\n"
                "FROM HEADER_TABLE A\n"
                "GROUP BY A.ID\n"
                "HAVING NOT EXISTS (\n"
                "      SELECT 1\n"
                "      FROM DETAIL_TABLE\n"
                "      WHERE DETAIL_TABLE.ID = A.ID\n"
                "  );\n"
            ),
        }
        for label, malformed in cases.items():
            with self.subTest(label=label):
                invalid = verify_sql_formatting_style(malformed, malformed)
                normalized = normalize_sql_join_layout(malformed)
                repaired = verify_sql_formatting_style(malformed, normalized)

                self.assertIn(
                    "if_exists_parenthesis_alignment_invalid",
                    issue_codes(invalid),
                )
                self.assertTrue(repaired.success, repaired.to_dict())

        on_malformed = (
            "SELECT A.ID\n"
            "     , B.CUSTOMER_NAME\n"
            "FROM ORDER_HEADER A\n"
            "        INNER JOIN CUSTOMER B\n"
            "                 ON EXISTS (\n"
            "      SELECT 1\n"
            "      FROM INPUT_ITEM\n"
            "      WHERE INPUT_ITEM.ID = A.ID\n"
            "  );\n"
        )
        plan = self._candidate_bound_alias_plan(on_malformed)
        on_invalid = verify_sql_formatting_style(
            on_malformed,
            on_malformed,
            alias_role_plan=plan,
        )
        on_normalized = normalize_sql_join_layout(on_malformed)
        on_repaired = verify_sql_formatting_style(
            on_malformed,
            on_normalized,
            alias_role_plan=plan,
        )

        self.assertIn(
            "if_exists_parenthesis_alignment_invalid",
            issue_codes(on_invalid),
        )
        self.assertTrue(on_repaired.success, on_repaired.to_dict())

        one_line_and_non_predicates = (
            "SELECT DBO.EXISTS(A.ID) AS EXISTS_VALUE\n"
            "     , 'WHERE EXISTS (SELECT 1)' AS SAMPLE_TEXT\n"
            "FROM HEADER_TABLE A\n"
            "WHERE EXISTS (SELECT 1 FROM DETAIL_TABLE);\n"
            "-- WHERE EXISTS (SELECT 1 FROM COMMENT_TABLE)\n"
        )
        unchanged = normalize_sql_join_layout(one_line_and_non_predicates)
        unchanged_result = verify_sql_formatting_style(
            one_line_and_non_predicates,
            unchanged,
        )

        self.assertEqual(one_line_and_non_predicates, unchanged)
        self.assertTrue(unchanged_result.success, unchanged_result.to_dict())

    def test_nested_if_not_exists_pairs_are_checked_independently(self):
        candidate = (
            "IF NOT EXISTS (\n"
            "               SELECT 1\n"
            "               FROM HEADER_TABLE A\n"
            "              )\n"
            "BEGIN\n"
            "    IF EXISTS (\n"
            "               SELECT 1\n"
            "               FROM DETAIL_TABLE B\n"
            "              )\n"
            "    BEGIN\n"
            "        RETURN;\n"
            "    END\n"
            "END\n"
        )

        result = verify_sql_formatting_style(candidate, candidate)

        self.assertTrue(result.success, result.to_dict())
        contract = result.metadata["style_lint"]["if_exists_layout_contract"]
        self.assertEqual(
            "token_line_and_zero_based_column_relationships",
            contract["measurement"],
        )

    def test_integrated_procedure_contract_rejects_join_comment_and_generation_drift(self):
        base = (
            "-- =============================================\n"
            "-- DESCRIPTION: SAMPLE SAVE\n"
            "-- =============================================\n"
            "CREATE OR ALTER PROCEDURE [DBO].[SP_SAMPLE_SAVE]\n"
            "AS\n"
            "BEGIN\n"
            "    IF EXISTS (\n"
            "               SELECT 1\n"
            "               FROM ORDER_HEADER A\n"
            "                       LEFT OUTER JOIN CUSTOMER B\n"
            "                                    ON A.CUSTOMER_ID = B.CUSTOMER_ID\n"
            "               WHERE A.ACTIVE_YN = 'Y'\n"
            "              )\n"
            "    BEGIN\n"
            "        RETURN;\n"
            "    END\n"
            "\n"
            "    -- Preserve detail delta behavior.\n"
            "    DELETE FROM DETAIL_TABLE\n"
            "    WHERE GBN = 'DEL';\n"
            "\n"
            "    INSERT INTO DETAIL_TABLE (ITEMCD)\n"
            "    SELECT ITEMCD\n"
            "    FROM @TMP\n"
            "    WHERE GBN = 'NEW';\n"
            "END\n"
        )
        base_plan = self._candidate_bound_alias_plan(base)
        valid = verify_sql_formatting_style(
            "",
            base,
            operation="generation",
            alias_role_plan=base_plan,
        )
        self.assertTrue(valid.success, valid.to_dict())
        self.assertNotIn("cte_exception_provenance_invalid", issue_codes(valid))
        self.assertNotIn("full_delete_reinsert_without_evidence", issue_codes(valid))
        self.assertNotIn("where_subquery_introduced", issue_codes(valid))

        bare_left = base.replace("LEFT OUTER JOIN", "LEFT JOIN")
        bare_left_result = verify_sql_formatting_style(
            "",
            bare_left,
            operation="generation",
            alias_role_plan=self._candidate_bound_alias_plan(bare_left),
        )
        self.assertFalse(bare_left_result.success)
        self.assertIn("outer_join_keyword_required", issue_codes(bare_left_result))
        contracted_result = verify_sql_formatting_style(
            base,
            bare_left,
            alias_role_plan=base_plan,
        )
        self.assertFalse(contracted_result.success)
        self.assertIn("token_stream_changed", preservation_issue_codes(contracted_result))
        self.assertNotIn("outer_join_keyword_required", issue_codes(contracted_result))
        self.assertIn("LEFT JOIN", normalize_sql_join_layout(bare_left))
        self.assertNotIn("LEFT OUTER JOIN", normalize_sql_join_layout(bare_left))

        for join_type in ("RIGHT", "FULL"):
            with self.subTest(join_type=join_type):
                bare_directional = base.replace(
                    "LEFT OUTER JOIN",
                    f"{join_type} JOIN",
                )
                directional_result = verify_sql_formatting_style(
                    "",
                    bare_directional,
                    operation="generation",
                    alias_role_plan=self._candidate_bound_alias_plan(
                        bare_directional
                    ),
                )
                self.assertFalse(directional_result.success)
                self.assertIn(
                    "outer_join_keyword_required",
                    issue_codes(directional_result),
                )

        inner_join = normalize_sql_join_layout(
            base.replace("LEFT OUTER JOIN", "INNER JOIN")
        )
        inner_result = verify_sql_formatting_style(
            "",
            inner_join,
            operation="generation",
            alias_role_plan=self._candidate_bound_alias_plan(inner_join),
        )
        self.assertTrue(inner_result.success, inner_result.to_dict())
        self.assertNotIn("outer_join_keyword_required", issue_codes(inner_result))

        removed_header = base.replace(
            "-- =============================================\n"
            "-- DESCRIPTION: SAMPLE SAVE\n"
            "-- =============================================\n",
            "",
        )
        removed_header_result = verify_sql_formatting_style(
            base,
            removed_header,
            alias_role_plan=base_plan,
        )
        self.assertFalse(removed_header_result.success)
        self.assertIn("comments_changed", preservation_issue_codes(removed_header_result))

        rewritten_comment = base.replace(
            "-- Preserve detail delta behavior.",
            "-- Rewritten unrelated note.",
        )
        rewritten_comment_result = verify_sql_formatting_style(
            base,
            rewritten_comment,
            alias_role_plan=base_plan,
        )
        self.assertFalse(rewritten_comment_result.success)
        self.assertIn(
            "comments_changed",
            preservation_issue_codes(rewritten_comment_result),
        )

        changed_literal = base.replace("WHERE GBN = 'NEW';", "WHERE GBN = 'ADDED';")
        changed_literal_result = verify_sql_formatting_style(
            base,
            changed_literal,
            alias_role_plan=base_plan,
        )
        self.assertFalse(changed_literal_result.success)
        self.assertIn(
            "string_literals_changed",
            preservation_issue_codes(changed_literal_result),
        )

        with_cte = base.replace(
            "    IF EXISTS (\n",
            "    ;WITH X AS (SELECT ITEMCD FROM @TMP)\n"
            "    SELECT ITEMCD FROM X;\n"
            "\n"
            "    IF EXISTS (\n",
            1,
        )
        with_cte_result = verify_sql_formatting_style(
            "",
            with_cte,
            operation="generation",
            alias_role_plan=self._candidate_bound_alias_plan(with_cte),
        )
        self.assertFalse(with_cte_result.success)
        self.assertIn("cte_exception_provenance_invalid", issue_codes(with_cte_result))

        full_replace = base.replace("    WHERE GBN = 'DEL';", "    WHERE ITEMCD <> '';").replace(
            "    WHERE GBN = 'NEW';",
            "    WHERE ITEMCD <> '';",
        )
        full_replace_result = verify_sql_formatting_style(
            "",
            full_replace,
            operation="generation",
            alias_role_plan=self._candidate_bound_alias_plan(full_replace),
        )
        self.assertFalse(full_replace_result.success)
        self.assertIn("full_delete_reinsert_without_evidence", issue_codes(full_replace_result))

        scalar_where = base.replace(
            "    WHERE GBN = 'NEW';",
            "    WHERE ITEMCD = (SELECT MAX(ITEMCD) FROM @TMP);",
        )
        scalar_where_result = verify_sql_formatting_style(
            "",
            scalar_where,
            operation="generation",
            alias_role_plan=self._candidate_bound_alias_plan(scalar_where),
        )
        self.assertFalse(scalar_where_result.success)
        self.assertIn(
            "where_scalar_subquery_introduced",
            issue_codes(scalar_where_result),
        )

    def test_sql_generation_allows_in_exists_and_not_exists_subqueries(self):
        candidates = (
            "SELECT A.ITEMCD FROM ITEM_MASTER A "
            "WHERE A.ITEMCD IN (SELECT B.ITEMCD FROM INPUT_ITEM B);",
            "SELECT A.ITEMCD FROM ITEM_MASTER A "
            "WHERE EXISTS (SELECT 1 FROM INPUT_ITEM B WHERE B.ITEMCD = A.ITEMCD);",
            "SELECT A.ITEMCD FROM ITEM_MASTER A "
            "WHERE NOT EXISTS (SELECT 1 FROM INPUT_ITEM B WHERE B.ITEMCD = A.ITEMCD);",
        )
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                result = verify_sql_formatting_style("", candidate, operation="generation")
                self.assertTrue(result.success, result.to_dict())
                self.assertNotIn("where_subquery_introduced", issue_codes(result))

    def test_sql_generation_uses_candidate_sql_for_alias_plan_baseline(self):
        candidate = (
            "SELECT A.ORDER_NO\n"
            "     , B.CUSTOMER_NAME\n"
            "FROM ORDER_HEADER A\n"
            "        LEFT OUTER JOIN CUSTOMER B\n"
            "                     ON A.CUSTOMER_ID = B.CUSTOMER_ID;\n"
        )
        plan = self._candidate_bound_alias_plan(candidate)

        result = verify_sql_formatting_style(
            "",
            candidate,
            operation="generation",
            alias_role_plan=plan,
        )

        self.assertTrue(result.success, result.to_dict())
        validation = result.metadata["alias_role_plan_validation"]
        self.assertEqual("verified", validation["status"])
        self.assertEqual("candidate_sql", validation["validation_baseline"]["kind"])
        self.assertEqual(
            result.metadata["formatted_sha256"],
            validation["validation_baseline"]["sha256"],
        )

    def test_sql_source_contract_does_not_authorize_not_in_from_in_artifact(self):
        artifact = (
            "SELECT A.ITEMCD FROM ITEM_MASTER A "
            "WHERE A.ITEMCD IN (SELECT B.ITEMCD FROM INPUT_ITEM B);"
        )
        candidate = (
            "SELECT A.ITEMCD FROM ITEM_MASTER A "
            "WHERE A.ITEMCD NOT IN (SELECT B.ITEMCD FROM INPUT_ITEM B);"
        )
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path = Path(tmp) / "source.sql"
            artifact_path.write_text(artifact, encoding="utf-8")
            result = verify_sql_formatting_style(
                "",
                candidate,
                operation="generation",
                where_subquery_source_contract={
                    "kind": "source_artifact",
                    "requirement": "preserve_where_subquery",
                    "formatted_sha256": hashlib.sha256(candidate.encode("utf-8")).hexdigest(),
                    "artifact_path": str(artifact_path.resolve()),
                    "artifact_sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                },
            )
        self.assertFalse(result.success)
        self.assertIn("where_subquery_introduced", issue_codes(result))

    def test_sql_generation_blocks_full_delete_reinsert(self):
        candidate = """
DELETE FROM DETAIL_TABLE
WHERE MASTER_ID = @MASTER_ID;

INSERT INTO DETAIL_TABLE (MASTER_ID, LINE_NO)
SELECT @MASTER_ID, A.LINE_NO
FROM INPUT_ROWS A;
"""
        result = verify_sql_formatting_style(
            "",
            candidate,
            operation="generation",
            alias_role_plan=self._ba035t_tmp_bound_alias_plan(candidate),
        )
        self.assertFalse(result.success)
        self.assertIn("full_delete_reinsert_without_evidence", issue_codes(result))

    def test_sql_full_replace_rejects_unsigned_user_claim(self):
        candidate = (
            "DELETE FROM DETAIL_TABLE\n"
            "WHERE MASTER_ID = @MASTER_ID;\n\n"
            "INSERT INTO DETAIL_TABLE (MASTER_ID)\n"
            "SELECT @MASTER_ID;\n"
        )
        result = verify_sql_formatting_style(
            "",
            candidate,
            operation="generation",
            save_row_state_contract={
                "mode": "full_replace",
                "authority": "user",
                "reason": "caller claims the user approved it",
                "formatted_sha256": hashlib.sha256(
                    candidate.encode("utf-8")
                ).hexdigest(),
            },
        )

        self.assertFalse(result.success)
        self.assertIn("full_delete_reinsert_without_evidence", issue_codes(result))
        policy = result.metadata["style_lint"]["save_row_state_policy"]
        self.assertEqual("blocked", policy["status"])
        self.assertIn("authenticated user receipt is required", policy["errors"])

    def test_sql_full_replace_accepts_matching_hash_bound_source_artifact(self):
        candidate = (
            "DELETE FROM DETAIL_TABLE\n"
            "WHERE MASTER_ID = @MASTER_ID;\n\n"
            "INSERT INTO DETAIL_TABLE (MASTER_ID)\n"
            "SELECT @MASTER_ID;\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "target-source.sql"
            path.write_text(candidate, encoding="utf-8", newline="")
            result = verify_sql_formatting_style(
                "",
                candidate,
                operation="generation",
                save_row_state_contract={
                    "mode": "full_replace",
                    "authority": "target_source",
                    "reason": "exact current target-source behavior",
                    "formatted_sha256": hashlib.sha256(
                        candidate.encode("utf-8")
                    ).hexdigest(),
                    "artifact_path": str(path.resolve()),
                    "artifact_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                },
            )

        self.assertTrue(result.success, result.to_dict())
        policy = result.metadata["style_lint"]["save_row_state_policy"]
        self.assertEqual("verified_source_preservation", policy["status"])
        self.assertEqual(["DETAIL_TABLE"], policy["tables"])

    def test_sql_full_replace_rejects_hash_bound_artifact_with_different_shape(self):
        candidate = (
            "DELETE FROM DETAIL_TABLE\n"
            "WHERE MASTER_ID = @MASTER_ID;\n\n"
            "INSERT INTO DETAIL_TABLE (MASTER_ID)\n"
            "SELECT @MASTER_ID;\n"
        )
        different_shape = candidate.replace("@MASTER_ID", "@OTHER_ID")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "different-target-source.sql"
            path.write_text(different_shape, encoding="utf-8", newline="")
            result = verify_sql_formatting_style(
                "",
                candidate,
                operation="generation",
                save_row_state_contract={
                    "mode": "full_replace",
                    "authority": "target_source",
                    "reason": "different target-source behavior",
                    "formatted_sha256": hashlib.sha256(
                        candidate.encode("utf-8")
                    ).hexdigest(),
                    "artifact_path": str(path.resolve()),
                    "artifact_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                },
            )

        self.assertFalse(result.success)
        policy = result.metadata["style_lint"]["save_row_state_policy"]
        self.assertIn(
            "target source artifact does not contain every identical full-replace shape",
            policy["errors"],
        )

    def test_sql_full_replace_accepts_authenticated_user_receipt(self):
        candidate = (
            "DELETE FROM DETAIL_TABLE\n"
            "WHERE MASTER_ID = @MASTER_ID;\n\n"
            "INSERT INTO DETAIL_TABLE (MASTER_ID)\n"
            "SELECT @MASTER_ID;\n"
        )
        formatted_sha256 = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
        blocked = verify_sql_formatting_style("", candidate, operation="generation")
        shape_sha256 = blocked.metadata["style_lint"]["save_row_state_policy"][
            "full_replace_shape_sha256"
        ]
        receipt = {
            "receipt_id": "save-row-state-user-1",
            "formatted_sha256": formatted_sha256,
            "full_replace_shape_sha256": shape_sha256,
            "authorized_constructs": ["full_replace"],
        }
        key = b"save-row-state-test-key"
        receipt["signature"] = hmac.new(
            key,
            _runtime_receipt_payload(receipt),
            hashlib.sha256,
        ).hexdigest()

        result = verify_sql_formatting_style(
            "",
            candidate,
            operation="generation",
            save_row_state_contract={
                "mode": "full_replace",
                "authority": "user",
                "reason": "authenticated explicit user approval",
                "formatted_sha256": formatted_sha256,
                "receipt": receipt,
            },
            runtime_receipt_authenticator=lambda payload, signature: (
                hmac.compare_digest(
                    hmac.new(key, payload, hashlib.sha256).hexdigest(),
                    signature,
                )
            ),
        )

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(
            "verified_source_preservation",
            result.metadata["style_lint"]["save_row_state_policy"]["status"],
        )

    def test_sql_generation_resolves_joined_delete_target_table(self):
        candidate = """
DELETE A
FROM BA035T A
INNER JOIN @tmp B
        ON A.ORGDIV = B.ORGDIV
       AND A.ITEMCD = B.ITEMCD;

INSERT INTO BA035T (ORGDIV, ITEMCD)
SELECT B.ORGDIV, B.ITEMCD
FROM @tmp B;
"""
        result = verify_sql_formatting_style("", candidate, operation="generation")
        self.assertFalse(result.success)
        self.assertIn("full_delete_reinsert_without_evidence", issue_codes(result))
        self.assertEqual(["BA035T"], _full_replace_pairs(candidate))

    def test_sql_generation_allows_explicit_delete_row_state_delta(self):
        direct_delta = """
DELETE FROM BA035T
WHERE GBN = 'Deleted';

INSERT INTO BA035T (ORGDIV, ITEMCD)
SELECT B.ORGDIV, B.ITEMCD
FROM @tmp B
WHERE B.GBN = 'Added';
"""
        joined_delta = """
DELETE A
FROM BA035T A
INNER JOIN @tmp B
        ON A.ORGDIV = B.ORGDIV
       AND A.ITEMCD = B.ITEMCD
       AND B.GBN = 'DEL';

INSERT INTO BA035T (ORGDIV, ITEMCD)
SELECT B.ORGDIV, B.ITEMCD
FROM @tmp B
WHERE B.GBN IN ('NEW', 'Added');
"""
        self.assertEqual([], _full_replace_pairs(direct_delta))
        self.assertEqual([], _full_replace_pairs(joined_delta))
        cases = (
            (direct_delta, None),
            (joined_delta, self._ba035t_tmp_bound_alias_plan(joined_delta)),
        )
        for candidate, alias_plan in cases:
            result = verify_sql_formatting_style(
                "",
                candidate,
                operation="generation",
                alias_role_plan=alias_plan,
            )
            self.assertNotIn("full_delete_reinsert_without_evidence", issue_codes(result))

    def test_sql_generation_blocks_delta_delete_with_unfiltered_or_deleted_reinsert(self):
        candidates = (
            """
DELETE A
FROM BA035T A
INNER JOIN @tmp B
        ON A.ORGDIV = B.ORGDIV
       AND A.ITEMCD = B.ITEMCD
       AND B.GBN = 'DEL';

INSERT INTO BA035T (ORGDIV, ITEMCD)
SELECT B.ORGDIV, B.ITEMCD
FROM @tmp B;
""",
            """
DELETE A
FROM BA035T A
INNER JOIN @tmp B
        ON A.ORGDIV = B.ORGDIV
       AND A.ITEMCD = B.ITEMCD
       AND B.ROW_STATE = 'Deleted';

INSERT INTO BA035T (ORGDIV, ITEMCD)
SELECT B.ORGDIV, B.ITEMCD
FROM @tmp B
WHERE B.ROW_STATE IN ('NEW', 'Deleted');
""",
        )
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                self.assertEqual(["BA035T"], _full_replace_pairs(candidate))
                result = verify_sql_formatting_style(
                    "",
                    candidate,
                    operation="generation",
                    alias_role_plan=self._ba035t_tmp_bound_alias_plan(candidate),
                )
                self.assertIn("full_delete_reinsert_without_evidence", issue_codes(result))

    def test_sql_full_replace_matches_default_schema_qualified_target(self):
        candidate = """
DELETE FROM dbo.DETAIL_TABLE
WHERE MASTER_ID = @MASTER_ID;

INSERT INTO DETAIL_TABLE (MASTER_ID)
SELECT A.MASTER_ID
FROM @tmp A;
"""
        self.assertEqual(["DETAIL_TABLE"], _full_replace_pairs(candidate))
        result = verify_sql_formatting_style("", candidate, operation="generation")
        self.assertIn("full_delete_reinsert_without_evidence", issue_codes(result))

    def test_sql_full_replace_ignores_simple_if_else_mutually_exclusive_branches(self):
        candidate = """
IF @MODE = 'DEL'
BEGIN
    DELETE FROM DETAIL_TABLE
    WHERE MASTER_ID = @MASTER_ID;
END
ELSE
BEGIN
    INSERT INTO DETAIL_TABLE (MASTER_ID)
    SELECT A.MASTER_ID
    FROM @tmp A;
END;
"""
        self.assertEqual([], _full_replace_pairs(candidate))
        result = verify_sql_formatting_style("", candidate, operation="generation")
        self.assertNotIn("full_delete_reinsert_without_evidence", issue_codes(result))


if __name__ == "__main__":
    unittest.main()
