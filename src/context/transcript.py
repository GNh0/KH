"""Incrementally archive user evidence from selected host transcripts, never reasoning/tools."""
import hashlib
import json
from pathlib import Path
from src.common.output import redact

SCAN_LIMIT = 8 * 1024 * 1024
TEXT_LIMIT = 64000
ADAPTER_VERSION = 2


def user_text(record: dict, host: str) -> str | None:
    if host == 'codex':
        payload = record.get('payload', {})
        if record.get('type') == 'event_msg' and payload.get('type') == 'user_message':
            value = payload.get('message')
        elif record.get('type') == 'response_item' and payload.get('type') == 'message' and payload.get('role') == 'user':
            value = payload.get('content')
        else:
            return None
    else:
        if record.get('type') != 'user':
            return None
        value = record.get('message', {}).get('content')
    if isinstance(value, list):
        # Filter host-only blocks individually: a real request can follow them in the same message.
        value = '\n'.join(part['text'] for part in value if isinstance(part, dict)
                          and part.get('type') in {'text', 'input_text'} and isinstance(part.get('text'), str)
                          and not _host_block(part['text']))
    if not isinstance(value, str) or not value.strip():
        return None
    if _host_block(value):
        return None
    return value


def _host_block(text: str) -> bool:
    stripped = text.strip()
    return ((stripped.startswith('<hook_prompt') and stripped.endswith('</hook_prompt>')) or
            stripped.startswith(('<environment_context>', '<user_instructions>', '<turn_aborted>',
                                 '<automations_context>', '<recommended_plugins>', '<external_codex_apps_open_page>')))


def _codex_session_matches(payload: dict, event: dict) -> bool:
    logged_id, session, agent = payload.get('id'), event.get('session_id'), event.get('agent_id')
    if not agent:
        return logged_id == session
    # A native child transcript identifies itself by id and carries its parent's
    # host session separately. Never accept the parent's log as the child's log.
    return logged_id == agent and (logged_id == session or
        (payload.get('session_id') == session and payload.get('parent_thread_id') == session))


def _sources(item: dict) -> list[dict]:
    return [item['source'], *item.get('source_aliases', [])]


def recent_users(users: list[dict], limit: int) -> list[dict]:
    """Stable ids identify records; offsets order records from the same selected log."""
    if limit <= 0:
        return []
    ordered = sorted(users, key=lambda item: item['seq'])
    groups: dict[str, list[int]] = {}
    unlinked = []
    for index, item in enumerate(ordered):
        source = item['source']
        if isinstance(source.get('path'), str) and isinstance(source.get('byte_offset'), int):
            groups.setdefault(source['path'], []).append(index)
        else:
            unlinked.append(item)
    for indices in groups.values():
        chronological = sorted((ordered[index] for index in indices), key=lambda item: item['source']['byte_offset'])
        for index, item in zip(indices, chronological):
            ordered[index] = item
    selected = ordered[-limit:]
    # Unlinked prompt events have no comparable source time. Do not silently lose the
    # newest observed one merely because older transcript records were backfilled.
    if unlinked and unlinked[-1] not in selected:
        selected = [unlinked[-1], *selected[-(limit - 1):]] if limit > 1 else [unlinked[-1]]
    return selected


def _coalesce_mirrors(users: list[dict], original_ids: set[int], path: str) -> list[dict]:
    ordered = sorted((item for item in users if item['source'].get('path') == path),
                     key=lambda item: item['source']['byte_offset'])
    other = [item for item in users if item['source'].get('path') != path]
    result = []
    previous = None
    for item in ordered:
        source = item['source']
        if (previous and not previous.get('source_aliases') and not item.get('source_aliases') and
                item['sha256'] == previous['sha256'] and source.get('kind') and
                previous['source'].get('kind') != source['kind'] and
                previous['source'].get('turn_boundary') == source.get('turn_boundary') and
                0 < source.get('record_index', 0) - previous['source'].get('record_index', 0) <= 5):
            # Keep an existing archive id during adapter upgrades, preserving CLI get references.
            kept, mirror = (item, previous) if item['seq'] in original_ids and previous['seq'] not in original_ids else (previous, item)
            result[-1] = {**kept, 'source_aliases': [*kept.get('source_aliases', []), *_sources(mirror)]}
            previous = None
        else:
            result.append(item)
            previous = item
    return sorted([*result, *other], key=lambda item: item['seq'])


def discard_host_records(state: dict) -> None:
    # Older adapters mistook native Stop continuations for real user requests.
    # Keep real archive ids stable and never reuse a removed host-record id.
    state['user_seq'] = max(state.get('user_seq', 0), max((item['seq'] for item in state.get('users', [])), default=0))
    state['users'] = sorted((item for item in state.get('users', []) if not _host_block(item['text'])),
                            key=lambda item: item['seq'])
    if 'pending_prompts' in state:
        state['pending_prompts'] = [item for item in state['pending_prompts'] if not _host_block(item['text'])]
    if _host_block(state.get('latest_prompt', {}).get('text', '')):
        state.pop('latest_prompt')


def capture(state: dict, event: dict, host: str) -> None:
    discard_host_records(state)
    raw_path = event.get('transcript_path')
    if not raw_path:
        state['capture_warning'] = 'Host supplied no transcript; only observed prompt events are archived.'
        return
    path = Path(raw_path)
    if not path.is_absolute() or not path.is_file():
        state['capture_warning'] = 'Selected transcript is unavailable; previous checkpoint is preserved.'
        return
    cursor = state.get('cursor', 0)
    before = path.stat()
    with path.open('rb') as identity:
        prefix = identity.read(state.get('prefix_length', min(before.st_size, 4096)))
    prefix_hash = hashlib.sha256(prefix).hexdigest()
    if before.st_size < cursor or (state.get('prefix_hash') and prefix_hash != state['prefix_hash']):
        state['capture_warning'] = 'Transcript identity changed/truncated; prior archive preserved, replacement not imported.'
        return
    state.pop('capture_warning', None)
    rescan = state.get('adapter_version', 1) < ADAPTER_VERSION
    if rescan:
        if cursor:
            state['rescan_until'] = cursor
            state['backfill_archive_ids'] = [item['seq'] for item in state.get('users', [])]
        cursor = 0
    consumed = 0
    imported = {'users': [{**item, 'source': dict(item['source'])} for item in state.get('users', [])],
                'user_seq': state['user_seq']}
    original_ids = set(state.get('backfill_archive_ids', [item['seq'] for item in imported['users']]))
    known = {(source.get('path'), source.get('byte_offset'), source.get('sha256')): item
             for item in imported['users'] for source in _sources(item) if source.get('path')}
    record_index = 0 if rescan else state.get('record_index', 0)
    turn_boundary = 0 if rescan else state.get('turn_boundary', 0)
    with path.open('rb') as stream:
        stream.seek(cursor)
        while consumed < SCAN_LIMIT:
            offset = stream.tell()
            line = stream.readline(SCAN_LIMIT + 1)
            if not line:
                break
            if not line.endswith(b'\n'):
                # An in-progress or oversized record remains unconsumed and visible as backlog.
                stream.seek(offset)
                break
            consumed += len(line)
            cursor = stream.tell()
            record_index += 1
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError('record must be an object')
                if record.get('type') == 'session_meta':
                    logged_id = record.get('payload', {}).get('id')
                    if logged_id and not _codex_session_matches(record['payload'], event):
                        state['capture_warning'] = 'Transcript session mismatch; archive was not imported.'
                        return
                if host == 'claude' and record.get('sessionId') not in (None, event['session_id']):
                    state['capture_warning'] = 'Transcript session mismatch; archive was not imported.'
                    return
                payload = record.get('payload', {})
                if (host == 'codex' and record.get('type') == 'response_item' and isinstance(payload, dict)
                        and payload.get('type') == 'message' and payload.get('role') == 'assistant'):
                    turn_boundary += 1
                text = user_text(record, host)
            except (ValueError, TypeError, AttributeError):
                state['malformed_records'] = state.get('malformed_records', 0) + 1
                continue
            if text:
                source = {'path': str(path), 'byte_offset': offset, 'sha256': hashlib.sha256(line).hexdigest(),
                          'kind': record.get('type'), 'record_index': record_index, 'turn_boundary': turn_boundary}
                existing = known.get((str(path), offset, source['sha256']))
                if existing:
                    if existing['source'].get('byte_offset') == offset:
                        existing['source'] = source
                else:
                    add_user(imported, text, source, merge_prompt=offset >= state.get('rescan_until', 0))
                    known[(str(path), offset, source['sha256'])] = imported['users'][-1]
    state['users'] = _coalesce_mirrors(imported['users'], original_ids, str(path)) if host == 'codex' else imported['users']
    state['user_seq'] = imported['user_seq']
    state['cursor'] = cursor
    state.update(adapter_version=ADAPTER_VERSION, record_index=record_index, turn_boundary=turn_boundary)
    if cursor >= state.get('rescan_until', 0):
        state.pop('rescan_until', None)
        state.pop('backfill_archive_ids', None)
    if cursor and not state.get('prefix_hash'):
        with path.open('rb') as identity:
            prefix = identity.read(min(cursor, 4096))
        state.update(prefix_length=len(prefix), prefix_hash=hashlib.sha256(prefix).hexdigest())
    state['transcript'] = str(path)
    state['backlog_bytes'] = max(0, before.st_size - cursor)
    if state.get('malformed_records'):
        state['capture_warning'] = 'Malformed transcript records were skipped; original evidence must be inspected.'
    elif record_index and not state['users'] and not state['backlog_bytes']:
        state['capture_warning'] = 'No supported user records observed; capture is unverified, inspect the original transcript format.'


def add_user(state: dict, text: str, source: dict, *, merge_prompt: bool = True) -> None:
    fingerprint = hashlib.sha256(text.encode('utf-8')).hexdigest()
    users = state.setdefault('users', [])
    # Prompt events and their transcript counterpart share content; distinct later repetitions remain.
    if users and users[-1]['sha256'] == fingerprint:
        prior = users[-1]['source']
        mirror = ((merge_prompt and source.get('path') and prior.get('event') == 'UserPromptSubmit') or
                  (source.get('path') and prior.get('path') == source['path'] and
                   prior.get('byte_offset') == source.get('byte_offset')) or
                  (source.get('event') and prior.get('event') and source.get('turn_id') == prior.get('turn_id')))
        if mirror:
            if source.get('path'):
                users[-1]['source'] = source
            return
    clean = redact(text)
    sequence = max(state.get('user_seq', 0), max((item['seq'] for item in users), default=0)) + 1
    state['user_seq'] = sequence
    users.append({'seq': sequence, 'sha256': fingerprint, 'text': clean[:TEXT_LIMIT],
                  'truncated': len(clean) > TEXT_LIMIT, 'source': source})
