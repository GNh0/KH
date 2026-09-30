"""Review new UI/data-flow choices; findings are not semantic rejection rules."""
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re

from src.common.results import Issue
from .control_defaults import _same_type, read_control_defaults
from .control_names import known_control_kind
from .control_style import direct_statement_spans
from .lexer import _scan_csharp, balanced_close, string_literal_value
from .source import _method_declaration_matches, _target_local_method_inventory
from .syntax import parameter_constructor_sites


@dataclass(frozen=True)
class _Finding:
    code: str
    method: str
    evidence: str
    offset: int


_MESSAGES = {
    'new_ui_data_helper': 'Review this new UI/data helper against the target project. Keep established event and save boundaries; shorter or shared code alone does not justify a new wrapper.',
    'entry_query_review': 'A new query runs on NEW/EDIT entry. Trace whether the target already has the header, detail and schema. Preserve existing data; reuse the actual initialization path when appropriate.',
    'save_gate_review': 'Review this new save-blocking condition against the requested behavior and existing UI/XML/SP validation. Do not invent a business restriction or duplicate confirmation.',
    'manual_selected_row_delete': 'Review this selected-row deletion loop against the actual grid deletion API, such as DeleteSelectedRows. Preserve selection semantics, row states and required per-row effects.',
    'client_sequence_review': 'Review this client-side maximum/row-version calculation against sequence ownership in the actual save procedure. Do not duplicate server-owned numbering.',
    'row_header_propagation_review': 'Review this new header/context assignment to a new detail row against XML/SP field ownership. Assign only fields the target detail contract requires.',
    'date_helper_review': 'The supplied target control exposes SetToDay(int), or this member already uses it. Prefer that existing date API when it matches the requested initialization; inspect intentional semantic differences.',
    'ui_state_policy_review': 'A screen boolean field controls editing, action availability or an event gate. Compare its declaration, reset, assignment and uses with the actual source and request. Do not introduce or broaden a business restriction as a style change.',
    'save_worktype_literal_review': 'A save boundary supplies a literal WORKTYPE. Follow the actual target edit-mode API and matching SP branches; retain a fixed operation only when that operation is required by the current contract.',
    'manual_original_row_comparison_review': 'A save manually compares several original field values before skipping a row. Review the existing DataRowState/XML change-selection contract instead of adding a second field-by-field change detector.',
    'input_tag_binding_review': 'An input control Tag is passed as an SP value. Trace the actual code/name binding and use its established EditValue or separate key control; action metadata in Tag is a different contract.',
    'focus_edit_gate_order_review': 'A negative focused-row return precedes an edit-mode guard in FocusedRowChanged. Check whether filter-row focus can bypass the guard; apply the target row-movement protection before that return when required.',
    'action_tag_case_preference': 'Use the agreed uppercase application action code consistently in button Tag assignments and matching switch cases. Preserve externally defined case-sensitive values when the actual contract requires them.',
    'save_success_notification_only_review': 'This direct save-success block only displays a message. Trace the actual caller/base path and restore the requested saved-row values, row state, edit mode and control protection after success. A message alone does not complete that lifecycle; preserve pending changes on failure.',
    'focused_row_save_navigation_review': 'A save imports the focused row into XML, but the corresponding local focus handlers show no cancellation or previous-row restoration. Verify the edited row identity and either block movement while edits are pending or confirm discard and restore that row before rebinding the next row. Binding-event suppression alone is not edit protection.',
}


def _methods(code: str):
    previous_end = -1
    for match in _method_declaration_matches(code):
        if match.start() < previous_end or match['body'] != '{':
            continue
        opening = match.end() - 1
        closing = balanced_close(code, opening, '{', '}')
        if closing < 0:
            continue
        previous_end = closing + 1
        yield match, opening + 1, closing


def _is_save_boundary(declaration: re.Match[str]) -> bool:
    return ('SaveCommandEventArgs' in declaration['parameters'] or
            declaration['name'] == 'CallSaveProcedure' or declaration['name'].endswith('_SaveCommand'))


def _focused_xml_navigation(code: str,
                            methods: Sequence[tuple[re.Match[str], int, int]]) -> list[_Finding]:
    """Observe one direct focused-row XML path and its supplied local handlers."""
    owners = []
    for owner in re.finditer(r'\bclass\s+\w+[^{}]*\{', code):
        closing = balanced_close(code, owner.end() - 1, '{', '}')
        if closing >= 0:
            owners.append((owner.end(), closing))

    def scope_at(offset: int) -> int:
        return max((left for left, right in owners if left <= offset < right), default=-1)

    local: dict[tuple[int, str], list[tuple[re.Match[str], int, int]]] = {}
    saved_views: set[tuple[int, str]] = set()
    for declaration, start, end in methods:
        scope = scope_at(start)
        local.setdefault((scope, declaration['name']), []).append((declaration, start, end))
        body = code[start:end]
        if not _is_save_boundary(declaration) or not re.search(r'\bDataTableToXml\s*\(', body):
            continue
        for row in re.finditer(r'\b(?:DataRow|var)\s+(\w+)\s*=\s*(?:this\.)?(\w+)\.GetFocusedDataRow\s*\(\s*\)', body):
            if re.search(r'\.ImportRow\s*\(\s*' + re.escape(row[1]) + r'\s*\)', body):
                saved_views.add((scope, row[2]))

    def reachable_bodies(scope: int, name: str) -> str:
        pending, visited, parts = [name], set(), []
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            matches = local.get((scope, current), [])
            if len(matches) != 1:
                continue
            _, start, end = matches[0]
            fragment = code[start:end]
            parts.append(fragment)
            for call in re.finditer(r'(?<![\w.])(?:this\.)?(\w+)\s*\(', fragment):
                if (scope, call[1]) in local:
                    pending.append(call[1])
        return '\n'.join(parts)

    findings = []
    for scope, view in sorted(saved_views):
        subscribed = {m[1] for m in re.finditer(
            r'\b(?:this\.)?' + re.escape(view) + r'\.FocusedRow(?:Changing|Changed)\s*\+=\s*(?:this\.)?(\w+)\s*;', code)
            if scope_at(m.start()) == scope}
        handlers = [(d, start, end) for d, start, end in methods if scope_at(start) == scope and
                    (d['name'] in subscribed or d['name'].lower() in {
                        view.lower() + '_focusedrowchanged', view.lower() + '_focusedrowchanging'})]
        bodies = '\n'.join(reachable_bodies(scope, d['name']) for d, _, _ in handlers)
        has_action = (re.search(r'\b\w+\.Cancel\s*=\s*true\b', bodies) or re.search(
            r'\b(?:this\.)?' + re.escape(view) + r'\.FocusedRowHandle\s*=\s*\w+\.PrevFocusedRowHandle\b', bodies))
        if not handlers or has_action:
            continue
        declaration = handlers[0][0]
        signature = declaration['name'] + '(' + re.sub(r'\s+', ' ', declaration['parameters']).strip() + ')'
        evidence = repr((view, [(kind, value) for kind, value, _, _ in _scan_csharp(bodies)[1]]))
        findings.append(_Finding('focused_row_save_navigation_review', signature, evidence, declaration.start('name')))
    return findings


def _parameter_values(source: str):
    """Observe a directly named parameter's second constructor argument."""
    code, _ = _scan_csharp(source)
    for _, name, offset in parameter_constructor_sites(source):
        if name is None:
            continue
        opening = code.find('(', offset)
        closing = balanced_close(code, opening, '(', ')')
        if closing < 0:
            continue
        _, tokens = _scan_csharp(source[opening + 1:closing])
        if len(tokens) < 3 or tokens[1][1] != ',':
            continue
        start = opening + 1 + tokens[2][2]
        end = closing
        depth = 0
        for _, value, left, _ in tokens[2:]:
            if value in {'(', '[', '{'}:
                depth += 1
            elif value in {')', ']', '}'}:
                depth -= 1
            elif value == ',' and depth == 0:
                end = opening + 1 + left
                break
        yield name, source[start:end].strip(), offset, closing + 1


def _date_types(sources: Sequence[str]) -> set[str]:
    result: set[str] = set()
    defaults = read_control_defaults(sources)
    for source in sources:
        code, _ = _scan_csharp(source)
        namespace = re.search(r'\bnamespace\s+([\w.]+)', code)
        for declaration in re.finditer(r'\bclass\s+(\w+)[^{}]*\{', code):
            end = balanced_close(code, declaration.end() - 1, '{', '}')
            if end < 0:
                continue
            body = code[declaration.end():end]
            for method in _method_declaration_matches(body):
                prefix = body[:method.start()]
                if (prefix.count('{') == prefix.count('}') and method['name'] == 'SetToDay' and 'public' in method['modifiers'].split()
                        and re.fullmatch(r'\s*(?:int|Int32|System\.Int32)\s+\w+\s*', method['parameters'])):
                    result.add((namespace[1] + '.' if namespace else '') + declaration[1])
    # Only follow declarations supplied by the caller, never assumed library APIs.
    changed = True
    while changed:
        changed = False
        for item in defaults:
            if item.type_name not in result and sum(_same_type(item.base_type, base) for base in result) == 1:
                result.add(item.type_name)
                changed = True
    return result


def _state_policies(source: str, code: str) -> list[_Finding]:
    findings: list[_Finding] = []
    for owner in re.finditer(r'\bclass\s+(\w+)[^{}]*\{', code):
        closing = balanced_close(code, owner.end() - 1, '{', '}')
        if closing < 0:
            continue
        body = code[owner.end():closing]
        for field in re.finditer(r'\b((?:(?:private|public|protected|internal|static|readonly|const|volatile)\s+)*)(?:bool|Boolean|System\.Boolean)\s+(\w+)\s*(?:=[^;{}]*)?;', body):
            prefix = body[:field.start()]
            if prefix.count('{') != prefix.count('}') or {'readonly', 'const'} & set(field[1].split()):
                continue
            member = field[2]
            reference = re.compile(r'(?<![\w.])(?:this\.)?' + re.escape(member) + r'\b')
            uses = []
            for declaration, start, end in _methods(body):
                fragment = body[start:end]
                # Bare names shadowed by a parameter/local are not resolved as fields.
                shadow = re.search(r'\b(?:bool|Boolean|System\.Boolean)\s+' + re.escape(member) + r'\b', declaration['parameters'] + ' ' + fragment)
                ref = re.compile(r'\bthis\.' + re.escape(member) + r'\b') if shadow else reference
                spans = []
                for assignment in re.finditer(r'\b(?:\w+\.)*(?:Enabled|ReadOnly|AllowEdit|Editable|Cancel|m_Editmode)\s*=(?!=)[^;{}]*;', fragment):
                    if ref.search(assignment[0]):
                        spans.append((assignment.start(), assignment.end()))
                for call in re.finditer(r'\bUsr_ControlsProtect\s*\(', fragment):
                    end_call = balanced_close(fragment, call.end() - 1, '(', ')')
                    if end_call >= 0 and ref.search(fragment[call.start():end_call + 1]):
                        spans.append((call.start(), end_call + 1))
                for condition in re.finditer(r'\bif\s*\(', fragment):
                    end_condition = balanced_close(fragment, condition.end() - 1, '(', ')')
                    if end_condition < 0 or not ref.search(fragment[condition.end():end_condition]):
                        continue
                    opening = end_condition + 1
                    while opening < len(fragment) and fragment[opening].isspace():
                        opening += 1
                    end_body = (balanced_close(fragment, opening, '{', '}') if fragment[opening:opening + 1] == '{'
                                else fragment.find(';', opening))
                    guarded = fragment[opening:end_body + 1] if end_body >= 0 else ''
                    if re.search(r'\breturn\b|\bUsr_ControlsProtect\s*\(|\.(?:Cancel|Enabled|ReadOnly|AllowEdit|Editable|Text|EditValue)\s*=(?!=)', guarded):
                        spans.append((condition.start(), end_body + 1))
                for left, right in spans:
                    raw = source[owner.end() + start + left:owner.end() + start + right]
                    tokens = [(kind, value) for kind, value, _, _ in _scan_csharp(raw)[1]]
                    uses.append((declaration['name'], repr(tokens)))
            if uses:
                findings.append(_Finding('ui_state_policy_review', owner[1] + '.' + member,
                                         repr(sorted(set(uses))), owner.end() + field.start(2)))
    return findings


def _findings(source: str, *, control_types: Mapping[str, str], date_types: set[str],
              known_date_members: set[str], input_members: set[str]) -> list[_Finding]:
    code, _ = _scan_csharp(source)
    helpers = {item['name'] for item in _target_local_method_inventory(code)}
    methods = list(_methods(code))
    findings = _state_policies(source, code) + _focused_xml_navigation(code, methods)
    for declaration, start, end in methods:
        name = declaration['name']
        signature = name + '(' + re.sub(r'\s+', ' ', declaration['parameters']).strip() + ')'
        body = code[start:end]

        def add(kind: str, left: int, right: int) -> None:
            evidence = repr([(kind, value) for kind, value, _, _ in _scan_csharp(source[start + left:start + right])[1]])
            findings.append(_Finding(kind, signature, evidence, start + left))

        if name in helpers and re.search(r'\b(?:CallSelectProcedure|GetSelectedRows|ImportRow|Clone)\s*\(|\.DataSource\s*=', body):
            findings.append(_Finding('new_ui_data_helper', signature, signature, declaration.start('name')))

        is_entry = bool(re.search(r'\b(?:New|Edit)CommandEventArgs\b', declaration['parameters']) or re.search(r'_(?:New|Edit)Command$', name))
        if is_entry:
            for call in re.finditer(r'\b(?:CallSelectProcedure|GetDataSetFromSP|GetDataTableFromSP)\s*\(', body):
                close = balanced_close(body, call.end() - 1, '(', ')')
                if close >= 0:
                    add('entry_query_review', call.start(), close + 1)

        is_save = _is_save_boundary(declaration)
        for parameter, value, left, right in _parameter_values(source[start:end]):
            literal = string_literal_value(value)
            if is_save and parameter.upper() == '@WORKTYPE' and literal is not None:
                add('save_worktype_literal_review', left, right)
            value_code, _ = _scan_csharp(value)
            for tag in re.finditer(r'\b(?:this\.)?(\w+)\.Tag\b', value_code):
                if tag[1] in input_members:
                    add('input_tag_binding_review', left, right)

        if is_save:
            for condition in re.finditer(r'\bif\s*\(', body):
                close = balanced_close(body, condition.end() - 1, '(', ')')
                opening = close + 1
                while opening < len(body) and body[opening].isspace():
                    opening += 1
                if close < 0 or opening >= len(body) or body[opening] != '{':
                    continue
                closing = balanced_close(body, opening, '{', '}')
                fragment = body[condition.start():closing + 1] if closing >= 0 else ''
                if re.search(r'\bShowMessage\w*\s*\(', fragment) and re.search(r'\breturn\b', fragment):
                    add('save_gate_review', condition.start(), closing + 1)
                comparison = body[condition.end():close]
                if name != 'CallSaveProcedure':
                    expression = comparison.strip()
                    save_call = re.match(r'(?:this\.)?CallSaveProcedure\s*\(', expression)
                    success_body = source[start + opening + 1:start + closing] if closing >= 0 else ''
                    statements = [body[opening + 1 + left:opening + 1 + right].strip()
                                  for left, right in direct_statement_spans(success_body)]
                    notifications = [re.fullmatch(r'(?:this\.)?ShowMessage\w*\s*\([\s\S]*\)\s*;', statement)
                                     for statement in statements]
                    if (save_call and balanced_close(expression, save_call.end() - 1, '(', ')') == len(expression) - 1
                            and notifications and all(notifications)):
                        add('save_success_notification_only_review', condition.start(), closing + 1)
                if (len(re.findall(r'\bDataRowVersion\.Original\b', comparison)) >= 2
                        and re.search(r'\bEquals\s*\(', comparison) and re.search(r'\bcontinue\b', fragment)):
                    add('manual_original_row_comparison_review', condition.start(), closing + 1)

        if name.endswith('_FocusedRowChanged') or 'FocusedRowChangedEventArgs' in declaration['parameters']:
            negative_guard = None
            for left, right in direct_statement_spans(source[start:end]):
                statement = body[left:right]
                condition = re.match(r'\s*if\s*\(', statement)
                if condition is None:
                    continue
                close = balanced_close(statement, condition.end() - 1, '(', ')')
                if close < 0:
                    continue
                expression = statement[condition.end():close]
                if re.search(r'\bFocusedRowHandle\s*<\s*0\b', expression) and re.search(r'\breturn\b', statement[close:]):
                    negative_guard = (left, right)
                elif (re.search(r'\bm_Editmode\b', expression) and
                      re.search(r'\breturn\b|\b(?:FocusedRowHandle|Cancel)\s*=', statement[close:])):
                    if negative_guard is not None:
                        add('focus_edit_gate_order_review', *negative_guard)
                    break

        for switch in re.finditer(r'\bswitch\s*\(', body):
            close = balanced_close(body, switch.end() - 1, '(', ')')
            if close < 0 or not re.search(r'\.Tag\b', body[switch.end():close]):
                continue
            opening = close + 1
            while opening < len(body) and body[opening].isspace():
                opening += 1
            if body[opening:opening + 1] != '{':
                continue
            closing = balanced_close(body, opening, '{', '}')
            if closing < 0:
                continue
            _, tokens = _scan_csharp(source[start + opening + 1:start + closing])
            depth = 0
            for index, (_, value, left, _) in enumerate(tokens):
                if value == '{':
                    depth += 1
                elif value == '}':
                    depth -= 1
                elif value == 'case' and depth == 0 and index + 2 < len(tokens) and tokens[index + 2][1] == ':':
                    literal = tokens[index + 1]
                    raw = source[start + opening + 1 + literal[2]:start + opening + 1 + literal[3]]
                    label = string_literal_value(raw)
                    if label and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', label) and label != label.upper():
                        add('action_tag_case_preference', opening + 1 + left, opening + 1 + literal[3])

        if (re.search(r'\b(?:for|foreach)\s*\(', body) and re.search(r'\.GetSelectedRows\s*\(', body)
                and re.search(r'\.GetDataRow\s*\(', body)):
            for match in re.finditer(r'\b\w+\.Delete\s*\(\s*\)', body):
                add('manual_selected_row_delete', match.start(), match.end())

        if re.search(r'\bDataRowVersion\b', body) and re.search(r'\.Rows\b', body):
            for match in re.finditer(r'\bMath\.Max\s*\(', body):
                close = balanced_close(body, match.end() - 1, '(', ')')
                if close >= 0:
                    add('client_sequence_review', match.start(), close + 1)

        new_rows = set(re.findall(r'\bDataRow\s+(\w+)\s*=\s*(?:this\.)?\w+\.NewRow\s*\(', body))
        for match in re.finditer(r'\b(\w+)\s*\[([^\]\n]*)\]\s*=(?!=)([^;{}]*);', body):
            if match[1] not in new_rows or not re.search(r'\buserInfo\s*\.|\.(?:Text|EditValue)\b', match[3]):
                continue
            column = source[start + match.start(2):start + match.end(2)]
            if string_literal_value(column) is not None:
                add('row_header_propagation_review', match.start(), match.end())

        for match in re.finditer(r'\b(?:this\.)?(\w+)\.EditValue\s*=\s*(?:System\.)?DateTime\.(?:Today|Now)\b[^;{}]*;', body):
            member = match[1]
            type_name = control_types.get(member, '')
            if member in known_date_members or (type_name and sum(_same_type(type_name, t) for t in date_types) == 1):
                add('date_helper_review', match.start(), match.end())
    return findings


def check_project_flow(source: str, *, original: str | None = None,
                       control_types: Mapping[str, str] | None = None,
                       control_sources: Sequence[str] = ()) -> list[Issue]:
    before, _ = _scan_csharp(original or '')
    known_members = set(re.findall(r'\b(?:this\.)?(\w+)\.SetToDay\s*\(', before))
    date_types = _date_types(control_sources)
    types = dict(control_types or {})
    defaults = read_control_defaults(control_sources)
    input_members: set[str] = set()
    for name, type_name in types.items():
        seen: set[str] = set()
        while type_name not in seen:
            seen.add(type_name)
            matching = [item for item in defaults if _same_type(type_name, item.type_name)]
            if len(matching) != 1:
                break
            type_name = matching[0].base_type
        if known_control_kind(type_name) in {
            'TextEdit', 'TextBox', 'ButtonEdit', 'LookUpEdit', 'GridLookUpEdit', 'DateEdit', 'SpinEdit', 'MemoEdit',
        }:
            input_members.add(name)
    existing_methods = {m['name'] + '(' + re.sub(r'\s+', ' ', m['parameters']).strip() + ')' for m, _, _ in _methods(before)}
    previous = Counter((item.code, item.method, item.evidence) for item in _findings(
        original or '', control_types=types, date_types=date_types, known_date_members=known_members,
        input_members=input_members))
    issues: list[Issue] = []
    for item in _findings(source, control_types=types, date_types=date_types, known_date_members=known_members,
                          input_members=input_members):
        key = item.code, item.method, item.evidence
        if previous[key]:
            previous[key] -= 1
            continue
        if item.code == 'new_ui_data_helper' and (original is None or item.method in existing_methods):
            continue
        issues.append(Issue(item.code, 'warning', _MESSAGES[item.code],
                            line=source.count('\n', 0, item.offset) + 1,
                            details={'method': item.method, 'baseline_supplied': original is not None}))
    return issues
