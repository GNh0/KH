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
from src.sql.procedure_authorship import author_key

CONTROL_WORK = frozenset({'csharp-control', 'csharp-designer', 'csharp-grid'})


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
            read = statement
            sliced = re.fullmatch(r'\((Get-Content\b.+)\)\s*\[\s*\d+(?:\s*\.\.\s*\d+)?\s*\]', read, re.I)
            if sliced:
                read = sliced[1]
            if re.match(r'(?i)^Get-Content\s', read):
                arguments = re.findall(r'''\x27(?:[^\x27]|\x27\x27)*\x27|"[^"\n]*"|\S+''', read)[1:]
                path = None
                index = 0
                while index < len(arguments):
                    argument = arguments[index]
                    option = argument.casefold()
                    if option in {'-raw', '-force'}:
                        index += 1
                        continue
                    if option in {'-encoding', '-totalcount', '-tail', '-readcount', '-literalpath', '-path'}:
                        index += 1
                        if index >= len(arguments):
                            return []
                        if option in {'-literalpath', '-path'}:
                            if path is not None:
                                return []
                            path = _ps_value(arguments[index], values, cwd)
                    elif option.startswith('-') or path is not None:
                        return []
                    else:
                        path = _ps_value(argument, values, cwd)
                    index += 1
                if path is None:
                    return []
                names.append(path)
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


def selected_source(reference: dict) -> tuple[str, str]:
    source = read_file(Path(reference['path']), max_bytes=1024 * 1024)
    lines = source.text().splitlines()
    start, end = reference['start'], reference['end']
    if not 1 <= start <= end <= len(lines):
        raise ValueError('Comparison source range no longer exists.')
    body = lines[start - 1:end]
    if not any(line.strip() for line in body):
        raise ValueError('Comparison source range is empty.')
    return source.sha256, '\n'.join(body)


def unit(reference: dict) -> tuple[str, list[str]]:
    sha, body = selected_source(reference)
    return sha, [hashlib.sha256(line.strip().encode()).hexdigest() for line in body.splitlines() if line.strip()]


def designer_comparison(body: str) -> bool:
    """Distinguish observed layout from a control's own constructor defaults."""
    from src.csharp.designer_model import parse_designer_source
    from src.csharp.control_defaults import read_control_defaults, control_base_type
    from src.csharp.control_names import known_control_kind
    model = parse_designer_source(body)
    if any(control.type_name and control.properties for control in model.controls.values()) or model.controls_add:
        return True
    if not model.form_properties:
        return False
    defaults = read_control_defaults([body])
    return not defaults or any(known_control_kind(control_base_type(item.type_name, defaults)) == 'Form' for item in defaults)


def successful_read_paths(event: dict) -> list[Path]:
    response = event.get('tool_response')
    if event.get('hook_event_name') == 'PostToolUseFailure':
        return []
    if isinstance(response, dict):
        if any(field in response and response[field] != 0 for field in ('exit_code', 'exitCode')):
            return []
        if response.get('isError') or response.get('is_error') or response.get('success') is False:
            return []
    return read_paths(event)


def select_references(state: dict, applied: list[dict], names: list[str], cwd: str,
                      *, work: list[str] | None = None) -> None:
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
        sha, body = selected_source(ref)
        ref['source_sha256'] = sha
        if path.suffix.casefold() == '.cs':
            from src.csharp.control_defaults import read_control_defaults
            ref['control_definition'] = bool(read_control_defaults([body]))
        prepared.append(ref)
    used = set()
    for applied_item in applied:
        target = Path(applied_item['target'])
        item = binding(state, target)
        if item is None:
            continue
        refs = [dict(ref) for ref in item.get('references', [])]
        chosen = set(work if work is not None else applied_item['work']) & set(item['work'])
        sp_roles = chosen & {'sql-select', 'sql-save'}
        if target.suffix.casefold() == '.sql' and sp_roles and any(Path(ref['path']).suffix.casefold() == '.sql' for ref in prepared):
            units = {(ref['path'], ref['start'], ref['end']) for ref in prepared}
            for ref in refs:
                if Path(ref['path']).suffix.casefold() == '.sql' and (ref['path'], ref['start'], ref['end']) not in units:
                    ref['work'] = sorted(set(ref.get('work', [])) - sp_roles)
            refs = [ref for ref in refs if ref.get('work')]
        if target.name.casefold().endswith('.designer.cs'):
            chosen.add('csharp-designer')
        for index, ref in enumerate(prepared):
            reference_domain = DOMAINS[Path(ref['path']).suffix.casefold()]
            target_domain = DOMAINS[target.suffix.casefold()]
            responsibilities = ({'pb-migrate'} if reference_domain == 'pb-to-csharp-migration-harness' and
                                'pb-migrate' in chosen else chosen - {'pb-migrate'} if reference_domain == target_domain else set())
            if not responsibilities:
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
            prior['work'] = sorted(set(prior.get('work', [])) | responsibilities)
            if 'control_definition' in ref:
                prior['control_definition'] = bool(ref['control_definition'] and set(prior['work']) & CONTROL_WORK)
        if len(refs) > 8:
            raise ValueError('More than eight comparison units for one output; narrow the actual responsibility scope.')
        item['references'] = refs
    if used != set(range(len(prepared))):
        raise ValueError('A comparison source has no matching responsibility; PB migration needs its PB original and the output-language style source separately.')


def observe_references(state: dict, returned: str, event: dict) -> None:
    paths = successful_read_paths(event)
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
    sp_work = path.suffix.casefold() == '.sql' and bool(set(item['work']) & {'sql-select', 'sql-save'})
    authors = item.get('sql_authorship', state.get('sql_authorship', {}))
    search_authors: set[str] = set()
    if sp_work:
        from src.sql.procedure_authorship import selected_authors
        try:
            authors = selected_authors(authors.get('author'), authors.get('reference_author'))
        except (AttributeError, ValueError):
            return ('Before this first SP draft, ask the user which name belongs in the target AUTHOR header and whose existing SPs to find and read for style. '
                    'Record the header name with --author; pass each search name separately with --reference-author.')
        names = authors['reference_author']
        search_authors = {author_key(name) for name in ([names] if isinstance(names, str) else names)}
    covered = set()
    for ref in item.get('references', []):
        selected_sp = sp_work and Path(ref['path']).suffix.casefold() == '.sql' and bool(
            set(ref.get('work', [])) & {'sql-select', 'sql-save'})
        try:
            if owned_source(state, Path(ref['path'])):
                if selected_sp:
                    return 'Select an independent comparison SP instead of an owned output: ' + ref['path']
                continue
            sha, _lines = unit(ref)
            if selected_sp and not (sha == ref.get('source_sha256') == ref.get('read_sha256')):
                return 'Reselect and read the current complete comparison SP: ' + ref['path']
            if sha == ref.get('source_sha256') == ref.get('read_sha256'):
                reference_domain = DOMAINS[Path(ref['path']).suffix.casefold()]
                reference_body = ''
                if sp_work and reference_domain == 'sql-formatting':
                    from src.sql.procedure_authorship import procedure_headers
                    raw = read_file(Path(ref['path']), max_bytes=1024 * 1024)
                    if raw.sha256 != sha:
                        return 'The comparison SP changed during checking; reselect and read it: ' + ref['path']
                    reference_body = raw.text()
                    headers = [header for header in procedure_headers(reference_body)
                               if ref['start'] <= header.line <= ref['end']]
                    if not headers or any(not header.body_observed or ref['start'] > header.unit_start or ref['end'] < header.unit_end or
                                          author_key(header.fields.get('AUTHOR', '')) not in search_authors for header in headers):
                        if selected_sp:
                            return 'Select and read a complete comparison SP with a requested AUTHOR: ' + ref['path']
                        continue
                responsibilities = set(ref.get('work', []))
                # Recheck roles for older stored applications as well. Output
                # language style never certifies the migration's PB original.
                if reference_domain == 'pb-to-csharp-migration-harness':
                    responsibilities &= {'pb-edit', 'pb-migrate'}
                else:
                    responsibilities.discard('pb-migrate')
                    if reference_domain != DOMAINS[path.suffix.casefold()]:
                        continue
                if sp_work and reference_domain == 'sql-formatting':
                    from src.sql.procedure_authorship import procedure_responsibilities
                    observed = procedure_responsibilities(reference_body, start=ref['start'], end=ref['end'])
                    responsibilities -= {'sql-select', 'sql-save'} - observed
                    if selected_sp and not responsibilities & {'sql-select', 'sql-save'}:
                        return 'Choose a comparison SP that performs the selected responsibility: ' + ref['path']
                if 'csharp-designer' in responsibilities:
                    body_sha, body = selected_source(ref)
                    if body_sha != sha or not designer_comparison(body):
                        responsibilities.discard('csharp-designer')
                covered.update(responsibilities)
        except (OSError, ValueError, UnicodeError, RuntimeError):
            if selected_sp:
                return 'The selected comparison SP could not be read; reselect its current definition: ' + ref['path']
            continue
    if path.suffix.casefold() == '.cs':
        _controls, _dependencies, control_problems = observed_control_sources(state, path)
        if control_problems:
            return 'Control-source evidence is missing for ' + str(path) + ': ' + '; '.join(control_problems)
    missing = set(item['work']) - covered
    if not missing:
        return ''
    return ('Comparison-source evidence is missing for ' + str(path) + ': ' + ', '.join(sorted(missing)) +
            ('; select and read the author header and complete SP batch authored by the user-selected reference author' if sp_work else '') +
            '. Use scoped apply --reference <actual comparison source[#Lstart-Lend]>, then retrieve its current relevant complete body. '
            'Registration/read evidence does not establish source approval, semantic comparison or an audit.')


def observed_comparisons(state: dict, path: Path) -> tuple[dict[str, str], list[dict], list[str]]:
    """Supply only current, observed selected C# units, never an arbitrary peer."""
    groups: dict[str, dict[str, list[tuple[int, int]]]] = {}
    dependencies, problems = [], []
    item = binding(state, path) or {}
    for ref in item.get('references', []):
        source = Path(ref['path'])
        if source.suffix.casefold() != '.cs':
            continue
        try:
            sha, _lines = unit(ref)
            dependencies.append({'path': str(source), 'sha256': sha})
            if owned_source(state, source) or sha != ref.get('source_sha256') or sha != ref.get('read_sha256'):
                continue
            body_sha, body = selected_source(ref)
            if body_sha != sha:
                continue
            layout = designer_comparison(body)
            for responsibility in set(ref.get('work', [])) & set(item.get('work', [])):
                if responsibility.startswith('csharp-'):
                    if not layout and ref.get('control_definition') and responsibility in CONTROL_WORK:
                        continue  # Definitions do not compete as layout programs.
                    kind = 'designer' if layout and responsibility in {'csharp-designer', 'csharp-control', 'csharp-grid'} else 'csharp'
                    groups.setdefault(kind + ':' + responsibility, {}).setdefault(str(source), []).append((ref['start'], ref['end']))
        except (OSError, ValueError, UnicodeError, RuntimeError):
            problems.append('Selected comparison source is unavailable: ' + str(source))
    bodies = {}
    for kind, sources in groups.items():
        if len(sources) != 1:
            problems.append('Multiple comparison programs for the same responsibility ' + kind + ' are ambiguous; narrow that responsibility before claiming this static comparison.')
            continue
        name, ranges = next(iter(sources.items()))
        raw = read_file(Path(name), max_bytes=1024 * 1024)
        if any(entry['sha256'] != raw.sha256 for entry in dependencies if entry['path'] == name):
            problems.append('Selected comparison source changed during inspection: ' + name)
            continue
        lines = raw.text().splitlines()
        selected = {index for start, end in ranges for index in range(start - 1, end)}
        bodies[kind] = '\n'.join(line for index, line in enumerate(lines) if index in selected)
    # Preserve the simple single-program interface without discarding distinct
    # query/report/etc. sources merely because they share a C# extension.
    for base in ('csharp', 'designer'):
        matches = [value for key, value in bodies.items() if key.startswith(base + ':')]
        if matches and len(set(matches)) == 1:
            bodies[base] = matches[0]
    return bodies, dependencies, problems


def observed_control_sources(state: dict, path: Path) -> tuple[list[str], list[dict], list[str]]:
    """Forward only selected, fully observed control-definition units."""
    from src.csharp.control_defaults import read_control_defaults
    sources, dependencies, problems = [], [], []
    for ref in (binding(state, path) or {}).get('references', []):
        source = Path(ref['path'])
        if (source.suffix.casefold() != '.cs' or owned_source(state, source) or
                not set(ref.get('work', [])) & CONTROL_WORK):
            continue
        try:
            sha, body = selected_source(ref)
            definitions = read_control_defaults([body])
            required = bool(definitions) or bool(ref.get('control_definition'))
            if not required:
                continue
            if sha != ref.get('source_sha256') or sha != ref.get('read_sha256'):
                problems.append('Selected control definition changed or has not been read in its selected range: ' + str(source))
                continue
            if definitions:
                sources.append(body)
                dependencies.append({'path': str(source), 'sha256': sha})
            else:
                problems.append('Selected control-definition range no longer supplies a complete supported class: ' + str(source))
        except (OSError, ValueError, UnicodeError, RuntimeError) as error:
            problems.append('Selected control definition is unverified: ' + str(source) + ': ' + str(error))
    return sources, dependencies, problems


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
        member = r'\w+(?:\[[^\]\n;]+\])?'
        for match in re.finditer(r'\b((?:this\.)?\w+)\.(?P<path>(?:' + member + r'\.)*\w+)\s*(?P<operation>=(?!=)|\()', masked):
            if match[1] in known:
                if match['operation'] == '(' and not (
                        match['path'] in {'BestFitColumns', 'BestFit', 'PopulateColumns', 'LayoutChanged', 'SetBounds', 'RestoreLayoutFromXml', 'RestoreLayoutFromStream', 'RestoreLayoutFromRegistry'} or
                        re.fullmatch(r'(?:\w+\.)*(?:Controls|Columns|Buttons|TileTemplate|Items)\.(?:Add|AddRange|Remove|RemoveAt|Clear|SetChildIndex)', match['path'])):
                    continue
                end = _assignment_end(masked, match.start())
                found[known[match[1]], _normalized_csharp_value(source[match.start():end if end is not None else match.end()])] += 1
        # Arbitrary receiver/helper effects require the actual method body and
        # explicit responsibility selection, not a naming/getter blacklist.
        return found

    old, new = features(before), features(after)
    return {kind for kind, _signature in (new - old) + (old - new)}
