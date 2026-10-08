"""Distinguish SQL preservation errors from scoped style preferences."""
from collections import Counter
import re
from src.common.results import CheckResult, HarnessResult, Issue
from .compare import compare_sql
from .lexer import _analyze_sql_integrity, _masked_sql, _scan_sql_tokens
from .layout import _style_lint
from .delta import _full_replace_records


def _generation_choices(source: str) -> list[tuple[str, str, int, dict[str, str]]]:
    """Observe explicit hints and aliased empty CAST results, not their necessity."""
    tokens = [token for token in _scan_sql_tokens(source)[0]
              if token.kind not in {'line_comment', 'block_comment'}]
    findings: list[tuple[str, str, int, dict[str, str]]] = []
    for index, token in enumerate(tokens):
        if token.kind != 'word' or index + 1 >= len(tokens) or tokens[index + 1].text != '(':
            continue
        closing = index + 2
        depth = 1
        while closing < len(tokens):
            value = tokens[closing].text
            if value == '(':
                depth += 1
            elif value == ')':
                depth -= 1
                if depth == 0:
                    break
            closing += 1
        if closing >= len(tokens):
            continue
        if token.normalized == 'WITH':
            for hint in tokens[index + 2:closing]:
                if hint.kind == 'word' and hint.normalized in {'UPDLOCK', 'HOLDLOCK'}:
                    findings.append(('locking_hint_review', hint.normalized, hint.start, {'hint': hint.normalized}))
        elif (token.normalized == 'CAST' and index + 4 < closing and
              tokens[index + 2].normalized in {"''", "N''", 'NULL'} and
              tokens[index + 3].normalized == 'AS' and closing + 2 < len(tokens) and
              tokens[closing + 1].normalized == 'AS' and
              tokens[closing + 2].kind in {'word', 'bracket_identifier', 'quoted_identifier'}):
            field = tokens[closing + 2].text
            identity = repr([t.normalized for t in tokens[index:closing + 3]])
            findings.append(('synthetic_result_field_review', identity, token.start, {'field': field}))
    return findings


def _review_generation_choices(candidate: str, original: str | None) -> list[Issue]:
    previous = Counter((code, identity) for code, identity, _, _ in _generation_choices(original or ''))
    messages = {
        'locking_hint_review': 'Review this added locking hint against the actual target concurrency and transaction contract. Do not add UPDLOCK/HOLDLOCK routinely; retain them when the requested behavior or verified necessity requires them.',
        'synthetic_result_field_review': 'This output field is a typed empty or NULL placeholder. Check the requested target result/binding contract; remove excluded source-only fields instead of carrying them as placeholders, and keep a placeholder only when the actual output type contract requires it.',
    }
    issues: list[Issue] = []
    for code, identity, offset, details in _generation_choices(candidate):
        if previous[(code, identity)]:
            previous[(code, identity)] -= 1
            continue
        issues.append(Issue(code, 'warning', messages[code],
                            line=candidate.count('\n', 0, offset) + 1, details=details))
    return issues


def check_sql(candidate: str, *, original: str | None = None, preserve_aliases: bool = False,
              check_style: bool = True, check_delta: bool = False, check_preferences: bool = True) -> CheckResult:
    result = compare_sql(original, candidate, preserve_aliases=preserve_aliases) if original is not None else CheckResult(
        checked=["SQL lexical integrity"], not_checked=["SQL Server execution", "complete T-SQL grammar and type semantics", "business equivalence to an unsupplied source"])
    result.metadata['comparison_baselines'] = {'sql': original is not None}
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
            if item.code == 'insert_select_alignment_unverified':
                result.not_checked.append('unsupported horizontal INSERT/SELECT alignment listed in insert_select_alignment_unverified')
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
        if check_preferences and len(re.findall(pattern, masked, re.I)) > len(re.findall(pattern, previous, re.I)):
            result.issues.append(Issue(code, "warning", "Use the preferred existing form unless avoiding this construct makes implementation difficult or the alternative performs extremely worse."))
    result.issues.extend(_review_generation_choices(candidate, original))
    result.checked.append('explicit added locking hints and aliased typed-empty output fields')
    result.not_checked.append('necessity of locking hints/placeholders, persisted numbering scope, save-state branches and target parameter/result contracts')
    result.metadata['review_status'] = 'needs_review' if result.issues else 'static_checks_only'
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
