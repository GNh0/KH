"""Distinguish SQL preservation errors from scoped style preferences."""
from collections import Counter
import re
from src.common.results import CheckResult, HarnessResult, Issue
from .compare import compare_sql
from .lexer import (
    _SqlToken, _analyze_sql_integrity, _identifier_value, _is_identifier_token,
    _masked_sql, _matching_parenthesis_token, _scan_sql_tokens,
)
from .layout import _style_lint
from .delta import _full_replace_records
from .dispatch import review_dispatch


def _review_line_number(source: str, offset: int) -> int:
    return len(re.findall(r'\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]', source[:offset])) + 1


def _absence_guard(tokens: list[_SqlToken]) -> bool:
    for index, token in enumerate(tokens):
        if token.kind == 'word' and token.normalized == 'IS':
            end = index + 1
            if end < len(tokens) and tokens[end].normalized == 'NOT':
                end += 1
            if end < len(tokens) and tokens[end].normalized == 'NULL':
                return True
        if token.text in {'=', '<>', '!='} and any(
                tokens[neighbor].normalized in {"''", "N''"}
                for neighbor in (index - 1, index + 1) if 0 <= neighbor < len(tokens)):
            return True
    return False


def _value_contexts(tokens: list[_SqlToken]) -> list[bool]:
    """Separate value production from predicate-only NULL handling."""
    clauses = [True]
    cases: list[tuple[int, bool]] = []
    iifs: dict[int, bool] = {}
    result = []
    for index, token in enumerate(tokens):
        result.append(clauses[-1])
        word = token.normalized if token.kind == 'word' else ''
        if token.text == '(':
            clauses.append(clauses[-1])
            if index and tokens[index - 1].kind == 'word' and tokens[index - 1].normalized == 'IIF':
                iifs[len(clauses)] = clauses[-1]
                clauses[-1] = False
        elif token.text == ',' and len(clauses) in iifs:
            clauses[-1] = iifs[len(clauses)]
        elif token.text == ')' and len(clauses) > 1:
            iifs.pop(len(clauses), None)
            clauses.pop()
        elif token.text == ';' or token.kind == 'batch_separator':
            clauses[-1] = True
        elif word in {'SELECT', 'SET', 'VALUES', 'RETURN', 'DECLARE'}:
            clauses[-1] = True
        elif word in {'FROM', 'JOIN', 'ON', 'WHERE', 'HAVING', 'GROUP', 'ORDER', 'IF', 'WHILE'}:
            clauses[-1] = False
        elif word == 'CASE':
            cases.append((len(clauses), clauses[-1]))
        elif word == 'WHEN' and cases:
            clauses[-1] = False
        elif word in {'THEN', 'ELSE'} and cases:
            clauses[-1] = cases[-1][1]
        elif word == 'END' and cases and cases[-1][0] == len(clauses):
            clauses[-1] = cases.pop()[1]
    return result


def _value_fallbacks(source: str) -> list[tuple[tuple[str, ...], str, int]]:
    """Recognize null/blank substitutions, not their authorization or necessity."""
    tokens = [t for t in _scan_sql_tokens(source)[0] if t.kind not in {'line_comment', 'block_comment'}]
    values = _value_contexts(tokens)
    found = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        form = token.normalized if token.kind == 'word' else ''
        close = None
        if not values[index]:
            index += 1
            continue
        if form in {'ISNULL', 'COALESCE', 'IIF'} and index + 1 < len(tokens) and tokens[index + 1].text == '(' and (not index or tokens[index - 1].text != '.'):
            close = _matching_parenthesis_token(tokens, index + 1, len(tokens))
            if close is not None and form == 'IIF':
                depth = 0
                comma = close
                for cursor in range(index + 2, close):
                    text = tokens[cursor].text
                    if text == '(':
                        depth += 1
                    elif text == ')':
                        depth -= 1
                    elif text == ',' and not depth:
                        comma = cursor
                        break
                if not _absence_guard(tokens[index + 2:comma]):
                    close = None
        elif form == 'CASE':
            depth = 1
            guard = None
            absent = False
            for cursor in range(index + 1, len(tokens)):
                word = tokens[cursor].normalized if tokens[cursor].kind == 'word' else ''
                if word == 'CASE':
                    depth += 1
                elif word == 'END':
                    depth -= 1
                    if not depth:
                        close = cursor
                        break
                elif word == 'WHEN' and depth == 1:
                    guard = cursor + 1
                elif word == 'THEN' and depth == 1 and guard is not None:
                    absent = absent or _absence_guard(tokens[guard:cursor])
                    guard = None
            if not absent:
                close = None
        if close is not None:
            found.append((tuple(t.normalized for t in tokens[index:close + 1]), form, token.start))
            index = close + 1  # One finding for a nested fallback chain.
        else:
            index += 1
    return found


def _review_value_fallbacks(candidate: str, original: str | None) -> list[Issue]:
    previous = Counter(identity for identity, _, _ in _value_fallbacks(original or ''))
    added = []
    for identity, form, offset in _value_fallbacks(candidate):
        if previous[identity]:
            previous[identity] -= 1
        else:
            added.append((form, offset))
    if added and original is not None and compare_sql(original, candidate).success:
        return []  # Recognized formatting/alias-only changes did not add a value policy.
    return [Issue('value_fallback_review', 'warning',
        'This new or changed null/blank substitution needs the user\'s explicit request for this value source. Preserve the supplied/stored value otherwise. A default-initialization request, nullable column, missing legacy data or defensive intent does not authorize a SAVE/SELECT fallback. Verify the actual request and owning flow; do not replace it with another fallback form to silence review.',
        line=_review_line_number(candidate, offset), details={'form': form, 'authorization_required': 'explicit user request for this substitution'})
        for form, offset in added]


def _xml_write_sources(source: str) -> tuple[bool, list[tuple[tuple[str, ...], int]]]:
    """Recognize simple XML-to-staging loads and XML sources in owning DML.

    This observes a preparation boundary; it does not ban a rowset API or
    establish XML schema, key cardinality, transaction or handle correctness.
    """
    tokens = [t for t in _scan_sql_tokens(source)[0] if t.kind not in {'line_comment', 'block_comment'}]
    staged = False
    direct = []
    operation = ''
    staging_target = False
    projection = False
    for index, token in enumerate(tokens):
        if token.depth:
            continue
        word = token.normalized if token.kind == 'word' else ''
        if token.text == ';' or token.kind == 'batch_separator' or word in {
                'EXEC', 'EXECUTE', 'DECLARE', 'BEGIN', 'END', 'IF', 'ELSE', 'RETURN', 'THROW'}:
            operation, projection = '', False
        elif word in {'INSERT', 'UPDATE', 'DELETE'}:
            operation, projection = word, False
            target = index + 1
            if target < len(tokens) and tokens[target].normalized == 'INTO':
                target += 1
            staging_target = word == 'INSERT' and target < len(tokens) and tokens[target].text.startswith(('@', '#'))
        elif word == 'SELECT':
            if operation != 'INSERT' or projection:
                operation = ''
            projection = True
        elif word == 'OPENXML' and operation and index + 1 < len(tokens) and tokens[index + 1].text == '(':
            close = _matching_parenthesis_token(tokens, index + 1, len(tokens))
            if close is not None:
                if operation == 'INSERT' and staging_target:
                    staged = True
                else:
                    direct.append(((operation, *(t.normalized for t in tokens[index:close + 1])), token.start))
    return staged, direct


def _review_xml_boundary(candidate: str, original: str | None) -> list[Issue]:
    before_staged, before_direct = _xml_write_sources(original or '')
    staged, direct = _xml_write_sources(candidate)
    if not (staged or before_staged):
        return []
    previous = Counter(signature for signature, _ in before_direct)
    result = []
    for signature, offset in direct:
        if previous[signature]:
            previous[signature] -= 1
            continue
        result.append(Issue('xml_save_boundary_review', 'warning',
            'This added write consumes XML directly while the procedure establishes parsed staging rows elsewhere. Compare the new action with that complete preparation/write boundary and the approved SAVE reference; preserve keys, types, row cardinality and handle/error ownership. Retain a different boundary only for a verified requirement; this is not a blanket OPENXML prohibition.',
            line=_review_line_number(candidate, offset), details={'operation': signature[0], 'staging_observed': True}))
    return result


def _where_subqueries(source: str) -> Counter[str]:
    """Count direct EXISTS/IN query shapes in recognizable WHERE contexts.

    Parenthesized predicates inherit their clause; an inner SELECT starts its
    own context. This is not a general T-SQL parser or a necessity judgment.
    """
    tokens = [token for token in _scan_sql_tokens(source)[0]
              if token.kind not in {'line_comment', 'block_comment'}]
    where = [False]
    found: Counter[str] = Counter()
    reset = {'SELECT', 'FROM', 'JOIN', 'ON', 'GROUP', 'ORDER', 'HAVING',
             'UNION', 'EXCEPT', 'INTERSECT', 'IF', 'WHILE', 'BEGIN',
             'RETURN', 'DECLARE', 'SET', 'INSERT', 'UPDATE', 'DELETE',
             'EXEC', 'EXECUTE', 'THROW', 'RAISERROR', 'OPTION'}
    for index, token in enumerate(tokens):
        if token.text == '(':
            where.append(where[-1])
        elif token.text == ')':
            if len(where) > 1:
                where.pop()
        elif token.text == ';' or token.kind == 'batch_separator':
            where[-1] = False
        elif token.kind == 'word':
            word = token.normalized
            if word == 'WHERE':
                where[-1] = True
            elif word in reset:
                where[-1] = False
            elif (where[-1] and word in {'EXISTS', 'IN'} and
                  index + 2 < len(tokens) and tokens[index + 1].text == '(' and
                  tokens[index + 2].kind == 'word' and tokens[index + 2].normalized == 'SELECT'):
                found[word] += 1
    return found


def _expression_subqueries(source: str) -> list[tuple[str, str, int]]:
    """Locate parenthesized queries in SELECT lists or scalar WHERE expressions."""
    tokens = [token for token in _scan_sql_tokens(source)[0]
              if token.kind not in {'line_comment', 'block_comment'}]
    clauses = ['']
    openers = ['']
    found: list[tuple[str, str, int]] = []
    reset = {'FROM', 'JOIN', 'ON', 'GROUP', 'ORDER', 'HAVING', 'UNION',
             'EXCEPT', 'INTERSECT', 'IF', 'WHILE', 'BEGIN',
             'RETURN', 'DECLARE', 'SET', 'INSERT', 'UPDATE', 'DELETE',
             'EXEC', 'EXECUTE', 'THROW', 'RAISERROR', 'OPTION', 'FOR'}
    for index, token in enumerate(tokens):
        if token.text == '(':
            clauses.append(clauses[-1])
            previous = tokens[index - 1] if index else None
            openers.append(previous.normalized if previous and previous.kind == 'word' else '')
        elif token.text == ')':
            if len(clauses) > 1:
                clauses.pop()
                openers.pop()
        elif token.text == ';' or token.kind == 'batch_separator':
            clauses[-1] = ''
        elif token.kind == 'word':
            word = token.normalized
            if word == 'SELECT':
                clause = clauses[-1]
                if (index and tokens[index - 1].text == '(' and
                        clause in {'SELECT', 'WHERE'} and
                        not (clause == 'WHERE' and openers[-1] in {'EXISTS', 'IN'})):
                    closing = _matching_parenthesis_token(tokens, index - 1, len(tokens))
                    if closing is not None:
                        identity = repr([item.normalized for item in tokens[index:closing]])
                        found.append((clause, identity, token.start))
                clauses[-1] = 'SELECT'
            elif word == 'WHERE':
                clauses[-1] = 'WHERE'
            elif word in reset:
                clauses[-1] = ''
    return found


def _cte_declarations(tokens: list[_SqlToken]) -> list[_SqlToken]:
    """Recognize statement-level WITH name [(columns)] AS (query) lists."""
    code = [token for token in tokens if token.kind not in {'line_comment', 'block_comment'}]
    declarations: list[_SqlToken] = []
    for index, token in enumerate(code):
        if token.depth != 0 or token.kind != 'word' or token.normalized != 'WITH':
            continue
        name_index = index + 1
        while name_index + 2 < len(code) and _is_identifier_token(code[name_index]):
            as_index = name_index + 1
            if code[as_index].text == '(':
                columns_end = _matching_parenthesis_token(code, as_index, len(code))
                if columns_end is None:
                    break
                as_index = columns_end + 1
            if as_index + 1 >= len(code) or code[as_index].normalized != 'AS' or code[as_index + 1].text != '(':
                break
            query_end = _matching_parenthesis_token(code, as_index + 1, len(code))
            if query_end is None:
                break
            declarations.append(code[name_index])
            if query_end + 1 >= len(code) or code[query_end + 1].text != ',':
                break
            name_index = query_end + 2
    return declarations


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
                            line=_review_line_number(candidate, offset), details=details))
    return issues


def check_sql(candidate: str, *, original: str | None = None, preserve_aliases: bool = False,
              check_style: bool = True, check_delta: bool = False, check_preferences: bool = True,
              compare_original: bool = True) -> CheckResult:
    comparing = original is not None and compare_original
    result = compare_sql(original, candidate, preserve_aliases=preserve_aliases) if original is not None and compare_original else CheckResult(
        checked=["SQL lexical integrity"], not_checked=["SQL Server execution", "complete T-SQL grammar and type semantics", "business equivalence to an unsupplied source"])
    result.metadata['comparison_baselines'] = {'sql': original is not None}
    result.metadata['original_comparison'] = 'formatting_preservation' if comparing else 'changed_preferences_only'
    if original is not None and not compare_original:
        result.not_checked.append('Original SQL is used for changed review findings, not to forbid requested behavior changes.')
    tokens, errors = _analyze_sql_integrity(candidate, check_kind="candidate")
    if not any(t.kind not in {'line_comment', 'block_comment'} for t in tokens):
        result.incomplete = True
        result.issues.append(Issue('sql_code_missing', 'warning', 'No SQL code is available beyond comments or whitespace.'))
    if not comparing:
        result.issues.extend(Issue(e.code, e.severity, e.message, details={"evidence": e.evidence}) for e in errors)
    if any(e.severity == "error" for e in errors):
        return result
    if check_style:
        result.checked.append("KH SQL layout preferences")
        for item in _style_lint(original or candidate, candidate, tokens, tokens,
                                operation="formatting" if original else "generation"):
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
    if check_preferences:
        pattern = r"\b(?:CREATE\s+TABLE\s+#|DECLARE\s+@\w+\s+TABLE|INTO\s+#)"
        if len(re.findall(pattern, masked, re.I)) > len(re.findall(pattern, previous, re.I)):
            result.issues.append(Issue('intermediate_table_preference', 'warning',
                'Use the preferred existing form unless avoiding this construct makes implementation difficult or the alternative performs extremely worse.'))
        original_tokens = _scan_sql_tokens(original)[0] if original else []
        previous_ctes = Counter(_identifier_value(token) for token in _cte_declarations(original_tokens))
        for declaration in _cte_declarations(tokens):
            name = _identifier_value(declaration)
            if previous_ctes[name]:
                previous_ctes[name] -= 1
                continue
            result.issues.append(Issue('cte_preference', 'warning',
                'Review this CTE against the approved procedure style. Retain it when the actual implementation or performance requires it. Check row keys, aggregation and duplicates before any rewrite.',
                line=_review_line_number(candidate, declaration.start), details={'cte': declaration.text}))
        added_subqueries = _where_subqueries(candidate) - _where_subqueries(original or '')
        if added_subqueries:
            result.issues.append(Issue('subquery_preference', 'warning',
                'Review added WHERE EXISTS/NOT EXISTS/IN queries against the target JOIN style. Preserve NULL behavior, duplicates and aggregation cardinality; IF EXISTS validation is a separate responsibility. Do not rewrite automatically.',
                details={'added_where_subqueries': dict(added_subqueries)}))
        previous_expressions = Counter((clause, identity) for clause, identity, _ in
                                       _expression_subqueries(original or ''))
        for clause, identity, offset in _expression_subqueries(candidate):
            if previous_expressions[(clause, identity)]:
                previous_expressions[(clause, identity)] -= 1
                continue
            result.issues.append(Issue('subquery_preference', 'warning',
                'Review this query in a SELECT list or scalar WHERE expression against the approved JOIN-based procedure. Resolve lookup or aggregation at its full key and row grain; preserve missing-row, NULL, duplicate and multi-row behavior. Do not substitute a variable or rewrite automatically.',
                line=_review_line_number(candidate, offset), details={'clause': clause}))
        result.checked.append('recognizable statement-level CTE declarations, SELECT-list/scalar-WHERE queries and WHERE EXISTS/NOT EXISTS/IN query counts')
        result.not_checked.append('CTE and subquery necessity, general clause grammar and JOIN-rewrite equivalence')
    result.issues.extend(_review_generation_choices(candidate, original))
    result.issues.extend(review_dispatch(candidate, original))
    result.issues.extend(_review_xml_boundary(candidate, original))
    result.issues.extend(_review_value_fallbacks(candidate, original))
    result.checked.append('added or changed ISNULL/COALESCE and supported NULL/blank-guard CASE/IIF substitutions')
    result.not_checked.append('user authorization for value substitution and equivalent fallbacks outside supported syntax')
    result.checked.append('recognizable new direct XML writes beside an established parsed-staging boundary')
    result.checked.append('explicit added locking hints and aliased typed-empty output fields')
    result.checked.append('supported repeated enclosing scalar-mode guards with no observed mode assignment')
    result.not_checked.append('necessity of locking hints/placeholders, persisted numbering scope, save-state branches and target parameter/result contracts')
    result.not_checked.append('sibling dispatch-phase ownership, jumps/loop re-entry, complex or unbraced predicates, case-sensitive parameter binding and complete mode-to-result-set behavior')
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
