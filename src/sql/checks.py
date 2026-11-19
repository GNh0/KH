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


def _unwrapped(tokens: list[_SqlToken]) -> list[_SqlToken]:
    while tokens and tokens[0].text == '(' and _matching_parenthesis_token(tokens, 0, len(tokens)) == len(tokens) - 1:
        tokens = tokens[1:-1]
    return tokens


def _expression_key(tokens: list[_SqlToken]) -> tuple[str, ...]:
    return tuple(_identifier_value(t).upper() if _is_identifier_token(t) else t.normalized
                 for t in _unwrapped(tokens))


def _absence_tests(tokens: list[_SqlToken]) -> list[tuple[tuple[str, ...], bool]]:
    """Return bounded NULL/blank tests and whether true means absence.

    A predicate alone is not a substitution. The normal result must also
    return this exact expression; status/aggregate classifications stay separate.
    """
    tokens = _unwrapped(tokens)
    if not tokens:
        return []
    depth = 0
    for index, token in enumerate(tokens):
        if token.text == '(':
            depth += 1
        elif token.text == ')':
            depth -= 1
        elif not depth and token.normalized in {'AND', 'OR'}:
            return _absence_tests(tokens[:index]) + _absence_tests(tokens[index + 1:])
    if tokens[0].normalized == 'NOT':
        return [(expression, not absent) for expression, absent in _absence_tests(tokens[1:])]
    for suffix, absent in ((['IS', 'NULL'], True), (['IS', 'NOT', 'NULL'], False)):
        if len(tokens) > len(suffix) and [t.normalized for t in tokens[-len(suffix):]] == suffix:
            return [(_expression_key(tokens[:-len(suffix)]), absent)]
    depth = 0
    for index, token in enumerate(tokens):
        if token.text == '(':
            depth += 1
        elif token.text == ')':
            depth -= 1
        elif not depth and token.text in {'=', '<>', '!='}:
            left, right = _unwrapped(tokens[:index]), _unwrapped(tokens[index + 1:])
            if len(left) == 1 and left[0].normalized in {"''", "N''"}:
                left, right = right, left
            if left and len(right) == 1 and right[0].normalized in {"''", "N''"}:
                return [(_expression_key(left), token.text == '=')]
    return []


def _substitutes(guard: list[_SqlToken], yes: list[_SqlToken], no: list[_SqlToken]) -> bool:
    yes_key = _expression_key(yes)
    no_key = _expression_key(no)
    if not yes_key or not no_key:
        return False
    return any((no_key == expression and yes_key != expression) if absent else
               (yes_key == expression and no_key != expression)
               for expression, absent in _absence_tests(guard))


def _case_substitutes(tokens: list[_SqlToken], start: int) -> tuple[int | None, bool]:
    depth = 1
    markers = []
    for cursor in range(start + 1, len(tokens)):
        word = tokens[cursor].normalized if tokens[cursor].kind == 'word' else ''
        if word == 'CASE':
            depth += 1
        elif word == 'END':
            depth -= 1
            if not depth:
                # Only searched CASE is supported. Simple CASE and expressions
                # without a preserved value branch remain unverified.
                if not markers or markers[0] != (start + 1, 'WHEN'):
                    return cursor, False
                boundaries = [*markers, (cursor, 'END')]
                otherwise = []
                for position, kind in markers:
                    if kind == 'ELSE':
                        otherwise = tokens[position + 1:cursor]
                preserved, replaced = set(), set()
                for index, (position, kind) in enumerate(markers):
                    if kind == 'WHEN' and index + 2 < len(boundaries) and boundaries[index + 1][1] == 'THEN':
                        then, end = boundaries[index + 1][0], boundaries[index + 2][0]
                        guard, value = tokens[position + 1:then], tokens[then + 1:end]
                        if _substitutes(guard, value, otherwise):
                            return cursor, True
                        for expression, absent in _absence_tests(guard):
                            if not absent and _expression_key(value) == expression:
                                preserved.add(expression)
                            elif absent and value and _expression_key(value) != expression:
                                replaced.add(expression)
                if preserved & replaced:
                    return cursor, True
                return cursor, False
        elif depth == 1 and word in {'WHEN', 'THEN', 'ELSE'}:
            markers.append((cursor, word))
    return None, False


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
                commas = []
                for cursor in range(index + 2, close):
                    text = tokens[cursor].text
                    if text == '(':
                        depth += 1
                    elif text == ')':
                        depth -= 1
                    elif text == ',' and not depth:
                        commas.append(cursor)
                if len(commas) != 2 or not _substitutes(tokens[index + 2:commas[0]],
                        tokens[commas[0] + 1:commas[1]], tokens[commas[1] + 1:close]):
                    close = None
        elif form == 'CASE':
            close, absent = _case_substitutes(tokens, index)
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


def _close_paren(tokens, opening: int) -> int | None:
    depth = 0
    for position in range(opening, len(tokens)):
        if tokens[position].text == '(':
            depth += 1
        elif tokens[position].text == ')':
            depth -= 1
            if depth == 0:
                return position
    return None


def _numeric_type(tokens, start: int, stop: int) -> tuple[str, int] | None:
    """Return a NUMERIC/DECIMAL(p[,s]) type key and the index after it."""
    if start >= stop or tokens[start].normalized not in {'NUMERIC', 'DECIMAL', 'DEC'}:
        return None
    if start + 1 < stop and tokens[start + 1].text == '(':
        close = _close_paren(tokens, start + 1)
        if close is None or close >= stop:
            return None
        sizes = [t.normalized for t in tokens[start + 2:close] if t.text != ',']
        return 'NUMERIC(' + ','.join(sizes) + ')', close + 1
    return 'NUMERIC', start + 1


def _conversion(tokens, index: int) -> tuple[str, int, int, int] | None:
    """For CONVERT(type, expr[, style]) or CAST(expr AS type): (type, expr start, expr end, close)."""
    if tokens[index].normalized not in {'CONVERT', 'CAST', 'TRY_CONVERT', 'TRY_CAST'} or index + 1 >= len(tokens) or tokens[index + 1].text != '(':
        return None
    close = _close_paren(tokens, index + 1)
    if close is None:
        return None
    if tokens[index].normalized.endswith('CONVERT'):
        typed = _numeric_type(tokens, index + 2, close)
        if typed is None or typed[1] >= close or tokens[typed[1]].text != ',':
            return None
        end, depth = typed[1] + 1, 0
        while end < close and not (depth == 0 and tokens[end].text == ','):
            depth += tokens[end].text == '('
            depth -= tokens[end].text == ')'
            end += 1
        return typed[0], typed[1] + 1, end, close
    depth = 0
    for position in range(index + 2, close):
        depth += tokens[position].text == '('
        depth -= tokens[position].text == ')'
        if depth == 0 and tokens[position].normalized == 'AS':
            typed = _numeric_type(tokens, position + 1, close)
            if typed is not None and typed[1] == close:
                return typed[0], index + 2, position, close
    return None


def _procedure_name(tokens, index: int) -> tuple[str, str] | None:
    """Name executed by EXEC/EXECUTE [@status =] proc, ignoring dynamic EXEC(...)."""
    cursor = index + 1
    if cursor + 1 < len(tokens) and tokens[cursor].text.startswith('@') and tokens[cursor + 1].text == '=':
        cursor += 2
    parts: list[str] = []
    while cursor < len(tokens):
        token = tokens[cursor]
        if token.kind in {'word', 'bracket_identifier', 'quoted_identifier'} and not token.text.startswith('@') and (not parts or parts[-1] == '.'):
            parts.append(token.text)
        elif token.text == '.' and parts and parts[-1] != '.':
            parts.append('.')
        else:
            break
        cursor += 1
    names = [part.strip('[]"').upper() for part in parts if part != '.']
    return (''.join(parts), names[-1]) if names else None


def _generation_choices(source: str) -> list[tuple[str, str, int, dict[str, str]]]:
    """Observe explicit hints, backup-procedure calls, directly nested same-type
    numeric conversions and aliased empty CAST results, not their necessity."""
    tokens = [token for token in _scan_sql_tokens(source)[0]
              if token.kind not in {'line_comment', 'block_comment'}]
    findings: list[tuple[str, str, int, dict[str, str]]] = []
    for index, token in enumerate(tokens):
        if token.kind == 'word' and token.normalized in {'EXEC', 'EXECUTE'} and (called := _procedure_name(tokens, index)):
            display, last = called
            if re.search(r'_BAK(?:_|\d|$)', last):
                findings.append(('backup_procedure_call', last, token.start, {'procedure': display}))
        if token.kind == 'word' and (outer := _conversion(tokens, index)):
            target, start, end, _ = outer
            inner = _conversion(tokens, start) if start < end else None
            # Only a conversion that is the whole argument is redundant; an
            # aggregate or arithmetic over a converted value can change type.
            if inner is not None and inner[0] == target and inner[3] == end - 1:
                identity = repr([t.normalized for t in tokens[index:outer[3] + 1]])
                findings.append(('redundant_numeric_convert_review', identity, token.start, {'target_type': target}))
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
        'backup_procedure_call': 'This new call executes a backup (_BAK) procedure. Call the active procedure, or confirm that the user explicitly requested the backup copy.',
        'redundant_numeric_convert_review': 'This conversion directly wraps another conversion to the same NUMERIC/DECIMAL type. Remove the redundant wrapper unless the actual type contract differs.',
    }
    severities = {'backup_procedure_call': 'error'}
    issues: list[Issue] = []
    for code, identity, offset, details in _generation_choices(candidate):
        if previous[(code, identity)]:
            previous[(code, identity)] -= 1
            continue
        issues.append(Issue(code, severities.get(code, 'warning'), messages[code],
                            line=_review_line_number(candidate, offset), details=details))
    return issues


def check_sql(candidate: str, *, original: str | None = None, preserve_aliases: bool = False,
              check_style: bool = True, check_delta: bool = False, check_preferences: bool = True,
              compare_original: bool = True, require_procedure_header: bool = False,
              procedure_author: str | None = None, procedure_changes_only: bool = False,
              review_sp_changes: bool = False) -> CheckResult:
    comparing = original is not None and compare_original
    result = compare_sql(original, candidate, preserve_aliases=preserve_aliases) if original is not None and compare_original else CheckResult(
        checked=["SQL lexical integrity"], not_checked=["SQL Server execution", "complete T-SQL grammar and type semantics", "business equivalence to an unsupplied source"])
    result.metadata['comparison_baselines'] = {'sql': original is not None}
    result.metadata['original_comparison'] = 'formatting_preservation' if comparing else 'changed_preferences_only'
    if review_sp_changes and original is not None:
        from .change_review import review_changes
        changes = review_changes(original, candidate, explicit_pair=not procedure_changes_only)
        result.issues.extend(changes)
        result.incomplete = bool(changes) or result.incomplete
        result.metadata['sp_change_review'] = {'findings': len(changes), 'semantic_approval_verified': False}
        result.checked.append('baseline comparison of literal block guards, table writes, named calls and explicit numeric output wrappers')
        result.not_checked.append('user intent, dynamic SQL, complete control flow, SQL Server type inference and caller compatibility')
    if require_procedure_header:
        from .procedure_authorship import review_procedure_headers
        result.issues.extend(review_procedure_headers(candidate, original, author=procedure_author, changed_only=procedure_changes_only))
        result.metadata['procedure_header_scope'] = 'changed definitions' if procedure_changes_only else 'all supplied definitions'
        result.checked.append('SP AUTHOR / CREATE DATE / DESCRIPTION header structure and new-SP author selection')
        result.not_checked.append('user question/answer provenance, actual first-creation date, program title and authored-source style compliance')
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
    result.checked.append('explicit added locking hints, backup (_BAK) procedure calls, directly nested same-type NUMERIC conversions and aliased typed-empty output fields')
    result.checked.append('supported repeated enclosing/sibling scalar-mode guards with no observed mode assignment')
    result.not_checked.append('necessity of locking hints/placeholders, persisted numbering scope, save-state branches and target parameter/result contracts')
    result.not_checked.append('necessity/ownership of repeated sibling phases, jumps/loop re-entry, complex or unbraced predicates, case-sensitive parameter binding and complete mode-to-result-set behavior')
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
