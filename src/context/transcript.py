"""Incrementally archive user evidence from selected host transcripts, never reasoning/tools."""
import hashlib
import json
from pathlib import Path
from src.common.output import redact

SCAN_LIMIT = 8 * 1024 * 1024
TEXT_LIMIT = 64000


def user_text(record: dict, host: str) -> str | None:
    if host == 'codex':
        # The event stream avoids copied response_item user mirrors.
        payload = record.get('payload', {})
        if record.get('type') != 'event_msg' or payload.get('type') != 'user_message':
            return None
        value = payload.get('message')
    else:
        if record.get('type') != 'user':
            return None
        value = record.get('message', {}).get('content')
        if isinstance(value, list):
            value = '\n'.join(part.get('text', '') for part in value
                              if isinstance(part, dict) and part.get('type') == 'text')
    if not isinstance(value, str) or not value.strip():
        return None
    if value.lstrip().startswith(('<environment_context>', '<user_instructions>', '<turn_aborted>', '<automations_context>')):
        return None
    return value


def capture(state: dict, event: dict, host: str) -> None:
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
    consumed = 0
    imported = {'users': list(state.get('users', []))}
    if imported['users']:
        imported['users'][-1] = dict(imported['users'][-1])
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
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError('record must be an object')
                if record.get('type') == 'session_meta':
                    logged_id = record.get('payload', {}).get('id')
                    if logged_id and logged_id != event['session_id']:
                        state['capture_warning'] = 'Transcript session mismatch; archive was not imported.'
                        return
                if host == 'claude' and record.get('sessionId') not in (None, event['session_id']):
                    state['capture_warning'] = 'Transcript session mismatch; archive was not imported.'
                    return
                text = user_text(record, host)
            except (ValueError, TypeError, AttributeError):
                state['malformed_records'] = state.get('malformed_records', 0) + 1
                continue
            if text:
                add_user(imported, text, {'path': str(path), 'byte_offset': offset,
                                      'sha256': hashlib.sha256(line).hexdigest()})
    state['users'] = imported['users']
    state['cursor'] = cursor
    if cursor and not state.get('prefix_hash'):
        with path.open('rb') as identity:
            prefix = identity.read(min(cursor, 4096))
        state.update(prefix_length=len(prefix), prefix_hash=hashlib.sha256(prefix).hexdigest())
    state['transcript'] = str(path)
    state['backlog_bytes'] = max(0, before.st_size - cursor)
    if state.get('malformed_records'):
        state['capture_warning'] = 'Malformed transcript records were skipped; original evidence must be inspected.'


def add_user(state: dict, text: str, source: dict) -> None:
    fingerprint = hashlib.sha256(text.encode('utf-8')).hexdigest()
    users = state.setdefault('users', [])
    # Prompt events and their transcript counterpart share content; distinct later repetitions remain.
    if users and users[-1]['sha256'] == fingerprint:
        prior = users[-1]['source']
        mirror = ((source.get('path') and prior.get('event') == 'UserPromptSubmit') or
                  (source.get('path') and prior.get('path') == source['path'] and
                   prior.get('byte_offset') == source.get('byte_offset')) or
                  (source.get('event') and prior.get('event') and source.get('turn_id') == prior.get('turn_id')))
        if mirror:
            if source.get('path'):
                users[-1]['source'] = source
            return
    clean = redact(text)
    users.append({'seq': len(users) + 1, 'sha256': fingerprint, 'text': clean[:TEXT_LIMIT],
                  'truncated': len(clean) > TEXT_LIMIT, 'source': source})
