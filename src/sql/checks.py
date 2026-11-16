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
        'locking_hint_review': 'Review this added locking hint against the actual target concurrency and transaction contract. Do not add UPDLOCK/HOLDLOCK routine…1545 tokens truncated… NULL, duplicate and multi-row behavior. Do not substitute a variable or rewrite automatically.',
                line=_review_line_number(candidate, offset), details={'clause': clause}))
        result.checked.append('recognizable statement-level CTE declarations, SELECT-list/scalar-WHERE queries and WHERE EXISTS/NOT EXISTS/IN query counts')
        result.not_checked.append('CTE and subquery necessity, general clause grammar and JOIN-rewrite equivalence')
    result.issues.extend(_review_generation_choices(candidate, original))
    result.issues.extend(review_dispatch(candidate, original))
    result.issues.extend(_review_xml_boundary(candidate, original))
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
