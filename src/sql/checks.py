"""Distinguish SQL preservation errors from scoped style preferences."""
import re
from src.common.results import CheckResult, HarnessResult, Issue
from .compare import compare_sql
from .lexer import _analyze_sql_integrity, _masked_sql
from .layout import _style_lint
from .delta import _full_replace_records


def check_sql(candidate: str, *, original: str | None = None, preserve_aliases: bool = False,
              check_style: bool = True, check_delta: bool = False) -> CheckResult:
    result = compare_sql(original, candidate, preserve_aliases=preserve_aliases) if original is not None else CheckResult(
        checked=["SQL lexical integrity"], not_checked=["SQL Server execution", "complete T-SQL grammar and type semantics", "business equivalence to an unsupplied source"])
    tokens, errors = _analyze_sql_integrity(candidate, check_kind="candidate")
    if not any(t.kind not in {'line_comment', 'block_comment'} for t in tokens):
        result.incomplete = True
        result.issues.append(Issue('sql_code_missing', 'warning', 'No SQL code is available beyond comments or whitespace.'))
    if original is None:
        result.issues.extend(Issue(e.code, e.severity, e.message, details={"evidence": e.evidence}) for e in errors)
    if any(e.severity == "error" for e in errors):
        return result
    if check_style:
        result.checked.append("KH SQL layout preferences")
        for item in _style_lint(original or candidate, candidate, tokens, tokens,
                                operation="formatting" if original is not None else "generation"):
            if preserve_aliases and item.code in {"ad_hoc_outer_alias", "outer_query_uses_derived_table_internal_alias"}:
                continue
            result.issues.append(Issue(item.code, "warning", item.message,
                                      details={"evidence": item.evidence, "scope": "KH SQL style"}))
    if check_delta:
        result.checked.append("DELETE/INSERT replacement shapes")
        before = {r["shape_sha256"] for r in _full_replace_records(original or "")}
        for record in _full_replace_records(candidate):
            if record["shape_sha256"] not in before:
                result.issues.append(Issue("review_full_replace", "warning",
                                          "Confirm the requested NEW/MOD/DEL contract before replacing all related rows.", details=record))
    masked = _masked_sql(candidate)
    previous = _masked_sql(original or "")
    for code, pattern in [("intermediate_table_preference", r"\b(?:CREATE\s+TABLE\s+#|DECLARE\s+@\w+\s+TABLE|INTO\s+#)"),
                          ("subquery_preference", r"\b(?:WHERE|AND|OR)\b[^;]*?\b(?:NOT\s+EXISTS|IN\s*\(\s*SELECT)")]:
        if len(re.findall(pattern, masked, re.I)) > len(re.findall(pattern, previous, re.I)):
            result.issues.append(Issue(code, "warning", "Use the preferred existing form unless avoiding this construct makes implementation difficult or the alternative performs extremely worse."))
    return result


def verify_sql_formatting_style(original: str, formatted: str, *, preserve_aliases: bool = False, **options) -> HarnessResult:
    """Retained text-check entrypoint. Removed runtime receipt options are rejected."""
    unsupported = set(options) - {"operation", "check_style", "check_delta"}
    if unsupported:
        raise TypeError("removed SQL runtime options: " + ", ".join(sorted(unsupported)))
    operation = options.get("operation", "formatting")
    if operation not in {"formatting", "generation"}:
        raise ValueError("operation must be formatting or generation; refactoring needs an explicit semantic review")
    result = check_sql(formatted, original=original if operation == "formatting" else None,
                       preserve_aliases=preserve_aliases, check_style=options.get("check_style", True),
                       check_delta=options.get("check_delta", False))
    return HarnessResult(success=result.success, stdout=result.to_json(), stderr="" if result.success else "SQL check failed",
                         exit_code=result.exit_code, metadata=result.to_dict())
