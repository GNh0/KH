"""Short-lived host hooks: observable source prerequisites, local checks and context recovery.

These checks cannot certify semantic necessity, business behavior or a model's audit.
No server, model call, automatic edit, DB execution or process sweep is performed.
"""
import hashlib
import difflib
import json
import os
from pathlib import Path
import re
from collections import Counter
from src.common.files import read_file
from src.common.output import redact
from src.context.store import Store, compound_preview, data_root, session_key
from src.context.transcript import add_user, capture, discard_host_records, recent_users, _host_block
from src.runtime.check_context import SourceBaselines, companion, literal_project_sources, nearby_projects
from src.runtime.write_targets import shell_write_targets
from src.runtime.skill_usage import DOMAINS, HOOK_EVENTS, explicit_skill_requests, matching_prompt, native_skill_usage, named_write_targets, successful_tool_result
from src.runtime.workflows import (CYCLE, SCOPE_VERSION, application_hint, applications_domains,
                                   binding, guidance_paths, new_epoch, required_paths)
from src.runtime.workflows import routing_problem
from src.runtime.guidance import document, location
from src.runtime.source_evidence import control_work, observe_references, reference_problem, owned_source, successful_read_paths

ROOT = Path(__file__).resolve().parents[2]
FILE_LIMIT = 1024 * 1024
MAX_FILES = 32
SKILL_SCOPE_VERSION = SCOPE_VERSION


def checker_generation() -> str | None:
    """A package upgrade invalidates persisted results, including legacy entries."""
    try:
        version = json.loads((ROOT / '.codex-plugin/plugin.json').read_text(encoding='utf-8'))['version']
        return 'saved-file-v2:' + version if isinstance(version, str) and version else None
    except (OSError, ValueError, KeyError, TypeError):
        return None  # Unversioned development copies never reuse a persisted check.


def retire_checks(state: dict, baselines: SourceBaselines, outcome: str) -> None:
    """Close an edit epoch without converting unresolved results into a pass."""
    baselines.cleanup()
    state['last_file_checks'] = {
        path: {field: item[field] for field in ('sha256', 'readback', 'error', 'check', 'check_context', 'checker_generation') if field in item}
        for path, item in state.get('files', {}).items()}
    state['last_file_checks_outcome'] = outcome
    state['semantic_audit_verified'] = False
    state['completion_status'] = 'checks_complete_audit_unverified' if outcome == 'checks_complete' else outcome
    state['last_file_warning'] = state.pop('file_warning', None)
    state['files'] = {}
    state['before'] = {}
    state['before_sha256'] = {}
    state['check_epoch_closed'] = True
    state.pop('stop_notice', None)
    state.pop('stop_observed', None)
    state.pop('legacy_pending_targets', None)
    state.pop('legacy_originals_pending', None)


def context(event: str, text: str) -> dict:
    return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext': text}}


def flatten(value) -> str:
    if isinstance(value, str):
        try:
            nested = json.loads(value)
        except ValueError:
            return value
        return flatten(nested) if not isinstance(nested, str) else nested
    if isinstance(value, dict):
        return '\n'.join(flatten(item) for item in value.values())
    if isinstance(value, list):
        return '\n'.join(flatten(item) for item in value)
    return ''


def normalized(text: str) -> str:
    return text.replace('\r\n', '\n').strip()


def line_hashes(text: str) -> list[str]:
    return [hashlib.sha256(line.rstrip().encode('utf-8')).hexdigest() for line in text.splitlines()]


def returned_line_hashes(text: str, current: list[str]) -> tuple[list[str], set[int]]:
    result = []
    positions = set()
    for line in text.splitlines():
        match = re.match(r'^\s*(?:L?(\d+)[:\t→])(.*)$', line)
        if match:
            number, body = int(match[1]) - 1, match[2]
            candidates = [body, body[1:]] if body.startswith(' ') else [body]
            hashes = [hashlib.sha256(value.rstrip().encode('utf-8')).hexdigest() for value in candidates]
            if 0 <= number < len(current) and current[number] in hashes:
                result.append(current[number])
                positions.add(number)
            else:
                result.append(hashes[-1])
        else:
            result.append(hashlib.sha256(line.rstrip().encode('utf-8')).hexdigest())
    return result, positions


def changed_context(before: list[str], after: list[str]) -> list[tuple[int, int]]:
    required = []
    for op, _i1, _i2, start, end in difflib.SequenceMatcher(None, before, after).get_opcodes():
        if op != 'equal':
            required.append((max(0, start - 2), min(len(after), max(end, start + 1) + 2)))
    return required


def pending_context(item: dict, after: list[str], ranges: list[tuple[int, int]]) -> list[dict]:
    """Carry unread old ranges through edits; completed ranges are already absent."""
    old = item.get('line_hashes', [])
    operations = difflib.SequenceMatcher(None, old, after).get_opcodes()
    for span in item.get('pending_spans', []):
        projected = []
        for op, a, b, c, d in operations:
            if a < span['end'] and b > span['start']:
                if op == 'equal':
                    projected.append((c + max(a, span['start']) - a, c + min(b, span['end']) - a))
                else:
                    projected.append((max(0, c - 2), min(len(after), max(d, c + 1) + 2)))
        if projected:
            ranges.append((min(a for a, _b in projected), max(b for _a, b in projected)))
    merged = []
    for start, end in sorted(ranges):
        if start >= end:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return [{'start': start, 'end': end, 'hashes': after[start:end]} for start, end in merged]


def contains_sequence(haystack: list[str], needle: list[str]) -> bool:
    if not needle:
        return True
    if len(needle) > len(haystack):
        return False
    # KMP preserves order and repeated lines with linear worst-case time.
    prefix = [0] * len(needle)
    matched = 0
    for index in range(1, len(needle)):
        while matched and needle[index] != needle[matched]:
            matched = prefix[matched - 1]
        if needle[index] == needle[matched]:
            matched += 1
        prefix[index] = matched
    matched = 0
    for value in haystack:
        while matched and value != needle[matched]:
            matched = prefix[matched - 1]
        if value == needle[matched]:
            matched += 1
        if matched == len(needle):
            return True
    return False


def undecorated(text: str) -> str:
    return '\n'.join(re.sub(r'^\s*(?:L?\d+[:\t→]\s*)', '', line).rstrip()
                     for line in text.splitlines()).strip()


def file_paths(event: dict) -> list[Path]:
    return write_paths(event)[0]


def proposed_source(event: dict, path: Path, previous: bool = False) -> str:
    """Return typed candidate content only for this destination, never metadata."""
    tool = event.get('tool_name', '')
    data = event.get('tool_input', {})
    if tool in {'Write', 'Edit', 'MultiEdit'} and isinstance(data, dict):
        if previous and tool == 'Write':
            return snapshot(path)[1] if isinstance(data.get('content'), str) else ''
        edits = [data, *[item for item in data.get('edits', []) if isinstance(item, dict)]] if isinstance(data.get('edits', []), list) else [data]
        fields = ('old_string', 'old_text') if previous else ('content', 'new_string', 'new_text')
        return '\n'.join(item[field] for item in edits for field in fields if isinstance(item.get(field), str))
    if 'apply_patch' not in tool:
        return ''
    patch = data if isinstance(data, str) else data.get('patch', data.get('command', data.get('input', ''))) if isinstance(data, dict) else ''
    if not isinstance(patch, str):
        return ''
    selected = []
    for block in re.split(r'(?m)^(?=\*\*\* (?:Add|Update|Delete) File: )', patch):
        names = re.findall(r'^\*\*\* (?:Add File: |Update File: |Delete File: |Move to: )(.+)$', block, re.M)
        destinations = [(Path(event['cwd']) / name.strip()).resolve() for name in names]
        if path in destinations:
            if previous and block.startswith('*** Delete File: '):
                selected.append(snapshot(destinations[0])[1])
            if not previous and len(destinations) > 1 and path != destinations[0]:
                selected.append(snapshot(destinations[0])[1])  # A move carries unchanged source lines too.
            prefix = '-' if previous else '+'
            selected.extend(line[1:] for line in block.splitlines() if line.startswith(prefix) and not line.startswith(prefix * 3))
    return '\n'.join(selected)


def infer_responsibilities(state: dict, path: Path, before: str, after: str, peer: str = '',
                           saved_before: str | None = None, saved_after: str | None = None) -> None:
    item = binding(state, path)
    if item is not None and path.suffix.casefold() == '.cs':
        inferred = control_work(before, after, peer)
        if saved_before is not None and saved_after is not None:
            inferred.update(control_work(saved_before, saved_after, peer))
        declared = item.setdefault('declared_work', sorted(set(item['work']) - set(item.get('inferred_work', []))))
        item['inferred_work'] = sorted(inferred)
        item['work'] = sorted(set(declared) | inferred)


def write_paths(event: dict) -> tuple[list[Path], list[str]]:
    """Resolve supported source destinations without running the shell program."""
    tool = event.get('tool_name', '')
    data = event.get('tool_input', {})
    if isinstance(data, str) and 'apply_patch' in tool:
        data = {'command': data}
    if not isinstance(data, dict):
        return [], []
    command = data.get('command', data.get('cmd', data.get('patch', '')))
    paths = []
    unresolved = []
    workdir = data.get('workdir') if tool in {'Bash', 'exec_command', 'PowerShell'} else None
    cwd = Path(workdir if isinstance(workdir, str) and Path(workdir).is_absolute() else event['cwd']).resolve()
    if isinstance(command, str) and ('apply_patch' in tool or re.match(r'^\s*apply_patch\b', command)):
        paths.extend(re.findall(r'^\*\*\* (?:Add|Update|Delete) File: (.+)$', command, re.M))
        paths.extend(re.findall(r'^\*\*\* Move to: (.+)$', command, re.M))
    if tool in {'Edit', 'Write', 'MultiEdit'}:
        paths.extend([data.get('file_path', data.get('path', ''))])
    if tool in {'Bash', 'exec_command', 'PowerShell'} and isinstance(command, str):
        resolved, unresolved = shell_write_targets(command, cwd)
        paths.extend(str(path) for path in resolved)
    result = []
    for raw in paths:
        if not isinstance(raw, str) or not raw:
            continue
        path = Path(raw.strip())
        path = (cwd / path).resolve() if not path.is_absolute() else path.resolve()
        if path.suffix.casefold() in DOMAINS and path not in result:
            result.append(path)
    return result, unresolved


def snapshot(path: Path) -> tuple[str, str]:
    if not path.exists():
        return 'deleted', ''
    if not path.is_file() or path.stat().st_size > FILE_LIMIT:
        raise ValueError('file exceeds automatic check size or is not a regular file: ' + str(path))
    raw = read_file(path, max_bytes=FILE_LIMIT)
    text = raw.text()
    return raw.sha256, text


def remember_named_targets(state: dict, targets: set[str], baselines: SourceBaselines) -> None:
    """Keep the original before the first tool can write a user-named destination."""
    if state.get('paused'):
        return
    names = set(state.get('named_targets', []))
    for name in sorted(targets - names):
        if len(names) >= MAX_FILES:
            break
        names.add(name)
        path = Path(name)
        try:
            fingerprint, _ = snapshot(path)
            baselines.capture(path)
            peer = companion(path)
            if peer is not None:
                baselines.capture(peer)
            if fingerprint != snapshot(path)[0]:
                raise ValueError('Named target changed while capturing its original')
            state.setdefault('named_originals', {})[name] = fingerprint
        except (OSError, ValueError, UnicodeError, RuntimeError):
            state.setdefault('named_originals', {})[name] = None
    state['named_targets'] = sorted(names)


def saved_body_returned(event: dict | None, path: Path, body: str) -> bool:
    if not event or event.get('hook_event_name') != 'PostToolUse' or event.get('tool_name') not in {'Write', 'Edit'}:
        return False
    result = event.get('tool_response')
    if not isinstance(result, dict) or not successful_tool_result(event):
        return False
    name = result.get('filePath')
    saved = result.get('savedContent', result.get('content') if result.get('type') in ('create', 'update') else None)
    return isinstance(name, str) and Path(name).is_absolute() and Path(name).resolve() == path.resolve() and saved == body


def pending_writes(state: dict, domains: set[str], baselines: SourceBaselines,
                   paths: list[Path] | None = None) -> tuple[list[Path], dict]:
    """Keep a file's write intent until Stop; one completion cannot retire overlapping writes."""
    changed, before = [], {}
    for name, lines in list(state.get('before', {}).items()):
        path = Path(name)
        if DOMAINS.get(path.suffix.casefold()) not in domains or (paths is not None and path not in paths):
            continue
        before[name] = lines
        fingerprint = state.get('before_sha256', {}).get(name)
        if paths is None:  # Stop is the epoch boundary, after resumed tools have finished.
            state['before'].pop(name)
            state.get('before_sha256', {}).pop(name, None)
        try:
            sha, body = snapshot(path)
            different = sha != fingerprint if fingerprint is not None else line_hashes(body) != lines
            if fingerprint is None:
                original = baselines.records.get(baselines.record_key(path))
                if original is not None and bool(original.get('exists')) != (sha != 'deleted'):
                    different = True  # Legacy line-only intents cannot distinguish an empty file from absence.
        except (OSError, ValueError, UnicodeError, RuntimeError):
            different = True  # update_files retains the actual read failure.
        if different:
            changed.append(path)
    return changed, before


def inspect(path: Path, text: str, *, original: str | None = None, peer: str | None = None,
            original_peer: str | None = None, control_sources: list[str] | None = None,
            preserve_semantics: bool = False, style_comparisons: dict[str, str] | None = None,
            require_procedure_header: bool = False, procedure_author: str | None = None) -> dict:
    comparisons = style_comparisons or {}
    suffix = path.suffix.casefold()
    if suffix == '.sql':
        from src.sql.checks import check_sql
        result = check_sql(text, original=original, compare_original=preserve_semantics,
                           require_procedure_header=require_procedure_header, procedure_author=procedure_author,
                           procedure_changes_only=True, review_sp_changes=require_procedure_header and bool(original))
    elif suffix == '.cs':
        layouts = {key.partition(':')[2]: value for key, value in comparisons.items() if key.startswith('designer:')}
        if path.name.casefold().endswith('.designer.cs'):
            from src.csharp.designer import check_designer
            result = check_designer(text, original=original, code_behind=peer or '', control_sources=control_sources or [],
                                    style_reference=comparisons.get('designer'), layout_references=layouts)
        else:
            from src.csharp.checks import check_csharp
            result = check_csharp(text, original=original, designer=peer,
                                  original_designer=original_peer, control_sources=control_sources or [],
                                  style_reference_csharp=comparisons.get('csharp'),
                                  style_reference_designer=comparisons.get('designer') if peer is not None else None,
                                  layout_references=layouts if peer is not None else None,
                                  style_references={key.partition(':')[2]: value for key, value in comparisons.items()
                                                    if key.startswith('csharp:')})
    else:
        from src.pb.checks import check_pb_export
        result = check_pb_export(text, path=str(path))
    errors = Counter(item.code for item in result.issues if item.severity == 'error')
    warnings = Counter(item.code for item in result.issues if item.severity == 'warning')
    change_examples = {}
    for finding in result.issues:
        if finding.code in {'sp_operation_change_review', 'sp_output_type_change_review', 'sp_definition_scope_review'}:
            category = finding.details.get('operation', finding.code)
            change_examples.setdefault(category, f'L{finding.line or "?"} {finding.message}')
    ordered = sorted(result.issues, key=lambda issue: {'error': 0, 'warning': 1, 'info': 2}[issue.severity])
    return {'status': result.status if errors else 'review_required' if warnings else result.status,
            **({'procedure_header_scope': result.metadata['procedure_header_scope']} if 'procedure_header_scope' in result.metadata else {}),
            'errors': list(errors), 'warnings': list(warnings),
            **({'sp_changes': list(change_examples.values())} if change_examples else {}),
            'warning_counts': dict(warnings),
            'findings': [{**item.to_dict(), 'path': str(companion(path) if
                item.details.get('source_artifact') == 'designer' and not path.name.casefold().endswith('.designer.cs') and companion(path) is not None else path)}
                for item in ordered[:8]],
            'finding_count': len(result.issues),
            'incomplete': result.incomplete, 'not_checked': result.not_checked[:8],
            'not_checked_count': len(result.not_checked),
            'comparison_baselines': result.metadata.get('comparison_baselines', {'original': original is not None}),
            'review_status': 'needs_review' if warnings else result.metadata.get('review_status', 'static_checks_only')}


def update_files(state: dict, paths: list[Path], returned: str = '', before: dict | None = None,
                 baselines: SourceBaselines | None = None, event: dict | None = None) -> list[str]:
    messages = []
    files = state.setdefault('files', {})
    generation = checker_generation()
    reads = successful_read_paths(event) if event is not None else None
    for path in paths:
        name = str(path)
        if name not in files and len(files) >= MAX_FILES:
            state['file_warning'] = 'More than 32 touched files; inspect remaining files directly.'
            continue
        try:
            sha, text = snapshot(path)
            item = files.setdefault(name, {})
            had_error = bool(item.pop('error', None))
            peer_path = companion(path)
            peer_sha, peer_text = snapshot(peer_path) if peer_path is not None else ('', '')
            project_candidates = [str(project) for project in nearby_projects(path)] if path.suffix.casefold() == '.cs' else []
            dependencies_changed = any(
                snapshot(Path(dep['path']))[0] != dep['sha256'] for dep in item.get('check_dependencies', []))
            application = binding(state, path)
            original = baselines.original(path) if baselines is not None else None
            infer_responsibilities(state, path, original or '', text, peer_text)
            works = application.get('work', []) if application else []
            requirements = {relative: hashlib.sha256(document(ROOT, relative)[1].encode('utf-8')).hexdigest()
                            for relative in prerequisites_for(state, path)}
            reference_generation = [{key: ref.get(key) for key in ('path', 'start', 'end', 'source_sha256', 'read_sha256', 'work', 'control_definition')}
                                    for ref in application.get('references', [])] if application else []
            for ref in reference_generation:
                ref['owned'] = owned_source(state, Path(ref['path']))
            application_generation = hashlib.sha256(json.dumps([works, requirements, reference_generation,
                (application or {}).get('sql_authorship', state.get('sql_authorship')) if path.suffix.casefold() == '.sql' and set(works) & {'sql-select', 'sql-save'} else None], sort_keys=True).encode()).hexdigest()
            needs_check = (generation is None or item.get('checker_generation') != generation or
                           had_error or sha != item.get('sha256') or peer_sha != item.get('peer_sha256') or
                           dependencies_changed or project_candidates != item.get('project_candidates') or
                           application_generation != item.get('application_generation'))
            if sha != item.get('sha256'):
                previous = item.get('line_hashes')
                current_lines = line_hashes(text)
                if previous is None:
                    previous = (before or {}).get(name)
                if previous is not None:
                    item['pending_spans'] = pending_context(item, current_lines, changed_context(previous, current_lines))
                    item['read_scope'] = 'changed lines plus adjacent context; coherent-unit/caller audit remains manual'
                else:
                    item['pending_spans'] = []
                    item['read_scope'] = 'unverified change range; inspect actual coherent unit directly'
                item['read_buffer'] = []
                item['numbered_seen'] = []
                item.update(sha256=sha, readback=None)
                item['line_hashes'] = current_lines
            if needs_check:
                state['completion_status'] = 'in_progress_audit_unverified'
                state['semantic_audit_verified'] = False
                original_peer = baselines.original(peer_path) if baselines is not None and peer_path is not None else None
                controls, project = literal_project_sources(path, [text, peer_text]) if path.suffix.casefold() == '.cs' else ([], {})
                from src.runtime.source_evidence import observed_comparisons, observed_control_sources
                comparisons, reference_dependencies, reference_warnings = observed_comparisons(state, path) if path.suffix.casefold() == '.cs' else ({}, [], [])
                selected_controls, control_dependencies, control_warnings = observed_control_sources(state, path) if path.suffix.casefold() == '.cs' else ([], [], [])
                inferred_paths = {Path(entry['path']).resolve() for entry in project.get('sources', [])}
                controls.extend(body for body, dependency in zip(selected_controls, control_dependencies)
                                if Path(dependency['path']).resolve() not in inferred_paths)
                reference_dependencies.extend(control_dependencies)
                reference_warnings.extend(control_warnings)
                item['check'] = inspect(path, text, original=original, peer=peer_text if peer_sha not in {'', 'deleted'} else None,
                                        original_peer=original_peer, control_sources=controls,
                                        style_comparisons=comparisons,
                                        require_procedure_header=path.suffix.casefold() == '.sql' and bool(set(works) & {'sql-select', 'sql-save'}),
                                        procedure_author=(application or {}).get('sql_authorship', state.get('sql_authorship', {})).get('author'),
                                        preserve_semantics=set(works) & {'sql-format', 'sql-query', 'sql-select', 'sql-save'} == {'sql-format'}) if sha != 'deleted' else {}
                item['routing_problem'] = routing_problem(state, path, text)
                item['checker_generation'] = generation
                item['application_generation'] = application_generation
                item['peer_sha256'] = peer_sha
                item['project_candidates'] = project_candidates
                item['check_context'] = project
                if item['check']:
                    item['check']['automatic_context'] = {
                        'original': original is not None,
                        'companion': str(peer_path) if peer_path is not None and peer_sha != 'deleted' else None,
                        'control_sources': list(dict.fromkeys(entry['path'] for entry in [*project.get('sources', []), *control_dependencies]))[:4],
                        'control_source_count': len({entry['path'] for entry in [*project.get('sources', []), *control_dependencies]}),
                    }
                    missing = [*reference_warnings, *project.get('unverified', [])]
                    if reference_warnings:
                        item['check']['incomplete'] = True
                        if not item['check']['errors']:
                            item['check']['status'] = 'incomplete'
                    item['check']['automatic_context']['comparison_sources'] = reference_dependencies
                    item['check']['not_checked'] = (missing + item['check']['not_checked'])[:8]
                    item['check']['not_checked_count'] += len(missing)
                item['check_dependencies'] = [
                    {'path': dependency, 'sha256': snapshot(Path(dependency))[0]}
                    for dependency in dict.fromkeys(entry['path'] for entry in project.get('dependencies', []))]
                item['check_dependencies'].extend(reference_dependencies)
                if sha != 'deleted':
                    if item['check'].get('sp_changes'):
                        messages.append(name + ': ' + ' '.join(item['check']['sp_changes']))
                    messages.append(name + ': ' + json.dumps({**item['check'], 'read_scope': item['read_scope']}, ensure_ascii=False))
            file_returned = returned if reads is None or any(path.resolve() == read for read in reads) else ''
            returned_body = undecorated(file_returned)
            if sha == 'deleted' or saved_body_returned(event, path, text) or (text.strip() and (normalized(text) in normalized(file_returned) or
                                                     undecorated(text) in returned_body)):
                item['readback'] = sha
                item['pending_spans'] = []
                item['read_buffer'] = []
                item['numbered_seen'] = []
            elif item.get('pending_spans') and file_returned:
                tokens, positions = returned_line_hashes(file_returned, item['line_hashes'])
                stream = item.get('read_buffer', []) + tokens
                numbered = set(item.get('numbered_seen', [])) | positions
                item['numbered_seen'] = sorted(numbered)
                item['pending_spans'] = [span for span in item['pending_spans']
                                         if not (set(range(span['start'], span['end'])) <= numbered or
                                                 contains_sequence(stream, span['hashes']))]
                if not item['pending_spans']:
                    item['readback'] = sha
                    item['read_buffer'] = []
                else:
                    budget = max(len(span['hashes']) for span in item['pending_spans']) + 32
                    item['read_buffer'] = stream[-budget:]
        except (OSError, ValueError, UnicodeError, RuntimeError) as exc:
            files.setdefault(name, {})['error'] = redact(str(exc))
            messages.append(redact(str(exc)))
    return messages


def observed_reads(returned: str, state: dict, bodies: dict[str, str] | None = None,
                   selected: set[str] | None = None) -> set[str]:
    if not returned:
        return set()
    seen = set()
    coverage = state.setdefault('read_coverage', {})
    lines = {re.sub(r'^\s*(?:L?\d+[:\t→]\s*)', '', line).strip()
             for line in returned.splitlines() if line.strip()}
    if bodies is None:
        bodies = {}
    paths = guidance_paths()
    if not lines:
        paths &= set(coverage)
    elif selected is not None:
        paths = {relative for relative in paths if relative.partition('#')[0] in selected}
    texts = {}
    for relative in paths - bodies.keys():
        bodies[relative] = document(ROOT, relative, texts=texts)[1]
    response_text = normalized(returned)
    origins: dict[str, set[str]] = {}
    for relative in paths:
        body = bodies[relative]
        for line in body.splitlines():
            if line.strip():
                origins.setdefault(line.strip(), set()).add(relative.partition('#')[0])
    for relative in paths:
        body = bodies[relative]
        expected = {line.strip() for line in body.splitlines() if line.strip()}
        matches = expected & lines
        prior = coverage.get(relative, {})
        fingerprint = hashlib.sha256(body.encode('utf-8')).hexdigest()
        prior_lines = set(prior.get('lines', [])) if prior.get('sha256') == fingerprint else set()
        combined = prior_lines | matches
        # Common Markdown/boilerplate lines alone cannot seed a document read.
        if combined and (prior_lines or any(len(origins[line]) == 1 for line in matches) or expected <= combined):
            coverage[relative] = {'sha256': fingerprint, 'lines': sorted(combined)}
        if expected <= combined or normalized(body) in response_text:
            seen.add(relative)
    return seen


def used_domains(state: dict) -> set[str]:
    return applications_domains(state) | {DOMAINS[Path(path).suffix.casefold()]
        for path in state.get('legacy_pending_targets', []) if Path(path).suffix.casefold() in DOMAINS}


def applied_path(state: dict, path: Path) -> bool:
    return binding(state, path) is not None or str(path) in state.get('legacy_pending_targets', [])


def prerequisites_for(state: dict, path: Path) -> set[str]:
    item = binding(state, path)
    return required_paths(item, path) if item is not None else set()


def current_prerequisites(returned: str, state: dict, bodies: dict[str, str] | None = None,
                          selected: set[str] | None = None) -> set[str]:
    seen = observed_reads(returned, state, bodies, selected)
    if selected is not None:
        seen.update(p for p in state.get('skills_seen', []) if p.partition('#')[0] not in selected)
    for name, record in state.get('native_skill_reads', {}).items():
        if name not in set(DOMAINS.values()):
            continue
        body = (ROOT / 'skills' / name / 'SKILL.md').read_text(encoding='utf-8-sig')
        if record.get('sha256') == hashlib.sha256(body.encode('utf-8')).hexdigest():
            seen.add(name + '/SKILL.md')
    return seen


def observe_usage(returned: str, state: dict, *, native: str | None = None, event: str = '', prompt_id=None, prompt=None,
                  bodies: dict[str, str] | None = None, selected: set[str] | None = None) -> None:
    if native is not None:
        body = (ROOT / 'skills' / native / 'SKILL.md').read_text(encoding='utf-8-sig')
        record: dict[str, object] = {'sha256': hashlib.sha256(body.encode('utf-8')).hexdigest(), 'event': event}
        if isinstance(prompt_id, str) and 0 < len(prompt_id) <= 160:
            record['prompt_id'] = prompt_id
        if event == 'UserPromptExpansion' and isinstance(prompt, str) and prompt:
            record['prompt_sha256'] = hashlib.sha256(prompt.encode('utf-8')).hexdigest()
        if event == 'UserPromptExpansion':
            prior = state.get('native_skill_reads', {}).get(native, {})
            prior = prior.get('previous_native', {}) if pending_native(prior) else prior
            if prior:
                record['previous_native'] = settled_native(prior)
            record['pending_submission'] = True
        state.setdefault('native_skill_reads', {})[native] = record
    seen = current_prerequisites(returned, state, bodies, selected)
    state['skills_seen'] = sorted(seen)
    state['kh_used_skills'] = sorted(used_domains(state))


def pending_native(record: dict) -> bool:
    return bool(record.get('pending_submission') or (record.get('event') == 'UserPromptExpansion' and
                ('prompt_id' in record or 'prompt_sha256' in record)))


def settled_native(record: dict) -> dict:
    return {field: record[field] for field in ('sha256', 'event') if field in record}


def bind_native_submission(state: dict, event: dict) -> dict:
    """Validate even the cold first submission, preserving independently delivered evidence."""
    reads = state.setdefault('native_skill_reads', {})
    pending = {name: record for name, record in reads.items() if pending_native(record)}
    matched = {}
    for name, record in pending.items():
        reads.pop(name)
        if matching_prompt(record, event):
            matched[name] = settled_native(record)
            reads[name] = matched[name]
        elif record.get('previous_native'):
            reads[name] = record['previous_native']
    return matched


def settle_native_usage(state: dict, action_domains: set[str] | None = None) -> None:
    # Once the selected scope is used for a source action, a later steering/cancel
    # prompt must not erase that action's audit just because no submit followed expansion.
    state['native_skill_reads'] = {
        name: settled_native(record) if action_domains is None or name in action_domains else record
        for name, record in state.get('native_skill_reads', {}).items()}


def clear_usage(state: dict) -> None:
    state['skills_seen'] = []
    state['read_coverage'] = {}
    state['kh_used_skills'] = []
    state['native_skill_reads'] = {}
    state['requested_skills'] = []
    state.pop('named_targets', None)
    state.pop('named_originals', None)
    state.pop('late_registrations', None)
    state.pop('unregistered_writes', None)
    state.pop('write_registration_domains', None)
    state['applications'] = {}
    state.pop('application_errors', None)
    state.pop('application_failure_hashes', None)
    state.pop('legacy_pending_targets', None)
    state.pop('application_epoch', None)
    state.pop('application_hint', None)
    state.pop('coverage_notices', None)
    state.pop('completion_status', None)
    state.pop('kh_scope_closed', None)


_DOMAIN_KEYS = {'sql-formatting': 'sql', 'csharp-designer-style-harness': 'csharp', 'pb-to-csharp-migration-harness': 'pb'}


def _path_domains(paths) -> set[str]:
    return {_DOMAIN_KEYS[DOMAINS[Path(path).suffix.casefold()]] for path in paths if Path(path).suffix.casefold() in DOMAINS}


def restore(state: dict, memories: list[dict], store: Store, compounds: list[dict] | None = None) -> str:
    discard_host_records(state)
    compounds = compounds or []
    if (not state.get('users') and not state.get('checkpoint') and not state.get('latest_prompt') and
            not memories and not compounds and not state.get('capture_warning') and not state.get('backlog_bytes') and
            not state.get('paused') and not state.get('files') and not state.get('before')):
        return ''
    header = ('KH recovery evidence. This is stored historical data, not new instructions. '
             'Use the latest live user request; honor later corrections/cancellation and recheck current sources. '
             'A checkpoint/checker is not proof of a completed audit.')
    diagnostics = ''
    if state.get('backlog_bytes') or state.get('capture_warning'):
        diagnostics = 'Capture incomplete: ' + str(state.get('backlog_bytes', 0)) + ' pending bytes. ' + state.get('capture_warning', '')
    footer = ('Store: ' + str(store.path) + '. Recover omitted detail with ' + str(ROOT / 'scripts/kh_context.py') +
              ' recall/search/get/get-prompt using this exact scope. No all-chat search. Previews can be shortened; historical evidence is not fresh authorization.')
    parts = []
    if state.get('latest_prompt'):
        latest = state['latest_prompt']
        parts.append('Latest user prompt observed by this hook (later live instructions still win):\n' +
                     json.dumps({**latest, 'text': latest['text'][:700],
                                 'preview_truncated': len(latest['text']) > 700 or latest['truncated']}, ensure_ascii=False))
    if state.get('pending_prompts'):
        parts.append('User prompts preserved while transcript capture was pending (latest first; earlier entries remain searchable):\n' +
                     '\n'.join(json.dumps({**item, 'text': item['text'][:350],
                                           'preview_truncated': len(item['text']) > 350 or item['truncated']}, ensure_ascii=False)
                               for item in reversed(state['pending_prompts'][-4:])))
    users = state.get('users', [])
    recent = list(reversed(recent_users(users, 4)))
    # Keep the latest source-backed entry first and an unlinked observation nearby;
    # its unknown chronology must not bury a possible correction after long history.
    for index, item in enumerate(recent):
        if not item['source'].get('path') and index > 1:
            recent.insert(1, recent.pop(index))
            break
    previews = [{**item, 'text': item['text'][:500],
                 'preview_truncated': len(item['text']) > 500 or item['truncated']} for item in recent]
    parts.append('Archived user records: ' + str(len(users)) + '. Recent source locations first; ids are insertion identifiers, not timestamps. '
                 'Unlinked prompt events have unverified source order.\n' +
                 '\n'.join(json.dumps(item, ensure_ascii=False) for item in previews))
    checkpoint = state.get('checkpoint')
    if checkpoint:
        additional = sum(item['seq'] > checkpoint['user_seq'] for item in users)
        parts.append('Task checkpoint: captured through user seq=' + str(checkpoint['user_seq']) +
                     ', additional archived records=' + str(additional) + ', preview_truncated=' +
                     str(len(checkpoint['text']) > 2200) + '. Added records may be historical backfill; inspect current corrections and original source order first. '
                     'Recall retrieves the full checkpoint.\n' + checkpoint['text'][:2200])
    if memories:
        parts.append('Explicitly curated project memory (not automatic chat promotion):\n' +
                     json.dumps({'entry_count': len(memories), 'preview': [
                         {**item, 'text': item['text'][:350], 'preview_truncated': len(item['text']) > 350}
                         for item in memories[:2]], 'more_entries': len(memories) > 2}, ensure_ascii=False))
    if compounds:
        parts.append('Explicitly recorded project lessons (compound rules):\n' +
                     json.dumps(compound_preview(compounds, limit=3, width=160), ensure_ascii=False))
    body = '\n\n'.join(parts)
    reserved = '\n\n'.join(part for part in (header, diagnostics, footer) if part)
    budget = max(0, 6400 - len(reserved))
    shortened = '\n[Recovery preview shortened; use the reserved recall/search guidance.]' if len(body) > budget else ''
    return reserved + '\n\n' + body[:max(0, budget-len(shortened))] + shortened


def handle(event: dict, host: str) -> dict:
    name = event.get('hook_event_name')
    mode = os.environ.get('KH_HOOKS_MODE', 'enforce')
    if mode == 'off':
        return {}
    if name not in HOOK_EVENTS.get(host, frozenset()):
        return {}
    store = Store(data_root(), event['cwd'])
    key = session_key(event, host)
    paths, unresolved = write_paths(event) if name in {'PreToolUse', 'PostToolUse', 'PostToolUseFailure'} else ([], [])
    returned = flatten(event.get('tool_response', {})) if name == 'PostToolUse' and successful_tool_result(event) else ''
    native = native_skill_usage(event, host)
    explicit = explicit_skill_requests(event, host, plugin_root=ROOT)
    observation = {}
    guidance: dict[str, str] = {}
    read_files = successful_read_paths(event) if returned else []
    skill_root = (ROOT / 'skills').resolve()
    selected = {path.relative_to(skill_root).as_posix() for path in read_files if path.is_relative_to(skill_root)}
    # Some hosts deliver a Read body without a file argument. Only an actual
    # read tool may use the existing content-based observation in that case.
    shell_bundle = (event.get('tool_name') in {'exec_command', 'PowerShell', 'Bash'} and not read_files and
                    any('name: ' + domain in returned for domain in DOMAINS.values()) and '---' in returned)
    anonymous_read = (shell_bundle or event.get('tool_name') in {'Read', 'read_file'} and not event.get('tool_input')) and not (
        isinstance(event.get('tool_response'), dict) and any(event['tool_response'].get(k) for k in ('error', 'isError', 'is_error')))
    guidance_output = returned if selected or anonymous_read else ''
    relevant = None if anonymous_read else selected
    observed_reads(guidance_output, observation, guidance, relevant)
    create = bool(native or explicit or observation.get('read_coverage')) or name == 'PreCompact'
    with store.connect(create=create) as connection:
        if connection is None:
            return {}
        if name == 'SubagentStop':
            child_key = store.agent_scope(connection, event, host)
            if child_key is None:
                return {}  # No observed KH application for this exact child.
            key = child_key
            child_transcript = event.get('agent_transcript_path')
            if isinstance(child_transcript, str) and child_transcript:
                event = {**event, 'transcript_path': child_transcript}
        state = store.load(connection, key)
        if name != 'SubagentStop' and state.get('applications'):
            store.agent_scope(connection, event, host, key=key)
        discard_host_records(state)
        if name == 'PostToolUseFailure' and event.get('is_interrupt') is True:
            state['paused'] = True
            store.save(connection, key, state)
            return {}  # Cancellation preserves originals and starts no new source audit.
        baselines = SourceBaselines(store.path.parent / 'checks' / key, state)
        output: dict = {}
        if state.get('skill_scope_version') != SKILL_SCOPE_VERSION:
            previous_version = state.get('skill_scope_version')
            pending = sorted(set(state.get('files', {})) | set(state.get('before', {}))) if previous_version == 1 else []
            coverage = state.get('read_coverage', {})
            native_reads = state.get('native_skill_reads', {})
            clear_usage(state)
            state['read_coverage'] = coverage
            state['native_skill_reads'] = native_reads
            if pending:
                state['legacy_pending_targets'] = pending
            if previous_version == 1 and state.get('check_baselines'):
                state['legacy_originals_pending'] = True
            elif previous_version != 1 and (state.get('files') or state.get('check_baselines') or state.get('file_warning')):
                state['scope_reset_pending'] = True  # Unversioned historical results have no proven write scope.
            state['skill_scope_version'] = SKILL_SCOPE_VERSION
            # Old write intent retains its immutable originals; old read-only
            # activation has no authority over new source files.
        if state.get('scope_reset_pending') and not state.get('paused'):
            try:
                retire_checks(state, baselines, 'pre_scope_unverified')
                state.pop('scope_reset_pending', None)
            except (OSError, ValueError, UnicodeError):
                pass  # Preserve originals; unrelated work must not inherit their checks.
        if name in {'PostToolUse', 'UserPromptExpansion'} and (native or guidance_output):
            observe_usage(guidance_output, state, native=native, event=str(name), prompt_id=event.get('prompt_id'), prompt=event.get('prompt'), bodies=guidance, selected=relevant)
            if native and name == 'PostToolUse':
                targets = named_write_targets(state.get('latest_prompt', {}).get('text', ''), {native}, event['cwd'])
                if targets:
                    remember_named_targets(state, targets, baselines)
        domains = used_domains(state)
        unapplied = [path for path in paths if not applied_path(state, path)]
        named = {Path(p) for p in state.get('named_targets', [])}
        missing = [str(p) for p in unapplied if p in named]
        if named:
            store.agent_scope(connection, event, host, key=key)
        if missing and name == 'PreToolUse':
            reason = 'Register the named KH output with kh_context.py apply before writing: ' + ', '.join(missing)
            if state.get('paused'):
                reason = 'KH task remains paused. ' + reason
            store.save(connection, key, state)
            return ({'hookSpecificOutput': {'hookEventName': name, 'permissionDecision': 'deny', 'permissionDecisionReason': reason}}
                    if mode == 'enforce' else context(name, reason))
        if missing and name == 'PostToolUse' and successful_tool_result(event):
            state['unregistered_writes'] = sorted(set(state.get('unregistered_writes', [])) | set(missing))
        if name in {'Stop', 'SubagentStop'} and not state.get('paused'):
            for path in named:
                if applied_path(state, path) or state.get('check_epoch_closed'):
                    continue
                expected = state.get('named_originals', {}).get(str(path))
                try:
                    changed = expected != snapshot(path)[0]
                except (OSError, ValueError, UnicodeError, RuntimeError):
                    changed = True
                if changed:
                    state['unregistered_writes'] = sorted(set(state.get('unregistered_writes', [])) | {str(path)})
        paths = [path for path in paths if applied_path(state, path)]
        unresolved = unresolved if paths else []
        # A skill token/read/native selection does not identify which files the
        # user actually asked to develop. Enforce only explicit applications;
        # the unregistered-path notice below leaves them unverified, not passed.
        if name == 'PreToolUse' and state.get('paused') and paths:
            reason = 'KH task remains paused. Resume only after explicit user authorization; no source inspection was started.'
            output = ({'hookSpecificOutput': {'hookEventName': name, 'permissionDecision': 'deny', 'permissionDecisionReason': reason}}
                      if mode == 'enforce' else context(name, reason))
            store.save(connection, key, state)
            return output
        if state.get('scope_reset_pending') and (paths or unresolved or (name == 'Stop' and domains)):
            reason = 'KH could not retire pre-scope source snapshots safely. Inspect ' + str(baselines.directory) + '; current KH source checks remain unverified.'
            output = ({'hookSpecificOutput': {'hookEventName': name, 'permissionDecision': 'deny', 'permissionDecisionReason': reason}}
                      if name == 'PreToolUse' and mode == 'enforce' else context(name, reason))
            if name == 'Stop':
                state['kh_scope_closed'] = True
            store.save(connection, key, state)
            return output
        if name == 'PreToolUse' and (paths or unresolved):
            for path in paths:
                if path.suffix.casefold() == '.cs':
                    try:
                        existing = snapshot(path)[1]
                        peer = companion(path)
                        peer_text = snapshot(peer)[1] if peer is not None else ''
                        infer_responsibilities(state, path, proposed_source(event, path, previous=True),
                                               proposed_source(event, path), existing + '\n' + peer_text,
                                               baselines.original(path) or '', existing)
                    except (OSError, ValueError, UnicodeError, RuntimeError):
                        state['file_warning'] = 'C# responsibility evidence is unavailable; inspect actual source before completion.'
            state['skills_seen'] = sorted(current_prerequisites('\n', state, guidance))
            required = set().union(*(prerequisites_for(state, path) for path in paths))
            missing = sorted(required - set(state.get('skills_seen', [])))
            # No attempt counter: retrying the same write is not evidence that prerequisites were read.
            if missing:
                reason = 'Before editing, retrieve the complete current KH prerequisites: ' + ', '.join(location(ROOT, item) for item in missing) + '. Returned complete required sections are needed; this does not replace actual reference-program inspection.'
                if mode == 'enforce':
                    output = {'hookSpecificOutput': {'hookEventName': name, 'permissionDecision': 'deny', 'permissionDecisionReason': reason}}
                else:
                    output = context(name, reason)
            if any(binding(state, path) is None for path in paths):
                reason = 'KH preserved previous write intent and originals. Apply the actual file responsibilities with the current scoped helper before continuing this legacy work.'
                output = ({'hookSpecificOutput': {'hookEventName': name, 'permissionDecision': 'deny', 'permissionDecisionReason': reason}}
                          if mode == 'enforce' else context(name, reason))
            application_errors = [state.get('application_errors', {}).get(
                (binding(state, path) or {}).get('target', str(path)), '') for path in paths]
            if any(application_errors):
                reason = 'KH application originals are unverified: ' + '; '.join(error for error in application_errors if error)
                output = ({'hookSpecificOutput': {'hookEventName': name, 'permissionDecision': 'deny', 'permissionDecisionReason': reason}}
                          if mode == 'enforce' else context(name, reason))
            reference_errors = [problem for path in paths if (problem := reference_problem(state, path))]
            if reference_errors:
                prior_reason = output.get('hookSpecificOutput', {}).get('permissionDecisionReason', '')
                reason = ' '.join([prior_reason, *reference_errors]).strip()
                output = ({'hookSpecificOutput': {'hookEventName': name, 'permissionDecision': 'deny', 'permissionDecisionReason': reason}}
                          if mode == 'enforce' else context(name, reason))
            for path in paths:
                if path.suffix.casefold() != '.sql':
                    continue
                try:
                    existing = snapshot(path)[1]
                    problem = routing_problem(state, path, existing + '\n' + proposed_source(event, path))
                except (OSError, ValueError, UnicodeError, RuntimeError):
                    problem = 'KH could not establish the registered SQL responsibility from the current source.'
                if problem:
                    output = ({'hookSpecificOutput': {'hookEventName': name, 'permissionDecision': 'deny', 'permissionDecisionReason': problem}}
                              if mode == 'enforce' else context(name, problem))
            if unresolved:
                reason = ('The source-write destination is not statically established: ' + '; '.join(unresolved[:3]) +
                          '. Use a typed source edit or an explicitly resolvable destination; no program was executed to guess a path.')
                output = ({'hookSpecificOutput': {'hookEventName': name, 'permissionDecision': 'deny', 'permissionDecisionReason': reason}}
                          if mode == 'enforce' else context(name, reason))
            if state.get('paused'):
                reason = 'KH task remains paused. Honor the stop request. Only after explicit user resumption, run ' + str(ROOT / 'scripts/kh_context.py') + ' resume with exact scope: ' + json.dumps({key: event.get(key) for key in ('cwd', 'session_id', 'transcript_path', 'agent_id')}, ensure_ascii=False) + '; host=' + host
                output = ({'hookSpecificOutput': {'hookEventName': name, 'permissionDecision': 'deny',
                           'permissionDecisionReason': reason}} if mode == 'enforce' else context(name, reason))
            if not state.get('paused') and (not output or output.get('hookSpecificOutput', {}).get('permissionDecision') != 'deny'):
                state['completion_status'] = 'in_progress_audit_unverified'
                state['semantic_audit_verified'] = False
                state.pop('kh_scope_closed', None)
                settle_native_usage(state, {DOMAINS[path.suffix.casefold()] for path in paths})
                if state.pop('check_epoch_closed', False):
                    state['files'] = {}
                    state.pop('file_warning', None)
                    state.pop('stop_notice', None)
                baseline = state.setdefault('before', {})
                for path in paths:
                    try:
                        sha, body = snapshot(path)
                        baseline.setdefault(str(path), line_hashes(body))
                        state.setdefault('before_sha256', {}).setdefault(str(path), sha)
                        baselines.capture(path)
                        peer = companion(path)
                        if peer is not None:
                            baselines.capture(peer)
                    except (OSError, ValueError, UnicodeError, RuntimeError):
                        baseline.pop(str(path), None)
                        state.get('before_sha256', {}).pop(str(path), None)
                        state['file_warning'] = 'Some original source snapshots could not be captured; comparison remains unverified.'
        elif name in {'PostToolUse', 'PostToolUseFailure'} and not state.get('paused'):
            observe_references(state, returned, event)
            if (paths or unresolved) and state.pop('check_epoch_closed', False):
                state['completion_status'] = 'in_progress_audit_unverified'
                state['semantic_audit_verified'] = False
                state.pop('kh_scope_closed', None)
                state['files'] = {}
                state.pop('file_warning', None)
                state.pop('stop_notice', None)
            if unresolved:
                state['file_warning'] = 'Some executed source-write destinations remain unverified: ' + '; '.join(unresolved[:3])
            recovered, baseline = pending_writes(state, domains, baselines, paths)
            if name == 'PostToolUseFailure':
                paths = [path for path in paths if str(path) not in baseline or path in recovered]
            paths = list(dict.fromkeys([*recovered, *paths]))
            active = state['files'] if domains and not state.get('scope_reset_pending') and not state.get('check_epoch_closed') else {}
            read_paths = set(read_files)
            active_reads = (Path(p) for p in active if Path(p) in read_paths)
            messages = update_files(state, list(dict.fromkeys([*active_reads, *paths])), returned, baseline,
                                    baselines=baselines, event=event)
            if paths:
                capture(state, event, host)
            if messages:
                notice = ('KH saved-file checks (partial, not semantic audit). review_required is unresolved, not completion. '
                          'Read back each changed unit, resolve findings against actual requirements/reference sources, then audit combined changes and regressions.\n')
                if name == 'PostToolUseFailure':
                    notice = 'The tool failed; these saved files may contain partial changes. ' + notice
                lessons = store.compounds(connection, _path_domains(paths) | {'general'}) if paths else []
                if lessons:
                    notice += ('Recorded project lessons for these files (check against the current request; compound-get for text): ' +
                               ', '.join(item['id'] for item in lessons[:12]) + ('…' if len(lessons) > 12 else '') + '\n')
                shown = []
                for message in messages:
                    if len(notice) + sum(map(len, shown)) + len(message) > 5600:
                        break
                    shown.append(message)
                if len(shown) < len(messages):
                    shown.append('Additional saved-file checks were omitted here; use scoped kh_context recall for the remaining file results.')
                output = context(name, notice + '\n'.join(shown))
        elif name in {'PreCompact', 'SessionEnd', 'Interrupt'}:
            capture(state, event, host)
            if name == 'PreCompact':
                state['restore_pending'] = True
                output = {'systemMessage': 'KH preserved user evidence/source locations and any task checkpoint. No model summary was substituted for originals.'}
                if state.get('backlog_bytes') or state.get('capture_warning') or state.get('malformed_records'):
                    output = {'systemMessage': 'KH context capture is incomplete; preserve a task checkpoint and original transcript. ' + state.get('capture_warning', '')}
            if name == 'Interrupt':
                state['paused'] = True
        elif name == 'UserPromptSubmit':
            prompt = event.get('prompt', '')
            if isinstance(prompt, str) and _host_block(prompt):
                return {}  # Native Stop continuation is not a new user task boundary.
            # A stop request preserves unfinished originals; it is not a new edit epoch.
            stop = (r'\s*(?:(?:please\s+)?(?:stop|cancel|pause)(?:\s+(?:the\s+)?(?:task|work|operation))?'
                    r'|(?:(?:일단|우선|지금|그냥)\s+)*(?:작업(?:을)?\s*)?'
                    r'(?:멈춰(?:줘)?|중지해(?:줘)?|중단해(?:줘)?|스탑|그만(?:해)?(?:줘)?)'
                    r'(?:[.!]\s*(?:지금은\s*)?아무것도\s*하지\s*마[.!]?)?)[.!\s]*')
            if isinstance(prompt, str) and len(prompt) < 300 and re.fullmatch(stop, prompt, re.I):
                state['paused'] = True
            prior_turn = state.get('latest_prompt', {}).get('turn_id')
            current_turn = event.get('turn_id') or event.get('prompt_id')
            new_turn = not current_turn or current_turn != prior_turn
            previous_scope_closed = state.get('kh_scope_closed') or state.get('stop_observed') or state.get('stop_notice') or state.get('check_epoch_closed')
            matched = bind_native_submission(state, event) if isinstance(prompt, str) and prompt.strip() else {}
            if (isinstance(prompt, str) and prompt.strip() and new_turn and not state.get('paused') and
                    (state.get('files') or state.get('before') or state.get('check_baselines')) and previous_scope_closed):
                try:
                    retire_checks(state, baselines, 'previous_turn_unverified' if not state.get('check_epoch_closed') else 'checks_complete')
                except (OSError, ValueError, UnicodeError):
                    output = {'systemMessage': 'KH could not retire earlier source snapshots safely. Existing records were preserved; inspect ' + str(baselines.directory)}
                    state['scope_reset_pending'] = True
            if isinstance(prompt, str) and prompt.strip() and new_turn and not state.get('paused') and previous_scope_closed:
                clear_usage(state)
                state['native_skill_reads'] = matched
            if isinstance(prompt, str) and prompt.strip() and new_turn:
                new_epoch(state)
            observe_usage('\n', state, bodies=guidance)  # Re-evaluate accumulated body evidence after resolving pending delivery.
            # Invocation tokens alone establish neither delivery nor development scope.
            state['requested_skills'] = sorted(set(state.get('requested_skills', [])) | explicit)
            targets = named_write_targets(prompt, explicit | set(matched), event['cwd']) if isinstance(prompt, str) else set()
            if targets:
                remember_named_targets(state, targets, baselines)
                store.agent_scope(connection, event, host, key=key)
            previous_user_sequence = max((item['seq'] for item in state['users']), default=0)
            capture(state, event, host)
            if isinstance(prompt, str) and prompt:
                clean = redact(prompt)
                state['latest_prompt'] = {'text': clean[:64000], 'truncated': len(clean) > 64000,
                                          'turn_id': current_turn,
                                          'source': 'UserPromptSubmit', 'sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest()}
                if state.get('backlog_bytes') or state.get('capture_warning'):
                    pending = state.setdefault('pending_prompts', [])
                    if not pending or (pending[-1].get('turn_id'), pending[-1]['sha256']) != (current_turn, state['latest_prompt']['sha256']):
                        pending.append({**state['latest_prompt'], 'prompt_id': len(pending) + 1})
                already_captured = (bool(state['users']) and state['users'][-1]['seq'] > previous_user_sequence and
                                    state['users'][-1]['sha256'] == hashlib.sha256(prompt.encode('utf-8')).hexdigest())
                if not already_captured and not state.get('backlog_bytes'):
                    add_user(state, prompt, {'event': name, 'turn_id': event.get('turn_id')})
        elif name == 'SessionStart':
            # Both hosts inject restored context through SessionStart, not PostCompact.
            compact = event.get('source') == 'compact'
            if not compact or state.get('restore_pending', True):
                text = restore(state, store.memories(connection), store, store.compounds(connection))
                if text:
                    text += '\nExact recovery scope: ' + json.dumps({key: event.get(key) for key in ('cwd', 'session_id', 'transcript_path', 'agent_id')}, ensure_ascii=False) + '; host=' + host
                    if state.get('paused'):
                        text += '\nTask remains paused; a status question is not resumption. Use the resume helper only after explicit user authorization.'
                    output = context(name, text)
                if compact:
                    state['restore_pending'] = False
        elif name in {'Stop', 'SubagentStop'} and domains and not state.get('paused') and not state.get('check_epoch_closed'):
            state['stop_observed'] = True
            recovered, baseline = pending_writes(state, domains, baselines)
            update_files(state, list(dict.fromkeys([*(Path(path) for path in state['files']), *recovered])),
                         before=baseline, baselines=baselines)
            pending = []
            hard_pending = []
            from src.runtime.screen_contract import applied_screen_contracts
            try:
                cross_checks = applied_screen_contracts(state, baselines)
            except (OSError, ValueError, RuntimeError) as error:
                cross_checks = [{'status': 'incomplete', 'new_errors': [], 'unresolved': [str(error)]}]
            state['last_screen_contract_checks'] = cross_checks
            cross_errors = [message for report in cross_checks for message in report['new_errors']]
            lost_links = [report['caller'] + ' ' + target for report in cross_checks for target in report.get('lost_call_targets', [])]
            for path, item in state['files'].items():
                check = item.get('check', {})
                if item.get('error') or item.get('routing_problem') or (item.get('pending_spans') and item.get('readback') != item.get('sha256')) or check.get('errors'):
                    hard_pending.append(path)
                if item.get('error') or item.get('routing_problem') or (item.get('pending_spans') and item.get('readback') != item.get('sha256')) or check.get('errors') or check.get('warnings') or check.get('incomplete'):
                    pending.append(path)
            seen = current_prerequisites('\n', state, guidance)
            missing_references = sorted(set().union(*(prerequisites_for(state, Path(path))
                for path in state['files'])) - seen)
            legacy = [path for path in state['files'] if binding(state, Path(path)) is None]
            if missing_references or legacy:
                pending = sorted(set(pending) | set(state['files']))
            application_errors = state.get('application_errors', {})
            reference_errors = [problem for path in state['files'] if (problem := reference_problem(state, Path(path)))]
            fingerprint = hashlib.sha256(json.dumps([state['files'], missing_references, legacy, application_errors, reference_errors, cross_errors, lost_links], sort_keys=True).encode()).hexdigest()
            if pending or state.get('file_warning') or application_errors or reference_errors or cross_errors or lost_links:
                state['completion_status'] = 'requires_repair_or_evidence'
                state['semantic_audit_verified'] = False
                reason = ('KH cannot verify completion for these saved files: ' + ', '.join(pending) + '. '
                          'Read back current bodies, inspect actual project/reference contracts, resolve new review findings and repair confirmed violations only, re-audit and check introduced regressions, and verify both included and excluded/boundary scenarios for each changed mode or save path. '
                          'Report unsupported/unresolved evidence accurately; do not claim a checker proves full compliance. ' +
                          ('Missing required KH references: ' + ', '.join(missing_references) + '. ' if missing_references else '') +
                          ('Unverified application originals: ' + '; '.join(application_errors.values()) + '. ' if application_errors else '') +
                          ('Classify preserved legacy file responsibilities through apply. ' if legacy else '') + state.get('file_warning', ''))
                problems = sorted({item['routing_problem'] for item in state['files'].values() if item.get('routing_problem')})
                if problems:
                    reason += ' ' + ' '.join(problems)
                if reference_errors:
                    reason += ' ' + ' '.join(reference_errors)
                sp_changes = [Path(path).name + ' ' + ' '.join(state['files'][path].get('check', {}).get('sp_changes', []))
                              for path in pending if state['files'][path].get('check', {}).get('sp_changes')]
                if sp_changes:
                    reason += ' Compare these changes to the actual request and named reference SPs before reporting completion: ' + ' '.join(sp_changes)[:3000]
                if cross_errors:
                    reason += ' Resolve the new mismatch between applied C# and SQL sources: ' + ' | '.join(cross_errors)[:3000]
                if lost_links:
                    reason += ' A previously resolved screen-to-procedure call no longer resolves. Compare the new target with its actual definition: ' + ', '.join(lost_links)
                hard_block = bool(hard_pending or missing_references or legacy or application_errors or reference_errors or cross_errors)
                if mode == 'enforce' and not event.get('stop_hook_active') and (hard_block or state.get('stop_notice') != fingerprint):
                    state['stop_notice'] = fingerprint
                    output = {'decision': 'block', 'reason': reason}
                else:
                    output = {'systemMessage': reason}
            elif not state.get('unregistered_writes'):
                try:
                    retire_checks(state, baselines, 'checks_complete')
                except (OSError, ValueError, UnicodeError):
                    output = {'systemMessage': 'KH could not verify cleanup of its task-local source baselines; inspect ' + str(baselines.directory)}
        if name in {'Stop', 'SubagentStop'} and state.get('unregistered_writes') and not state.get('paused'):
            reason = ('KH observed an unregistered change to a named output. Run kh_context.py apply for this output, '
                      'then compare its saved change with the captured pre-edit original: ' + ', '.join(state['unregistered_writes']))
            state['completion_status'] = 'requires_repair_or_evidence'
            state['semantic_audit_verified'] = False
            output = ({'decision': 'block', 'reason': reason} if mode == 'enforce' and not event.get('stop_hook_active')
                      else {'systemMessage': reason})
        elif name in {'Stop', 'SubagentStop'} and named and not domains and not state.get('paused'):
            baselines.cleanup()
        if name in {'Stop', 'SubagentStop', 'SessionEnd'}:
            state['kh_scope_closed'] = True
            settle_native_usage(state)
            if not state.get('files') and not state.get('before'):
                state.pop('write_registration_domains', None)
        if name == 'PreToolUse' and unapplied and not state.get('paused'):
            available_domains = {domain for domain in set(DOMAINS.values()) if domain + '/SKILL.md' in state.get('skills_seen', [])}
            notices = state.setdefault('coverage_notices', [])
            outside = [str(path) for path in unapplied if DOMAINS[path.suffix.casefold()] in available_domains and str(path) not in notices]
            if outside and not output and len(notices) < MAX_FILES:
                notices.extend(outside[:max(0, MAX_FILES - len(notices))])
                output = context(name, 'These writes are outside registered KH coverage: ' + ', '.join(outside[:MAX_FILES]) +
                    '. If they belong to this KH development task, use scoped apply before writing. Other work remains allowed and is not inspected. No KH compliance result is established for these files.')
        available = any(domain + '/SKILL.md' in state.get('skills_seen', []) for domain in set(DOMAINS.values()))
        if ((name == 'PostToolUse' and (available or native)) or
                (name in {'UserPromptSubmit', 'SessionStart'} and
                 (explicit or available or state.get('applications') or state.get('legacy_pending_targets') or state.get('legacy_originals_pending')))):
            hint = application_hint(state, event, host, store.path.parent.parent, ROOT)
            if hint:
                if output.get('hookSpecificOutput', {}).get('additionalContext'):
                    output['hookSpecificOutput']['additionalContext'] += '\n' + hint
                elif not output:
                    output = context(str(name), hint)
        store.save(connection, key, state)
        return output
