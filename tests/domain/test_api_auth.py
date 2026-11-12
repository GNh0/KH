"""Protocol counterexamples against a real HTTP server and real current-user DPAPI.

The server enforces credential roles, refresh rotation and revocation order independently
of the client. It is not evidence that any paid/live provider account was exercised.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from src.api_auth.manager import Manager
from src.api_auth.profile import api_base, validate_bundle, validate_profile
from src.api_auth.security import AuthError, UserCipher, safe_output
from src.api_auth.store import Store
from src.api_auth.transport import Transport


ROOT = Path(__file__).resolve().parents[2]


class ProviderFixture(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def answer(self, code, body):
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    @property
    def state(self):
        return self.server.fixture

    def authorized(self):
        if self.headers.get('Authorization') in {'Bearer fixture-management-secret', 'Bearer fixture-management-secret-2'}:
            return True
        self.answer(403, {'error': 'management authority required'})
        return False

    def do_GET(self):
        path = urlsplit(self.path).path
        self.state['events'].append(('GET', path))
        if path.endswith('/admin/check') or path == '/v2/projects/123/locations/global/keys':
            if self.authorized():
                self.answer(200, {})
        elif path in {'/v1/models', '/workload/check', '/custom/check'}:
            self.state['checks'] += 1
            key = self.headers.get('Authorization', '').removeprefix('Bearer ') or self.headers.get('x-goog-api-key')
            if key not in self.state['valid']:
                self.answer(401, {'error': {'code': 'invalid_api_key'}})
            elif self.state['check_status'] != 200:
                self.answer(self.state['check_status'], {'error': 'controlled permission/quota/server failure'})
            else:
                if key != 'fixture-old-secret':
                    self.state['verified_new'] = True
                self.answer(200, {'data': [], 'echo': key, 'api_key': key})
        elif path.endswith('/keys/old-key'):
            if self.authorized():
                self.answer(200, {'name': 'projects/123/locations/global/keys/old-key', 'restrictions': self.state['restrictions'],
                                  'serviceAccountEmail': 'fixture@example.invalid', 'annotations': {'owner': 'fixture'}})
        elif path == '/v2/operations/create-one':
            if self.authorized():
                self.answer(200, {'name': 'operations/create-one', 'done': True,
                                  'response': {'name': 'projects/123/locations/global/keys/new-key'}})
        elif path == '/v2/operations/delete-one':
            if self.authorized():
                self.answer(200, {'name': 'operations/delete-one', 'done': True, 'response': {}})
        elif path.endswith('/keys/new-key/keyString'):
            if self.authorized():
                if self.state['string_status'] != 200:
                    self.answer(self.state['string_status'], {'error': 'controlled key retrieval failure'})
                else:
                    self.answer(200, {'keyString': 'fixture-new-secret'})
        elif path == '/v1/redirect':
            self.send_response(302)
            self.send_header('Location', '/leak')
            self.send_header('Content-Length', '0')
            self.end_headers()
        elif path == '/v1/ordinary-data':
            self.answer(200, {'entries': ['INVALID_GRANT', 'API_KEY_INVALID'], 'count': 2})
        elif path == '/leak':
            self.state['leaks'] += 1
            self.answer(200, {})
        else:
            self.answer(404, {})

    def do_POST(self):
        path = urlsplit(self.path).path
        raw = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        self.state['events'].append(('POST', path))
        if path == '/token':
            form = parse_qs(raw.decode())
            if form.get('grant_type') != ['refresh_token'] or form.get('refresh_token') != [self.state['refresh']]:
                self.answer(400, {'error': 'invalid_grant'})
                return
            self.state['refreshes'] += 1
            number = self.state['refreshes']
            token = 'fixture-refreshed-secret-' + str(number)
            self.state['refresh'] = 'fixture-refresh-' + str(number)
            self.state['valid'] = {token, 'fixture-management-secret'}
            self.answer(200, {'access_token': token, 'refresh_token': self.state['refresh'], 'expires_in': 3600, 'token_type': 'Bearer'})
            return
        if path == '/custom/tokens':
            body = json.loads(raw)
            key = self.headers.get('Authorization', '').removeprefix('Bearer ')
            if key not in self.state['valid'] or body != {'name': 'fixture', 'permissions': ['read']}:
                self.answer(403, {})
                return
            self.state['issues'] += 1
            self.answer(200, {'payload': {'credential': 'fixture-new-secret', 'id': 'custom-new', 'ttl': 3600}})
            return
        if not self.authorized():
            return
        body = json.loads(raw)
        if path == '/v1/organization/projects/proj-one/service_accounts/sa-one/api_keys':
            if body.get('scopes') != ['api.model.read'] or body.get('expires_in_seconds') != 3600:
                self.answer(400, {'error': 'unexpected privilege or lifetime'})
                return
            self.state['issues'] += 1
            if self.state['drop_issuance']:
                self.close_connection = True
                return
            self.answer(200, {'value': 'fixture-new-secret', 'id': 'key-new', 'expires_at': time.time() + 3600})
        elif path == '/v2/projects/123/locations/global/keys':
            key_id = parse_qs(urlsplit(self.path).query).get('keyId', [''])[0]
            if (body.get('restrictions') != self.state['restrictions'] or body.get('serviceAccountEmail') != 'fixture@example.invalid'
                    or body.get('annotations') != {'owner': 'fixture'} or not re.fullmatch(r'kh-[a-z0-9]{24}', key_id)):
                self.answer(400, {'error': 'restrictions or identity not preserved'})
                return
            self.state['issues'] += 1
            self.answer(200, {'name': 'operations/create-one', 'done': False})
        else:
            self.answer(404, {})

    def do_DELETE(self):
        path = urlsplit(self.path).path
        self.state['events'].append(('DELETE', path))
        if not self.authorized():
            return
        if not self.state['verified_new']:
            self.answer(409, {'error': 'old key cannot be removed before replacement verification'})
            return
        if self.state['delete_status'] != 200:
            self.answer(self.state['delete_status'], {'error': 'controlled revocation failure'})
            return
        self.state['deletes'] += 1
        self.state['valid'].discard('fixture-old-secret')
        if path.startswith('/v2/'):
            self.answer(200, {'name': 'operations/delete-one', 'done': True, 'response': {}})
        else:
            self.answer(200, {'deleted': True})


class ProfileTests(unittest.TestCase):
    def test_one_google_registration_can_use_google_api_family_with_origin_guards(self):
        profile = validate_profile({'id': 'google', 'provider': 'google-cloud', 'base_url': 'https://generativelanguage.googleapis.com',
                                    'check_path': '/v1beta/models', 'auth': 'header'})
        self.assertEqual('https://texttospeech.googleapis.com/v1', api_base(profile, 'https://texttospeech.googleapis.com/v1'))
        for url in ('https://googleapis.com.attacker.invalid', 'https://notgoogleapis.com', 'https://texttospeech.googleapis.com:444',
                    'http://texttospeech.googleapis.com', 'https://user@texttospeech.googleapis.com'):
            with self.subTest(url=url), self.assertRaises(AuthError):
                api_base(profile, url)

    def test_unsafe_endpoints_headers_and_nonfinite_expiry_are_rejected(self):
        base = {'id': 'example', 'base_url': 'https://example.invalid', 'check_path': '/check'}
        for url in ('http://example.invalid', 'https://user:password@example.invalid', 'https://example.invalid?key=secret', 'https://example.invalid/#fragment'):
            with self.subTest(url=url), self.assertRaises(AuthError):
                validate_profile({**base, 'base_url': url})
        for header in ('Host', 'Content-Length', 'bad\r\nheader'):
            with self.assertRaises(AuthError):
                validate_profile({**base, 'header': header})
        for end in (float('nan'), float('inf'), True, -1):
            with self.assertRaises(AuthError):
                validate_bundle({'secret': 'fixture', 'expires_at': end})

    def test_unknown_fields_cannot_smuggle_credentials_into_profiles(self):
        with self.assertRaises(AuthError):
            validate_profile({'id': 'example', 'base_url': 'https://example.invalid', 'check_path': '/', 'api_key': 'fixture'})
        self.assertEqual({'message': '[REDACTED]', 'refresh_token': '[REDACTED]'},
                         safe_output({'message': 'opaque-google-fixture-key', 'refresh_token': 'anything'}, ['opaque-google-fixture-key']))

    def test_echoed_secret_dictionary_keys_and_new_credential_fields_are_masked(self):
        result = safe_output({'fixture-current-secret': {'ok': True}, 'credential': 'fixture-new-secret',
                              'credentials': {'opaque': 'fixture-created-secret'}}, ['fixture-current-secret'])
        self.assertNotIn('fixture-current-secret', json.dumps(result))
        self.assertEqual('[REDACTED]', result['credential'])
        self.assertEqual('[REDACTED]', result['credentials'])

    def test_manual_and_oauth_profiles_cannot_enable_an_unrelated_delete_protocol(self):
        base = {'id': 'example', 'base_url': 'https://example.invalid', 'check_path': '/check'}
        for rotation in ({'mode': 'manual', 'revoke_previous': True, 'management_service': 'control'},
                         {'mode': 'oauth2', 'token_url': 'https://example.invalid/token', 'revoke_previous': True}):
            with self.assertRaises(AuthError):
                validate_profile({**base, 'rotation': rotation})


@unittest.skipUnless(os.name == 'nt', 'actual Windows current-user DPAPI')
class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kh-api-auth-test-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name).resolve()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), ProviderFixture)
        self.server.fixture = {'valid': {'fixture-old-secret', 'fixture-new-secret', 'fixture-management-secret'},
                               'refresh': 'fixture-refresh-0', 'refreshes': 0, 'issues': 0, 'deletes': 0,
                               'check_status': 200, 'delete_status': 200, 'string_status': 200,
                               'checks': 0, 'leaks': 0, 'verified_new': False, 'drop_issuance': False,
                               'events': [], 'restrictions': {'apiTargets': [{'service': 'fixture.googleapis.com', 'methods': ['Read']}],
                                                            'serverKeyRestrictions': {'allowedIps': ['127.0.0.1']}}}
        self.worker = threading.Thread(target=self.server.serve_forever)
        self.worker.start()
        self.addCleanup(self.close_server)
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)
        self.store = Store(self.folder / 'vault')
        self.manager = Manager(self.store, Transport(loopback=True))
        self.registration_plans = {}
        self.profile('workload', self.base + '/v1', '/models')

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=3)
        self.assertFalse(self.worker.is_alive())

    def profile(self, name, base, check, **values):
        profile = validate_profile({'id': name, 'base_url': base, 'check_path': check, **values}, loopback=True)
        self.store.configure(profile)
        return profile

    def register(self, name='workload', **values):
        plan = self.manager.prepare_registration(name, source_url=self.base + '/account', session_label='fixture-session',
                                                 account_label='fixture-account', create_key=True)['plan']['id']
        self.registration_plans[name] = plan
        self.manager.authorize_registration(plan)
        return self.manager.register(name, {'secret': 'fixture-old-secret', **values}, approved_plan=plan)

    def managed(self, mode, *, revoke_old=True):
        if mode == 'openai-service-account':
            self.profile('control', self.base + '/v1', '/admin/check')
            rotation = {'mode': mode, 'management_service': 'control', 'project_id': 'proj-one', 'service_account_id': 'sa-one',
                        'scopes': ['api.model.read'], 'lifetime_seconds': 3600, 'revoke_previous': revoke_old}
            remote = 'key-old'
        else:
            self.profile('control', self.base + '/v2', '/projects/123/locations/global/keys')
            rotation = {'mode': mode, 'management_service': 'control',
                        'resource_name': 'projects/123/locations/global/keys/old-key', 'revoke_previous': revoke_old}
            remote = rotation['resource_name']
        self.register('control', secret='fixture-management-secret')
        if mode == 'google-cloud-key':
            self.profile('workload', self.base + '/workload', '/check', auth='header', rotation=rotation)
        else:
            self.profile('workload', self.base + '/v1', '/models', rotation=rotation)
        self.register(remote_id=remote)
        return self.manager.prepare('workload', 'user_request')['plan']['id']

    def test_registration_cold_process_reuse_and_no_plaintext_at_rest_or_output(self):
        self.assertEqual('connected', self.register()['status'])
        self.assertTrue(self.manager.status('workload')['registered'])
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/kh_api.py'), '--loopback-fixture', 'request', 'workload', '--path', '/models'],
                                env={**os.environ, 'KH_API_DATA': str(self.folder / 'vault')}, capture_output=True, text=True, encoding='utf-8', check=True, timeout=10)
        self.assertNotIn('fixture-old-secret', result.stdout + result.stderr)
        self.assertEqual('[REDACTED]', json.loads(result.stdout)['data']['echo'])
        for file in self.folder.rglob('*'):
            if file.is_file():
                self.assertNotIn(b'fixture-old-secret', file.read_bytes())
        blob = UserCipher().seal({'secret': 'fixture'})
        with self.assertRaises(AuthError):
            UserCipher().open(blob[:20] + b'damaged')

    def test_initial_offline_registration_keeps_encrypted_candidate_for_check(self):
        self.server.fixture['check_status'] = 503
        self.assertEqual('reconnection_pending', self.register()['status'])
        self.assertFalse(self.manager.status('workload')['registered'])
        self.server.fixture['check_status'] = 200
        self.assertEqual('registered_and_connected', self.manager.maintain(self.registration_plans['workload'])['status'])
        self.assertTrue(self.manager.status('workload')['registered'])

    def test_pending_registration_check_respects_the_service_owner(self):
        self.server.fixture['check_status'] = 503
        self.register()
        self.server.fixture['check_status'] = 200
        with self.store.lease('workload'), self.assertRaises(AuthError) as error:
            self.manager.check('workload')
        self.assertEqual('service_busy', error.exception.code)
        self.assertEqual('connected', self.manager.check('workload')['status'])

    def test_prepare_cannot_mix_an_old_target_with_a_new_credential_revision(self):
        self.register(remote_id='old-id')
        original = self.store.plan
        def interleave(service, details, snapshot):
            self.store.save(service, {'secret': 'fixture-new-secret', 'remote_id': 'new-id'}, snapshot['revision'])
            return original(service, details, snapshot)
        with patch.object(self.store, 'plan', interleave), self.assertRaises(AuthError) as error:
            self.manager.prepare('workload', 'user_request')
        self.assertEqual('stale_plan', error.exception.code)

    def test_manual_replacement_requires_plan_and_completed_plan_cannot_replay(self):
        self.register()
        self.assertEqual('already_registered', self.manager.prepare_registration('workload', source_url=self.base + '/account',
            session_label='fixture-session', account_label='fixture-account')['status'])
        plan = self.manager.prepare('workload', 'user_request')['plan']
        self.assertEqual(0, self.server.fixture['issues'])
        with self.assertRaises(AuthError):
            self.manager.maintain('not-an-approved-plan')
        self.manager.authorize(plan['id'])
        result = self.manager.maintain(plan['id'], replacement={'secret': 'fixture-new-secret'})
        self.assertEqual('renewed_and_reconnected', result['status'])
        with self.assertRaises(AuthError) as error:
            self.manager.maintain(plan['id'], replacement={'secret': 'fixture-old-secret'})
        self.assertEqual('plan_consumed', error.exception.code)

    def test_manual_bad_pending_candidate_can_be_corrected_in_the_approved_plan(self):
        self.register()
        plan = self.manager.prepare('workload', 'user_request')['plan']['id']
        self.manager.authorize(plan)
        self.assertEqual('reconnection_pending', self.manager.maintain(plan, replacement={'secret': 'fixture-invalid-secret'})['status'])
        self.assertEqual('renewed_and_reconnected', self.manager.maintain(plan, replacement={'secret': 'fixture-new-secret'})['status'])
        self.assertEqual('fixture-new-secret', self.store.get('workload')['active']['secret'])

    def test_success_response_containing_error_words_is_still_success(self):
        self.register()
        result = self.manager.request('workload', 'GET', '/ordinary-data')
        self.assertEqual('connected', result['status'])
        self.assertEqual(2, result['data']['count'])

    def test_expired_stale_and_concurrent_plans_are_rejected(self):
        self.register()
        plan = self.manager.prepare('workload', 'user_request')['plan']
        plan['expires_at'] = time.time() - 1
        self.store.update_plan(plan)
        with self.assertRaises(AuthError) as error:
            self.manager.maintain(plan['id'], replacement={'secret': 'fixture-new-secret'})
        self.assertEqual('approval_expired', error.exception.code)
        plan = self.manager.prepare('workload', 'user_request')['plan']
        with self.store.lease('workload'), self.assertRaises(AuthError) as error:
            self.manager.maintain(plan['id'], replacement={'secret': 'fixture-new-secret'})
        self.assertEqual('service_busy', error.exception.code)
        self.store.save('workload', {'secret': 'fixture-new-secret'}, self.store.get('workload')['revision'])
        with self.assertRaises(AuthError) as error:
            self.manager.maintain(plan['id'])
        self.assertEqual('stale_plan', error.exception.code)

    def test_expiry_unknown_due_and_expired_are_distinct(self):
        self.register()
        self.assertEqual('unknown', self.manager.status('workload')['expiry'])
        entry = self.store.get('workload')
        self.store.save('workload', {'secret': 'fixture-old-secret', 'expires_at': time.time() + 60}, entry['revision'])
        self.assertTrue(self.manager.request('workload', 'GET', '/models')['renewal_due'])
        entry = self.store.get('workload')
        self.store.save('workload', {'secret': 'fixture-old-secret', 'expires_at': time.time() - 1}, entry['revision'])
        calls = self.server.fixture['checks']
        self.assertEqual('renewal_approval_required', self.manager.request('workload', 'GET', '/models')['status'])
        self.assertEqual(calls, self.server.fixture['checks'])

    def test_auth_permissions_quota_and_server_failure_do_not_rotate_keys(self):
        self.register()
        for status, name in [(403, 'permission_denied'), (429, 'quota_or_rate_limit'), (503, 'service_error')]:
            self.server.fixture['check_status'] = status
            self.assertEqual(name, self.manager.check('workload')['status'])
        self.assertEqual(0, self.server.fixture['issues'])

    def test_oauth_rotated_refresh_survives_failed_reconnect_and_is_not_reissued(self):
        self.profile('workload', self.base + '/v1', '/models', rotation={'mode': 'oauth2', 'token_url': self.base + '/token'})
        self.register(refresh_token='fixture-refresh-0', client_id='fixture-client')
        plan = self.manager.prepare('workload', 'expired')['plan']['id']
        self.server.fixture['check_status'] = 503
        self.assertEqual('reconnection_pending', self.manager.maintain(plan)['status'])
        self.assertEqual('fixture-refresh-1', self.store.get('workload')['pending']['refresh_token'])
        self.server.fixture['check_status'] = 200
        self.assertEqual('renewed_and_reconnected', self.manager.maintain(plan)['status'])
        self.assertEqual(1, self.server.fixture['refreshes'])
        again = self.manager.prepare('workload', 'user_request')['plan']['id']
        self.manager.maintain(again)
        self.assertEqual(2, self.server.fixture['refreshes'])

    def test_openai_service_account_issue_verify_then_revoke(self):
        plan = self.managed('openai-service-account')
        self.assertEqual(0, self.server.fixture['issues'])
        result = self.manager.maintain(plan)
        self.assertEqual('renewed_and_reconnected', result['status'])
        self.assertEqual((1, 1), (self.server.fixture['issues'], self.server.fixture['deletes']))
        self.assertEqual('fixture-new-secret', self.store.get('workload')['active']['secret'])
        self.assertNotIn('fixture-old-secret', self.server.fixture['valid'])

    def test_google_reissue_preserves_restrictions_and_resumes_same_operation(self):
        plan = self.managed('google-cloud-key')
        self.server.fixture['string_status'] = 503
        with self.assertRaises(AuthError):
            self.manager.maintain(plan)
        self.assertEqual(1, self.server.fixture['issues'])
        self.server.fixture['string_status'] = 200
        self.assertEqual('renewed_and_reconnected', self.manager.maintain(plan)['status'])
        self.assertEqual((1, 1), (self.server.fixture['issues'], self.server.fixture['deletes']))

    def test_new_json_api_joins_by_profile_without_provider_code(self):
        self.profile('custom', self.base + '/custom', '/check', rotation={
            'mode': 'http-json', 'issue_path': '/tokens', 'issue_body': {'name': 'fixture', 'permissions': ['read']},
            'secret_field': ['payload', 'credential'], 'id_field': ['payload', 'id'], 'expires_in_field': ['payload', 'ttl']})
        self.register('custom')
        plan = self.manager.prepare('custom', 'user_request')['plan']['id']
        self.assertEqual('renewed_and_reconnected', self.manager.maintain(plan)['status'])
        self.assertEqual(1, self.server.fixture['issues'])
        self.assertEqual('custom-new', self.store.get('custom')['active']['remote_id'])
        self.assertEqual('connected', self.manager.request('custom', 'GET', '/check')['status'])

    def test_cold_process_cannot_take_over_a_live_maintenance_lock(self):
        self.register()
        script = 'import sys;sys.path.insert(0,sys.argv[1]);from src.api_auth.store import Store;from pathlib import Path\nwith Store(Path(sys.argv[2])).lease("workload"): print("unexpected")'
        with self.store.lease('workload'):
            result = subprocess.run([sys.executable, '-B', '-c', script, str(ROOT), str(self.folder / 'vault')], capture_output=True, timeout=10)
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn(b'unexpected', result.stdout)
        with self.store.lease('workload'):
            pass

    def test_lost_issuance_response_never_blindly_issues_again(self):
        plan = self.managed('openai-service-account')
        self.server.fixture['drop_issuance'] = True
        with self.assertRaises(AuthError) as error:
            self.manager.maintain(plan)
        self.assertEqual('network_error', error.exception.code)
        with self.assertRaises(AuthError) as error:
            self.manager.maintain(plan)
        self.assertEqual('issuance_unknown', error.exception.code)
        with self.assertRaises(AuthError) as error:
            self.manager.prepare('workload', 'user_request')
        self.assertEqual('issuance_unknown', error.exception.code)
        self.assertEqual(1, self.server.fixture['issues'])

    def test_old_planned_nonce_cannot_bypass_another_ambiguous_issuance(self):
        first = self.managed('openai-service-account')
        second = self.manager.prepare('workload', 'user_request')['plan']['id']
        self.server.fixture['drop_issuance'] = True
        with self.assertRaises(AuthError):
            self.manager.maintain(first)
        with self.assertRaises(AuthError) as error:
            self.manager.maintain(second)
        self.assertEqual('maintenance_in_progress', error.exception.code)
        self.assertEqual(1, self.server.fixture['issues'])

    def test_reconciliation_requires_an_explicit_inventory_outcome(self):
        plan = self.managed('openai-service-account')
        self.server.fixture['drop_issuance'] = True
        with self.assertRaises(AuthError):
            self.manager.maintain(plan)
        with self.assertRaises(AuthError):
            self.manager.reconcile(plan, 'not-issued', '')
        result = self.manager.reconcile(plan, 'orphan-revoked', 'fixture inventory cleanup request reference 123')
        self.assertEqual('reconciled', result['status'])
        with self.assertRaises(AuthError) as error:
            self.manager.maintain(plan)
        self.assertEqual('plan_consumed', error.exception.code)
        self.assertEqual('user_approval_required', self.manager.prepare('workload', 'user_request')['status'])

    def authority_resume(self, stage):
        plan = self.managed('openai-service-account')
        self.server.fixture['check_status' if stage == 'candidate_saved' else 'delete_status'] = 503
        self.manager.maintain(plan)
        self.assertEqual(stage, self.store.get_plan(plan)['stage'])
        control = self.manager.prepare('control', 'user_request')['plan']['id']
        self.manager.authorize(control)
        self.manager.maintain(control, replacement={'secret': 'fixture-management-secret-2'})
        fresh = self.manager.prepare('workload', 'user_request')['plan']
        self.assertEqual(plan, fresh['resume_of'])
        self.assertEqual(stage, fresh['resume_stage'])
        self.assertEqual('key-old', fresh['details']['old_remote_id'])
        self.server.fixture['check_status'] = self.server.fixture['delete_status'] = 200
        self.assertEqual('renewed_and_reconnected', self.manager.maintain(fresh['id'])['status'])
        self.assertEqual(1, self.server.fixture['issues'])
        with self.assertRaises(AuthError) as error:
            self.manager.maintain(plan)
        self.assertEqual('plan_consumed', error.exception.code)

    def test_changed_management_authority_can_reapprove_and_resume_candidate(self):
        self.authority_resume('candidate_saved')

    def test_changed_management_authority_can_reapprove_and_finish_revocation(self):
        self.authority_resume('active_saved')

    def test_revocation_failure_resumes_without_another_issuance(self):
        plan = self.managed('openai-service-account')
        self.server.fixture['delete_status'] = 503
        result = self.manager.maintain(plan)
        self.assertEqual('revocation_pending', result['status'])
        self.assertTrue(result['credential_activated'])
        self.assertTrue(result['connection_verified'])
        self.assertEqual('active_saved', self.store.get_plan(plan)['stage'])
        self.assertEqual('fixture-new-secret', self.store.get('workload')['active']['secret'])
        self.server.fixture['delete_status'] = 200
        self.assertEqual('renewed_and_reconnected', self.manager.maintain(plan)['status'])
        self.assertEqual(1, self.server.fixture['issues'])

    def test_redirect_is_not_followed_and_registered_target_is_immutable(self):
        self.register()
        self.assertEqual('redirect_blocked', self.manager.request('workload', 'GET', '/redirect')['status'])
        self.assertEqual(0, self.server.fixture['leaks'])
        with self.assertRaises(AuthError):
            self.profile('workload', self.base + '/different', '/check')

    def test_registration_requires_the_exact_approved_account_session_plan(self):
        plan = self.manager.prepare_registration('workload', source_url=self.base + '/account', session_label='fixture-session',
                                                 account_label='fixture-account', create_key=True)['plan']
        self.assertFalse(self.manager.status('workload')['registered'])
        self.assertEqual('fixture-session', plan['details']['session_label'])
        self.assertTrue(plan['details']['create_key_if_needed'])
        with self.assertRaises(AuthError):
            self.manager.register('workload', {'secret': 'fixture-old-secret'}, approved_plan='not-approved')
        self.assertFalse(self.manager.status('workload')['registered'])
        with self.assertRaises(AuthError):
            self.manager.register('workload', {'secret': 'fixture-old-secret'}, approved_plan=plan['id'])
        self.manager.authorize_registration(plan['id'])
        self.assertEqual('connected', self.manager.register('workload', {'secret': 'fixture-old-secret'}, approved_plan=plan['id'])['status'])

    def test_manual_renewal_displays_source_and_requires_fresh_authorization(self):
        self.register()
        plan = self.manager.prepare('workload', 'expired')['plan']
        self.assertEqual('manual_replacement', plan['details']['purpose'])
        self.assertEqual('fixture-session', plan['details']['session_label'])
        self.assertEqual('fixture-account', plan['details']['account_label'])
        with self.assertRaises(AuthError) as error:
            self.manager.maintain(plan['id'], replacement={'secret': 'fixture-new-secret'})
        self.assertEqual('approval_required', error.exception.code)
        self.assertEqual('planned', self.store.get_plan(plan['id'])['stage'])
        self.manager.authorize(plan['id'])
        self.assertEqual('renewed_and_reconnected', self.manager.maintain(plan['id'], replacement={'secret': 'fixture-new-secret'})['status'])
        changed = self.manager.prepare('workload', 'user_request', source_url=self.base + '/other-account',
            session_label='other-session', account_label='other-account', create_key=False)['plan']
        self.assertEqual('other-account', changed['details']['account_label'])
        self.assertFalse(changed['details']['create_key_if_needed'])
        with self.assertRaises(AuthError):
            self.manager.prepare('workload', 'user_request', account_label='partial-change')

    def test_observed_metadata_keeps_the_key_and_rejects_races_or_other_key_ids(self):
        self.register()
        revision = self.store.get('workload')['revision']
        result = self.manager.record_metadata('workload', revision=revision, expires_at=time.time() + 3600, remote_id='same-key-id')
        self.assertEqual('due', result['credential']['expiry'])
        self.assertEqual('fixture-old-secret', self.store.get('workload')['active']['secret'])
        with self.assertRaises(AuthError):
            self.manager.record_metadata('workload', revision=revision, expires_at=time.time() + 7200)
        revision = self.store.get('workload')['revision']
        with self.assertRaises(AuthError):
            self.manager.record_metadata('workload', revision=revision, remote_id='different-key-id')
        plan = self.manager.prepare('workload', 'expiry_due')['plan']['id']
        self.manager.authorize(plan)
        with self.assertRaises(AuthError):
            self.manager.record_metadata('workload', revision=revision, expires_at=time.time() + 7200)


class SessionInputTests(unittest.TestCase):
    def test_no_window_or_implicit_secret_input_is_used(self):
        from src.api_auth.input import read_credential
        with self.assertRaises(AuthError) as error:
            read_credential()
        self.assertEqual('authorized_session_required', error.exception.code)

    def test_standard_camelcase_credential_fields_are_masked(self):
        value = {'accessToken': 'new-a', 'refreshToken': 'new-b', 'clientSecret': 'new-c', 'idToken': 'new-d'}
        self.assertEqual({key: '[REDACTED]' for key in value}, safe_output(value))

    def test_clipboard_sequence_guard_preserves_unrelated_user_data(self):
        from src.api_auth.input import clear_owned_clipboard, read_credential
        class User:
            reads = 0
            def GetClipboardSequenceNumber(self): return 42
            def OpenClipboard(self, owner): return True
            def CloseClipboard(self): return True
            def EmptyClipboard(self): self.reads += 1; return True
        user = User()
        with patch('src.api_auth.input._clipboard_api', return_value=(user, object())):
            with self.assertRaises(AuthError):
                read_credential(clipboard=True, expected_sequence=41)
            self.assertFalse(clear_owned_clipboard(41))
        self.assertEqual(0, user.reads)

