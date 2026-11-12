"""Incremental HTTP event decoding and configurable presentation; no provider routing."""
import base64
import codecs
import json
import math
from pathlib import Path
import re
import time
import uuid

from src.api_auth.security import AuthError, safe_output


MISSING = object()
KINDS = {'status', 'phase', 'tool_call', 'tool_result', 'text_delta', 'summary_delta', 'progress', 'image_preview', 'artifact', 'usage', 'completed', 'error', 'data'}


def strict_json(text):
    def invalid(_value):
        raise ValueError('Non-finite JSON value')
    return json.loads(text, parse_constant=invalid)


def lines(chunks, maximum):
    decoder = codecs.getincrementaldecoder('utf-8-sig')('strict')
    pending = ''
    try:
        for block in chunks:
            pending += decoder.decode(block)
            while True:
                match = re.search(r'\r\n|\r|\n', pending)
                if match is None or (match.group() == '\r' and match.end() == len(pending)):
                    break
                line, pending = pending[:match.start()], pending[match.end():]
                if len(line.encode('utf-8')) > maximum:
                    raise AuthError('stream_event_too_large', 'Stream line exceeded its event bound.')
                yield line
            if len(pending.encode('utf-8')) > maximum:
                raise AuthError('stream_event_too_large', 'Stream line exceeded its event bound.')
        pending += decoder.decode(b'', final=True)
        # A final CR is a complete line ending. A remaining unterminated line is not.
        if pending.endswith('\r'):
            yield pending[:-1]
            pending = ''
        if pending:
            yield pending
    except UnicodeError:
        raise AuthError('invalid_stream_data', 'Stream contained invalid UTF-8.') from None


def wire_events(chunks, protocol, limits):
    count = 0
    if protocol == 'text':
        decoder = codecs.getincrementaldecoder('utf-8-sig')('strict')
        try:
            for block in chunks:
                text = decoder.decode(block)
                if text:
                    if len(text.encode('utf-8')) > limits.max_event_bytes:
                        raise AuthError('stream_event_too_large', 'Text chunk exceeded its event bound.')
                    count += 1
                    if count > limits.max_events:
                        raise AuthError('stream_event_limit', 'Stream exceeded its event count bound.')
                    yield {'event': 'text', 'id': None, 'data': text, 'json': False}
            text = decoder.decode(b'', final=True)
            if text:
                yield {'event': 'text', 'id': None, 'data': text, 'json': False}
        except UnicodeError:
            raise AuthError('invalid_stream_data', 'Stream contained invalid UTF-8.') from None
        return
    data_lines, event, event_id, event_bytes = [], '', None, 0
    for line in lines(chunks, limits.max_event_bytes):
        if protocol == 'ndjson':
            if not line.strip():
                continue
            try:
                value = strict_json(line)
                is_json = True
            except (ValueError, RecursionError):
                raise AuthError('invalid_stream_data', 'NDJSON record was not valid finite JSON.') from None
        else:
            if line:
                event_bytes += len(line.encode('utf-8')) + 1
                if event_bytes > limits.max_event_bytes:
                    raise AuthError('stream_event_too_large', 'SSE event exceeded its byte bound.')
                if line.startswith(':'):
                    continue
                key, separator, value = line.partition(':')
                if separator and value.startswith(' '):
                    value = value[1:]
                if key == 'data':
                    data_lines.append(value)
                elif key == 'event':
                    event = value
                elif key == 'id' and '\0' not in value:
                    event_id = value
                continue
            event_bytes = 0
            if not data_lines:
                event = ''
                continue
            raw = '\n'.join(data_lines)
            data_lines = []
            try:
                value = strict_json(raw)
                is_json = True
            except (ValueError, RecursionError):
                value = raw
                is_json = False
        count += 1
        if count > limits.max_events:
            raise AuthError('stream_event_limit', 'Stream exceeded its event count bound.')
        inferred = value.get('type', value.get('event_type', 'message')) if isinstance(value, dict) else 'message'
        yield {'event': event or (inferred if isinstance(inferred, str) else 'message'), 'id': event_id, 'data': value, 'json': is_json}
        event = ''
    # SSE dispatch requires a blank line; do not promote a truncated final event.


def choose_protocol(protocol, content_type):
    if protocol not in {'auto', 'sse', 'ndjson', 'text'}:
        raise AuthError('invalid_stream_protocol', 'Choose auto, sse, ndjson or text.')
    if protocol != 'auto':
        return protocol
    media = content_type.split(';', 1)[0].strip().lower()
    if media == 'text/event-stream':
        return 'sse'
    if media in {'application/x-ndjson', 'application/ndjson'}:
        return 'ndjson'
    if media == 'text/plain':
        return 'text'
    raise AuthError('unsupported_stream_media_type', 'Response is not SSE, NDJSON or streaming UTF-8 text; inspect the actual API contract.')


def selector(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 16:
        raise AuthError('invalid_stream_mapping', 'A field selector must be a bounded list of JSON keys or array indices.')
    for part in value:
        if isinstance(part, bool) or not ((isinstance(part, str) and 0 < len(part) <= 128) or (isinstance(part, int) and 0 <= part <= 10000)):
            raise AuthError('invalid_stream_mapping', 'Field selector components must be JSON keys or nonnegative indices.')
    return value


def select(value, path):
    for part in path:
        if isinstance(part, str) and isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(part, int) and isinstance(value, list) and part < len(value):
            value = value[part]
        else:
            return MISSING
    return value


class Mapping:
    def __init__(self, config=None):
        config = {} if config is None else config
        if not isinstance(config, dict) or set(config) - {'rules', 'done_marker'}:
            raise AuthError('invalid_stream_mapping', 'Unknown stream mapping field.')
        self.done_marker = config.get('done_marker')
        if self.done_marker is not None and (not isinstance(self.done_marker, str) or not 1 <= len(self.done_marker) <= 100):
            raise AuthError('invalid_stream_mapping', 'A done marker must be bounded text.')
        self.rules = config.get('rules', [])
        if not isinstance(self.rules, list) or len(self.rules) > 64:
            raise AuthError('invalid_stream_mapping', 'Use a bounded list of stream presentation rules.')
        for rule in self.rules:
            if not isinstance(rule, dict) or set(rule) - {'event', 'when', 'kind', 'fields', 'channel', 'artifact', 'terminal'} or rule.get('kind') not in KINDS:
                raise AuthError('invalid_stream_mapping', 'Invalid stream presentation rule.')
            if 'event' in rule and (not isinstance(rule['event'], str) or not 1 <= len(rule['event']) <= 200):
                raise AuthError('invalid_stream_mapping', 'Event matching uses one exact event name.')
            conditions = rule.get('when', [])
            if not isinstance(conditions, list) or len(conditions) > 8:
                raise AuthError('invalid_stream_mapping', 'Invalid event conditions.')
            for condition in conditions:
                if not isinstance(condition, dict) or set(condition) != {'path', 'equals'} or isinstance(condition['equals'], (dict, list)):
                    raise AuthError('invalid_stream_mapping', 'Conditions compare selected fields with scalar JSON values.')
                selector(condition['path'])
                if isinstance(condition['equals'], float) and not math.isfinite(condition['equals']):
                    raise AuthError('invalid_stream_mapping', 'Event conditions require finite JSON values.')
            fields = rule.get('fields', {})
            if not isinstance(fields, dict) or len(fields) > 16:
                raise AuthError('invalid_stream_mapping', 'Invalid mapped display fields.')
            for key, path in fields.items():
                if not isinstance(key, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,39}', key) or key in {'kind', 'seq', 'elapsed_seconds', 'event', 'event_id', 'artifact', 'channel', 'terminal'}:
                    raise AuthError('invalid_stream_mapping', 'Mapped fields cannot replace stream control metadata.')
                if rule['kind'] == 'error' and key == 'data':
                    raise AuthError('invalid_stream_mapping', 'Error data preserves the original provider event; choose another display field.')
                selector(path)
            if 'channel' in rule:
                selector(rule['channel'])
            if 'terminal' in rule and not isinstance(rule['terminal'], bool):
                raise AuthError('invalid_stream_mapping', 'terminal must be boolean.')
            if 'artifact' in rule:
                artifact = rule['artifact']
                if not isinstance(artifact, dict) or set(artifact) != {'path', 'format'} or artifact['format'] not in {'png', 'jpeg', 'webp', 'gif', 'bin'}:
                    raise AuthError('invalid_stream_mapping', 'Artifacts need a selected base64 field and an explicit supported format.')
                selector(artifact['path'])

    @property
    def needs_artifacts(self):
        return any('artifact' in rule for rule in self.rules)

    def render(self, wire):
        value = wire['data']
        if self.done_marker is not None and value == self.done_marker:
            return {'kind': 'completed', 'terminal': True}
        for rule in self.rules:
            if 'event' in rule and wire['event'] != rule['event']:
                continue
            if any(select(value, item['path']) is MISSING or
                   isinstance(select(value, item['path']), bool) != isinstance(item['equals'], bool) or
                   select(value, item['path']) != item['equals'] for item in rule.get('when', [])):
                continue
            record = {'kind': rule['kind'], 'terminal': rule.get('terminal', rule['kind'] in {'completed', 'error'})}
            if rule['kind'] == 'error':
                record['data'] = value
            for key, path in rule.get('fields', {}).items():
                selected = select(value, path)
                if selected is not MISSING:
                    record[key] = selected
            if 'channel' in rule:
                channel = select(value, rule['channel'])
                if channel is MISSING or not isinstance(channel, (str, int)) or isinstance(channel, bool):
                    raise AuthError('invalid_stream_data', 'Text channel must be a string or integer.')
                record['channel'] = str(channel)
            if 'artifact' in rule:
                record['_artifact'] = (select(value, rule['artifact']['path']), rule['artifact']['format'])
            return record
        if self.rules:
            return {'kind': 'event'}
        return {'kind': 'text_delta', 'text': value} if isinstance(value, str) and not wire.get('json') else {'kind': 'data', 'data': value}


class TextRedactor:
    def __init__(self, secrets):
        self.secrets = sorted(set(secrets), key=len, reverse=True)
        self.pending = ''

    def feed(self, text, *, final=False):
        value = self.pending + text
        if final and len(self.pending) >= 4 and not text and any(secret.startswith(self.pending) for secret in self.secrets):
            self.pending = ''
            return '[REDACTED]'
        for secret in self.secrets:
            value = value.replace(secret, '[REDACTED]')
        hold = 0
        if not final:
            for secret in self.secrets:
                for size in range(min(len(value), len(secret) - 1), hold, -1):
                    if value.endswith(secret[:size]):
                        hold = size
                        break
        self.pending = value[-hold:] if hold else ''
        return value[:-hold] if hold else value


class Presenter:
    def __init__(self, sink, secrets, mapping, output_dir=None):
        self.sink, self.secrets, self.mapping = sink, secrets, mapping
        self.started, self.seq = time.monotonic(), 0
        self.text_channels = {}
        self.output_dir = None
        self.stem = 'stream-' + uuid.uuid4().hex[:12]
        if mapping.needs_artifacts:
            if output_dir is None or not Path(output_dir).is_absolute():
                raise AuthError('stream_output_required', 'Artifact streams require an explicit absolute output directory outside the source tree.')
            root = Path(output_dir)
            for path in [root, *root.parents]:
                if path.exists() and getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
                    raise AuthError('invalid_stream_output', 'Artifact output cannot traverse a reparse point.')
            root.mkdir(parents=True, exist_ok=True)
            self.output_dir = root

    def emit(self, record):
        self.seq += 1
        value = safe_output(record, self.secrets)
        self.sink({**value, 'seq': self.seq, 'elapsed_seconds': round(time.monotonic() - self.started, 3)})

    def flush_text(self):
        for (kind, channel), redactor in self.text_channels.items():
            text = redactor.feed('', final=True)
            if text:
                self.emit({'kind': kind, 'channel': channel, 'text': text})
        self.text_channels.clear()

    def accept(self, wire):
        record = self.mapping.render(wire)
        record.update(event=wire['event'], event_id=wire['id'])
        artifact = record.pop('_artifact', None)
        if artifact:
            encoded, fmt = artifact
            if not isinstance(encoded, str) or self.output_dir is None:
                raise AuthError('invalid_stream_artifact', 'Artifact event omitted its base64 content or output directory.')
            try:
                data = base64.b64decode(encoded, validate=True)
            except (ValueError, UnicodeError):
                raise AuthError('invalid_stream_artifact', 'Artifact event contained invalid base64.') from None
            valid = (fmt == 'bin' or (fmt == 'png' and data.startswith(b'\x89PNG\r\n\x1a\n')) or
                     (fmt == 'jpeg' and data.startswith(b'\xff\xd8\xff')) or
                     (fmt == 'gif' and data[:6] in {b'GIF87a', b'GIF89a'}) or
                     (fmt == 'webp' and data[:4] == b'RIFF' and data[8:12] == b'WEBP'))
            if not valid:
                raise AuthError('invalid_stream_artifact', 'Artifact bytes did not match the mapped format.')
            if any(secret.encode('utf-8') in data for secret in self.secrets):
                raise AuthError('sensitive_stream_artifact', 'Artifact contained a registered credential value; nothing was saved.')
            for path in [self.output_dir, *self.output_dir.parents]:
                if path.exists() and getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
                    raise AuthError('invalid_stream_output', 'Artifact output changed to a reparse point.')
            target = self.output_dir / (self.stem + '-' + str(self.seq + 1).zfill(4) + '.' + fmt)
            created = False
            try:
                with target.open('xb') as file:
                    created = True
                    if file.write(data) != len(data):
                        raise OSError('Incomplete artifact write')
            except OSError:
                if created:
                    try:
                        target.unlink(missing_ok=True)
                    except OSError:
                        raise AuthError('artifact_cleanup_required', 'An owned partial artifact could not be removed; inspect the configured output directory before retrying.') from None
                raise AuthError('artifact_write_error', 'Artifact could not be saved; the stream was stopped and no retry was sent.') from None
            record['artifact'] = {'path': str(target), 'format': fmt, 'bytes': len(data)}
        terminal = record.pop('terminal', False)
        if terminal:
            self.flush_text()
        if record['kind'] in {'text_delta', 'summary_delta'}:
            text = record.get('text')
            if not isinstance(text, str):
                raise AuthError('invalid_stream_data', 'Text and summary events require a mapped text string.')
            channel = record.get('channel', 'default')
            key = (record['kind'], channel)
            if key not in self.text_channels:
                if len(self.text_channels) >= 64:
                    raise AuthError('stream_channel_limit', 'Stream exceeded its text-channel bound.')
                self.text_channels[key] = TextRedactor(self.secrets)
            record['text'] = self.text_channels[key].feed(text)
            if not record['text'] and text:
                return terminal, record['kind']
        self.emit(record)
        return terminal, record['kind']
