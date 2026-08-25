"""Structural guard for risky constructs introduced by PB SQL generation.

The policy deliberately uses a small lexer instead of a SQL parser dependency.
It does not try to validate T-SQL; it identifies parenthesized query
expressions, predicate forms, and allocation constructs governed by GM-28.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


POLICY_ID = "pb_sql_generation_subquery_policy"
POLICY_VERSION = 3

ISSUE_NEW_SCALAR_WHERE_SUBQUERY = (
    "invented_scalar_where_subquery_in_generated_sp"
)
AUTHORIZATION_PRESERVE_SCALAR_WHERE_SUBQUERIES = (
    "preserve_scalar_where_subqueries"
)
AUTHORIZATION_PRESERVE_EXACT_SOURCE_CONSTRUCTS = (
    "preserve_exact_source_constructs"
)

ISSUE_NEW_TEMP_TABLE = "invented_temp_table_in_generated_sp"
ISSUE_NEW_TABLE_VARIABLE = "invented_table_variable_in_generated_sp"
ISSUE_NEW_IDENTITY_ALLOCATION = (
    "invented_identity_allocation_in_generated_sp"
)
ISSUE_NEW_ROW_NUMBER_SEQUENCING = (
    "invented_row_number_sequencing_in_generated_sp"
)
ISSUE_NEW_SEQUENCE_DDL = "invented_sequence_ddl_in_generated_sp"
ISSUE_NEW_NEXT_VALUE_FOR = "invented_next_value_for_in_generated_sp"
ISSUE_NEW_SEQUENCE_ALLOCATION = (
    "invented_sequence_allocation_in_generated_sp"
)

_QUERY_STARTERS = {"SELECT", "WITH"}
_SEMI_PREDICATE_KINDS = {"exists", "not_exists", "in", "not_in"}
_CLAUSE_BOUNDARIES = {
    "WHERE",
    "HAVING",
    "ON",
    "SELECT",
    "FROM",
    "JOIN",
    "SET",
    "VALUES",
    "ORDER",
    "GROUP",
    "UNION",
    "EXCEPT",
    "INTERSECT",
}
_BUILTIN_DECLARE_TYPES = {
    "BIGINT",
    "BINARY",
    "BIT",
    "CHAR",
    "DATE",
    "DATETIME",
    "DATETIME2",
    "DATETIMEOFFSET",
    "DECIMAL",
    "FLOAT",
    "GEOGRAPHY",
    "GEOMETRY",
    "HIERARCHYID",
    "IMAGE",
    "INT",
    "MONEY",
    "NCHAR",
    "NTEXT",
    "NUMERIC",
    "NVARCHAR",
    "REAL",
    "ROWVERSION",
    "SMALLDATETIME",
    "SMALLINT",
    "SMALLMONEY",
    "SQL_VARIANT",
    "SYSNAME",
    "TEXT",
    "TIME",
    "TIMESTAMP",
    "TINYINT",
    "UNIQUEIDENTIFIER",
    "VARBINARY",
    "VARCHAR",
    "XML",
}
_SEQUENCE_NAME_PARTS = {
    "ID",
    "INDEX",
    "KEY",
    "NO",
    "NUM",
    "NUMBER",
    "ORD",
    "ORDINAL",
    "SEQ",
    "SEQUENCE",
}


@dataclass(frozen=True)
class SourceEquivalenceEvidence:
    """Evidence binding a preservation decision to exact source and candidate."""

    source_sha256: str
    candidate_sha256: str
    equivalent: bool
    authorization: str = AUTHORIZATION_PRESERVE_SCALAR_WHERE_SUBQUERIES
    authorized_subquery_sha256: Tuple[str, ...] = ()
    authorized_construct_fingerprints: Tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "SourceEquivalenceEvidence":
        hashes = value.get("authorized_subquery_sha256", ())
        if isinstance(hashes, str):
            hashes = (hashes,)
        fingerprints = value.get("authorized_construct_fingerprints", ())
        if isinstance(fingerprints, str):
            fingerprints = (fingerprints,)
        authorization = str(value.get("authorization", "")).strip()
        if not authorization:
            authorization = (
                AUTHORIZATION_PRESERVE_EXACT_SOURCE_CONSTRUCTS
                if fingerprints
                else AUTHORIZATION_PRESERVE_SCALAR_WHERE_SUBQUERIES
            )
        return cls(
            source_sha256=str(value.get("source_sha256", "")),
            candidate_sha256=str(value.get("candidate_sha256", "")),
            equivalent=value.get("equivalent") is True,
            authorization=authorization,
            authorized_subquery_sha256=tuple(str(item) for item in hashes),
            authorized_construct_fingerprints=tuple(
                str(item) for item in fingerprints
            ),
            metadata=dict(value.get("metadata", {}) or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_sha256": self.source_sha256,
            "candidate_sha256": self.candidate_sha256,
            "equivalent": self.equivalent,
            "authorization": self.authorization,
            "authorized_subquery_sha256": list(
                self.authorized_subquery_sha256
            ),
            "authorized_construct_fingerprints": list(
                self.authorized_construct_fingerprints
            ),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class PolicyIssue:
    code: str
    message: str
    metadata: Mapping[str, Any]
    severity: str = "error"

    def to_dict(self) -> Dict[str, Any]:
        metadata = dict(self.metadata)
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            **metadata,
            "metadata": metadata,
        }


@dataclass(frozen=True)
class PolicyResult:
    allowed: bool
    issues: Tuple[PolicyIssue, ...]
    metadata: Mapping[str, Any]

    @property
    def issue_codes(self) -> Tuple[str, ...]:
        return tuple(issue.code for issue in self.issues)

    @property
    def success(self) -> bool:
        """Compatibility alias for the repository's validation results."""

        return self.allowed

    @property
    def integration_issues(self) -> Tuple[Dict[str, Any], ...]:
        """Return issue dictionaries that can be appended to harness issues."""

        return tuple(issue.to_dict() for issue in self.issues)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "success": self.success,
            "issue_codes": list(self.issue_codes),
            "issues": list(self.integration_issues),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class _Token:
    text: str
    kind: str
    start: int
    end: int
    depth: int

    @property
    def keyword(self) -> str:
        return self.text.upper() if self.kind == "word" else ""


@dataclass(frozen=True)
class _Subquery:
    open_index: int
    close_index: int
    start: int
    end: int
    predicate_kind: str
    clause: str
    direct_if: bool
    canonical: str
    text_sha256: str
    ancestor_predicate_kind: str


@dataclass(frozen=True)
class _Construct:
    kind: str
    variant: str
    issue_code: str
    start: int
    end: int
    canonical: str
    fingerprint: str


def sha256_text(value: str) -> str:
    """Return the exact UTF-8 hash used by policy evidence."""

    return "sha256:" + sha256(value.encode("utf-8")).hexdigest()


def build_source_equivalence_evidence(
    source_sql: str,
    candidate_sql: str,
    *,
    equivalent: bool,
    authorized_subquery_sha256: Iterable[str] = (),
    authorized_construct_fingerprints: Iterable[str] = (),
    authorization: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> SourceEquivalenceEvidence:
    """Build evidence that cannot be reused for different SQL text."""

    construct_fingerprints = tuple(authorized_construct_fingerprints)
    effective_authorization = str(authorization or "").strip() or (
        AUTHORIZATION_PRESERVE_EXACT_SOURCE_CONSTRUCTS
        if construct_fingerprints
        else AUTHORIZATION_PRESERVE_SCALAR_WHERE_SUBQUERIES
    )
    return SourceEquivalenceEvidence(
        source_sha256=sha256_text(source_sql),
        candidate_sha256=sha256_text(candidate_sql),
        equivalent=equivalent,
        authorization=effective_authorization,
        authorized_subquery_sha256=tuple(authorized_subquery_sha256),
        authorized_construct_fingerprints=construct_fingerprints,
        metadata=dict(metadata or {}),
    )


def evaluate_pb_sql_generation_policy(
    candidate_sql: str,
    *,
    source_sql: Optional[str] = None,
    evidence: Optional[
        SourceEquivalenceEvidence | Mapping[str, Any]
    ] = None,
) -> PolicyResult:
    """Evaluate generated SQL and return stable issue codes plus metadata.

    EXISTS, NOT EXISTS, IN, and NOT IN query predicates are structural
    semi/anti-semi forms. A query expression used as a scalar in a WHERE
    predicate is rejected unless equivalence evidence is bound to the exact
    source and candidate hashes. An optional subquery hash allowlist narrows
    that authorization; an empty allowlist authorizes every preserved scalar
    WHERE subquery in the hash-bound candidate. GM-28 allocation constructs
    always require an explicit construct fingerprint in exact hash-bound
    evidence, even when the same canonical construct exists in source SQL.
    """

    if not isinstance(candidate_sql, str):
        raise TypeError("candidate_sql must be a string")
    if source_sql is not None and not isinstance(source_sql, str):
        raise TypeError("source_sql must be a string or None")

    candidate_tokens = _tokenize(candidate_sql)
    candidate_subqueries = _find_subqueries(candidate_sql, candidate_tokens)
    candidate_constructs = _find_generation_constructs(
        candidate_sql,
        candidate_tokens,
    )
    source_signatures = _source_signatures(source_sql)
    source_construct_signatures = _source_construct_signatures(source_sql)
    parsed_evidence = _coerce_evidence(evidence)
    evidence_status = _validate_evidence(
        parsed_evidence,
        source_sql=source_sql,
        candidate_sql=candidate_sql,
    )

    issues: List[PolicyIssue] = []
    findings: List[Dict[str, Any]] = []
    counts = {
        "total": 0,
        "exists": 0,
        "not_exists": 0,
        "in": 0,
        "not_in": 0,
        "scalar": 0,
        "scalar_where": 0,
        "source_backed": 0,
        "evidence_authorized": 0,
    }
    construct_counts = {
        "total": 0,
        "temp_table": 0,
        "table_variable": 0,
        "identity_allocation": 0,
        "row_number_sequencing": 0,
        "sequence_ddl": 0,
        "next_value_for": 0,
        "sequence_allocation": 0,
        "source_backed": 0,
        "evidence_authorized": 0,
    }
    construct_findings: List[Dict[str, Any]] = []

    for subquery in candidate_subqueries:
        counts["total"] += 1
        counts[subquery.predicate_kind] += 1
        if subquery.predicate_kind == "scalar" and subquery.clause == "WHERE":
            counts["scalar_where"] += 1

        signature = (subquery.predicate_kind, subquery.canonical)
        source_backed = signature in source_signatures
        if source_backed:
            counts["source_backed"] += 1

        evidence_authorized = _evidence_authorizes_subquery(
            evidence_status,
            parsed_evidence,
            subquery.text_sha256,
        )
        if evidence_authorized:
            counts["evidence_authorized"] += 1

        line, column = _line_column(candidate_sql, subquery.start)
        finding = {
            "predicate_kind": subquery.predicate_kind,
            "clause": subquery.clause,
            "direct_if": subquery.direct_if,
            "ancestor_predicate_kind": subquery.ancestor_predicate_kind,
            "source_backed": source_backed,
            "evidence_authorized": evidence_authorized,
            "start": subquery.start,
            "end": subquery.end,
            "line": line,
            "column": column,
            "subquery_sha256": subquery.text_sha256,
        }
        findings.append(finding)

        is_nested_scalar = (
            subquery.predicate_kind == "scalar"
            and subquery.ancestor_predicate_kind in _SEMI_PREDICATE_KINDS
        )
        is_scalar_where = (
            subquery.predicate_kind == "scalar"
            and subquery.clause == "WHERE"
        )
        if (is_scalar_where or is_nested_scalar) and not evidence_authorized:
            issue_metadata = dict(finding)
            issue_metadata["reason"] = (
                "nested_scalar_subquery"
                if is_nested_scalar and not is_scalar_where
                else "scalar_where_subquery"
            )
            issues.append(
                PolicyIssue(
                    code=ISSUE_NEW_SCALAR_WHERE_SUBQUERY,
                    message=(
                        "Generated SQL contains a scalar predicate subquery "
                        "without exact source-hash equivalence authorization."
                    ),
                    metadata=issue_metadata,
                )
            )

    for construct in candidate_constructs:
        construct_counts["total"] += 1
        construct_counts[construct.kind] += 1
        signature = (construct.kind, construct.variant, construct.canonical)
        source_backed = signature in source_construct_signatures
        if source_backed:
            construct_counts["source_backed"] += 1
        evidence_authorized = _evidence_authorizes_construct(
            evidence_status,
            parsed_evidence,
            construct.fingerprint,
            source_backed=source_backed,
        )
        if evidence_authorized:
            construct_counts["evidence_authorized"] += 1

        line, column = _line_column(candidate_sql, construct.start)
        finding = {
            "construct_kind": construct.kind,
            "construct_variant": construct.variant,
            "construct_fingerprint": construct.fingerprint,
            "canonical_construct": construct.canonical,
            "source_backed": source_backed,
            "evidence_authorized": evidence_authorized,
            "evidence_reason": evidence_status["reason"],
            "start": construct.start,
            "end": construct.end,
            "line": line,
            "column": column,
        }
        construct_findings.append(finding)
        if evidence_authorized:
            continue

        issue_metadata = dict(finding)
        if not source_backed:
            issue_metadata["reason"] = "construct_not_in_exact_source"
        elif not evidence_status.get("valid"):
            issue_metadata["reason"] = (
                "exact_hash_authorization_missing_or_invalid"
            )
        else:
            issue_metadata["reason"] = (
                "construct_fingerprint_not_authorized"
            )
        issues.append(
            PolicyIssue(
                code=construct.issue_code,
                message=_construct_issue_message(construct.kind),
                metadata=issue_metadata,
            )
        )

    issue_payloads = [issue.to_dict() for issue in issues]
    result_metadata = {
        "policy_id": POLICY_ID,
        "policy_version": POLICY_VERSION,
        "status": "passed" if not issues else "blocked",
        "candidate_sha256": sha256_text(candidate_sql),
        "source_sha256": sha256_text(source_sql) if source_sql is not None else None,
        "source_supplied": source_sql is not None,
        "evidence": evidence_status,
        "counts": counts,
        "construct_counts": construct_counts,
        "subqueries": findings,
        "constructs": construct_findings,
        "issue_codes": [issue.code for issue in issues],
        "issues": issue_payloads,
    }
    return PolicyResult(
        allowed=not issues,
        issues=tuple(issues),
        metadata=result_metadata,
    )


def evaluate_policy(
    candidate_sql: str,
    *,
    source_sql: Optional[str] = None,
    evidence: Optional[
        SourceEquivalenceEvidence | Mapping[str, Any]
    ] = None,
) -> PolicyResult:
    """Thin-integration alias for :func:`evaluate_pb_sql_generation_policy`."""

    return evaluate_pb_sql_generation_policy(
        candidate_sql,
        source_sql=source_sql,
        evidence=evidence,
    )


def validate_pb_sql_generation_policy(
    candidate_sql: str,
    *,
    source_sql: Optional[str] = None,
    evidence: Optional[
        SourceEquivalenceEvidence | Mapping[str, Any]
    ] = None,
) -> PolicyResult:
    """Validation-named alias for integration with PB harness code."""

    return evaluate_pb_sql_generation_policy(
        candidate_sql,
        source_sql=source_sql,
        evidence=evidence,
    )


def find_pb_sql_generation_policy_issues(
    candidate_sql: str,
    *,
    source_sql: Optional[str] = None,
    evidence: Optional[
        SourceEquivalenceEvidence | Mapping[str, Any]
    ] = None,
) -> List[Dict[str, Any]]:
    """Return only append-ready issue dictionaries for a thin caller."""

    result = evaluate_pb_sql_generation_policy(
        candidate_sql,
        source_sql=source_sql,
        evidence=evidence,
    )
    return list(result.integration_issues)


def _coerce_evidence(
    evidence: Optional[SourceEquivalenceEvidence | Mapping[str, Any]],
) -> Optional[SourceEquivalenceEvidence]:
    if evidence is None:
        return None
    if isinstance(evidence, SourceEquivalenceEvidence):
        return evidence
    if isinstance(evidence, Mapping):
        return SourceEquivalenceEvidence.from_mapping(evidence)
    raise TypeError("evidence must be SourceEquivalenceEvidence, a mapping, or None")


def _validate_evidence(
    evidence: Optional[SourceEquivalenceEvidence],
    *,
    source_sql: Optional[str],
    candidate_sql: str,
) -> Dict[str, Any]:
    status: Dict[str, Any] = {
        "supplied": evidence is not None,
        "valid": False,
        "reason": "not_supplied",
        "authorization": "",
        "scope": "none",
        "authorized_subquery_sha256": [],
        "authorized_construct_fingerprints": [],
    }
    if evidence is None:
        return status

    status["authorization"] = evidence.authorization
    if source_sql is None:
        status["reason"] = "source_sql_missing"
        return status
    if evidence.authorization not in {
        AUTHORIZATION_PRESERVE_SCALAR_WHERE_SUBQUERIES,
        AUTHORIZATION_PRESERVE_EXACT_SOURCE_CONSTRUCTS,
    }:
        status["reason"] = "authorization_mismatch"
        return status
    if evidence.equivalent is not True:
        status["reason"] = "equivalence_not_asserted"
        return status
    if _normalize_hash(evidence.source_sha256) != _normalize_hash(
        sha256_text(source_sql)
    ):
        status["reason"] = "source_hash_mismatch"
        return status
    if _normalize_hash(evidence.candidate_sha256) != _normalize_hash(
        sha256_text(candidate_sql)
    ):
        status["reason"] = "candidate_hash_mismatch"
        return status

    status.update(
        {
            "valid": True,
            "reason": "exact_hash_equivalence_authorized",
            "scope": _evidence_scope(evidence),
            "authorized_subquery_sha256": list(
                evidence.authorized_subquery_sha256
            ),
            "authorized_construct_fingerprints": list(
                evidence.authorized_construct_fingerprints
            ),
        }
    )
    return status


def _evidence_authorizes_subquery(
    evidence_status: Mapping[str, Any],
    evidence: Optional[SourceEquivalenceEvidence],
    subquery_hash: str,
) -> bool:
    if not evidence_status.get("valid") or evidence is None:
        return False
    if evidence.authorized_subquery_sha256:
        normalized = {
            _normalize_hash(item)
            for item in evidence.authorized_subquery_sha256
        }
        return _normalize_hash(subquery_hash) in normalized
    if (
        evidence.authorization
        == AUTHORIZATION_PRESERVE_SCALAR_WHERE_SUBQUERIES
    ):
        return True
    return False


def _evidence_authorizes_construct(
    evidence_status: Mapping[str, Any],
    evidence: Optional[SourceEquivalenceEvidence],
    fingerprint: str,
    *,
    source_backed: bool,
) -> bool:
    if not source_backed or not evidence_status.get("valid") or evidence is None:
        return False
    normalized = {
        _normalize_hash(item)
        for item in evidence.authorized_construct_fingerprints
    }
    return _normalize_hash(fingerprint) in normalized


def _evidence_scope(evidence: SourceEquivalenceEvidence) -> str:
    subqueries = bool(evidence.authorized_subquery_sha256)
    constructs = bool(evidence.authorized_construct_fingerprints)
    if subqueries and constructs:
        return "selected_subqueries_and_constructs"
    if constructs:
        return "selected_constructs"
    if subqueries:
        return "selected_subqueries"
    if (
        evidence.authorization
        == AUTHORIZATION_PRESERVE_SCALAR_WHERE_SUBQUERIES
    ):
        return "all_scalar_where_subqueries"
    return "no_construct_fingerprints"


def _normalize_hash(value: str) -> str:
    text = str(value or "").strip().lower()
    return text[7:] if text.startswith("sha256:") else text


def _source_signatures(source_sql: Optional[str]) -> set[Tuple[str, str]]:
    if source_sql is None:
        return set()
    tokens = _tokenize(source_sql)
    return {
        (subquery.predicate_kind, subquery.canonical)
        for subquery in _find_subqueries(source_sql, tokens)
    }


def _source_construct_signatures(
    source_sql: Optional[str],
) -> set[Tuple[str, str, str]]:
    if source_sql is None:
        return set()
    tokens = _tokenize(source_sql)
    return {
        (construct.kind, construct.variant, construct.canonical)
        for construct in _find_generation_constructs(source_sql, tokens)
    }


def _find_generation_constructs(
    sql: str,
    tokens: Sequence[_Token],
) -> List[_Construct]:
    pairs = _parenthesis_pairs(tokens)
    constructs: List[_Construct] = []
    seen: set[Tuple[str, str, int, int]] = set()

    def add(
        kind: str,
        variant: str,
        issue_code: str,
        start_index: int,
        end_index: int,
    ) -> None:
        if not (0 <= start_index <= end_index < len(tokens)):
            return
        key = (kind, variant, start_index, end_index)
        if key in seen:
            return
        seen.add(key)
        canonical = _canonical_construct_tokens(
            tokens[start_index : end_index + 1]
        )
        constructs.append(
            _Construct(
                kind=kind,
                variant=variant,
                issue_code=issue_code,
                start=tokens[start_index].start,
                end=tokens[end_index].end,
                canonical=canonical,
                fingerprint=sha256_text(
                    f"{kind}\n{variant}\n{canonical}"
                ),
            )
        )

    for index, token in enumerate(tokens):
        keyword = token.keyword

        if (
            keyword == "CREATE"
            and _keyword_at(tokens, index + 1) == "TABLE"
            and _is_temp_identifier_at(tokens, index + 2)
        ):
            end_index = _declaration_end_index(
                tokens,
                pairs,
                index + 2,
            )
            add(
                "temp_table",
                "create_table",
                ISSUE_NEW_TEMP_TABLE,
                index,
                end_index,
            )

        if keyword == "INTO" and _is_temp_identifier_at(tokens, index + 1):
            select_index = _find_preceding_statement_keyword(
                tokens,
                index,
                "SELECT",
            )
            if select_index >= 0:
                add(
                    "temp_table",
                    "select_into",
                    ISSUE_NEW_TEMP_TABLE,
                    select_index,
                    _statement_end_index(tokens, index),
                )

        if _is_variable_identifier(token):
            table_index = index + 1
            if _keyword_at(tokens, table_index) == "AS":
                table_index += 1
            if _keyword_at(tokens, table_index) == "TABLE":
                declare_index = _find_preceding_statement_keyword(
                    tokens,
                    index,
                    "DECLARE",
                )
                if declare_index >= 0:
                    add(
                        "table_variable",
                        "declare_table",
                        ISSUE_NEW_TABLE_VARIABLE,
                        declare_index,
                        _declaration_end_index(
                            tokens,
                            pairs,
                            table_index,
                        ),
                    )
            else:
                type_end = _user_defined_type_end_index(tokens, table_index)
                declare_index = _find_preceding_statement_keyword(
                    tokens,
                    index,
                    "DECLARE",
                )
                if type_end >= table_index and declare_index >= 0:
                    add(
                        "table_variable",
                        "declare_user_defined_type",
                        ISSUE_NEW_TABLE_VARIABLE,
                        declare_index,
                        type_end,
                    )

        if keyword == "IDENTITY" and (
            _keyword_at(tokens, index - 1) != "."
        ):
            identity_end = index
            variant = "identity_property"
            if index + 1 in pairs:
                identity_end = pairs[index + 1]
                variant = "identity_function"
            elif not _identity_is_column_property(tokens, index):
                identity_end = -1
            if identity_end >= index:
                add(
                    "identity_allocation",
                    variant,
                    ISSUE_NEW_IDENTITY_ALLOCATION,
                    index,
                    identity_end,
                )

        if keyword == "ROW_NUMBER" and index + 1 in pairs:
            row_number_close = pairs[index + 1]
            over_index = row_number_close + 1
            over_open = over_index + 1
            if (
                _keyword_at(tokens, over_index) == "OVER"
                and over_open in pairs
            ):
                add(
                    "row_number_sequencing",
                    "row_number_over",
                    ISSUE_NEW_ROW_NUMBER_SEQUENCING,
                    index,
                    pairs[over_open],
                )

        if (
            keyword in {"CREATE", "ALTER", "DROP"}
            and _keyword_at(tokens, index + 1) == "SEQUENCE"
        ):
            add(
                "sequence_ddl",
                f"{keyword.lower()}_sequence",
                ISSUE_NEW_SEQUENCE_DDL,
                index,
                _statement_end_index(tokens, index),
            )

        if (
            keyword == "NEXT"
            and _keyword_at(tokens, index + 1) == "VALUE"
            and _keyword_at(tokens, index + 2) == "FOR"
        ):
            add(
                "next_value_for",
                "next_value_for",
                ISSUE_NEW_NEXT_VALUE_FOR,
                index,
                _next_value_end_index(tokens, pairs, index),
            )

        if keyword == "MAX" and index + 1 in pairs:
            max_close = pairs[index + 1]
            end_index = _plus_one_end_index(tokens, max_close)
            if (
                end_index >= 0
                and _is_sequence_allocation_value(
                    tokens,
                    index + 2,
                    max_close - 1,
                )
                and _sequence_allocation_context_is_ordinal(
                    tokens,
                    index + 2,
                    max_close - 1,
                    index,
                    end_index,
                )
            ):
                add(
                    "sequence_allocation",
                    "max_plus_one",
                    ISSUE_NEW_SEQUENCE_ALLOCATION,
                    index,
                    end_index,
                )

        if keyword in {"ISNULL", "COALESCE"} and index + 1 in pairs:
            outer_close = pairs[index + 1]
            max_index = index + 2
            if (
                _keyword_at(tokens, max_index) == "MAX"
                and max_index + 1 in pairs
            ):
                max_close = pairs[max_index + 1]
                end_index = _plus_one_end_index(tokens, outer_close)
                if (
                    max_close < outer_close
                    and _keyword_at(tokens, max_close + 1) == ","
                    and end_index >= 0
                    and _is_sequence_allocation_value(
                        tokens,
                        max_index + 2,
                        max_close - 1,
                    )
                    and _sequence_allocation_context_is_ordinal(
                        tokens,
                        max_index + 2,
                        max_close - 1,
                        index,
                        end_index,
                    )
                ):
                    add(
                        "sequence_allocation",
                        f"{keyword.lower()}_max_plus_one",
                        ISSUE_NEW_SEQUENCE_ALLOCATION,
                        index,
                        end_index,
                    )

    constructs.sort(key=lambda item: (item.start, item.end, item.kind))
    return constructs


def _construct_issue_message(kind: str) -> str:
    messages = {
        "temp_table": (
            "Generated SQL introduces a #temp table without exact "
            "source-hash authorization for its construct fingerprint."
        ),
        "table_variable": (
            "Generated SQL introduces a table variable without exact "
            "source-hash authorization for its construct fingerprint."
        ),
        "identity_allocation": (
            "Generated SQL introduces IDENTITY allocation without exact "
            "source-hash authorization for its construct fingerprint."
        ),
        "row_number_sequencing": (
            "Generated SQL introduces ROW_NUMBER-based sequencing without "
            "exact source-hash authorization for its construct fingerprint."
        ),
        "sequence_ddl": (
            "Generated SQL introduces sequence DDL without exact source-hash "
            "authorization for its construct fingerprint."
        ),
        "next_value_for": (
            "Generated SQL introduces NEXT VALUE FOR without exact "
            "source-hash authorization for its construct fingerprint."
        ),
        "sequence_allocation": (
            "Generated SQL introduces MAX-based sequence allocation without "
            "exact source-hash authorization for its construct fingerprint."
        ),
    }
    return messages[kind]


def _keyword_at(tokens: Sequence[_Token], index: int) -> str:
    if not 0 <= index < len(tokens):
        return ""
    return tokens[index].keyword or tokens[index].text


def _is_temp_identifier_at(tokens: Sequence[_Token], index: int) -> bool:
    if not 0 <= index < len(tokens):
        return False
    text = tokens[index].text
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1].replace("]]", "]")
    elif text.startswith('"') and text.endswith('"'):
        text = text[1:-1].replace('""', '"')
    return text.startswith("#")


def _is_variable_identifier(token: _Token) -> bool:
    return token.kind == "word" and token.text.startswith("@")


def _user_defined_type_end_index(
    tokens: Sequence[_Token],
    start_index: int,
) -> int:
    if not 0 <= start_index < len(tokens):
        return -1
    first = tokens[start_index]
    if first.kind not in {"word", "identifier"}:
        return -1
    if first.keyword in _BUILTIN_DECLARE_TYPES or first.keyword in {
        "CURSOR",
        "TABLE",
    }:
        return -1

    end_index = start_index
    index = start_index + 1
    while (
        index + 1 < len(tokens)
        and tokens[index].text == "."
        and tokens[index + 1].kind in {"word", "identifier"}
    ):
        end_index = index + 1
        index += 2
    return end_index


def _plus_one_end_index(
    tokens: Sequence[_Token],
    value_close_index: int,
) -> int:
    if (
        _keyword_at(tokens, value_close_index + 1) == "+"
        and _keyword_at(tokens, value_close_index + 2) == "1"
    ):
        return value_close_index + 2
    return -1


def _is_sequence_allocation_value(
    tokens: Sequence[_Token],
    start_index: int,
    end_index: int,
) -> bool:
    if not 0 <= start_index <= end_index < len(tokens):
        return False
    value_tokens = tokens[start_index : end_index + 1]
    if not value_tokens:
        return False
    expect_identifier = True
    for token in value_tokens:
        if expect_identifier:
            if token.kind not in {"word", "identifier"}:
                return False
            expect_identifier = False
        elif token.text == ".":
            expect_identifier = True
        else:
            return False
    return not expect_identifier


def _identifier_is_sequence_name(token: _Token) -> bool:
    if token.kind not in {"word", "identifier"}:
        return False
    value = token.text
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1].replace("]]", "]")
    elif value.startswith('"') and value.endswith('"'):
        value = value[1:-1].replace('""', '"')
    value = value.upper().lstrip("@")
    parts = [part for part in value.replace("-", "_").split("_") if part]
    return any(
        part in _SEQUENCE_NAME_PARTS
        or part.startswith(("KEY", "SEQ", "ORD"))
        or part.endswith(("KEY", "SEQ", "ORD", "NO", "NUM", "ID"))
        for part in parts
    )


def _sequence_allocation_context_is_ordinal(
    tokens: Sequence[_Token],
    value_start_index: int,
    value_end_index: int,
    expression_start_index: int,
    expression_end_index: int,
) -> bool:
    if any(
        _identifier_is_sequence_name(token)
        for token in tokens[value_start_index : value_end_index + 1]
    ):
        return True

    next_index = expression_end_index + 1
    if _keyword_at(tokens, next_index) == "AS":
        next_index += 1
    if (
        next_index < len(tokens)
        and tokens[next_index].kind in {"word", "identifier"}
        and tokens[next_index].keyword
        not in {"FROM", "WHERE", "GROUP", "ORDER", "HAVING", "JOIN"}
        and _identifier_is_sequence_name(tokens[next_index])
    ):
        return True

    equal_index = expression_start_index - 1
    if _keyword_at(tokens, equal_index) != "=":
        return False
    target_index = equal_index - 1
    return (
        0 <= target_index < len(tokens)
        and _identifier_is_sequence_name(tokens[target_index])
    )


def _declaration_end_index(
    tokens: Sequence[_Token],
    pairs: Mapping[int, int],
    name_or_table_index: int,
) -> int:
    base_depth = tokens[name_or_table_index].depth
    for index in range(name_or_table_index + 1, len(tokens)):
        token = tokens[index]
        if token.depth < base_depth:
            break
        if token.text == "(" and token.depth == base_depth and index in pairs:
            return pairs[index]
        if token.text == ";" and token.depth == base_depth:
            return index
    return name_or_table_index


def _statement_end_index(tokens: Sequence[_Token], start_index: int) -> int:
    base_depth = tokens[start_index].depth
    for index in range(start_index + 1, len(tokens)):
        token = tokens[index]
        if token.depth < base_depth:
            return index - 1
        if token.depth == base_depth:
            if token.text == ";":
                return index
            if token.keyword == "END":
                return max(start_index, index - 1)
    return len(tokens) - 1


def _find_preceding_statement_keyword(
    tokens: Sequence[_Token],
    start_index: int,
    keyword: str,
) -> int:
    target_depth = tokens[start_index].depth
    for index in range(start_index - 1, -1, -1):
        token = tokens[index]
        if token.depth > target_depth:
            continue
        if token.depth < target_depth:
            return -1
        if token.text == ";" or token.keyword in {"BEGIN", "END"}:
            return -1
        if token.keyword == keyword:
            return index
    return -1


def _identity_is_column_property(
    tokens: Sequence[_Token],
    identity_index: int,
) -> bool:
    for index in range(identity_index - 1, -1, -1):
        token = tokens[index]
        if token.text == ";" or token.keyword in {"BEGIN", "END"}:
            return False
        if token.keyword == "DECLARE":
            return any(
                item.keyword == "TABLE"
                for item in tokens[index + 1 : identity_index]
            )
        if (
            token.keyword == "CREATE"
            and _keyword_at(tokens, index + 1) == "TABLE"
        ):
            return True
        if token.keyword in {"SELECT", "INSERT", "UPDATE", "DELETE"}:
            return False
    return False


def _next_value_end_index(
    tokens: Sequence[_Token],
    pairs: Mapping[int, int],
    next_index: int,
) -> int:
    index = next_index + 3
    end_index = next_index + 2
    expect_identifier = True
    while index < len(tokens):
        token = tokens[index]
        if expect_identifier and token.kind in {"word", "identifier"}:
            end_index = index
            expect_identifier = False
            index += 1
            continue
        if not expect_identifier and token.text == ".":
            end_index = index
            expect_identifier = True
            index += 1
            continue
        break
    if (
        _keyword_at(tokens, index) == "OVER"
        and index + 1 in pairs
    ):
        return pairs[index + 1]
    return end_index


def _canonical_construct_tokens(tokens: Sequence[_Token]) -> str:
    values: List[str] = []
    for token in tokens:
        if token.kind in {"word", "identifier"}:
            values.append(token.text.upper())
        else:
            values.append(token.text)
    return " ".join(values)


def _find_subqueries(sql: str, tokens: Sequence[_Token]) -> List[_Subquery]:
    pairs = _parenthesis_pairs(tokens)
    candidates: List[Tuple[int, int]] = []
    for open_index, close_index in pairs.items():
        first = open_index + 1
        if first < close_index and tokens[first].keyword in _QUERY_STARTERS:
            candidates.append((open_index, close_index))
    candidates.sort()

    result: List[_Subquery] = []
    for open_index, close_index in candidates:
        kind, direct_if = _predicate_kind(tokens, open_index)
        clause = _containing_clause(tokens, open_index)
        canonical = _canonical_tokens(tokens[open_index + 1 : close_index])
        ancestor_kind = ""
        enclosing = [
            item
            for item in result
            if item.open_index < open_index < item.close_index
        ]
        if enclosing:
            ancestor_kind = enclosing[-1].predicate_kind
        start = tokens[open_index].start
        end = tokens[close_index].end
        result.append(
            _Subquery(
                open_index=open_index,
                close_index=close_index,
                start=start,
                end=end,
                predicate_kind=kind,
                clause=clause,
                direct_if=direct_if,
                canonical=canonical,
                text_sha256=sha256_text(sql[start:end]),
                ancestor_predicate_kind=ancestor_kind,
            )
        )
    return result


def _predicate_kind(tokens: Sequence[_Token], open_index: int) -> Tuple[str, bool]:
    previous = tokens[open_index - 1] if open_index else None
    before_previous = tokens[open_index - 2] if open_index > 1 else None
    third_previous = tokens[open_index - 3] if open_index > 2 else None

    if previous and previous.keyword == "EXISTS":
        if before_previous and before_previous.keyword == "NOT":
            direct_if = bool(third_previous and third_previous.keyword == "IF")
            return "not_exists", direct_if
        direct_if = bool(before_previous and before_previous.keyword == "IF")
        return "exists", direct_if
    if previous and previous.keyword == "IN":
        if before_previous and before_previous.keyword == "NOT":
            return "not_in", False
        return "in", False
    return "scalar", False


def _containing_clause(tokens: Sequence[_Token], open_index: int) -> str:
    target_depth = tokens[open_index].depth
    for token in reversed(tokens[:open_index]):
        if token.depth > target_depth:
            continue
        if token.depth < target_depth:
            break
        keyword = token.keyword
        if keyword in _CLAUSE_BOUNDARIES:
            return keyword
        if token.text == ";":
            break
    return ""


def _parenthesis_pairs(tokens: Sequence[_Token]) -> Dict[int, int]:
    stack: List[int] = []
    pairs: Dict[int, int] = {}
    for index, token in enumerate(tokens):
        if token.text == "(":
            stack.append(index)
        elif token.text == ")" and stack:
            pairs[stack.pop()] = index
    return pairs


def _canonical_tokens(tokens: Sequence[_Token]) -> str:
    values = []
    for token in tokens:
        if token.kind == "word":
            values.append(token.text.upper())
        else:
            values.append(token.text)
    return " ".join(values)


def _line_column(text: str, offset: int) -> Tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    last_newline = text.rfind("\n", 0, offset)
    column = offset + 1 if last_newline < 0 else offset - last_newline
    return line, column


def _tokenize(sql: str) -> List[_Token]:
    tokens: List[_Token] = []
    index = 0
    depth = 0
    length = len(sql)

    while index < length:
        character = sql[index]
        if character.isspace():
            index += 1
            continue
        if sql.startswith("--", index):
            newline = sql.find("\n", index + 2)
            index = length if newline < 0 else newline + 1
            continue
        if sql.startswith("/*", index):
            index = _skip_block_comment(sql, index)
            continue
        if character == "'":
            end = _skip_quoted(sql, index, "'", "''")
            tokens.append(_Token(sql[index:end], "literal", index, end, depth))
            index = end
            continue
        if character == '"':
            end = _skip_quoted(sql, index, '"', '""')
            tokens.append(_Token(sql[index:end], "identifier", index, end, depth))
            index = end
            continue
        if character == "[":
            end = _skip_bracket_identifier(sql, index)
            tokens.append(_Token(sql[index:end], "identifier", index, end, depth))
            index = end
            continue
        if character == "(":
            tokens.append(_Token(character, "symbol", index, index + 1, depth))
            depth += 1
            index += 1
            continue
        if character == ")":
            depth = max(0, depth - 1)
            tokens.append(_Token(character, "symbol", index, index + 1, depth))
            index += 1
            continue
        if character.isalpha() or character in "_@#$":
            end = index + 1
            while end < length and (
                sql[end].isalnum() or sql[end] in "_@#$"
            ):
                end += 1
            tokens.append(_Token(sql[index:end], "word", index, end, depth))
            index = end
            continue
        if character.isdigit():
            end = index + 1
            while end < length and (sql[end].isalnum() or sql[end] in ".xX"):
                end += 1
            tokens.append(_Token(sql[index:end], "number", index, end, depth))
            index = end
            continue

        two_character = sql[index : index + 2]
        if two_character in {"<=", ">=", "<>", "!=", "!<", "!>", "::"}:
            tokens.append(
                _Token(two_character, "operator", index, index + 2, depth)
            )
            index += 2
        else:
            tokens.append(
                _Token(character, "symbol", index, index + 1, depth)
            )
            index += 1

    return tokens


def _skip_block_comment(sql: str, start: int) -> int:
    depth = 1
    index = start + 2
    while index < len(sql) and depth:
        if sql.startswith("/*", index):
            depth += 1
            index += 2
        elif sql.startswith("*/", index):
            depth -= 1
            index += 2
        else:
            index += 1
    return index


def _skip_quoted(sql: str, start: int, delimiter: str, escaped: str) -> int:
    index = start + 1
    while index < len(sql):
        if sql.startswith(escaped, index):
            index += len(escaped)
        elif sql.startswith(delimiter, index):
            return index + len(delimiter)
        else:
            index += 1
    return len(sql)


def _skip_bracket_identifier(sql: str, start: int) -> int:
    index = start + 1
    while index < len(sql):
        if sql.startswith("]]", index):
            index += 2
        elif sql[index] == "]":
            return index + 1
        else:
            index += 1
    return len(sql)


__all__ = [
    "AUTHORIZATION_PRESERVE_EXACT_SOURCE_CONSTRUCTS",
    "AUTHORIZATION_PRESERVE_SCALAR_WHERE_SUBQUERIES",
    "ISSUE_NEW_IDENTITY_ALLOCATION",
    "ISSUE_NEW_NEXT_VALUE_FOR",
    "ISSUE_NEW_ROW_NUMBER_SEQUENCING",
    "ISSUE_NEW_SCALAR_WHERE_SUBQUERY",
    "ISSUE_NEW_SEQUENCE_ALLOCATION",
    "ISSUE_NEW_SEQUENCE_DDL",
    "ISSUE_NEW_TABLE_VARIABLE",
    "ISSUE_NEW_TEMP_TABLE",
    "POLICY_ID",
    "POLICY_VERSION",
    "PolicyIssue",
    "PolicyResult",
    "SourceEquivalenceEvidence",
    "build_source_equivalence_evidence",
    "evaluate_pb_sql_generation_policy",
    "evaluate_policy",
    "find_pb_sql_generation_policy_issues",
    "sha256_text",
    "validate_pb_sql_generation_policy",
]
