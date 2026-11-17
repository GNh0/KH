"""Observed comparison-source reads and bounded C# artifact responsibilities.

This records available source evidence, never approval, semantic necessity or an
agent's audit. Unregistered files are not inspected by these helpers.
"""
from collections import Counter
import hashlib
from pathlib import Path
import re
import shlex

from src.common.files import read_file
from src.runtime.skill_usage import DOMAINS
from src.runtime.workflows import binding
from src.runtime.check_context import companion


def owned_source(state: dict, path: Path) -> bool:
    if binding(state, path):
        return True
    for item in state.get('applications', {}).values():
        peer = companion(Path(item['target']))
        if peer is not None and (peer == path or (peer.exists() and path.exists() and peer.samefile(path))):
            return True
    return False


def read_paths(event: dict) -> list[Path]:
    """Recognize read provenance without executing or guessing dynamic commands."""
    from src.runtime.write_targets import _shell_statements, _ps_value
    data = event.get('tool_input', {})
    if not isinstance(data, dict):
        return []
    tool = event.get('tool_name', '')
    workdir = data.get('workdir') if tool in {'exec_command', 'PowerShell', 'Bash'} else None
    cwd = Path(workdir if isinstance(workdir, str) and Path(workdir).is_absolute() else event['cwd']).resolve()
    names = []
    if tool in {'Read', 'read_file'}:
        names.append(data.get('file_path', data.get('path')))
    elif tool in {'exec_command', 'PowerShell', 'Bash'}:
        command = data.get('cmd', data.get('command', ''))
        if not isinstance(command, str):
            return []
        values = {}
        for statement in _shell_statements(command):
            assignment = re.fullmatch(r'(\$\w+)\s*=\s*(.+)', statement)
            if assignment:
                values[assignment[1].casefold()] = _ps_value(assignment[2], values, cwd)
                continue
            match = re.match(r'''(?i)^Get-Content\s+(?:(?:-LiteralPath|-Path)\s+)?('(?:[^']|'')*'|"[^"]*"|\$\w+)(?:\s|$)''', statement)
            if match:
                names.append(_ps_value(match[1], values, cwd))
            elif tool == 'Bash' and re.match(r'^cat\s', statement):
                try:
                    parts = shlex.split(statement)
                    if all(not name.startswith('-') or name == '--' for name in parts[1:]):
                        names.extend(name for name in parts[1:] if name != '--')
                except ValueError:
                    return []
            elif statement and not re.match(r'(?i)^Select-Object\b', statement):
                return []  # Unknown control flow/output cannot establish that a later read executed.
    return [(cwd / name).resolve() for name in names if isinstance(name, (str, Path)) and str(name)]


def unit(reference: dict) -> tuple[str, list[str]]:
    source = read_file(Path(reference['path']), max_bytes=1024 * 1024)
    lines = source.text().splitlines()
    start, end = reference['start'], reference['end']
    if not 1 <= start <= end <= len(lines):
        raise ValueError('Comparison source range no longer exists.')
    body = lines[start - 1:end]
    if not any(line.strip() for line in body):
        raise ValueError('Comparison source range is empty.')
    return source.sha256, [hashlib.sha256(line.strip().encode()).hexdigest() for line in body]


def select_references(state: dict, applied: list[dict], names: list[str], cwd: str) -> None:
    """Select actual sources for current responsibilities; no read is certified."""
    prepared = []
    for name in names:
        match = re.fullmatch(r'(.+)#L(\d+)-L(\d+)', name)
        path = Path(match[1] if match else name)
        path = (Path(cwd) / path).resolve()
        if not path.is_file() or path.suffix.casefold() not in DOMAINS or owned_source(state, path):
            raise ValueError('Comparison must be an existing SQL/C#/PB source outside the owned output set: ' + str(path))
        lines = read_file(path, max_bytes=1024 * 1024).text().splitlines()
        ref = {'path': str(path), 'start': int(match[2]) if match else 1,
               'end': int(match[3]) if match else len(lines)}
        sha, _lines = unit(ref)
        ref['source_sha256'] = sha
        prepared.append(ref)
    used = set()
    for applied_item in applied:
        target = Path(applied_item['target'])
        item = binding(state, target)
        if item is None:
            continue
        refs = [dict(ref) for ref in item.get('references', [])]
        for index, ref in enumerate(prepared):
            if DOMAINS[Path(ref['path']).suffix.casefold()] != DOMAINS[target.suffix.casefold()]:
                continue
            try:
                if target.exists() and target.samefile(ref['path']):
                    raise ValueError('An output cannot certify itself as its comparison source.')
            except FileNotFoundError:
                pass
            used.add(index)
            prior = next((old for old in refs if all(old.get(key) == ref[key] for key in ('path', 'start', 'end'))), None)
            if prior is None:
                prior = dict(ref)
                refs.append(prior)
            elif prior.get('source_sha256') != ref['source_sha256']:
                prior = dict(ref)
                refs = [prior if all(old.get(key) == ref[key] for key in ('path', 'start', 'end')) else old for old in refs]
            prior['work'] = sorted(set(prior.get('work', [])) | set(item['work']))
        if len(refs) > 8:
            raise ValueError('More than eight comparison units for one output; narrow the actual responsibility scope.')
        item['references'] = refs
    if used != set(range(len(prepared))):
        raise ValueError('A comparison source has no matching output domain.')


def observe_references(state: dict, returned: str, event: dict) -> None:
    response = event.get('tool_response')
    if isinstance(response, dict) and any(response.get(field) not in (None, 0) for field in ('exit_code', 'exitCode')):
        return
    paths = read_paths(event)
    if not paths:
        return
    hashes = [(hashlib.sha256(line.strip().encode()).hexdigest(),
               hashlib.sha256(re.sub(r'^\s*(?:L?\d+[:\t→]\s*)', '', line).strip().encode()).hexdigest())
              for line in returned.splitlines()]
    for item in state.get('applications', {}).values():
        for ref in item.get('references', []):
            try:
                source_path = Path(ref['path'])
                if owned_source(state, source_path) or not any(path == source_path or (path.exists() and path.samefile(source_path)) for path in paths):
                    continue
                sha, expected = unit(ref)
                if sha != ref.get('source_sha256'):
                    ref.pop('read_sha256', None)
                    ref.pop('read_buffer', None)
                    continue
                if ref.get('read_sha256') == sha or not hashes:
                    continue
                expected_set = set(expected)
                observed = [next((value for value in choices if value in expected_set), '') for choices in hashes]
                stream = ref.get('read_buffer', []) + [value for value in observed if value]
                if '|' + '|'.join(expected) + '|' in '|' + '|'.join(stream) + '|':
                    ref['read_sha256'] = sha
                    ref.pop('read_buffer', None)
                else:
                    ref['read_buffer'] = stream[-(len(expected) + 32):]
            except (OSError, ValueError, UnicodeError, RuntimeError):
                ref.pop('read_sha256', None)


def reference_problem(state: dict, path: Path) -> str:
    item = binding(state, path)
    if item is None or set(item['work']) <= {'sql-format'}:
        return ''
    covered = set()
    for ref in item.get('references', []):
        try:
            if owned_source(state, Path(ref['path'])):
                continue
            sha, _lines = unit(ref)
            if sha == ref.get('source_sha256') == ref.get('read_sha256'):
                covered.update(ref.get('work', []))
        except (OSError, ValueError, UnicodeError, RuntimeError):
            continue
    missing = set(item['work']) - covered
    if not missing:
        return ''
    return ('Comparison-source evidence is missing for ' + str(path) + ': ' + ', '.join(sorted(missing)) +
            '. Use scoped apply --reference <actual comparison source[#Lstart-Lend]>, then retrieve its current relevant complete body. '
            'Registration/read evidence does not establish source approval, semantic comparison or an audit.')


def control_work(before: str, after: str, companion: str = '') -> set[str]:
    """Infer only supported framework artifacts, not business intent or API bans."""
    from src.csharp.lexer import _scan_csharp, _mask_range
    from src.csharp.designer_model import parse_designer_source, _assignment_end, _normalized_csharp_value
    from src.csharp.control_names import _PREFIXES, SINGLE_LINE_INPUT_KINDS

    def code(source):
        masked, tokens = _scan_csharp(source)
        chars = list(masked)
        for kind, _, start, end in tokens:
            if kind in {'string', 'interpolated_string', 'char'}:
                _mask_range(chars, source, start, end)
        return ''.join(chars)

    aliases = dict(re.findall(r'\busing\s+(\w+)\s*=\s*([\w.:]+)\s*;', code(before + '\n' + after + '\n' + companion)))

    def role(type_name):
        type_name = type_name.removeprefix('global::')
        first, separator, rest = type_name.partition('.')
        type_name = (aliases.get(first, first) + (separator + rest if separator else '')).removeprefix('global::')
        leaf = type_name.rsplit('.', 1)[-1]
        if type_name.startswith('DevExpress.XtraGrid.') and leaf in {'GridControl', 'GridView', 'BandedGridView', 'AdvBandedGridView', 'GridColumn', 'GridFormatRule', 'GridGroupSummaryItem', 'GridColumnSummaryItem'}:
            return 'csharp-grid'
        if type_name.startswith('DevExpress.XtraReports.UI.') and (leaf.startswith('XR') or leaf == 'XtraReport'):
            return 'csharp-report'
        if type_name.startswith('DevExpress.XtraEditors.') and (leaf in _PREFIXES or leaf in SINGLE_LINE_INPUT_KINDS or leaf == 'BaseEdit' or ('.Repository.' in type_name and leaf.startswith('RepositoryItem'))):
            return 'csharp-control'
        if type_name.startswith('System.Windows.Forms.') and leaf in {'Control', 'Form', 'UserControl', 'TextBox', 'Label', 'ComboBox', 'GroupBox', 'ListBox', 'TableLayoutPanel', 'FlowLayoutPanel', 'CheckBox', 'RadioButton', 'PictureBox', 'Panel', 'TabControl', 'Button', 'DateTimePicker', 'NumericUpDown'}:
            return 'csharp-control'
        return ''

    known = {}
    for source in (before, after, companion):
        model = parse_designer_source(source)
        contained = {entry['child'] for entry in model.controls_add}
        for name, record in model.controls.items():
            kind = role(record.type_name) or ('csharp-control' if name in contained else '')
            if kind:
                known['this.' + name] = kind
                known[name] = kind
        for match in re.finditer(r'\b((?:this\.)?\w+)\s*=\s*new\s+([\w.:]+)\s*\(', code(source)):
            kind = role(match[2])
            if kind:
                known[match[1]] = kind
            elif not match[1].startswith('this.'):
                known.pop(match[1], None)  # A local non-control object must not inherit a same-named field's role.

    for source in (before, after):
        for match in re.finditer(r'\b([\w.:]+)\s+(\w+)\s*(?=[=,;)])', code(source)):
            if match[1] not in {'return', 'new', 'this', 'var'} and not role(match[1]):
                known.pop(match[2], None)

    def features(source):
        masked = code(source)
        found = Counter()
        for match in re.finditer(r'\bnew\s+([\w.:]+)\s*\(', masked):
            kind = role(match[1])
            if kind:
                end = _assignment_end(masked, match.start())
                found[kind, _normalized_csharp_value(source[match.start():end if end is not None else match.end()])] += 1
        for match in re.finditer(r'\b((?:this\.)?\w+)\.(?:\w+\.)*\w+\s*=(?!=)', masked):
            if match[1] in known:
                end = _assignment_end(masked, match.end())
                found[known[match[1]], _normalized_csharp_value(source[match.start():end if end is not None else match.end()])] += 1
        return found

    old, new = features(before), features(after)
    return {kind for kind, _signature in (new - old) + (old - new)}
