import unittest

from src.skills.pb_sql_generation_policy import (
    AUTHORIZATION_PRESERVE_EXACT_SOURCE_CONSTRUCTS,
    ISSUE_NEW_IDENTITY_ALLOCATION,
    ISSUE_NEW_NEXT_VALUE_FOR,
    ISSUE_NEW_ROW_NUMBER_SEQUENCING,
    ISSUE_NEW_SCALAR_WHERE_SUBQUERY,
    ISSUE_NEW_SEQUENCE_ALLOCATION,
    ISSUE_NEW_SEQUENCE_DDL,
    ISSUE_NEW_TABLE_VARIABLE,
    ISSUE_NEW_TEMP_TABLE,
    SourceEquivalenceEvidence,
    build_source_equivalence_evidence,
    evaluate_pb_sql_generation_policy,
    evaluate_policy,
    find_pb_sql_generation_policy_issues,
    sha256_text,
    validate_pb_sql_generation_policy,
)


class PbSqlGenerationPolicyTests(unittest.TestCase):
    def assertAllowed(self, candidate, source=None, evidence=None):
        result = evaluate_pb_sql_generation_policy(
            candidate,
            source_sql=source,
            evidence=evidence,
        )
        self.assertTrue(result.allowed, result.to_dict())
        self.assertEqual((), result.issue_codes)
        return result

    def assertScalarRejected(self, candidate, source=None, evidence=None):
        result = evaluate_pb_sql_generation_policy(
            candidate,
            source_sql=source,
            evidence=evidence,
        )
        self.assertFalse(result.allowed, result.to_dict())
        self.assertIn(ISSUE_NEW_SCALAR_WHERE_SUBQUERY, result.issue_codes)
        issue = result.issues[0]
        self.assertEqual("scalar", issue.metadata["predicate_kind"])
        self.assertIn("subquery_sha256", issue.metadata)
        self.assertIn("line", issue.metadata)
        self.assertIn("column", issue.metadata)
        return result

    def assertConstructRejected(
        self,
        candidate,
        issue_code,
        construct_kind,
        construct_variant,
        source=None,
        evidence=None,
    ):
        result = evaluate_pb_sql_generation_policy(
            candidate,
            source_sql=source,
            evidence=evidence,
        )
        self.assertFalse(result.allowed, result.to_dict())
        self.assertIn(issue_code, result.issue_codes)
        issue = next(item for item in result.issues if item.code == issue_code)
        self.assertEqual(construct_kind, issue.metadata["construct_kind"])
        self.assertEqual(
            construct_variant,
            issue.metadata["construct_variant"],
        )
        self.assertRegex(
            issue.metadata["construct_fingerprint"],
            r"^sha256:[0-9a-f]{64}$",
        )
        self.assertTrue(issue.metadata["canonical_construct"])
        self.assertIn("source_backed", issue.metadata)
        self.assertIn("evidence_authorized", issue.metadata)
        self.assertIn("evidence_reason", issue.metadata)
        self.assertIn("line", issue.metadata)
        self.assertIn("column", issue.metadata)
        return result, issue

    def test_source_backed_exists_not_exists_in_and_not_in_pass(self):
        statements = [
            "SELECT 1 FROM RootA r WHERE EXISTS (SELECT 1 FROM ChildA c WHERE c.Id = r.Id)",
            "SELECT 1 FROM RootB r WHERE NOT EXISTS (SELECT 1 FROM ChildB c WHERE c.Id = r.Id)",
            "SELECT 1 FROM RootC r WHERE r.Id IN (SELECT c.Id FROM ChildC c)",
            "SELECT 1 FROM RootD r WHERE r.Id NOT IN (SELECT c.Id FROM ChildD c)",
        ]

        expected_kinds = ["exists", "not_exists", "in", "not_in"]
        for statement, expected_kind in zip(statements, expected_kinds):
            with self.subTest(expected_kind=expected_kind):
                result = self.assertAllowed(statement, source=statement)
                self.assertEqual(1, result.metadata["counts"][expected_kind])
                self.assertEqual(1, result.metadata["counts"]["source_backed"])

    def test_direct_if_exists_with_from_and_join_passes(self):
        sql = """
        IF EXISTS
        (
            SELECT 1
              FROM AnyHeader AS H
              JOIN AnyDetail AS D
                ON D.HeaderId = H.Id
             WHERE H.Enabled = 1
        )
        BEGIN
            SELECT 1;
        END
        """

        result = self.assertAllowed(sql, source=sql)
        finding = result.metadata["subqueries"][0]
        self.assertEqual("exists", finding["predicate_kind"])
        self.assertTrue(finding["direct_if"])

    def test_nested_scalar_where_subquery_inside_if_exists_fails(self):
        source = """
        IF EXISTS
        (
            SELECT 1
              FROM HeaderOne AS H
              JOIN DetailOne AS D ON D.HeaderId = H.Id
             WHERE H.Enabled = 1
        )
        SELECT 1;
        """
        candidate = """
        IF EXISTS
        (
            SELECT 1
              FROM HeaderOne AS H
              JOIN DetailOne AS D ON D.HeaderId = H.Id
             WHERE H.Enabled = (SELECT MAX(X.Enabled) FROM FlagsOne AS X)
        )
        SELECT 1;
        """

        result = self.assertScalarRejected(candidate, source=source)
        self.assertEqual(1, result.metadata["counts"]["exists"])
        self.assertEqual(1, result.metadata["counts"]["scalar_where"])
        self.assertEqual("exists", result.issues[0].metadata["ancestor_predicate_kind"])

    def test_scalar_where_subquery_fails_even_when_same_text_is_in_source_without_evidence(self):
        sql = "SELECT * FROM Alpha a WHERE a.Value = (SELECT MAX(b.Value) FROM Beta b)"

        result = self.assertScalarRejected(sql, source=sql)
        self.assertTrue(result.issues[0].metadata["source_backed"])
        self.assertFalse(result.issues[0].metadata["evidence_authorized"])

    def test_exact_hash_equivalence_evidence_authorizes_preservation(self):
        source = "SELECT * FROM Gamma g WHERE g.Value = (SELECT MAX(d.Value) FROM Delta d)"
        candidate = source.replace("Gamma", "GAMMA")
        evidence = build_source_equivalence_evidence(
            source,
            candidate,
            equivalent=True,
            metadata={"reviewer": "source-contract"},
        )

        result = self.assertAllowed(candidate, source=source, evidence=evidence)
        self.assertTrue(result.metadata["evidence"]["valid"])
        self.assertEqual(
            "exact_hash_equivalence_authorized",
            result.metadata["evidence"]["reason"],
        )
        self.assertEqual(1, result.metadata["counts"]["evidence_authorized"])

    def test_mismatched_source_hash_does_not_authorize_scalar_subquery(self):
        source = "SELECT * FROM Epsilon e WHERE e.Id = (SELECT MAX(z.Id) FROM Zeta z)"
        candidate = source
        evidence = SourceEquivalenceEvidence(
            source_sha256=sha256_text(source + " "),
            candidate_sha256=sha256_text(candidate),
            equivalent=True,
        )

        result = self.assertScalarRejected(candidate, source=source, evidence=evidence)
        self.assertEqual("source_hash_mismatch", result.metadata["evidence"]["reason"])

    def test_mismatched_candidate_hash_does_not_authorize_scalar_subquery(self):
        source = "SELECT * FROM Eta e WHERE e.Id = (SELECT MAX(t.Id) FROM Theta t)"
        candidate = source
        evidence = SourceEquivalenceEvidence(
            source_sha256=sha256_text(source),
            candidate_sha256=sha256_text(candidate + " "),
            equivalent=True,
        )

        result = self.assertScalarRejected(candidate, source=source, evidence=evidence)
        self.assertEqual("candidate_hash_mismatch", result.metadata["evidence"]["reason"])

    def test_subquery_hash_allowlist_only_authorizes_selected_scalar(self):
        source = """
        SELECT *
          FROM Iota i
         WHERE i.FirstValue = (SELECT MAX(k.FirstValue) FROM Kappa k)
           AND i.SecondValue = (SELECT MAX(k.SecondValue) FROM Kappa k)
        """
        candidate = source
        baseline = evaluate_policy(candidate, source_sql=source)
        selected_hash = baseline.metadata["subqueries"][0]["subquery_sha256"]
        evidence = build_source_equivalence_evidence(
            source,
            candidate,
            equivalent=True,
            authorized_subquery_sha256=[selected_hash],
        )

        result = evaluate_policy(candidate, source_sql=source, evidence=evidence)
        self.assertFalse(result.allowed)
        self.assertEqual(1, len(result.issues))
        self.assertEqual(1, result.metadata["counts"]["evidence_authorized"])

    def test_comments_and_literals_do_not_create_false_subqueries(self):
        sql = """
        SELECT '(SELECT SecretValue FROM HiddenTable)' AS LiteralValue
          FROM OrdinaryTable
         WHERE Label = 'IN (SELECT OtherValue FROM OtherTable)'
           -- AND Id = (SELECT Id FROM CommentedTable)
           /* AND Id IN (SELECT Id FROM BlockCommentTable) */
        """

        result = self.assertAllowed(sql)
        self.assertEqual(0, result.metadata["counts"]["total"])

    def test_policy_is_table_name_independent_and_returns_thin_metadata(self):
        sql = """
        SELECT q.Id
          FROM [Unusual Schema].[Table 2048] AS q
         WHERE q.Id = (SELECT MAX(v.Id) FROM #RuntimeValues AS v)
        """

        result = self.assertScalarRejected(sql)
        payload = result.to_dict()
        self.assertFalse(result.success)
        self.assertEqual(
            [ISSUE_NEW_SCALAR_WHERE_SUBQUERY],
            payload["issue_codes"],
        )
        self.assertEqual(
            "invented_scalar_where_subquery_in_generated_sp",
            payload["issue_codes"][0],
        )
        self.assertEqual(
            ISSUE_NEW_SCALAR_WHERE_SUBQUERY,
            payload["issues"][0]["code"],
        )
        self.assertEqual("error", payload["issues"][0]["severity"])
        self.assertEqual(
            payload["issues"],
            payload["metadata"]["issues"],
        )
        self.assertEqual(
            "pb_sql_generation_subquery_policy",
            payload["metadata"]["policy_id"],
        )
        self.assertNotIn("Unusual Schema", repr(payload["metadata"]["counts"]))

        validated = validate_pb_sql_generation_policy(sql)
        integration_issues = find_pb_sql_generation_policy_issues(sql)
        self.assertEqual(result.issue_codes, validated.issue_codes)
        self.assertEqual(payload["issues"], integration_issues)

    def test_gm28_rejects_new_generation_constructs_with_stable_metadata(self):
        cases = [
            (
                "CREATE TABLE ##GeneratedRows (ID INT);",
                ISSUE_NEW_TEMP_TABLE,
                "temp_table",
                "create_table",
            ),
            (
                "SELECT R.ID INTO [#GeneratedRows] FROM RealRows AS R;",
                ISSUE_NEW_TEMP_TABLE,
                "temp_table",
                "select_into",
            ),
            (
                "DECLARE @GeneratedRows AS TABLE (ID INT);",
                ISSUE_NEW_TABLE_VARIABLE,
                "table_variable",
                "declare_table",
            ),
            (
                "CREATE TABLE RealRows (ID INT IDENTITY(1, 1));",
                ISSUE_NEW_IDENTITY_ALLOCATION,
                "identity_allocation",
                "identity_function",
            ),
            (
                "CREATE TABLE RealRows (ID INT IDENTITY);",
                ISSUE_NEW_IDENTITY_ALLOCATION,
                "identity_allocation",
                "identity_property",
            ),
            (
                "SELECT ROW_NUMBER() OVER (ORDER BY R.ID) AS SEQ FROM RealRows R;",
                ISSUE_NEW_ROW_NUMBER_SEQUENCING,
                "row_number_sequencing",
                "row_number_over",
            ),
            (
                "CREATE SEQUENCE dbo.GeneratedSequence START WITH 1;",
                ISSUE_NEW_SEQUENCE_DDL,
                "sequence_ddl",
                "create_sequence",
            ),
            (
                "ALTER SEQUENCE dbo.GeneratedSequence RESTART WITH 1;",
                ISSUE_NEW_SEQUENCE_DDL,
                "sequence_ddl",
                "alter_sequence",
            ),
            (
                "DROP SEQUENCE dbo.GeneratedSequence;",
                ISSUE_NEW_SEQUENCE_DDL,
                "sequence_ddl",
                "drop_sequence",
            ),
            (
                "SELECT NEXT VALUE FOR dbo.GeneratedSequence AS ID;",
                ISSUE_NEW_NEXT_VALUE_FOR,
                "next_value_for",
                "next_value_for",
            ),
        ]

        for candidate, issue_code, kind, variant in cases:
            with self.subTest(kind=kind, variant=variant):
                result, issue = self.assertConstructRejected(
                    candidate,
                    issue_code,
                    kind,
                    variant,
                )
                self.assertEqual("construct_not_in_exact_source", issue.metadata["reason"])
                self.assertEqual(1, result.metadata["construct_counts"]["total"])
                self.assertEqual(1, result.metadata["construct_counts"][kind])
                payload = result.to_dict()
                self.assertEqual(issue_code, payload["issues"][0]["code"])
                self.assertEqual(
                    payload["issues"],
                    payload["metadata"]["issues"],
                )

    def test_gm28_rejects_invented_user_defined_table_type_variables(self):
        cases = [
            "DECLARE @Stage custom.StageRowsType;",
            "DECLARE @Stage [another schema].[StageRowsType];",
            "DECLARE @Stage AS StageRowsType;",
        ]

        for candidate in cases:
            with self.subTest(candidate=candidate):
                result, issue = self.assertConstructRejected(
                    candidate,
                    ISSUE_NEW_TABLE_VARIABLE,
                    "table_variable",
                    "declare_user_defined_type",
                )
                self.assertEqual(1, result.metadata["construct_counts"]["table_variable"])
                self.assertEqual("construct_not_in_exact_source", issue.metadata["reason"])

    def test_gm28_rejects_sequence_allocation_but_not_ordinary_max_reports(self):
        positive_cases = [
            (
                "SELECT MAX(RecordKey) + 1 AS RecordKey FROM Records;",
                "max_plus_one",
            ),
            (
                "SELECT ISNULL(MAX(RecordKey), 0) + 1 AS NextKey FROM Records;",
                "isnull_max_plus_one",
            ),
            (
                "SELECT COALESCE(MAX(RowSeq), 0) + 1 AS NextOrdinal FROM Records;",
                "coalesce_max_plus_one",
            ),
        ]

        for candidate, variant in positive_cases:
            with self.subTest(variant=variant):
                result, issue = self.assertConstructRejected(
                    candidate,
                    ISSUE_NEW_SEQUENCE_ALLOCATION,
                    "sequence_allocation",
                    variant,
                )
                self.assertEqual(1, result.metadata["construct_counts"]["total"])
                self.assertEqual(
                    1,
                    result.metadata["construct_counts"]["sequence_allocation"],
                )
                self.assertEqual("construct_not_in_exact_source", issue.metadata["reason"])

        negative_cases = [
            "SELECT MAX(Amount) + 1 AS AdjustedAmount FROM Sales;",
            "SELECT ISNULL(MAX(Amount), 0) + 1 AS AdjustedAmount FROM Sales;",
            "SELECT MAX(Amount) + 1 FROM Sales;",
            "SELECT MAX(RecordKey) + 2 AS RecordKey FROM Records;",
        ]
        for candidate in negative_cases:
            with self.subTest(candidate=candidate):
                self.assertAllowed(candidate)

    def test_gm28_new_construct_detection_ignores_comments_literals_and_builtin_types(self):
        sql = """
        DECLARE @Count INT;
        DECLARE @Label NVARCHAR(40);
        SELECT MAX(Amount) + 1 AS AdjustedAmount,
               'DECLARE @Fake custom.FakeType; MAX(FakeSeq) + 1' AS Note
          FROM Sales
         WHERE Description = 'ISNULL(MAX(FakeKey), 0) + 1';
        -- DECLARE @Fake custom.FakeType;
        /* SELECT MAX(FakeSeq) + 1 AS FakeSeq FROM HiddenRows; */
        """

        result = self.assertAllowed(sql)
        self.assertEqual(0, result.metadata["construct_counts"]["total"])
        self.assertEqual([], result.metadata["constructs"])

    def test_gm28_exact_hash_authorizes_new_constructs_only_by_fingerprint(self):
        cases = [
            "DECLARE @Stage custom.StageRowsType;",
            "SELECT ISNULL(MAX(RecordKey), 0) + 1 AS NextKey FROM Records;",
        ]

        for candidate in cases:
            with self.subTest(candidate=candidate):
                baseline = evaluate_pb_sql_generation_policy(
                    candidate,
                    source_sql=candidate,
                )
                self.assertEqual(1, len(baseline.metadata["constructs"]))
                fingerprint = baseline.metadata["constructs"][0][
                    "construct_fingerprint"
                ]
                evidence = build_source_equivalence_evidence(
                    candidate,
                    candidate,
                    equivalent=True,
                    authorized_construct_fingerprints=[fingerprint],
                )
                result = self.assertAllowed(
                    candidate,
                    source=candidate,
                    evidence=evidence,
                )
                self.assertEqual(
                    1,
                    result.metadata["construct_counts"]["source_backed"],
                )
                self.assertEqual(
                    1,
                    result.metadata["construct_counts"]["evidence_authorized"],
                )

    def test_gm28_source_presence_alone_is_not_authorization(self):
        cases = [
            (
                "CREATE TABLE #GeneratedRows (ID INT);",
                ISSUE_NEW_TEMP_TABLE,
                "temp_table",
                "create_table",
            ),
            (
                "DECLARE @GeneratedRows TABLE (ID INT);",
                ISSUE_NEW_TABLE_VARIABLE,
                "table_variable",
                "declare_table",
            ),
            (
                "CREATE TABLE RealRows (ID INT IDENTITY(1, 1));",
                ISSUE_NEW_IDENTITY_ALLOCATION,
                "identity_allocation",
                "identity_function",
            ),
            (
                "SELECT ROW_NUMBER() OVER (ORDER BY R.ID) AS SEQ FROM RealRows R;",
                ISSUE_NEW_ROW_NUMBER_SEQUENCING,
                "row_number_sequencing",
                "row_number_over",
            ),
            (
                "CREATE SEQUENCE dbo.GeneratedSequence START WITH 1;",
                ISSUE_NEW_SEQUENCE_DDL,
                "sequence_ddl",
                "create_sequence",
            ),
            (
                "SELECT NEXT VALUE FOR dbo.GeneratedSequence AS ID;",
                ISSUE_NEW_NEXT_VALUE_FOR,
                "next_value_for",
                "next_value_for",
            ),
        ]

        for candidate, issue_code, kind, variant in cases:
            with self.subTest(kind=kind):
                result, issue = self.assertConstructRejected(
                    candidate,
                    issue_code,
                    kind,
                    variant,
                    source=candidate,
                )
                self.assertTrue(issue.metadata["source_backed"])
                self.assertFalse(issue.metadata["evidence_authorized"])
                self.assertEqual(
                    "exact_hash_authorization_missing_or_invalid",
                    issue.metadata["reason"],
                )
                self.assertEqual("not_supplied", issue.metadata["evidence_reason"])
                self.assertEqual(1, result.metadata["construct_counts"]["source_backed"])

    def test_gm28_exact_hash_and_fingerprint_authorize_each_construct(self):
        cases = [
            "CREATE TABLE #GeneratedRows (ID INT);",
            "DECLARE @GeneratedRows TABLE (ID INT);",
            "CREATE TABLE RealRows (ID INT IDENTITY(1, 1));",
            "SELECT ROW_NUMBER() OVER (ORDER BY R.ID) AS SEQ FROM RealRows R;",
            "CREATE SEQUENCE dbo.GeneratedSequence START WITH 1;",
            "SELECT NEXT VALUE FOR dbo.GeneratedSequence AS ID;",
        ]

        for candidate in cases:
            with self.subTest(candidate=candidate):
                baseline = evaluate_pb_sql_generation_policy(
                    candidate,
                    source_sql=candidate,
                )
                self.assertEqual(1, len(baseline.metadata["constructs"]))
                fingerprint = baseline.metadata["constructs"][0][
                    "construct_fingerprint"
                ]
                evidence = build_source_equivalence_evidence(
                    candidate,
                    candidate,
                    equivalent=True,
                    authorized_construct_fingerprints=[fingerprint],
                )

                result = self.assertAllowed(
                    candidate,
                    source=candidate,
                    evidence=evidence,
                )
                self.assertEqual(
                    AUTHORIZATION_PRESERVE_EXACT_SOURCE_CONSTRUCTS,
                    result.metadata["evidence"]["authorization"],
                )
                self.assertEqual(
                    "selected_constructs",
                    result.metadata["evidence"]["scope"],
                )
                self.assertEqual(
                    1,
                    result.metadata["construct_counts"]["evidence_authorized"],
                )
                self.assertTrue(
                    result.metadata["constructs"][0]["source_backed"]
                )
                self.assertTrue(
                    result.metadata["constructs"][0]["evidence_authorized"]
                )

    def test_gm28_authorized_fingerprint_cannot_replace_source_construct(self):
        source = (
            "SELECT ROW_NUMBER() OVER (ORDER BY R.ID) AS SEQ "
            "FROM RealRows R;"
        )
        candidate = (
            "SELECT ROW_NUMBER() OVER (ORDER BY R.CODE) AS SEQ "
            "FROM RealRows R;"
        )
        baseline = evaluate_pb_sql_generation_policy(candidate)
        fingerprint = baseline.metadata["constructs"][0][
            "construct_fingerprint"
        ]
        evidence = build_source_equivalence_evidence(
            source,
            candidate,
            equivalent=True,
            authorized_construct_fingerprints=[fingerprint],
        )

        result, issue = self.assertConstructRejected(
            candidate,
            ISSUE_NEW_ROW_NUMBER_SEQUENCING,
            "row_number_sequencing",
            "row_number_over",
            source=source,
            evidence=evidence,
        )
        self.assertTrue(result.metadata["evidence"]["valid"])
        self.assertFalse(issue.metadata["source_backed"])
        self.assertFalse(issue.metadata["evidence_authorized"])
        self.assertEqual("construct_not_in_exact_source", issue.metadata["reason"])

    def test_gm28_exact_hash_evidence_requires_explicit_fingerprint(self):
        sql = "DECLARE @GeneratedRows TABLE (ID INT);"
        evidence = build_source_equivalence_evidence(
            sql,
            sql,
            equivalent=True,
            authorization=AUTHORIZATION_PRESERVE_EXACT_SOURCE_CONSTRUCTS,
        )

        result, issue = self.assertConstructRejected(
            sql,
            ISSUE_NEW_TABLE_VARIABLE,
            "table_variable",
            "declare_table",
            source=sql,
            evidence=evidence,
        )
        self.assertTrue(result.metadata["evidence"]["valid"])
        self.assertEqual(
            "no_construct_fingerprints",
            result.metadata["evidence"]["scope"],
        )
        self.assertEqual(
            "construct_fingerprint_not_authorized",
            issue.metadata["reason"],
        )

    def test_gm28_hash_mismatch_cannot_authorize_listed_fingerprint(self):
        sql = "CREATE TABLE #GeneratedRows (ID INT);"
        baseline = evaluate_pb_sql_generation_policy(sql, source_sql=sql)
        fingerprint = baseline.metadata["constructs"][0][
            "construct_fingerprint"
        ]
        cases = [
            (
                SourceEquivalenceEvidence(
                    source_sha256=sha256_text(sql + " "),
                    candidate_sha256=sha256_text(sql),
                    equivalent=True,
                    authorization=AUTHORIZATION_PRESERVE_EXACT_SOURCE_CONSTRUCTS,
                    authorized_construct_fingerprints=(fingerprint,),
                ),
                "source_hash_mismatch",
            ),
            (
                SourceEquivalenceEvidence(
                    source_sha256=sha256_text(sql),
                    candidate_sha256=sha256_text(sql + " "),
                    equivalent=True,
                    authorization=AUTHORIZATION_PRESERVE_EXACT_SOURCE_CONSTRUCTS,
                    authorized_construct_fingerprints=(fingerprint,),
                ),
                "candidate_hash_mismatch",
            ),
        ]

        for evidence, evidence_reason in cases:
            with self.subTest(evidence_reason=evidence_reason):
                result, issue = self.assertConstructRejected(
                    sql,
                    ISSUE_NEW_TEMP_TABLE,
                    "temp_table",
                    "create_table",
                    source=sql,
                    evidence=evidence,
                )
                self.assertFalse(result.metadata["evidence"]["valid"])
                self.assertEqual(
                    evidence_reason,
                    result.metadata["evidence"]["reason"],
                )
                self.assertEqual(
                    "exact_hash_authorization_missing_or_invalid",
                    issue.metadata["reason"],
                )

    def test_gm28_real_columns_comments_and_literals_are_not_constructs(self):
        sql = """
        SELECT R.IDENTITY,
               R.ROW_NUMBER,
               R.SEQUENCE_NAME,
               R.NEXT_VALUE,
               SCOPE_IDENTITY() AS LAST_ID
          FROM RealIdentityRows AS R
         WHERE R.Note = 'CREATE TABLE #Fake (ID INT IDENTITY(1, 1));'
           AND R.OtherNote = 'ROW_NUMBER() OVER (ORDER BY Fake.ID)'
           -- DECLARE @Fake TABLE (ID INT);
           /* CREATE SEQUENCE dbo.Fake; NEXT VALUE FOR dbo.Fake; */
        SET IDENTITY_INSERT RealIdentityRows ON;
        """

        result = self.assertAllowed(sql)
        self.assertEqual(0, result.metadata["construct_counts"]["total"])
        self.assertEqual([], result.metadata["constructs"])

    def test_gm28_exact_authorized_row_number_uses_canonical_tokens(self):
        source = """
        SELECT ROW_NUMBER() OVER (ORDER BY R.ID) AS SEQ
          FROM RealRows AS R;
        """
        candidate = """
        SELECT ROW_NUMBER /* preserved source construct */
               ( ) OVER ( ORDER BY R.ID ) AS SEQ,
               'ROW_NUMBER() OVER (ORDER BY Fake.ID)' AS LiteralValue
          FROM RealRows AS R;
        -- ROW_NUMBER() OVER (ORDER BY Commented.ID)
        """
        baseline = evaluate_pb_sql_generation_policy(
            candidate,
            source_sql=source,
        )
        self.assertEqual(1, len(baseline.metadata["constructs"]))
        finding = baseline.metadata["constructs"][0]
        self.assertTrue(finding["source_backed"])
        evidence = build_source_equivalence_evidence(
            source,
            candidate,
            equivalent=True,
            authorized_construct_fingerprints=[
                finding["construct_fingerprint"]
            ],
        )

        result = self.assertAllowed(
            candidate,
            source=source,
            evidence=evidence,
        )
        self.assertEqual(1, result.metadata["construct_counts"]["total"])
        self.assertEqual(
            1,
            result.metadata["construct_counts"]["evidence_authorized"],
        )

    def test_gm28_combined_select_reports_all_allocation_constructs(self):
        sql = """
        SELECT IDENTITY(INT, 1, 1) AS ID,
               ROW_NUMBER() OVER (ORDER BY R.ID) AS SEQ
          INTO #GeneratedRows
          FROM RealRows AS R;
        """

        result = evaluate_pb_sql_generation_policy(sql)
        self.assertFalse(result.allowed, result.to_dict())
        self.assertEqual(
            {
                ISSUE_NEW_TEMP_TABLE,
                ISSUE_NEW_IDENTITY_ALLOCATION,
                ISSUE_NEW_ROW_NUMBER_SEQUENCING,
            },
            set(result.issue_codes),
        )
        self.assertEqual(3, result.metadata["construct_counts"]["total"])
        self.assertEqual(1, result.metadata["construct_counts"]["temp_table"])
        self.assertEqual(
            1,
            result.metadata["construct_counts"]["identity_allocation"],
        )
        self.assertEqual(
            1,
            result.metadata["construct_counts"]["row_number_sequencing"],
        )


if __name__ == "__main__":
    unittest.main()
