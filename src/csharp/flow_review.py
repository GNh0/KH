"""Review new UI/data-flow choices; findings are not semantic rejection rules."""
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re

from src.common.results import Issue
from .control_defaults import _same_type, read_control_defaults
from .lexer import _scan_csharp, balanced_close, string_literal_value
from .source import _method_declaration_matches, _target_local_method_inventory


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
              known_date_members: set[str]) -> list[_Finding]:
    code, _ = _scan_csharp(source)
    helpers = {item['name'] for item in _target_local_method_inventory(code)}
    findings = _state_policies(source, code)
    for declaration, start, end in _methods(code):
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

        is_save = 'SaveCommandEventArgs' in declaration['parameters'] or name == 'CallSaveProcedure' or name.endswith('_SaveCommand')
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
    types = control_types or {}
    existing_methods = {m['name'] + '(' + re.sub(r'\s+', ' ', m['parameters']).strip() + ')' for m, _, _ in _methods(before)}
    previous = Counter((item.code, item.method, item.evidence) for item in _findings(
        original or '', control_types=types, date_types=date_types, known_date_members=known_members))
    issues: list[Issue] = []
    for item in _findings(source, control_types=types, date_types=date_types, known_date_members=known_members):
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
