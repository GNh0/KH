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
from src.common.files import read_file
from src.common.output import redact
from src.context.store import Store, data_root, session_key
from src.context.transcript import add_user, capture

ROOT = Path(__file__).resolve().parents[2]
DOMAINS = {'.sql': 'sql-formatting', '.cs': 'csharp-designer-style-harness',
           '.srd': 'pb-to-csharp-migration-harness', '.srw': 'pb-to-csharp-migration-harness',
           '.sru': 'pb-to-csharp-migration-harness', '.srf': 'pb-to-csharp-migration-harness'}
CYCLE = 'work-execution/references/source-style-cycle.md'
FILE_LIMIT = 1024 * 1024
MAX_FILES = 32


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
    """Typed edit tools and literal shell write paths only; no claim to parse arbitrary code."""
    tool = event.get('tool_name', '')
    data = event.get('tool_input', {})
    if isinstance(data, str) and 'apply_patch' in tool:
        data = {'command': data}
    if not isinstance(data, dict):
        return []
    command = data.get('command', data.get('cmd', data.get('patch', '')))
    paths = []
    if isinstance(command, str):
        paths.extend(re.findall(r'^\*\*\* (?:Add|Update|Delete) File: (.+)$', command, re.M))
        paths.extend(re.findall(r'^\*\*\* Move to: (.+)$', command, re.M))
    if tool in {'Edit', 'Write', 'MultiEdit'}:
        paths.extend([data.get('file_path', data.get('path', ''))])
    if tool in {'Bash', 'exec_command'} and isinstance(command, str):
        literal = r'[\'\"]([^\'\"\r\n]+)[\'\"]'
        for pattern in (r'(?:Set-Content|Add-Content|Out-File)\s+(?:-(?:LiteralPath|FilePath|Path)\s+)?' + literal,
                        r'WriteAll(?:Text|Bytes)\s*\(\s*' + literal,
                        r'Path\(\s*' + literal + r'\s*\)\.(?:write_text|write_bytes)\b',
                        r'(?<!>)>{1,2}\s*' + literal):
            paths.extend(re.findall(pattern, command, re.I))
    result = []
    cwd = Path(event['cwd']).resolve()
    for raw in paths:
        if not isinstance(raw, str) or not raw:
            continue
        path = Path(raw.strip())
        path = (cwd / path).resolve() if not path.is_absolute() else path.resolve()
        if path.suffix.casefold() in DOMAINS and path not in result:
            result.append(path)
    return result


def snapshot(path: Path) -> tuple[str, str]:
    if not path.exists():
        return 'deleted', ''
    if not path.is_file() or path.stat().st_size > FILE_LIMIT:
        raise ValueError('file exceeds automatic check size or is not a regular file: ' + str(path))
    raw = read_file(path, max_bytes=FILE_LIMIT)
    text = raw.text()
    return raw.sha256, text


def inspect(path: Path, text: str) -> dict:
    suffix = path.suffix.casefold()
    if suffix == '.sql':
        from src.sql.checks import check_sql
        result = check_sql(text)
    elif suffix == '.cs':
        if path.name.casefold().endswith('.designer.cs'):
            from src.csharp.designer import check_designer
            result = check_designer(text)
        else:
            from src.csharp.checks import check_csharp
            result = check_csharp(text)
    else:
        from src.pb.checks import check_pb_export
        result = check_pb_export(text, path=str(path))
    return {'errors': [item.code for item in result.issues if item.severity == 'error'],
            'warnings': [item.code for item in result.issues if item.severity != 'error'],
            'incomplete': result.incomplete, 'not_checked': result.not_checked,
            'review_status': result.metadata.get('review_status', 'unverified')}


def update_files(state: dict, paths: list[Path], returned: str = '', before: dict | None = None) -> list[str]:
    messages = []
    files = state.setdefault('files', {})
    for path in paths:
        name = str(path)
        if name not in files and len(files) >= MAX_FILES:
            state['file_warning'] = 'More than 32 touched files; inspect remaining files directly.'
            continue
        try:
            sha, text = snapshot(path)
            item = files.setdefault(name, {})
            item.pop('error', None)
            if sha != item.get('sha256'):
                previous = (before or {}).get(name)
                current_lines = line_hashes(text)
                if previous is None and item.get('line_hashes') is not None:
                    previous = item['line_hashes']
                if previous is not None:
                    item['pending_spans'] = pending_context(item, current_lines, changed_context(previous, current_lines))
                    item['read_scope'] = 'changed lines plus adjacent context; coherent-unit/caller audit remains manual'
                else:
                    item['pending_spans'] = []
                    item['read_scope'] = 'unverified change range; inspect actual coherent unit directly'
                item['read_buffer'] = []
                item['numbered_seen'] = []
                item.update(sha256=sha, readback=None, check=inspect(path, text) if sha != 'deleted' else {})
                item['line_hashes'] = current_lines
                if sha != 'deleted':
                    messages.append(name + ': ' + json.dumps({**item['check'], 'read_scope': item['read_scope']}, ensure_ascii=False))
            returned_body = undecorated(returned)
            if sha == 'deleted' or (text.strip() and (normalized(text) in normalized(returned) or
                                                     undecorated(text) in returned_body)):
                item['readback'] = sha
                item['pending_spans'] = []
                item['read_buffer'] = []
                item['numbered_seen'] = []
            elif item.get('pending_spans') and returned:
                tokens, positions = returned_line_hashes(returned, item['line_hashes'])
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


def observed_reads(returned: str, state: dict) -> set[str]:
    if not returned:
        return set()
    seen = set()
    coverage = state.setdefault('read_coverage', {})
    lines = {re.sub(r'^\s*(?:L?\d+[:\t→]\s*)', '', line).strip()
             for line in returned.splitlines() if line.strip()}
    for relative in [CYCLE, *(name + '/SKILL.md' for name in set(DOMAINS.values()))]:
        body = (ROOT / 'skills' / relative).read_text(encoding='utf-8-sig')
        expected = {line.strip() for line in body.splitlines() if line.strip()}
        matches = expected & lines
        prior = coverage.get(relative, {})
        fingerprint = hashlib.sha256(body.encode('utf-8')).hexdigest()
        prior_lines = set(prior.get('lines', [])) if prior.get('sha256') == fingerprint else set()
        combined = prior_lines | matches
        if combined:
            coverage[relative] = {'sha256': fingerprint, 'lines': sorted(combined)}
        if expected <= combined or normalized(body) in normalized(returned):
            seen.add(relative)
    return seen


def restore(state: dict, memories: list[dict], store: Store) -> str:
    if not state.get('users') and not state.get('checkpoint') and not state.get('latest_prompt') and not memories and not state.get('capture_warning') and not state.get('backlog_bytes'):
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
    checkpoint = state.get('checkpoint')
    if checkpoint:
        newer = max(0, len(state.get('users', [])) - checkpoint['user_seq'])
        parts.append('Task checkpoint: captured through user seq=' + str(checkpoint['user_seq']) +
                     ', newer user records=' + str(newer) + ', preview_truncated=' +
                     str(len(checkpoint['text']) > 2200) + '. Inspect newer corrections first; recall retrieves the full checkpoint.\n' + checkpoint['text'][:2200])
    users = state.get('users', [])
    previews = [{**item, 'text': item['text'][:500],
                 'preview_truncated': len(item['text']) > 500 or item['truncated']} for item in reversed(users[-4:])]
    parts.append('Archived user records: ' + str(len(users)) + '. Latest first; source locations remain available.\n' +
                 '\n'.join(json.dumps(item, ensure_ascii=False) for item in previews))
    if memories:
        parts.append('Explicitly curated project memory (not automatic chat promotion):\n' +
                     json.dumps({'entry_count': len(memories), 'preview': [
                         {**item, 'text': item['text'][:350], 'preview_truncated': len(item['text']) > 350}
                         for item in memories[:2]], 'more_entries': len(memories) > 2}, ensure_ascii=False))
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
    if name not in {'SessionStart', 'UserPromptSubmit', 'PreToolUse', 'PostToolUse', 'PreCompact',
                    'PostCompact', 'Stop', 'Interrupt', 'SessionEnd'}:
        return {}
    store = Store(data_root(), event['cwd'])
    key = session_key(event, host)
    paths = file_paths(event) if name in {'PreToolUse', 'PostToolUse'} else []
    returned = flatten(event.get('tool_response', {})) if name == 'PostToolUse' else ''
    observation = {}
    observed_reads(returned, observation)
    create = bool(paths or observation.get('read_coverage')) or name == 'PreCompact'
    with store.connect(create=create) as connection:
        if connection is None:
            return {}
        state = store.load(connection, key)
        output = {}
        if name == 'PreToolUse' and paths:
            state['skills_seen'] = sorted(observed_reads('\n', state))
            required = {CYCLE, *(DOMAINS[path.suffix.casefold()] + '/SKILL.md' for path in paths)}
            missing = sorted(required - set(state.get('skills_seen', [])))
            # No attempt counter: retrying the same write is not evidence that prerequisites were read.
            if missing:
                reason = 'Before editing, retrieve the complete current KH prerequisites: ' + ', '.join(str(ROOT / 'skills' / item) for item in missing) + '. Returned complete bodies are required; this does not replace actual reference-program inspection.'
                if mode == 'enforce':
                    output = {'hookSpecificOutput': {'hookEventName': name, 'permissionDecision': 'deny', 'permissionDecisionReason': reason}}
                else:
                    output = context(name, reason)
            if state.get('paused'):
                reason = 'KH task remains paused. Honor the stop request. Only after explicit user resumption, run ' + str(ROOT / 'scripts/kh_context.py') + ' resume with exact scope: ' + json.dumps({key: event.get(key) for key in ('cwd', 'session_id', 'transcript_path', 'agent_id')}, ensure_ascii=False) + '; host=' + host
                output = ({'hookSpecificOutput': {'hookEventName': name, 'permissionDecision': 'deny',
                           'permissionDecisionReason': reason}} if mode == 'enforce' else context(name, reason))
            if not output or output.get('hookSpecificOutput', {}).get('permissionDecision') != 'deny':
                baseline = state.setdefault('before', {})
                for path in paths:
                    try:
                        _sha, body = snapshot(path)
                        baseline[str(path)] = line_hashes(body)
                    except (OSError, ValueError, UnicodeError, RuntimeError):
                        baseline.pop(str(path), None)
        elif name == 'PostToolUse':
            state['skills_seen'] = sorted(observed_reads(returned, state))
            baseline = {str(path): state.get('before', {}).pop(str(path)) for path in paths
                        if str(path) in state.get('before', {})}
            messages = update_files(state, list(dict.fromkeys([*(Path(p) for p in state['files']), *paths])), returned, baseline)
            if paths:
                capture(state, event, host)
            if messages:
                output = context(name, ('KH saved-file checks (partial, not semantic audit). Read back each changed unit, resolve findings against actual requirements/reference sources, then audit combined changes and regressions.\n' + '\n'.join(messages))[:6000])
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
            previous_user_count = len(state['users'])
            capture(state, event, host)
            prompt = event.get('prompt', '')
            if isinstance(prompt, str) and prompt:
                clean = redact(prompt)
                state['latest_prompt'] = {'text': clean[:64000], 'truncated': len(clean) > 64000,
                                          'turn_id': event.get('turn_id'),
                                          'source': 'UserPromptSubmit', 'sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest()}
                if state.get('backlog_bytes') or state.get('capture_warning'):
                    pending = state.setdefault('pending_prompts', [])
                    if not pending or (pending[-1].get('turn_id'), pending[-1]['sha256']) != (event.get('turn_id'), state['latest_prompt']['sha256']):
                        pending.append({**state['latest_prompt'], 'prompt_id': len(pending) + 1})
                already_captured = (len(state['users']) > previous_user_count and
                                    state['users'][-1]['sha256'] == hashlib.sha256(prompt.encode('utf-8')).hexdigest())
                if not already_captured and not state.get('backlog_bytes'):
                    add_user(state, prompt, {'event': name, 'turn_id': event.get('turn_id')})
                # Only standalone stop imperatives; a Cancel/Stop button request is ordinary work.
                stop = (r'\s*(?:(?:please\s+)?(?:stop|cancel|pause)(?:\s+(?:the\s+)?(?:task|work|operation))?'
                        r'|(?:(?:일단|우선|지금|그냥)\s+)*(?:작업(?:을)?\s*)?'
                        r'(?:멈춰(?:줘)?|중지해(?:줘)?|중단해(?:줘)?|스탑|그만(?:해)?(?:줘)?)'
                        r'(?:[.!]\s*(?:지금은\s*)?아무것도\s*하지\s*마[.!]?)?)[.!\s]*')
                if len(prompt) < 300 and re.fullmatch(stop, prompt, re.I):
                    state['paused'] = True
        elif name in {'SessionStart', 'PostCompact'}:
            if host == 'claude' and name == 'PostCompact':
                # Claude PostCompact is observational; SessionStart(source=compact) injects context.
                store.save(connection, key, state)
                return {}
            compact = name == 'PostCompact' or event.get('source') == 'compact'
            if not compact or state.get('restore_pending', True):
                text = restore(state, store.memories(connection), store)
                if text:
                    text += '\nExact recovery scope: ' + json.dumps({key: event.get(key) for key in ('cwd', 'session_id', 'transcript_path', 'agent_id')}, ensure_ascii=False) + '; host=' + host
                    if state.get('paused'):
                        text += '\nTask remains paused; a status question is not resumption. Use the resume helper only after explicit user authorization.'
                    output = context(name, text)
                if compact:
                    state['restore_pending'] = False
        elif name == 'Stop' and not state.get('paused'):
            update_files(state, [Path(path) for path in state['files']])
            pending = []
            for path, item in state['files'].items():
                if item.get('error') or (item.get('pending_spans') and item.get('readback') != item.get('sha256')) or item.get('check', {}).get('errors'):
                    pending.append(path)
            fingerprint = hashlib.sha256(json.dumps(state['files'], sort_keys=True).encode()).hexdigest()
            if pending or state.get('file_warning'):
                reason = ('KH cannot verify completion for these saved files: ' + ', '.join(pending) + '. '
                          'Read back current bodies, inspect actual project/reference contracts, repair confirmed violations only, re-audit and check introduced regressions. '
                          'Report unsupported/unresolved evidence accurately; do not claim a checker proves full compliance. ' + state.get('file_warning', ''))
                if mode == 'enforce' and not event.get('stop_hook_active') and state.get('stop_notice') != fingerprint:
                    state['stop_notice'] = fingerprint
                    output = {'decision': 'block', 'reason': reason}
                else:
                    output = {'systemMessage': reason}
        store.save(connection, key, state)
        return output
