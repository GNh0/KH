"""User SAVE-procedure rules that are statically observable.

- Locking hints (UPDLOCK/HOLDLOCK...) are not written unless the user explicitly asks,
  including hints that already existed in the original being changed.
- Mode branches: a WORKTYPE block that writes or commits and then RETURNs, with the
  remaining modes continuing unguarded below it, and more than one COMMIT per batch.
- Count variables compared with @@ROWCOUNT or in a condition, and a scalar MAX
  variable used as the base of per-row numbering.
- Intermediate results stored in a table variable/temp table (other than parsed XML)
  and staging-table UPDATEs that assign sequence numbers.
- Variables beyond the necessary ones: never read, or assigned once and read once
  outside an EXEC/RAISERROR argument.
- Row-by-row loops that write a table with a nested loop, TOP 1 variable fetching or
  several loop variables, and shared steps copied into two mode branches.

These are lexical observations, not a T-SQL control-flow parser. They do not decide
which validation replaces a removed count check.
"""
from collections import Counter
from dataclasses import dataclass, field

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
    'row_by_row_loop': (
        'This loop writes a table one row at a time (nested loop, SELECT TOP 1 @variable fetching or several loop '
        'variables). Write the rows with one set-based statement: JOIN the requested rows to derived running totals '
        'and INSERT the overlaps (see the SAVE allocation example). Use a loop only when the work cannot be '
        'expressed as a set, and say why.'),
    'duplicated_mode_code': (
        'The same statements appear in two mode branches. Put the shared NEW/EDIT steps once after the mode-specific '
        'parts, inside ELSE IF @WORKTYPE IN (\'NEW\', \'EDIT\').'),
    'insert_long_value_not_last': (
        'This long INSERT column or SELECT value is not the last item on its line, so every other row of the column '
        'is padded to its width. Break the line before it: put it at the end of its line or on its own line, and break '
        'the INSERT column list at the same position. Do not pad the other columns to a long value.'),
    'unused_variable': (
        'This variable is declared or assigned but never read. Remove it.'),
    'single_use_variable': (
        'This variable is assigned once and read once. Use the expression, or JOIN the staging/target row it was read '
        'from, at that place. Keep variables only where T-SQL needs one: an OUTPUT argument (key procedure, XML '
        'handle), an EXEC/RAISERROR argument, a value captured at one moment (@@TRANCOUNT), or a value such as a '
        'generated document number that several statements use.'),
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
        elif word == 'OUTPUT' and index + 1 < len(code) and code[index + 1].normalized in {'INSERTED', 'DELETED', '$ACTION'}:
            into = next((j for j in range(index + 1, len(code)) if code[j].depth == token.depth and (
                code[j].normalized == 'INTO' or code[j].normalized in _STATEMENT_STARTS)), None)
            if into is not None and code[into].normalized == 'INTO' and into + 1 < len(code) and _local_table(code[into + 1].text):
                found.append(('intermediate_table', token.start, {'table': code[into + 1].text.upper(), 'form': 'OUTPUT INTO'}))
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


_STATEMENT_STARTS = frozenset({'SELECT', 'SET', 'IF', 'BEGIN', 'END', 'EXEC', 'EXECUTE', 'INSERT', 'UPDATE', 'DELETE',
                               'MERGE', 'DECLARE', 'WHILE', 'RETURN', 'RAISERROR', 'THROW', 'PRINT', 'WITH', ';'})
_CAPTURES = frozenset({'@@ROWCOUNT', '@@TRANCOUNT', '@@ERROR', '@@IDENTITY', '@@PROCID', 'SCOPE_IDENTITY',
                       'ERROR_MESSAGE', 'ERROR_NUMBER', 'ERROR_SEVERITY', 'ERROR_STATE', 'GETDATE', 'SYSDATETIME', 'NEWID'})


@dataclass
class _Usage:
    declared: int
    reads: list[int] = field(default_factory=list)
    writes: list[str] = field(default_factory=list)  # 'value', 'output' or 'capture'
    fixed_reads: int = 0  # Reads where T-SQL needs a variable or literal (EXEC/RAISERROR arguments).


def _write_kind(code: list[_SqlToken], index: int) -> str:
    """'value' for SET/SELECT/DECLARE assignment; 'capture' when the value is a moment-dependent function."""
    cursor = index + 2
    while cursor < len(code) and (code[cursor].text == '(' or code[cursor].normalized == 'SELECT'):
        cursor += 1
    return 'capture' if cursor < len(code) and code[cursor].normalized in _CAPTURES else 'value'


def _variable_usage(code: list[_SqlToken]) -> dict[str, _Usage]:
    usage: dict[str, _Usage] = {}
    declaring = False
    fixed_args = False  # EXEC/RAISERROR/THROW arguments accept a variable or literal, not an expression.
    for index, token in enumerate(code):
        word = token.normalized if token.kind == 'word' else token.text
        if token.depth == 0 and word in _STATEMENT_STARTS:
            declaring = word == 'DECLARE'
            fixed_args = word in {'EXEC', 'EXECUTE', 'RAISERROR', 'THROW'}
        if token.kind != 'word' or not token.text.startswith('@') or token.text.startswith('@@'):
            continue
        name = token.text.upper()
        previous = code[index - 1].normalized if index else ''
        following = code[index + 1].normalized if index + 1 < len(code) else ''
        if declaring and previous in {'DECLARE', ','} and token.depth == 0:
            if following in {'TABLE', 'CURSOR', 'AS'}:
                declaring = following != 'TABLE' and declaring
                continue
            usage[name] = _Usage(token.start)
            cursor = index + 1  # DECLARE @V TYPE[(n)] = value
            while cursor < len(code) and not (code[cursor].depth == token.depth and code[cursor].text in {'=', ','})                     and code[cursor].normalized not in _STATEMENT_STARTS:
                cursor += 1
            if cursor < len(code) and code[cursor].text == '=':
                usage[name].writes.append(_write_kind(code, cursor - 1))
            continue
        item = usage.get(name)
        if item is None:
            continue  # Parameters and undeclared names.
        if following in {'OUTPUT', 'OUT'} or (previous in {'EXEC', 'EXECUTE'} and following == '=') or previous == 'INTO':
            item.writes.append('output')
        elif following in {'=', '+=', '-=', '*=', '/='} and previous in {'SET', 'SELECT', ','}:
            item.writes.append(_write_kind(code, index))
            if following != '=':
                item.reads.append(token.start)
        else:
            item.reads.append(token.start)
            if fixed_args:
                item.fixed_reads += 1
    return usage


def _minimal_variables(code: list[_SqlToken], reported: set[str]) -> list[tuple[str, int, dict]]:
    found: list[tuple[str, int, dict]] = []
    loops = any(t.normalized in {'WHILE', 'CURSOR', 'GOTO'} for t in code if t.kind == 'word')  # Re-reads.
    for name, item in _variable_usage(code).items():
        if name in reported:
            continue
        if not item.reads:
            if not item.writes or 'output' not in item.writes:  # A callee's OUTPUT argument needs a variable.
                found.append(('unused_variable', item.declared, {'variable': name}))
        elif (not loops and len(item.reads) == 1 and item.writes == ['value'] and not item.fixed_reads):
            found.append(('single_use_variable', item.declared, {'variable': name, 'use_offset': item.reads[0]}))
    return found


def _block_end(code: list[_SqlToken], begin: int) -> int:
    """Index of the END that closes the BEGIN at code[begin] (len(code) when unclosed)."""
    blocks = 0
    for index in range(begin, len(code)):
        word = code[index].normalized if code[index].kind == 'word' else ''
        following = code[index + 1].normalized if index + 1 < len(code) else ''
        if word == 'CASE' or (word == 'BEGIN' and following not in _NON_BLOCK_BEGIN):
            blocks += 1
        elif word == 'END' and following != 'CONVERSATION':
            blocks -= 1
            if not blocks:
                return index
    return len(code)


def _loop_bodies(code: list[_SqlToken]) -> list[tuple[int, int, int]]:
    """(WHILE index, body start, body end) for WHILE ... BEGIN ... END loops."""
    loops = []
    for index, token in enumerate(code):
        if token.kind != 'word' or token.normalized != 'WHILE':
            continue
        begin = next((j for j in range(index + 1, len(code)) if code[j].depth == token.depth
                      and code[j].normalized in {'BEGIN'} | _STATEMENT_STARTS - {'SELECT'}), None)
        if begin is not None and code[begin].normalized == 'BEGIN':
            loops.append((index, begin, _block_end(code, begin)))
    return loops


def _row_loops(code: list[_SqlToken], real_writes: set[int]) -> list[tuple[str, int, dict]]:
    """A WHILE/cursor loop that writes a real table one row at a time with a nested loop,
    SELECT TOP 1 @variable fetching or several loop variables. A plain retry or batch loop is not reported."""
    found: list[tuple[str, int, dict]] = []
    covered = -1
    for start, begin, end in _loop_bodies(code):
        if start < covered:
            continue  # Inside a loop already reported.
        body = code[begin:end]
        writes = sum(t.start in real_writes for t in body)
        nested = sum(t.kind == 'word' and t.normalized == 'WHILE' for t in body)
        top_one = 0
        assigned: set[str] = set()
        fetching = False
        for j, t in enumerate(body):
            if t.kind == 'word' and t.normalized in _STATEMENT_STARTS | {'FETCH'}:
                fetching = t.normalized == 'FETCH'
            if fetching and t.text.startswith('@') and j and body[j - 1].normalized in {'INTO', ','}:
                assigned.add(t.text.upper())  # FETCH ... INTO @A, @B
            if t.kind == 'word' and t.normalized == 'TOP':
                k = j + 1
                wrapped = k < len(body) and body[k].text == '('
                k += wrapped
                if k < len(body) and body[k].text == '1':
                    k += 1 + wrapped
                    if k + 1 < len(body) and body[k].text.startswith('@') and body[k + 1].text == '=':
                        top_one += 1
                        assigned.add(body[k].text.upper())
            if t.kind == 'word' and t.text.startswith('@') and not t.text.startswith('@@') and j + 1 < len(body):
                previous = body[j - 1].normalized if j else ''
                if body[j + 1].text in {'=', '+=', '-='} and previous in {'SET', 'SELECT', ','} or previous == 'INTO':
                    assigned.add(t.text.upper())
        if writes and (nested or top_one or len(assigned) >= 3):
            found.append(('row_by_row_loop', code[start].start,
                          {'nested_loops': nested, 'top_1_assignments': top_one, 'loop_variables': sorted(assigned)}))
            covered = end
    return found


def _duplicated_branches(code: list[_SqlToken], size: int = 200) -> list[tuple[str, int, dict]]:
    """The same run of `size` tokens in two sibling branches of one mode parameter.

    Author-written SAVE SPs share at most about 110 consecutive tokens between NEW and EDIT
    (similar INSERT column lists); a copied block of shared steps is far longer."""
    blocks = []
    for index, token in enumerate(code):
        if token.kind == 'word' and token.normalized == 'IF' and (parsed := _guard(code, index)):
            parameter, _operator, values = parsed[1].signature
            if code[parsed[0]].normalized == 'BEGIN':
                blocks.append((parameter.upper(), frozenset(v for _, v in values), parsed[0], _block_end(code, parsed[0])))
    found: list[tuple[str, int, dict]] = []
    keys = [t.normalized for t in code]
    for i, (parameter, values, begin, end) in enumerate(blocks):
        windows = {tuple(keys[k:k + size]): k for k in range(begin + 1, end - size + 1)}
        for other, other_values, other_begin, other_end in blocks[i + 1:]:
            if other != parameter or values & other_values or other_begin < end:
                continue  # Same parameter, other modes, not nested.
            match = next(((k, windows[tuple(keys[k:k + size])]) for k in range(other_begin + 1, other_end - size + 1)
                          if tuple(keys[k:k + size]) in windows), None)
            if match:
                found.append(('duplicated_mode_code', code[match[0]].start,
                              {'parameter': parameter, 'first_offset': code[match[1]].start}))
    return found


LONG_INSERT_VALUE = 30


def _long_insert_values(sql: str) -> list[tuple[str, int, dict]]:
    """An INSERT column or SELECT/VALUES value of LONG_INSERT_VALUE+ columns that is not the last item
    on its line forces every other row of that column to be padded; it belongs at the end of a line."""
    from .layout import _extract_insert_select_ranges
    from .insert_alignment import _cells, _rows, _text_columns
    found: list[tuple[str, int, dict]] = []
    for target_start, target_end, select_start, select_end in _extract_insert_select_ranges(sql):
        for start, end, select in ((target_start, target_end, False), (select_start, select_end, True)):
            cells, _prefix, _reason = _cells(sql, start, end, select=select)
            for row in _rows(sql, cells):
                for cell in row[:-1]:
                    text = sql[cell.start:cell.end]
                    width = max(_text_columns(line) for line in text.split('\n'))
                    if width >= LONG_INSERT_VALUE:
                        found.append(('insert_long_value_not_last', cell.start, {'width': width, 'value': text[:80]}))
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
    variables = _variables(code)
    reported = {details['variable'] for _, _, details in variables if 'variable' in details}
    from .procedure_authorship import table_writes
    real_writes = {token.start for token, _table in table_writes(_scan_sql_tokens(candidate)[0])}
    for code_name, offset, details in sorted(_mode_flow(code) + variables + _staging(code) + _minimal_variables(code, reported)
                                             + _row_loops(code, real_writes) + _duplicated_branches(code),
                                             key=lambda item: item[1]):
        for key in ('use_offset', 'first_offset'):
            if key in details:
                details = {name: value for name, value in details.items() if name != key} | {
                    key.replace('_offset', '_line'): _line(candidate, details[key])}
        issues.append(Issue(code_name, severity, _MESSAGES[code_name], line=_line(candidate, offset), details=details))
    # Layout only: a formatting request must fix it too.
    layout = candidate.replace('\r\n', '\n')
    for code_name, offset, details in _long_insert_values(layout):
        issues.append(Issue(code_name, 'error', _MESSAGES[code_name], line=_line(layout, offset), details=details))
    return issues
