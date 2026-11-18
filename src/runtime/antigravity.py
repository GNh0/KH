"""Observe scoped Antigravity saves and deliver diagnostics once, without read receipts."""
import json
from pathlib import Path
import re
from uuid import UUID

from src.context.store import Store, data_root, digest
from src.runtime.check_context import SourceBaselines
from src.runtime.skill_usage import DOMAINS, named_write_targets


ROOT = Path(__file__).resolve().parents[2]
WRITES = {'write_to_file', 'replace_file_content', 'multi_replace_file_content'}


def _selection(prompt: str) -> tuple[str, bool]:
    # A bare native slash command needs a matching IsSkillFile open from *this* package.
    # The fully qualified KH token is an explicit user selection even without that event.
    match = re.match(r'^\s*(/|\$kh-uaf:)([a-z0-9-]+)(?=\s|$)', prompt)
    if match and match[2] in DOMAINS.values():
        return match[2], match[1] != '/'
    return '', False


def _check(path: Path, body: str, original: str | None = None) -> dict:
    from src.runtime.hooks import inspect
    result = inspect(path, body, original=original)
    return {'file': path.name[:160], 'status': result['status'], 'count': result['finding_count'],
            'comparison': 'previous_file' if original is not None else 'standalone',
            'findings': [{'code': item['code'], 'line': item.get('line')} for item in result['findings']],
            'incomplete': result['incomplete']}


def _proposal(path: Path, call: dict) -> dict:
    args = call['args']
    if call['name'] == 'write_to_file':
        candidate = args.get('CodeContent')
    else:
        from src.runtime.hooks import snapshot
        chunks = [args] if call['name'] == 'replace_file_content' else args.get('ReplacementChunks')
        if not isinstance(chunks, list) or not 0 < len(chunks) <= 64:
            return {}
        _, original = snapshot(path)
        candidate = original.replace('\r\n', '\n')
        for chunk in chunks:
            if not isinstance(chunk, dict):
                return {}
            old, new = chunk.get('TargetContent'), chunk.get('ReplacementContent')
            if not isinstance(old, str) or not old or not isinstance(new, str):
                return {}
            old = old.replace('\r\n', '\n')
            if candidate.count(old) != 1:
                return {}
            candidate = candidate.replace(old, new.replace('\r\n', '\n'), 1)
    if not isinstance(candidate, str) or len(candidate) > 1024 * 1024:
        return {}
    candidate = candidate.replace('\r\n', '\n')
    return {'sha': digest(candidate)}


def _saved_result(path: Path, proposed: dict, baseline: SourceBaselines | None) -> dict:
    from src.runtime.hooks import snapshot
    try:
        fingerprint, body = snapshot(path)
        if fingerprint == 'deleted':
            raise ValueError('saved file unavailable')
        if proposed.get('sha') == digest(body.replace('\r\n', '\n')) and baseline is not None:
            record = baseline.records.get(baseline.record_key(path), {})
            if record.get('exists'):
                return _check(path, body, baseline.original(path))
        return _check(path, body)
    except (ValueError, OSError, UnicodeError):
        return {'file': path.name[:160], 'status': 'unverified'}


def _release_originals(directory: Path, state: dict, keys=None) -> None:
    originals = state.get('originals', {})
    for key in list(originals if keys is None else keys):
        if key not in originals:
            continue
        if not re.fullmatch('[a-f0-9]{64}', key):
            raise ValueError('Invalid Antigravity snapshot directory')
        SourceBaselines(directory / key, originals[key]).cleanup()
        del originals[key]


def _handle(name: str, event: dict, storage: Path | None) -> dict:
    if not isinstance(event, dict) or name not in {'PreInvocation', 'PreToolUse', 'PostToolUse', 'Stop'}:
        return {}
    prompt = event.get('lastUserInput')
    if not isinstance(prompt, str):
        prompt = ''
    skill, qualified = _selection(prompt)
    if not skill and name in {'PreToolUse', 'PostToolUse'}:
        return {}
    conversation = event.get('conversationId')
    roots = event.get('workspacePaths')
    if not isinstance(conversation, str) or not isinstance(roots, list) or not 0 < len(roots) <= 32:
        return {}
    try:
        identity = str(UUID(conversation))
        if not all(isinstance(value, str) and Path(value).is_absolute() for value in roots):
            return {}
        workspaces = sorted({Path(value).resolve() for value in roots})
    except (OSError, RuntimeError, ValueError):
        return {}
    scope = digest(json.dumps([identity, *map(str, workspaces)]))
    store = Store((storage or data_root()) / 'antigravity' / scope, str(workspaces[0]))
    token = digest(prompt) if skill else ''
    load_skill = False
    target = None
    call = event.get('toolCall', {})
    if name in {'PreToolUse', 'PostToolUse'}:
        # A relative destination in a multi-root workspace has no authoritative cwd.
        groups = {frozenset(paths) for root in workspaces
                  if (paths := named_write_targets(prompt, {skill}, str(root)))}
        if len(groups) != 1:
            return {}
        owned = {Path(path) for path in groups.pop()}
        if not isinstance(call, dict) or not isinstance(call.get('args'), dict):
            return {}
        args = call['args']
        if name == 'PostToolUse' and call.get('name') == 'view_file':
            location = args.get('AbsolutePath')
            load_skill = (args.get('IsSkillFile') is True and isinstance(location, str) and
                          Path(location).is_absolute() and Path(location).resolve() == ROOT / 'skills' / skill / 'SKILL.md')
            if not load_skill or event.get('error'):
                return {}
        elif call.get('name') in WRITES:
            location = args.get('TargetFile')
            if not isinstance(location, str) or not Path(location).is_absolute():
                return {}
            target = Path(location).resolve()
            if target not in owned:
                return {}
        else:
            return {}
    if name == 'Stop' and event.get('fullyIdle') is not True:
        return {}
    directory = store.path.parent / 'originals'
    with store.connect(create=load_skill or (qualified and target is not None)) as connection:
        if connection is None:
            return {}
        state = store.load(connection, scope)
        if state.get('prompt') and state['prompt'] != token:
            _release_originals(directory, state)
            connection.execute('DELETE FROM sessions WHERE id=?', (scope,))
            state.clear()
        state['prompt'] = token
        pending = state.get('pending', {})
        review = state.get('overflow') or any(item.get('status') != 'passed' or item.get('incomplete')
                                               for item in pending.values())
        if load_skill:
            state['selected_skill_path'] = skill
        elif target is not None:
            if not qualified and state.get('selected_skill_path') != skill:
                return {}
            step = event.get('stepIdx')
            has_step = type(step) is int and step >= 0
            step_key = digest(json.dumps([str(target), step])) if has_step else ''
            proposals = state.setdefault('proposals', {})
            key = digest(str(target))
            originals = state.setdefault('originals', {})
            if name == 'PreToolUse':
                if has_step and len(proposals) < 32:
                    proposal = _proposal(target, call)
                    if key not in originals and key not in pending and len(originals) < 16:
                        SourceBaselines(directory / key, originals.setdefault(key, {})).capture(target)
                    proposals[step_key] = {**proposal, 'path': key}
                    store.save(connection, scope, state)
                return {}
            proposal = proposals.pop(step_key, {})
            if event.get('error'):
                if key not in pending and not any(item.get('path') == key for item in proposals.values()):
                    _release_originals(directory, state, [key])
                store.save(connection, scope, state)
                return {}
            pending = state.setdefault('pending', {})
            if key in pending or len(pending) < 16:
                baseline = SourceBaselines(directory / key, originals[key]) if key in originals else None
                pending[key] = _saved_result(target, proposal, baseline)
            else:
                state['overflow'] = True
        elif pending and skill and (name != 'Stop' or (event.get('terminationReason') == 'model_stop' and review)):
            completed = state.pop('pending')
            reports = list(completed.values())
            in_flight = {item.get('path') for item in state.get('proposals', {}).values()}
            _release_originals(directory, state, completed.keys() - in_flight)
            notice = ('KH saved-file static checks (no agent-read/runtime evidence): ' +
                      json.dumps(reports, ensure_ascii=False))
            if state.pop('overflow', False):
                notice += ' Other changed files exceed the report limit; inspect them directly.'
            store.save(connection, scope, state)
            return ({'decision': 'continue', 'reason': notice} if name == 'Stop'
                    else {'injectSteps': [{'ephemeralMessage': notice}]})
        elif name == 'Stop':
            _release_originals(directory, state)
            connection.execute('DELETE FROM sessions WHERE id=?', (scope,))
            return {}
        else:
            return {}
        store.save(connection, scope, state)
    return {}


def handle(name: str, event: dict, *, storage: Path | None = None) -> dict:
    result = _handle(name, event, storage)
    return {'decision': 'allow'} if name == 'PreToolUse' else result
