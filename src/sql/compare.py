"""Scope-aware alpha-equivalence for SQL formatting, without receipt gates."""
from collections import Counter
from src.common.results import CheckResult, Issue
from .lexer import _analyze_sql_integrity, _canonical_token_value
from .scopes import _AliasChange, _build_sql_scopes, _find_alias_changes
from .compare_core import _canonical_token_stream, _first_token_difference


def compare_sql(original: str, candidate: str, *, preserve_aliases: bool = False) -> CheckResult:
    result = CheckResult(checked=["SQL lexical integrity", "token order, literals and comments", "scope-bound alias references"],
                         not_checked=["SQL Server execution", "complete T-SQL grammar and type semantics", "case-sensitive database identifier resolution"])
    left, left_errors = _analyze_sql_integrity(original, check_kind="source")
    right, right_errors = _analyze_sql_integrity(candidate, check_kind="candidate")
    for finding in left_errors + right_errors:
        result.issues.append(Issue(finding.code, finding.severity, finding.message,
                                   details={"evidence": finding.evidence}))
    if not result.success:
        return result
    left_scopes, right_scopes = _build_sql_scopes(left), _build_sql_scopes(right)
    for label, scopes in [("original", left_scopes), ("candidate", right_scopes)]:
        for scope in scopes:
            aliases = Counter(d.effective_alias for d in scope.declarations)
            if any(count > 1 for count in aliases.values()):
                result.issues.append(Issue("ambiguous_source_alias", "error", "A scope contains duplicate source aliases.",
                                           details={"side": label, "scope": scope.scope_id}))
    changes = [] if preserve_aliases else _find_alias_changes(left_scopes, right_scopes)
    for a, b in zip(left_scopes, right_scopes):
        for source, target in zip(a.declarations, b.declarations):
            if source.source == target.source and source.effective_alias == target.effective_alias:
                # AS on a source alias is optional; column AS is not in this range.
                has_as_before = source.alias_start is not None and left[source.alias_start].normalized == "AS"
                has_as_after = target.alias_start is not None and right[target.alias_start].normalized == "AS"
                if has_as_before != has_as_after:
                    changes.append(_AliasChange(b.scope_id, target.source, source.effective_alias,
                                                target.effective_alias, source, target))
    before = _canonical_token_stream(left, left_scopes, changes, "original")
    after = _canonical_token_stream(right, right_scopes, changes, "formatted")
    if before != after:
        result.issues.append(Issue("sql_meaning_tokens_changed", "error",
                                  "SQL changed beyond whitespace, casing, and permitted bound alias renaming.",
                                  details={"first_difference": _first_token_difference(before, after)}))
    # Keep localized text, comment placement/order and string spelling intact.
    for label, kinds in [("literals", {"string", "unicode_string"}), ("comments", {"line_comment", "block_comment"})]:
        first = [t.text for t in left if t.kind in kinds]
        second = [t.text for t in right if t.kind in kinds]
        if first != second:
            result.issues.append(Issue(label + "_changed", "error", f"The original {label} changed."))
    result.metadata["alias_changes"] = [{"scope": c.scope_id, "source": c.source,
                                          "before": c.original_alias, "after": c.formatted_alias} for c in changes]
    return result
