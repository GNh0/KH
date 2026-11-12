"""Wire-boundary and authenticated callback checks, independent of paid providers."""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from src.api_auth.manager import Manager
from src.api_auth.profile import validate_profile
from src.api_auth.security import AuthError
from src.api_auth.store import Store
from src.api_auth.streaming import Mapping, Presenter, choose_protocol, wire_events
from src.api_auth.transport import StreamLimits, Transport


class WireTests(unittest.TestCase):
    def test_sse_split_utf8_newlines_fields_and_truncated_tail(self):
        text = '\ufeff: heartbeat\r\nid: one\r\nevent: note\r\ndata: 한글\r\ndata: second\r\n\r\nunknown: ignored\ndata: 0\n\ndata: lost'
        data = text.encode('utf-8')
        events = list(wire_events((data[index:index + 1] for index in range(len(data))), 'sse', StreamLimits()))
        self.assertEqual(['한글\nsecond', 0], [event['data'] for event in events])
        self.assertEqual(['note', 'message'], [event['event'] for event in events])
        self.assertEqual(['one', 'one'], [event['id'] for event in events])

    def test_ndjson_preserves_all_json_value_types(self):
        events = list(wire_events([b'0\r\nfalse\nnull\n[]\n"hello"'], 'ndjson', StreamLimits()))
        records = [Mapping().render(event) for event in events]
        self.assertEqual([0, False, None, [], 'hello'], [record['data'] for record in records])
        self.assertTrue(all(record['kind'] == 'data' for record in records))

    def test_text_decode_and_validation(self):
        data = '가나다'.encode('utf-8')
        events = list(wire_events((data[index:index + 1] for index in range(len(data))), 'text', StreamLimits()))
        self.assertEqual('가나다', ''.join(event['data'] for event in events))
        with self.assertRaises(AuthError):
            list(wire_events([b'\xff'], 'text', StreamLimits()))
        with self.assertRaises(AuthError):
            list(wire_events([b'{bad}\n'], 'ndjson', StreamLimits()))

    def test_wire_limits_and_media_type(self):
        with self.assertRaises(AuthError):
            list(wire_events([b'data: 1\n\ndata: 2\n\n'], 'sse', StreamLimits(max_events=1)))
        with self.assertRaises(AuthError):
            list(wire_events([b'data: abcd\n\n'], 'sse', StreamLimits(max_event_bytes=8)))
        self.assertEqual('sse', choose_protocol('auto', 'text/event-stream; charset=utf-8'))
        with self.assertRaises(AuthError):
            choose_protocol('auto', 'application/json')

    def test_empty_sse_data_is_dispatched_with_event_metadata(self):
        events = list(wire_events([b'event: empty\nid: empty-one\ndata:\n\n'], 'sse', StreamLimits()))
        records = []
        presenter = Presenter(records.append, [], Mapping())
        for event in events:
            presenter.accept(event)
        self.assertEqual(1, len(records))
        self.assertEqual('', records[0]['text'])
        self.assertEqual('empty-one', records[0]['event_id'])

    def test_generic_json_output_is_not_truncated_by_a_display_limit(self):
        records = []
        data = {'items': ['public stream data' * 400]}
        Presenter(records.append, [], Mapping()).accept({'event': 'message', 'id': None, 'data': data, 'json': True})
        self.assertEqual(data, records[0]['data'])

    def test_mapping_progress_is_actual_provider_data(self):
        mapping = Mapping({'rules': [{'event': 'work', 'kind': 'progress', 'fields': {'percent': ['done_percentage'], 'optional': ['absent']}}]})
        record = mapping.render({'event': 'work', 'data': {'done_percentage': 23}})
        self.assertEqual(23, record['percent'])
        self.assertNotIn('optional', record)
        self.assertNotIn('percent', mapping.render({'event': 'different', 'data': {}}))

    def test_error_mapping_cannot_overwrite_original_provider_envelope(self):
        with self.assertRaises(AuthError) as error:
            Mapping({'rules': [{'kind': 'error', 'fields': {'data': ['error']}}]})
        self.assertEqual('invalid_stream_mapping', error.exception.code)

    def test_stream_text_redacts_credentials_across_events_and_at_stop(self):
        records = []
        mapping = Mapping({'rules': [{'kind': 'text_delta', 'fields': {'text': ['chunk']}}]})
        presenter = Presenter(records.append, ['fixture-stream-secret'], mapping)
        for text in ('hello fixture-st', 'ream-secret world'):
            presenter.accept({'event': 'token', 'id': None, 'data': {'chunk': text}})
        presenter.flush_text()
        self.assertEqual('hello [REDACTED] world', ''.join(record['text'] for record in records))
        records.clear()
        presenter.accept({'event': 'token', 'id': None, 'data': {'chunk': 'fixture-stream-'}})
        presenter.flush_text()
        self.assertEqual('[REDACTED]', ''.join(record['text'] for record in records))

    def test_artifacts_require_explicit_output_and_matching_format(self):
        mapping = Mapping({'rules': [{'kind': 'image_preview', 'artifact': {'path': ['image'], 'format': 'png'}}]})
        with self.assertRaises(AuthError):
            Presenter(lambda _value: None, [], mapping)
        with tempfile.TemporaryDirectory(prefix='kh-stream-artifact-') as folder:
            records = []
            presenter = Presenter(records.append, [], mapping, folder)
            with self.assertRaises(AuthError):
                presenter.accept({'event': 'preview', 'id': None, 'data': {'image': base64.b64encode(b'not PNG').decode()}})
            self.assertEqual([], list(Path(folder).iterdir()))
            sensitive = b'\x89PNG\r\n\x1a\n' + b'fixture-stream-secret'
            presenter = Presenter(records.append, ['fixture-stream-secret'], mapping, folder)
            with self.assertRaises(AuthError) as error:
                presenter.accept({'event': 'preview', 'id': None, 'data': {'image': base64.b64encode(sensitive).decode()}})
            self.assertEqual('sensitive_stream_artifact', error.exception.code)
            self.assertEqual([], list(Path(folder).iterdir()))


class StreamFixture(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *_args):
        pass

    def do_GET(self):
        self.close_connection = True
        self.server.calls.append(self.path)
        if self.headers.get('Authorization') != 'Bearer fixture-stream-secret':
            self.send_error(401)
            return
        if self.path == '/redirect':
            self.send_response(302)
            self.send_header('Location', '/trap')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        if self.path == '/short':
            self.send_response(200)
            self.send_header('Content-Type', 'application/x-ndjson')
            self.send_header('Content-Length', '50')
            self.end_headers()
            self.wfile.write(b'1\n')
            self.wfile.flush()
            self.close_connection = True
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Transfer-Encoding', 'chunked')
        self.send_header('x-request-id', 'req-fixture-stream-secret' if self.path == '/provider-error' else 'req-stream-fixture')
        self.end_headers()
        try:
            payloads = (b'event: progress\ndata: {"percent":12}\n\n', b'event: finish\ndata: {"ok":true}\n\n')
            if self.path == '/artifact':
                self.server.gate.set()
                image = base64.b64encode(b'\x89PNG\r\n\x1a\n' + bytes(24)).decode()
                payloads = (('event: image\ndata: ' + json.dumps({'b64': image}) + '\n\n').encode(),)
            if self.path == '/provider-error':
                self.server.gate.set()
                payloads = (b'event: error\ndata: {"error":{"code":"generation_failed","message":"fixture-stream-secret failed"}}\n\n',)
            for payload in payloads:
                self.wfile.write(format(len(payload), 'x').encode() + b'\r\n' + payload + b'\r\n')
                self.wfile.flush()
                if not self.server.gate.wait(3):
                    return
            self.wfile.write(b'0\r\n\r\n')
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass


class HTTPStreamTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kh-stream-http-')
        self.addCleanup(self.temp.cleanup)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), StreamFixture)
        self.server.calls = []
        self.server.gate = threading.Event()
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.addCleanup(self.close_server)
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)
        store = Store(Path(self.temp.name) / 'vault')
        store.configure(validate_profile({'id': 'fixture', 'base_url': self.base, 'check_path': '/check'}, loopback=True))
        store.save('fixture', {'secret': 'fixture-stream-secret'}, store.get('fixture')['revision'])
        self.manager = Manager(store, Transport(loopback=True))
        self.mapping = {'rules': [{'event': 'progress', 'kind': 'progress', 'fields': {'percent': ['percent']}}, {'event': 'finish', 'kind': 'completed'}]}

    def close_server(self):
        self.server.gate.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.assertFalse(self.thread.is_alive())

    def test_callback_receives_first_event_before_server_gate(self):
        records = []
        def receive(record):
            records.append(record)
            if record['kind'] == 'progress':
                self.assertFalse(self.server.gate.is_set())
                self.server.gate.set()
        result = self.manager.stream('fixture', 'GET', '/stream', sink=receive, mapping=self.mapping)
        self.assertEqual('completed', result['status'])
        self.assertTrue(result['terminal_received'])
        self.assertEqual('connection_closed', records[-1]['kind'])
        self.assertTrue(records[-1]['local_connection_closed'])
        self.assertEqual('req-stream-fixture', result['request_id'])
        self.assertEqual('req-stream-fixture', next(record for record in records if record['kind'] == 'connected')['request_id'])
        self.assertEqual(list(range(1, len(records) + 1)), [record['seq'] for record in records])

    def test_nested_provider_error_and_request_id_are_retained_and_redacted(self):
        records = []
        mapping = {'rules': [{'event': 'error', 'kind': 'error', 'fields': {'message': ['message']}}]}
        result = self.manager.stream('fixture', 'GET', '/provider-error', sink=records.append, mapping=mapping)
        error = next(record for record in records if record['kind'] == 'error')
        self.assertEqual('generation_failed', error['data']['error']['code'])
        self.assertEqual('[REDACTED] failed', error['data']['error']['message'])
        self.assertEqual('provider_error', result['status'])
        self.assertEqual('req-[REDACTED]', result['request_id'])
        self.assertNotIn('fixture-stream-secret', json.dumps(records))
        self.assertEqual(['/provider-error'], self.server.calls)
        self.assertTrue(records[-1]['local_connection_closed'])

    def test_redirect_and_truncated_response_do_not_complete(self):
        records = []
        result = self.manager.stream('fixture', 'GET', '/redirect', sink=records.append)
        self.assertEqual('redirect_blocked', result['status'])
        self.assertNotIn('/trap', self.server.calls)
        result = self.manager.stream('fixture', 'GET', '/short', sink=records.append)
        self.assertEqual('truncated_stream', result['status'])
        self.assertFalse(result['terminal_received'])

    def test_keyboard_cancellation_releases_local_connection(self):
        records = []
        def cancel(record):
            records.append(record)
            if record['kind'] == 'progress':
                raise KeyboardInterrupt
        result = self.manager.stream('fixture', 'GET', '/stream', sink=cancel, mapping=self.mapping)
        self.assertEqual('cancelled', result['status'])
        self.assertEqual('connection_closed', records[-1]['kind'])
        self.assertTrue(records[-1]['local_connection_closed'])

    def test_artifact_write_failure_reports_error_and_closes_connection(self):
        records = []
        mapping = {'rules': [{'event': 'image', 'kind': 'artifact', 'artifact': {'path': ['b64'], 'format': 'png'}}]}
        with patch.object(Path, 'open', side_effect=OSError('controlled disk failure')):
            result = self.manager.stream('fixture', 'GET', '/artifact', sink=records.append, mapping=mapping,
                                         output_dir=str(Path(self.temp.name) / 'images'))
        self.assertEqual('artifact_write_error', result['status'])
        self.assertTrue(any(record['kind'] == 'error' and record['category'] == 'artifact_write_error' for record in records))
        self.assertEqual('artifact_write_error', records[-1]['status'])
        self.assertTrue(records[-1]['local_connection_closed'])


if __name__ == '__main__':
    unittest.main()
