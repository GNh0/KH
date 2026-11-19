"""Compare observable changes to an existing procedure with its original definition."""
from collections import Counter
from dataclasses import dataclass

from src.common.results import Issue
from .delta import _identifier_path_at
from .dispatch import _guard, _NON_BLOCK_BEGIN
from .lexer import _identifier_value, _is_identifier_token, _scan_sql_tokens, _SqlToken
from .procedure_authorship import procedure_headers, table_writes


# (parameter, compared literals, negated). A negated label is an ELSE arm or the
# code that follows a mode block ending in RETURN.
_Label = tuple[str, frozenset[str], bool]


@dataclass(frozen=True)
class Observation:
    kind: str
    name: str
    guards: tuple[str, ...]
    offset: int

    def key(self) -> tuple:
        return self.kind, self.name, self.guards


@dataclass(frozen=True)
class _RawObservation:
    kind: str
    name: str
    scope: tuple[_Label, ...]
    offset: int
    excluded: frozenset[str] = frozenset()


def _effective(scope: tuple[_Label, ...], domains: dict[str, frozenset[str]]) -> tuple[str, ...]:
    """Resolve nested and ELSE/early-return mode labels to the modes that reach a statement.

    A negation is resolved only against a mode set the procedure itself closes
    (for example IF ISNULL(@MODE, '') NOT IN (...) RETURN); otherwise it stays
    an ELSE label, so an unlisted mode is never assumed away.
    """
    positive: dict[str, frozenset[str]] = {}
    negative: dict[str, frozenset[str]] = {}
    for parameter, values, negated in scope:
        if negated:
            negative[parameter] = negative.get(parameter, frozenset()) | values
        else:
            positive[parameter] = positive[parameter] & values if parameter in positive else values
    result = []
    for parameter in sorted(set(positive) | set(negative)):
        excluded = negative.get(parameter, frozenset())
        allowed = positive.get(parameter, domains.get(parameter))
        if allowed is not None:
            result.append(parameter + ' IN (' + ', '.join(sorted(allowed - excluded)) + ')')
        else:
            result.append('ELSE (' + parameter + ' IN (' + ', '.join(sorted(excluded)) + '))')
    return tuple(result)


def _closed_domains(code: list[_SqlToken], parameters: set[str]) -> dict[str, frozenset[str]]:
    """Mode sets closed by IF [ISNULL(]@P[, '')] NOT IN (...) followed by an error/return block."""
    found: dict[str, frozenset[str]] = {}
    for i, token in enumerate(code):
        if token.normalized != 'IF':
            continue
        cursor = i + 1
        wrapped = cursor + 1 < len(code) and code[cursor].normalized in {'ISNULL', 'COALESCE'} and code[cursor + 1].text == '('
        if wrapped:
            cursor += 2
        if cursor >= len(code) or code[cursor].normalized not in parameters:
            continue
        parameter = code[cursor].normalized
        cursor += 1
        if wrapped:
            while cursor < len(code) and code[cursor].text != ')':
                cursor += 1
            cursor += 1
        if (cursor + 2 >= len(code) or code[cursor].normalized != 'NOT' or code[cursor + 1].normalized != 'IN'
                or code[cursor + 2].text != '('):
            continue
        cursor += 3
        values: set[str] = set()
        while cursor < len(code) and code[cursor].text != ')':
            if code[cursor].kind in {'string', 'unicode_string', 'number'}:
                values.add(code[cursor].normalized)
            elif code[cursor].text != ',':
                values = set()
                break
            cursor += 1
        rejects = any(t.normalized in {'RETURN', 'RAISERROR', 'THROW'} for t in code[cursor + 1:cursor + 12])
        if values and rejects:
            found[parameter] = found.get(parameter, frozenset()) | frozenset(values)
    return found


def _ends_with_return(code: list[_SqlToken], end: int) -> bool:
    before = end - 1
    if before >= 0 and code[before].text == ';':
        before -= 1
    return before >= 0 and code[before].normalized == 'RETURN'


def _statement_end(code: list[_SqlToken], start: int) -> int:
    """Exclusive end of a recognized mode arm, including the nearest nested ELSE."""
    if code[start].normalized == 'IF' and (guard := _guard(code, start, allow_statement=True)):
        end = _statement_end(code, guard[0])
        if end + 1 < len(code) and code[end].normalized == 'ELSE':
            end = _statement_end(code, end + 1)
        return end
    blocks = 0
    braced = code[start].normalized == 'BEGIN'
    verb = code[start].normalized
    insert_source = verb == 'INSERT'
    update_set = verb == 'UPDATE'
    for i in range(start, len(code)):
        token = code[i]
        if token.depth != code[start].depth:
            continue
        word = token.normalized
        following = code[i + 1].normalized if i + 1 < len(code) else ''
        if word == 'CASE' or word == 'BEGIN' and following not in _NON_BLOCK_BEGIN:
            blocks += 1
        elif word == 'END' and following != 'CONVERSATION':
            if not blocks:
                return i
            blocks -= 1
            if not blocks and braced:
                return i + 1
        elif not blocks and i > start:
            if word == ';':
                return i + 1
            if word in {'ELSE', 'IF', 'RETURN', 'PRINT', 'THROW', 'EXEC', 'EXECUTE'}:
                return i
            if word == 'SET' and update_set:
                update_set = False
            elif word == 'SELECT' and (insert_source or code[i - 1].normalized in {'UNION', 'INTERSECT', 'EXCEPT'}
                                       or i >= 2 and code[i - 2].normalized == 'UNION' and code[i - 1].normalized == 'ALL'):
                insert_source = False
            elif verb != 'MERGE' and word in {'SELECT', 'SET', 'INSERT', 'UPDATE', 'DELETE', 'MERGE', 'DECLARE'}:
                return i
    return len(code)


def _operations(tokens: list[_SqlToken], parameters: set[str]) -> tuple[
        list[_RawObservation], dict[int, tuple[_Label, ...]], dict[str, frozenset[str]]]:
    writes = {token.start: (token.normalized, table) for token, table in table_writes(tokens)}
    code = [t for t in tokens if t.kind not in {'line_comment', 'block_comment'}]
    pending: dict[int, _Label] = {}
    single_arms: dict[int, list[tuple[int, _Label]]] = {}
    active_arms: list[tuple[int, _Label]] = []
    stack: list[_Label | None] = []
    implied: list[list[_Label]] = [[]]  # Labels implied by an earlier mode block ending in RETURN.
    found: list[_RawObservation] = []
    contexts: dict[int, tuple[_Label, ...]] = {}

    def enclosing() -> tuple[_Label, ...]:
        return tuple(label for label in stack if label) + tuple(label for frame in implied for label in frame)

    for i, t in enumerate(code):
        word = t.normalized
        following = code[i + 1].normalized if i + 1 < len(code) else ''
        active_arms = [arm for arm in active_arms if i < arm[0]]
        active_arms.extend(single_arms.pop(i, ()))
        scope = enclosing() + tuple(label for _end, label in active_arms)
        contexts[t.start] = scope
        if word == 'IF' and (parsed := _guard(code, i, allow_statement=True)):
            start, guard = parsed
            parameter, _operator, values = guard.signature
            if parameter.upper() not in parameters:
                continue
            literals = [literal for _kind, literal in values]
            for literal in literals:
                found.append(_RawObservation('branch', parameter.upper() + ' = ' + literal, scope, t.start))
            label: _Label = (parameter.upper(), frozenset(literals), False)
            if code[start].normalized == 'BEGIN':
                pending[start] = label
            else:
                end = _statement_end(code, start)
                single_arms.setdefault(start, []).append((end, label))
                if end + 1 < len(code) and code[end].normalized == 'ELSE' and code[end + 1].normalized != 'IF':
                    single_arms.setdefault(end + 1, []).append((_statement_end(code, end + 1), (label[0], label[1], True)))
        elif word == 'CASE' or (word == 'BEGIN' and following not in _NON_BLOCK_BEGIN):
            stack.append(pending.get(i))
            implied.append([])
        elif word == 'END' and following != 'CONVERSATION' and stack:
            ended = stack.pop()
            implied.pop()
            if ended and following == 'ELSE' and i + 2 < len(code):
                other: _Label = (ended[0], ended[1], not ended[2])
                if code[i + 2].normalized == 'BEGIN':
                    pending[i + 2] = other
                elif code[i + 2].normalized != 'IF':
                    single_arms.setdefault(i + 2, []).append((_statement_end(code, i + 2), other))
            elif ended and _ends_with_return(code, i):
                # The rest of the enclosing block runs only for the other modes.
                found.append(_RawObservation('implied-branch', ended[0], enclosing(), t.start,
                                             frozenset() if ended[2] else ended[1]))
                implied[-1].append((ended[0], ended[1], not ended[2]))
        elif t.start in writes:
            op, table = writes[t.start]
            found.append(_RawObservation('write', op + ' ' + table, scope, t.start))
        elif word == 'INTO' and not t.depth:
            # A SELECT INTO creates a table. INSERT/MERGE INTO already has its own event.
            command = next((c.normalized for c in reversed(code[:i]) if c.depth == 0 and c.normalized in
                            {'SELECT', 'INSERT', 'MERGE', 'UPDATE', 'DELETE', 'OUTPUT', 'FETCH', 'EXEC', ';'}), '')
            name, _last = _identifier_path_at(code, i + 1, len(code))
            if command == 'SELECT' and name and not name.split('.')[-1].startswith(('#', '@')):
                found.append(_RawObservation('write', 'SELECT INTO ' + name, scope, t.start))
        elif word in {'EXEC', 'EXECUTE'}:
            pos = i + 1
            if pos + 1 < len(code) and code[pos].text.startswith('@') and code[pos + 1].text == '=':
                pos += 2
            name, _last = _identifier_path_at(code, pos, len(code))
            if name and not name.startswith('@'):
                found.append(_RawObservation('call', name, scope, t.start))
    return found, contexts, _closed_domains(code, parameters)


def _resolve(raw: list[_RawObservation], domains: dict[str, frozenset[str]]) -> list[Observation]:
    """Express observations by the modes that reach them, so moving the code after an
    early-return mode block into the matching ELSE IF arm is not a changed operation."""
    result = []
    for item in raw:
        guards = _effective(item.scope, domains)
        if item.kind != 'implied-branch':
            result.append(Observation(item.kind, item.name, guards, item.offset))
        elif item.name in domains and item.excluded:
            for literal in sorted(domains[item.name] - item.excluded):
                result.append(Observation('branch', item.name + ' = ' + literal, guards, item.offset))
    return result


def _projections(tokens: list[_SqlToken]) -> list[tuple]:
    """Recognize explicit AS aliases and outer fixed-point casts on the same expression."""
    code = [t for t in tokens if t.kind not in {'line_comment', 'block_comment'}]
    found = []
    for i, token in enumerate(code[:-1]):
        if token.normalized != 'AS' or not _is_identifier_token(code[i + 1]):
            continue
        begin = i - 1
        while begin >= 0 and (code[begin].depth > token.depth or code[begin].depth == token.depth
                               and code[begin].normalized not in {',', 'SELECT', 'FROM', 'AS', ';'}):
            begin -= 1
        if begin < 0 or code[begin].normalized not in {'SELECT', ','}:
            continue
        expr = code[begin + 1:i]
        if not expr:
            continue
        offset = expr[0].start
        target_type = ''
        if len(expr) > 5 and expr[0].normalized in {'CONVERT', 'CAST'} and expr[1].text == '(' and expr[-1].text == ')':
            is_cast = expr[0].normalized == 'CAST'
            split = next((j for j,t in enumerate(expr[2:-1], 2)
                          if t.depth == token.depth + 1 and t.normalized == ('AS' if is_cast else ',')), None)
            if split is not None:
                dtype = expr[split + 1:-1] if is_cast else expr[2:split]
                if dtype and dtype[0].normalized in {'DECIMAL', 'NUMERIC'}:
                    target_type = ''.join(t.normalized for t in dtype)
                    expr = expr[2:split] if is_cast else expr[split + 1:-1]
        key = (_identifier_value(code[i + 1]), tuple(t.normalized for t in expr))
        found.append((key, target_type, offset))
    return found


def review_changes(original: str, candidate: str, *, explicit_pair: bool = False) -> list[Issue]:
    def units(source: str) -> dict:
        lines = source.splitlines(keepends=True)
        result = {}
        for h in procedure_headers(source):
            signature = source[len(''.join(lines[:h.line - 1])):h.body_start]
            parameters = {t.normalized for t in _scan_sql_tokens(signature)[0]
                          if t.kind == 'word' and t.text.startswith('@') and not t.text.startswith('@@')}
            result[h.parts] = h, ''.join(lines[:h.unit_end])[h.body_start:], parameters
        return result

    prior, current = units(original), units(candidate)
    issues = []
    if not prior or prior.keys() != current.keys():
        issues.append(Issue('sp_definition_scope_review', 'warning',
                            'Verify the original and candidate procedure identities and any requested addition, removal or rename.'))
    if explicit_pair and len(prior) == len(current) == 1 and prior.keys() != current.keys():
        # The CLI caller explicitly supplied both definitions, e.g. a named backup.
        prior = {next(iter(current)): next(iter(prior.values()))}
    for ident in sorted(prior.keys() & current.keys()):
        header, body, params = current[ident]
        old_header, old_body, old_params = prior[ident]
        if not old_header.body_observed or not header.body_observed:
            issues.append(Issue('sp_definition_scope_review', 'warning',
                f'{header.name}: retrieve the complete original and candidate procedure bodies before comparing them.'))
            continue
        if body == old_body:
            continue
        old_tokens = _scan_sql_tokens(old_body)[0]
        new_tokens = _scan_sql_tokens(body)[0]
        old_raw, old_contexts, old_domains = _operations(old_tokens, old_params)
        new_raw, new_contexts, new_domains = _operations(new_tokens, params)
        domains = {name: old_domains.get(name, frozenset()) | new_domains.get(name, frozenset())
                   for name in set(old_domains) | set(new_domains)}
        old_ops, new_ops = _resolve(old_raw, domains), _resolve(new_raw, domains)
        old_scopes = {offset: _effective(scope, domains) for offset, scope in old_contexts.items()}
        new_scopes = {offset: _effective(scope, domains) for offset, scope in new_contexts.items()}
        counts = Counter(op.key() for op in old_ops)
        for op in new_ops:
            if counts[op.key()]:
                counts[op.key()] -= 1
                continue
            context = ', '.join(op.guards) or 'outside recognized dispatch blocks'
            previous = sorted({', '.join(item.guards) or 'outside recognized dispatch blocks' for item in old_ops
                               if (item.kind, item.name) == (op.kind, op.name)})
            prior_location = '; original: ' + ' / '.join(previous) if previous else ''
            issues.append(Issue('sp_operation_change_review', 'warning',
                f'{header.name}: {op.kind} {op.name} in {context}{prior_location}. Verify that the requested operation needs this change.',
                line=candidate.count('\n', 0, header.body_start + op.offset) + 1,
                details={'procedure': header.name, 'operation': op.kind, 'name': op.name, 'guards': list(op.guards)}))
        old_types = {}
        old_counts = Counter()
        for key, dtype, offset in _projections(old_tokens):
            old_types.setdefault(key, set()).add(dtype or 'original expression')
            old_counts[key, dtype, old_scopes[offset]] += 1
        for key, dtype, offset in _projections(new_tokens):
            identity = key, dtype, new_scopes[offset]
            if old_counts[identity]:
                old_counts[identity] -= 1
            elif dtype and key in old_types:
                previous_types = ', '.join(sorted(old_types[key]))
                issues.append(Issue('sp_output_type_change_review', 'warning',
                    f'{header.name}: {key[0]} now uses {dtype} here; original form(s): {previous_types}. Verify the required result type and consuming contract.',
                    line=candidate.count('\n', 0, header.body_start + offset) + 1,
                    details={'procedure': header.name, 'column': key[0], 'target_type': dtype}))
    return issues
