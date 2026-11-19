"""User SAVE-procedure rules that are statically observable.

- Locking hints (UPDLOCK/HOLDLOCK...) are not written unless the user explicitly asks,
  including hints that already existed in the original being changed.
- Mode branches: a WORKTYPE block that writes or commits and then RETURNs, with the
  remaining modes continuing unguarded below it, and more than one COMMIT per batch.
- Count variables compared with @@ROWCOUNT or in a condition, and a scalar MAX
  variable used as the base of per-row numbering.
- Intermediate results stored in a table variable/temp table (other than parsed XML)
  and staging-table UPDATEs that assign sequence numbers.

These are lexical observations, not a T-SQL control-flow parser. They do not decide
which validation replaces a removed count check.
"""
from collections import Counter

from src.common.results import Issue, Severity
from .dispatch import _guard, _NON_BLOCK_BEGIN
from .lexer import _SqlToken, _scan_sql_tokens

LOCKING_HINTS = frozenset({'UPDLOCK', 'HOLDLOCK', 'XLOCK', 'TABLOCKX', 'SERIALIZABLE', 'REPEATABLEREAD'})
_COMPARISONS = frozenset({'=', '<>', '!=', '<', '>', '<=', '>='})
_WRITES = frozenset({'INSERT', 'UPDATE', 'DELETE', 'MERGE'})

_MESSAGES = {
    'locking_hint': (
        'Remove this locking hint. The user does not use UPDLOCK/HOLDLOCK-style hints in SAVE procedures and has '
        'repeatedly rejected them; an existing hint in the original, a reference SP that contains one, stock or '
        'numbering concurrency, or "defensive" intent is not a reason to keep or add it. Keep it only when the user '
        'explicitly asked for this hint in this task, and then pass --allow-locking-hints.'),
    'save_mode_early_exit': (
        'This mode block writes or commits and then RETURNs while the remaining modes continue below it without a '
        'mode condition. Split the procedure as IF @WORKTYPE = \'DELETE\' ... ELSE IF @WORKTYPE IN (\'NEW\', \'EDIT\') '
        'BEGIN ... IF \'NEW\' ... ELSE IF \'EDIT\' ... shared NEW/EDIT steps ... END, and COMMIT once after the branches.'),
    'save_multiple_commit': (
        'This batch commits in more than one place. Keep one COMMIT after all mode branches; error paths RAISERROR/RETURN '
        'or THROW to the CATCH rollback.'),
    'rowcount_count_variable': (
        'Do not verify a write by comparing @@ROWCOUNT with a count variable. Validate the target rows with IF EXISTS '
        '(full key, LEFT OUTER JOIN ... IS NULL, duplicate keys) before the write, then write the row set.'),
    'count_variable': (
        'Do not hold a row count in a variable for a later check. Use IF EXISTS / IF NOT EXISTS on the actual row set '
        'where the check is needed.'),
    'scalar_sequence_base': (
        'Do not keep the current MAX sequence in a variable and add it to each row. Number rows in the INSERT itself: '
        'ISNULL(C.SEQ, 0) + ROW_NUMBER() OVER (ORDER BY ...) with a LEFT OUTER JOIN to a derived MAX(...) grouped by '
        'the parent key.'),
    'intermediate_table': (
        'Do not store an intermediate query result in a table variable or temp table and read it again. Compute it in '
        'the final INSERT/UPDATE/DELETE with JOINs and derived tables. Staging parsed XML (FROM OPENXML) is the only '
        'table-variable fill; a reference SP that uses one is not a reason to add or keep it.'),
    'staging_sequence_update': (
        'Do not number rows by updating a staging table first. Assign the sequence in the INSERT itself '
        '(ISNULL(C.SEQ, 0) + ROW_NUMBER() OVER (...) with a derived MAX JOIN); later steps read the generated key '
        'from the written target rows by their business key.'),
}


def _code(source: str) -> list[_SqlToken]:
    return [t for t in _scan_sql_tokens(source)[0] if t.kind not in {'line_comment', 'block_comment'}]


def _line(source: str, offset: int) -> int:
    return source.count('\n', 0, offset) + 1


def _locking_hints(code: list[_SqlToken]) -> list[tuple[str, int]]:
    found = []
    for index, token in enumerate(code[:-1]):
        if token.kind != 'word' or token.normalized != 'WITH' or code[index + 1].text != '(':
            continue
        depth = 0
        for hint in code[index + 1:]:
            if hint.text == '(':
                depth += 1
            elif hint.text == ')':
                depth -= 1
                if not depth:
                    break
            elif depth == 1 and hint.kind == 'word' and hint.normalized in LOCKING_HINTS:
                found.append((hint.normalized, hint.start))
    return found


def _batches(code: list[_SqlToken]) -> list[list[_SqlToken]]:
    batches: list[list[_SqlToken]] = [[]]
    for token in code:
        if token.kind == 'batch_separator':
            batches.append([])
        else:
            batches[-1].append(token)
    return [batch for batch in batches if batch]


def _mode_flow(code: list[_SqlToken]) -> list[tuple[str, int, dict]]:
    found: list[tuple[str, int, dict]] = []
    for batch in _batches(code):
        commits = [t for t in batch if t.kind == 'word' and t.normalized == 'COMMIT']
        if len(commits) > 1:
            found.append(('save_multiple_commit', commits[1].start, {'commit_count': len(commits)}))
        pending: dict[int, tuple[str, int]] = {}
        # Each frame: guard (parameter, IF offset) or None, and whether it writes/commits.
        frames: list[list] = []
        for index, token in enumerate(batch):
            word = token.normalized if token.kind == 'word' else ''
            following = batch[index + 1].normalized if index + 1 < len(batch) else ''
            if word == 'IF' and (parsed := _guard(batch, index)):
                parameter, _operator, values = parsed[1].signature
                if values and all(kind in {'string', 'unicode_string'} for kind, _ in values):
                    pending[parsed[0]] = (parameter.upper(), token.start)
            elif word == 'CASE' or (word == 'BEGIN' and following not in _NON_BLOCK_BEGIN):
                frames.append([pending.pop(index, None), False])
            elif word in _WRITES or word == 'COMMIT':
                for frame in frames:
                    frame[1] = True
            elif word == 'END' and following != 'CONVERSATION' and frames:
                guard, acts = frames.pop()
                if not guard or not acts or following == 'ELSE':
                    continue
                before = index - 1
                if before >= 0 and batch[before].text == ';':
                    before -= 1
                if before < 0 or batch[before].normalized != 'RETURN':
                    continue
                rest = batch[index + 1].normalized if index + 1 < len(batch) else ''
                if rest and rest != 'END':  # Statements follow in the same enclosing block.
                    found.append(('save_mode_early_exit', guard[1], {'parameter': guard[0]}))
    return found


def _assigned_from(code: list[_SqlToken], index: int, functions: set[str]) -> bool:
    """@v = [(SELECT] [ISNULL(|COALESCE(] FUNCTION( in a SELECT/SET assignment."""
    if index + 1 >= len(code) or code[index + 1].text != '=' or not index:
        return False
    if code[index - 1].normalized not in {'SELECT', 'SET', ','}:
        return False
    cursor = index + 2
    while cursor < len(code) and (code[cursor].text == '(' or code[cursor].normalized == 'SELECT'):
        cursor += 1
    if cursor + 1 < len(code) and code[cursor].normalized in {'ISNULL', 'COALESCE'} and code[cursor + 1].text == '(':
        cursor += 2
    return (cursor + 1 < len(code) and code[cursor].normalized in functions and code[cursor + 1].text == '(')


def _variables(code: list[_SqlToken]) -> list[tuple[str, int, dict]]:
    found: list[tuple[str, int, dict]] = []
    counts: dict[str, int] = {}
    bases: dict[str, int] = {}
    compared: set[str] = set()
    sequenced: dict[str, int] = {}
    for index, token in enumerate(code):
        text = token.text
        if token.kind != 'word' or not text.startswith('@'):
            continue
        name = text.upper()
        if name == '@@ROWCOUNT':
            for other, operator in ((index + 2, index + 1), (index - 2, index - 1)):
                if 0 <= other < len(code) and code[operator].text in _COMPARISONS:
                    variable = code[other].text
                    assignment = other < index and code[operator].text == '=' and other and \
                        code[other - 1].normalized in {'SELECT', 'SET', ','}
                    if variable.startswith('@') and not variable.startswith('@@') and not assignment:
                        found.append(('rowcount_count_variable', token.start, {'variable': variable.upper()}))
                        compared.add(variable.upper())
            continue
        if name.startswith('@@'):
            continue
        if _assigned_from(code, index, {'COUNT', 'COUNT_BIG'}):
            counts.setdefault(name, token.start)
            continue
        if _assigned_from(code, index, {'MAX'}):
            bases.setdefault(name, token.start)
            continue
        before = code[index - 1].text if index else ''
        after = code[index + 1].text if index + 1 < len(code) else ''
        assignment = after == '=' and index and code[index - 1].normalized in {'SELECT', 'SET', ',', 'DECLARE'}
        if not assignment and (after in _COMPARISONS or before in _COMPARISONS):
            compared.add(name)
        if name in bases and (after == '+' and index + 2 < len(code) or before == '+' and index >= 2):
            other = code[index + 2] if after == '+' else code[index - 2]
            if other.kind == 'word' and not other.text.startswith('@') and other.normalized not in {'NULL'}:
                sequenced.setdefault(name, token.start)
    for name, offset in counts.items():
        if name in compared:
            found.append(('count_variable', offset, {'variable': name}))
    for name, offset in bases.items():
        if name in sequenced:
            found.append(('scalar_sequence_base', offset, {'variable': name, 'use_offset': sequenced[name]}))
    return found


def _local_table(name: str) -> bool:
    return name.startswith(('@', '#')) and not name.startswith('@@')


def _staging(code: list[_SqlToken]) -> list[tuple[str, int, dict]]:
    """INSERT/SELECT INTO a table variable or temp table from a query other than OPENXML,
    and an UPDATE of one that assigns ROW_NUMBER/MAX numbering."""
    from .change_review import _statement_end
    found: list[tuple[str, int, dict]] = []
    for index, token in enumerate(code):
        word = token.normalized if token.kind == 'word' else ''
        if word == 'INSERT':
            target = index + 1
            if target < len(code) and code[target].normalized == 'INTO':
                target += 1
            if target >= len(code) or not _local_table(code[target].text):
                continue
            end = _statement_end(code, index)
            body = {t.normalized for t in code[index:end] if t.kind == 'word'}
            if 'FROM' in body and 'OPENXML' not in body:
                found.append(('intermediate_table', token.start, {'table': code[target].text.upper()}))
        elif word == 'INTO' and index + 1 < len(code) and code[index + 1].text.startswith('#'):
            command = next((c.normalized for c in reversed(code[:index]) if c.depth == token.depth and c.normalized in
                            {'SELECT', 'INSERT', 'MERGE', 'UPDATE', 'DELETE', 'OUTPUT', 'FETCH', 'EXEC', ';'}), '')
            if command == 'SELECT':
                found.append(('intermediate_table', token.start, {'table': code[index + 1].text.upper()}))
        elif word == 'UPDATE' and index + 1 < len(code):
            end = _statement_end(code, index)
            statement = code[index:end]
            target = code[index + 1].text
            alias = code[index + 1].normalized
            local = target if _local_table(target) else next((
                t.text for j, t in enumerate(statement) if _local_table(t.text) and (
                    j + 1 < len(statement) and statement[j + 1].normalized == alias or
                    j + 2 < len(statement) and statement[j + 1].normalized == 'AS' and statement[j + 2].normalized == alias)), '')
            numbering = any(t.normalized in {'ROW_NUMBER', 'MAX'} for t in statement if t.kind == 'word')
            if local and numbering:
                found.append(('staging_sequence_update', token.start, {'table': local.upper()}))
    return found


def review_save_rules(candidate: str, original: str | None = None, *, enforce: bool = True,
                      allow_locking_hints: bool = False, personal_rules: bool = True) -> list[Issue]:
    """Report every occurrence in the candidate, including ones carried over from the original.

    enforce: a logic change or new SQL (error); False for formatting-only preservation (info).
    personal_rules: False under the project style policy, which reports added locking hints only.
    """
    code = _code(candidate)
    issues: list[Issue] = []
    previous = Counter(hint for hint, _ in _locking_hints(_code(original or '')))
    for hint, offset in _locking_hints(code):
        retained = previous[hint] > 0
        if retained:
            previous[hint] -= 1
        if not personal_rules:
            if not retained:
                issues.append(Issue('locking_hint', 'warning', _MESSAGES['locking_hint'], line=_line(candidate, offset),
                                    details={'hint': hint, 'origin': 'added'}))
            continue
        severity: Severity = 'info' if allow_locking_hints or not enforce else 'error'
        issues.append(Issue('locking_hint', severity, _MESSAGES['locking_hint'], line=_line(candidate, offset),
                            details={'hint': hint, 'origin': 'retained' if retained else 'added' if original is not None else 'present',
                                     **({'allowed_by': '--allow-locking-hints'} if allow_locking_hints else {})}))
    if not personal_rules:
        return issues
    severity = 'error' if enforce else 'info'
    for code_name, offset, details in sorted(_mode_flow(code) + _variables(code) + _staging(code), key=lambda item: item[1]):
        if 'use_offset' in details:
            details = {key: value for key, value in details.items() if key != 'use_offset'} | {
                'use_line': _line(candidate, details['use_offset'])}
        issues.append(Issue(code_name, severity, _MESSAGES[code_name], line=_line(candidate, offset), details=details))
    return issues
