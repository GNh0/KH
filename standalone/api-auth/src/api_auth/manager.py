"""One lifecycle for registration, reuse, planned renewal and reconnection."""
from contextlib import ExitStack
import re
import time

from src.api_auth.profile import api_base, expiry, fingerprint, validate_bundle, validate_profile
from src.api_auth.providers import google_issue, headers, http_issue, openai_issue, refresh, revoke
from src.api_auth.security import AuthError, safe_output, secret_values
from src.api_auth.store import Store
from src.api_auth.streaming import Mapping, Presenter, choose_protocol, strict_json, wire_events
from src.api_auth.transport import StreamLimits, Transport, category, validate_url


class Manager:
    def __init__(self, store: Store, transport: Transport | None = None):
        self.store = store
        self.transport = transport or Transport()

    def entry(self, service: str) -> dict:
        value = self.store.get(service)
        validate_profile(value['profile'], loopback=self.transport.loopback)
        return value

    def _verify(self, entry: dict, bundle: dict):
        profile = entry['profile']
        return self.transport.send('GET', profile['base_url'] + profile['check_path'], headers(profile, bundle))

    def status(self, service: str) -> dict:
        value = self.entry(service)
        bundle = value['active'] or value['pending']
        return {'service': service, 'registered': value['active'] is not None, 'pending_reconnection': value['pending'] is not None,
                'expiry': expiry(bundle, value['profile']) if bundle else 'unregistered',
                'expires_at': bundle.get('expires_at') if bundle else None,
                'maintenance_mode': value['profile']['rotation']['mode'], 'revision': value['revision']}

    def record_metadata(self, service: str, *, revision: int, expires_at=None, remote_id=None) -> dict:
        with self.store.lease(service):
            current = self.entry(service)
            if current['revision'] != revision:
                raise AuthError('stale_plan', 'Credential changed before its observed metadata was recorded.')
            if self.store.unfinished(service):
                raise AuthError('maintenance_in_progress', 'Finish the current registration or maintenance before changing metadata.')
            if current['active'] is None:
                raise AuthError('registration_required', 'Register and verify this credential before recording its metadata.')
            if expires_at is None and remote_id is None:
                raise AuthError('invalid_request', 'Supply a verified expiry timestamp or remote identifier for this same credential.')
            bundle = dict(current['active'])
            if remote_id is not None:
                if bundle.get('remote_id') and bundle['remote_id'] != remote_id:
                    raise AuthError('credential_changed', 'A different remote identifier may describe another key; use its own registration.')
                bundle['remote_id'] = remote_id
            if expires_at is not None:
                bundle['expires_at'] = expires_at
            self.store.save(service, validate_bundle(bundle), revision)
        return {'status': 'metadata_recorded', 'credential': self.status(service),
                'boundary': 'Caller-observed metadata for the same approved credential; this operation does not query or alter the remote key.'}

    def prepare_registration(self, service: str, *, source_url: str, session_label: str, account_label: str, create_key=False, clipboard_baseline=None) -> dict:
        current = self.entry(service)
        if current['active']:
            return {'status': 'already_registered', 'credential': self.status(service)}
        unfinished = self.store.unfinished(service)
        if unfinished:
            return {'status': 'maintenance_in_progress', 'plan': unfinished}
        self._validate_source_scope(source_url, session_label, account_label)
        details = {'purpose': 'registration', 'mode': 'register', 'source_url': source_url,
                   'session_label': session_label, 'account_label': account_label, 'create_key_if_needed': bool(create_key),
                   'revoke_previous': False, 'actions': ['use the named account/session after explicit user approval',
                       'create a key if approved and needed' if create_key else 'obtain an existing recoverable credential',
                       'handoff internally without displaying the secret', 'save encrypted', 'verify connection']}
        if clipboard_baseline is not None:
            if isinstance(clipboard_baseline, bool) or not isinstance(clipboard_baseline, int) or clipboard_baseline < 0:
                raise AuthError('clipboard_provenance_required', 'Clipboard baseline must be the host sequence number.')
            details['clipboard_baseline'] = clipboard_baseline
        plan = self.store.plan(service, details, current)
        return {'status': 'user_approval_required', 'plan': plan,
                'approval_boundary': 'The host/caller must obtain actual user approval for this named account/session and scope before acquiring credentials. Labels are not independent session attestation.'}

    def _validate_source_scope(self, source_url, session_label, account_label):
        validate_url(source_url, loopback=self.transport.loopback)
        if not all(isinstance(value, str) and 1 <= len(value) <= 200 and not any(ord(c) < 32 for c in value)
                   for value in (session_label, account_label)):
            raise AuthError('source_scope_required', 'Identify the actual account and host-owned source session for user approval.')

    def register(self, service: str, bundle: dict, *, approved_plan: str) -> dict:
        bundle = validate_bundle(bundle)
        plan = self.store.get_plan(approved_plan)
        if plan['service'] != service or plan['details'].get('purpose') != 'registration':
            raise AuthError('approval_required', 'Use the exact registration plan approved for this account/session and service.')
        if plan['stage'] not in {'approved', 'candidate_saved'}:
            raise AuthError('approval_required', 'Record actual account/session approval before acquiring or handing off a registration credential.')
        result = self.maintain(approved_plan, replacement=bundle)
        if result['status'] == 'registered_and_connected':
            result['status'] = 'connected'
        return result

    def authorize_registration(self, plan_id: str) -> dict:
        plan = self.store.get_plan(plan_id)
        if plan['details'].get('purpose') != 'registration':
            raise AuthError('approval_required', 'This is not an account/session registration plan.')
        return self.authorize(plan_id)

    def authorize(self, plan_id: str) -> dict:
        plan = self.store.get_plan(plan_id)
        if plan['details'].get('purpose') not in {'registration', 'manual_replacement'}:
            raise AuthError('approval_required', 'This plan does not authorize browser/account credential acquisition.')
        with self.store.lease(plan['service']):
            plan = self.store.get_plan(plan_id)
            current = self.entry(plan['service'])
            if plan['revision'] != current['revision'] or plan['profile_hash'] != fingerprint(current['profile']):
                raise AuthError('stale_plan', 'Credential or source scope changed before account/session authorization.')
            other = self.store.unfinished(plan['service'], excluding=plan_id)
            if other:
                raise AuthError('maintenance_in_progress', 'Another registration or maintenance operation owns this service.')
            if plan['stage'] == 'planned':
                if plan['expires_at'] < time.time():
                    raise AuthError('approval_expired', 'Prepare a fresh registration scope; no account action was authorized by this expired nonce.')
                self.store.approve(plan, 'chat')
            elif plan['stage'] != 'approved':
                raise AuthError('invalid_state', 'This account-session operation is already in progress or terminal; inspect its existing state.')
        return {'status': 'account_session_authorized', 'plan_id': plan_id, 'scope': plan['details'],
                'boundary': 'Records actual caller-obtained conversational approval; it does not independently authenticate the user or browser session.'}

    def check(self, service: str) -> dict:
        current = self.entry(service)
        if current['active'] is None and current['pending']:
            with self.store.lease(service):
                return self._check(service, self.entry(service))
        return self._check(service, current)

    def _check(self, service: str, current: dict) -> dict:
        bundle = current['active'] or current['pending']
        if bundle is None:
            return {'service': service, 'status': 'registration_required'}
        response = self._verify(current, bundle)
        return {'service': service, 'status': response.category, 'http_status': response.status,
                'renewal_due': expiry(bundle, current['profile']) in {'due', 'expired'},
                'pending_reconnection': self.entry(service)['pending'] is not None}

    def request(self, service: str, method: str, path: str, body=None, *, selected_base: str | None = None) -> dict:
        if method not in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD'}:
            raise AuthError('invalid_request', 'Unsupported HTTP method.')
        if not isinstance(path, str) or not path.startswith('/') or path.startswith('//') or '\\' in path:
            raise AuthError('invalid_request', 'Use a path relative to the registered API base URL.')
        current = self.entry(service)
        bundle = current['active']
        if bundle is None:
            return {'service': service, 'status': 'registration_required'}
        state = expiry(bundle, current['profile'])
        if state == 'expired':
            return {'service': service, 'status': 'renewal_approval_required', 'reason': 'expired'}
        base = api_base(current['profile'], selected_base, loopback=self.transport.loopback)
        url = validate_url(base + path, loopback=self.transport.loopback)
        response = self.transport.send(method, url, headers(current['profile'], bundle), body)
        return safe_output({'service': service, 'status': response.category, 'http_status': response.status,
                            'renewal_due': state == 'due', 'data': response.data}, secret_values(bundle))

    def stream(self, service: str, method: str, path: str, body=None, *, sink, protocol='auto', mapping=None,
               output_dir=None, limits: StreamLimits | None = None, selected_base: str | None = None) -> dict:
        if method not in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD'}:
            raise AuthError('invalid_request', 'Unsupported HTTP method.')
        if not isinstance(path, str) or not path.startswith('/') or path.startswith('//') or '\\' in path:
            raise AuthError('invalid_request', 'Use a path relative to the registered API base URL.')
        if protocol not in {'auto', 'sse', 'ndjson', 'text'}:
            raise AuthError('invalid_stream_protocol', 'Choose auto, sse, ndjson or text.')
        current = self.entry(service)
        bundle = current['active']
        if bundle is None:
            raise AuthError('registration_required', 'Register this service before streaming.')
        if expiry(bundle, current['profile']) == 'expired':
            raise AuthError('renewal_approval_required', 'This credential expired; review its maintenance before another request.')
        base = api_base(current['profile'], selected_base, loopback=self.transport.loopback)
        url = validate_url(base + path, loopback=self.transport.loopback)
        limits = limits or StreamLimits()
        presenter = Presenter(sink, secret_values(bundle), Mapping(mapping), output_dir)
        outgoing = headers(current['profile'], bundle)
        outgoing['Accept'] = {'sse': 'text/event-stream', 'ndjson': 'application/x-ndjson', 'text': 'text/plain'}.get(protocol, 'text/event-stream, application/x-ndjson, text/plain')
        result = {'service': service, 'status': 'stream_closed', 'terminal_received': False}
        presenter.emit({'kind': 'request_started', 'service': service, 'method': method,
                        'renewal_due': expiry(bundle, current['profile']) == 'due'})
        try:
            with self.transport.open_stream(method, url, outgoing, body, limits) as response:
                result.update(http_status=response.status, request_id=response.request_id)
                if not 200 <= response.status < 300:
                    error_blocks, error_size = [], 0
                    for block in response.chunks:
                        error_size += len(block)
                        if error_size > 1024 * 1024:
                            raise AuthError('response_too_large', 'Stream error response exceeded the 1 MiB bound.')
                        error_blocks.append(block)
                    raw = b''.join(error_blocks)
                    try:
                        data = strict_json(raw)
                    except (ValueError, UnicodeError, RecursionError):
                        data = {'message': 'Non-JSON error response omitted.'}
                    result['status'] = category(response.status, data)
                    presenter.emit({'kind': 'error', 'category': result['status'], 'http_status': response.status, 'data': data})
                else:
                    actual_protocol = choose_protocol(protocol, response.content_type)
                    presenter.emit({'kind': 'connected', 'http_status': response.status, 'protocol': actual_protocol,
                                    'request_id': response.request_id})
                    for wire in wire_events(response.chunks, actual_protocol, limits):
                        terminal, kind = presenter.accept(wire)
                        if terminal:
                            result.update(status='provider_error' if kind == 'error' else 'completed', terminal_received=True)
                            break
                    presenter.flush_text()
        except AuthError as error:
            result['status'] = error.code
            presenter.flush_text()
            presenter.emit({'kind': 'error', 'category': error.code, 'message': str(error)})
        except KeyboardInterrupt:
            result['status'] = 'cancelled'
            presenter.flush_text()
            presenter.emit({'kind': 'cancelled', 'upstream_cancelled': False,
                            'message': 'Local stream stopped. Closing HTTP does not prove that remote work was cancelled.'})
        finally:
            presenter.emit({'kind': 'connection_closed', **result, 'local_connection_closed': True})
        return safe_output(result, secret_values(bundle))

    def prepare(self, service: str, reason: str, *, clipboard_baseline=None, source_url=None, session_label=None, account_label=None, create_key=None) -> dict:
        if reason not in {'user_request', 'expiry_due', 'expired', 'authentication_rejected'}:
            raise AuthError('invalid_request', 'Maintenance reason must identify user request, expiry, or an authentication failure.')
        current = self.entry(service)
        unfinished = self.store.unfinished(service)
        resume = None
        if unfinished:
            if unfinished['stage'] == 'issuing' and not unfinished.get('operation'):
                raise AuthError('issuance_unknown', 'Unresolved issuance in plan ' + unfinished['id'] + '. Inspect provider inventory and reconcile it before another issuance.')
            management_id = unfinished['details'].get('management_service')
            changed_authority = management_id and self.entry(management_id)['revision'] != unfinished['details']['management_revision']
            if changed_authority and unfinished['stage'] in {'approved', 'candidate_saved', 'active_saved'}:
                resume = unfinished
            else:
                return {'status': 'maintenance_in_progress', 'plan': unfinished,
                        'next_action': 'Resume the existing approved scope if still authorized; do not create another issuance.'}
        profile, bundle = current['profile'], current['active'] or current['pending']
        if bundle is None:
            raise AuthError('registration_required', 'Register a credential before preparing maintenance.')
        config = profile['rotation']
        details = {'reason': reason, 'mode': 'reconnect' if current['pending'] else config['mode'],
                   'replacement_policy': config,
                   'api_origin': profile['base_url'], 'verification_path': profile['check_path'],
                   'old_remote_id': (current['active'] or {}).get('remote_id') or config.get('resource_name'),
                   'revoke_previous': config.get('revoke_previous', False),
                   'actions': ['obtain replacement or resume pending credential', 'save candidate encrypted',
                               'verify connection', 'activate verified credential']}
        if config['mode'] == 'manual':
            supplied = (source_url, session_label, account_label)
            if any(value is not None for value in supplied):
                if not all(value is not None for value in supplied):
                    raise AuthError('source_scope_required', 'A changed source requires its URL, account and host-owned session together.')
                scope = dict(source_url=source_url, session_label=session_label, account_label=account_label,
                             create_key_if_needed=bool(create_key))
            else:
                scope = self.store.source_scope(service)
                if scope is None:
                    raise AuthError('source_scope_required', 'Identify the official source URL, account and host-owned session before manual replacement.')
                if create_key is not None:
                    scope['create_key_if_needed'] = bool(create_key)
            self._validate_source_scope(scope['source_url'], scope['session_label'], scope['account_label'])
            details.update(scope, purpose='manual_replacement')
            details['actions'][0:1] = ['use the named account/session after fresh explicit user approval',
                'create a replacement if approved and needed' if scope['create_key_if_needed'] else 'obtain an existing recoverable replacement',
                'handoff internally without displaying the secret']
        elif any(value is not None for value in (source_url, session_label, account_label, create_key)):
            raise AuthError('invalid_request', 'Source session options apply to manual account/session replacement only.')
        if clipboard_baseline is not None:
            if isinstance(clipboard_baseline, bool) or not isinstance(clipboard_baseline, int) or clipboard_baseline < 0:
                raise AuthError('clipboard_provenance_required', 'Clipboard baseline must be the host sequence number.')
            details['clipboard_baseline'] = clipboard_baseline
        if config['mode'] == 'oauth2':
            details['refresh_endpoint'] = config['token_url']
            if not current['pending'] and not bundle.get('refresh_token'):
                raise AuthError('user_input_required', 'OAuth renewal needs a refresh credential; register a complete credential for this service.')
        if config['mode'] == 'google-cloud-key':
            parent = config['resource_name'].rsplit('/keys/', 1)[0]
            if not re.fullmatch(re.escape(parent) + r'/keys/[A-Za-z0-9-]+', str(details['old_remote_id'])):
                raise AuthError('invalid_credential', 'Stored Google key must belong to the configured project.')
        if config.get('management_service'):
            management = self.entry(config['management_service'])
            if not management['active'] or expiry(management['active'], management['profile']) == 'expired':
                raise AuthError('management_registration_required', 'Register or renew the separate management credential first.')
            details.update(management_service=config['management_service'], management_revision=management['revision'],
                           management_origin=management['profile']['base_url'])
        if resume:
            # Re-approval changes only authority for the remaining steps; it must not issue another key.
            fresh_authority = {key: details[key] for key in ('management_service', 'management_revision', 'management_origin')}
            details = {**resume['details'], **fresh_authority, 'reason': reason}
            details['actions'] = (['verify the saved candidate', 'activate the saved candidate'] if resume['stage'] == 'candidate_saved'
                                  else ['finish pending previous-key revocation'] if resume['stage'] == 'active_saved'
                                  else details['actions'])
        if details['revoke_previous']:
            if not details['old_remote_id'] or (not config.get('management_service') and config['mode'] != 'http-json'):
                raise AuthError('invalid_profile', 'Revocation requires the old resource identifier and a separate management credential.')
            details['actions'].append('revoke previous remote key after successful activation')
        else:
            details['actions'].append('previous remote key is retained; revoke it separately if required')
        plan = self.store.plan(service, details, current)
        if resume:
            plan.update(resume_of=resume['id'], resume_stage=resume['stage'])
            for field in ('operation', 'revoke_operation'):
                if field in resume:
                    plan[field] = resume[field]
            self.store.update_plan(plan)
        return {'status': 'user_approval_required', 'plan': plan,
                'approval_scope': 'The displayed maintenance, encrypted save, reconnection and any displayed revocation. Unrelated API actions are excluded.',
                'approval_boundary': 'The caller must obtain actual user approval. A plan id alone is not proof of consent.'}

    def maintain(self, plan_id: str, *, replacement: dict | None = None, approval_source='chat') -> dict:
        plan = self.store.get_plan(plan_id)
        if plan['stage'] in {'done', 'reconciled', 'superseded', 'abandoned'}:
            raise AuthError('plan_consumed', 'This maintenance plan already completed; it cannot issue another credential.')
        if plan['stage'] not in {'planned', 'approved', 'issuing', 'candidate_saved', 'active_saved'}:
            raise AuthError('invalid_state', 'Unknown maintenance plan state.')
        service = plan['service']
        manager_id = plan['details'].get('management_service')
        targets: set[str] = {service}
        if manager_id:
            if not isinstance(manager_id, str):
                raise AuthError('invalid_state', 'Management service id is invalid.')
            targets.add(manager_id)
        with ExitStack() as stack:
            for target in sorted(targets):
                stack.enter_context(self.store.lease(target))
            # Re-read after acquiring ownership to reject simultaneous/replayed approval attempts.
            plan = self.store.get_plan(plan_id)
            unfinished = self.store.unfinished(service, excluding=plan_id)
            if unfinished and unfinished['id'] != plan.get('resume_of'):
                raise AuthError('maintenance_in_progress', 'Another unfinished maintenance plan owns this service: ' + unfinished['id'])
            current = self.entry(service)
            if plan['profile_hash'] != fingerprint(current['profile']) or plan['revision'] != current['revision']:
                raise AuthError('stale_plan', 'Credential or target changed; prepare and review a fresh plan.')
            if plan['stage'] in {'done', 'reconciled', 'superseded', 'abandoned'}:
                raise AuthError('plan_consumed', 'This plan already completed.')
            if plan['stage'] == 'planned':
                if plan['expires_at'] < time.time():
                    raise AuthError('approval_expired', 'The unapproved plan expired. Prepare a fresh plan for review.')
                if plan['details'].get('purpose') in {'registration', 'manual_replacement'}:
                    raise AuthError('approval_required', 'Record actual account/session approval before acquiring or handing off a credential.')
                self.store.approve(plan, approval_source)
            manager = self.entry(manager_id) if manager_id else None
            if manager and manager['revision'] != plan['details']['management_revision']:
                raise AuthError('stale_plan', 'Management credential changed; prepare a fresh plan.')
            profile = current['profile']
            mode = plan['details']['mode']
            local_input = profile['rotation']['mode'] == 'manual' or plan['details'].get('purpose') == 'registration'
            if replacement is not None and current['active'] and replacement.get('secret') == current['active']['secret']:
                raise AuthError('credential_unchanged', 'The replacement matches the current credential; no renewal was performed.')
            if plan['stage'] == 'candidate_saved' and local_input and replacement is not None:
                self.store.candidate(plan, validate_bundle(replacement))
                current = self.entry(service)
            if plan['stage'] == 'issuing' and not plan.get('operation'):
                raise AuthError('issuance_unknown', 'A prior issuance may have succeeded. Inspect provider key inventory; do not issue again blindly.')
            if plan['stage'] in {'approved', 'issuing'}:
                if local_input and replacement is not None:
                    self.store.candidate(plan, validate_bundle(replacement))
                elif current['pending']:
                    plan['stage'] = 'candidate_saved'
                    self.store.update_plan(plan)
                else:
                    if mode == 'manual':
                        raise AuthError('authorized_session_required', 'Obtain the replacement from the approved account/session and hand it off internally, then resume this approved plan.')
                    plan['stage'] = 'issuing'
                    self.store.update_plan(plan)
                    try:
                        if mode == 'oauth2':
                            candidate = refresh(self.transport, profile, current['active'])
                        elif mode == 'openai-service-account':
                            if manager is None:
                                raise AuthError('management_registration_required', 'A management credential is required.')
                            candidate = openai_issue(self.transport, profile, manager)
                        elif mode == 'google-cloud-key':
                            if manager is None:
                                raise AuthError('management_registration_required', 'A management credential is required.')
                            candidate = google_issue(self.transport, profile, manager, plan['details']['old_remote_id'], plan, self.store.update_plan)
                        elif mode == 'http-json':
                            candidate = http_issue(self.transport, profile, manager or current)
                        else:
                            raise AuthError('invalid_state', 'No pending credential is available to reconnect.')
                    except AuthError as error:
                        if error.code in {'authentication_rejected', 'permission_denied', 'request_error', 'quota_or_rate_limit', 'user_input_required'} and not plan.get('operation'):
                            plan['stage'] = 'approved'
                            self.store.update_plan(plan)
                        raise
                    if current['active'] and candidate['secret'] == current['active']['secret']:
                        raise AuthError('invalid_response', 'Provider returned the existing credential instead of a replacement.')
                    if plan['details']['revoke_previous'] and candidate.get('remote_id') == plan['details']['old_remote_id']:
                        raise AuthError('invalid_response', 'Replacement and previous key identifiers must differ before revocation.')
                    self.store.candidate(plan, candidate)
                current = self.entry(service)
            if plan['stage'] == 'candidate_saved':
                try:
                    response = self._verify(current, current['pending'])
                except AuthError as error:
                    return {'status': 'reconnection_pending', 'category': error.code, 'plan_id': plan_id,
                            'candidate_saved_encrypted': True, 'next_action': 'Resume this same approved plan; no new credential is issued.'}
                if not response.ok:
                    return {'status': 'reconnection_pending', 'category': response.category, 'http_status': response.status,
                            'plan_id': plan_id, 'candidate_saved_encrypted': True,
                            'next_action': 'Resume this same approved plan after resolving connectivity or permissions; no new credential is issued.'}
                self.store.activate(plan)
            if plan['stage'] == 'active_saved' and plan['details']['revoke_previous']:
                if profile['rotation']['mode'] == 'http-json' and manager is None:
                    manager = self.entry(service)
                if manager is None:
                    raise AuthError('management_registration_required', 'A management credential is required for revocation.')
                try:
                    revoke(self.transport, profile, manager, plan['details']['old_remote_id'], plan, self.store.update_plan)
                except AuthError as error:
                    return {'status': 'revocation_pending', 'category': error.code, 'service': service, 'plan_id': plan_id,
                            'credential_activated': True, 'connection_verified': True,
                            'next_action': 'Resume this same approved plan to finish previous-key revocation; no new credential is issued.'}
            plan['stage'] = 'done'
            self.store.update_plan(plan)
            return {'status': 'registered_and_connected' if plan['details'].get('purpose') == 'registration' else 'renewed_and_reconnected', 'service': service, 'plan_id': plan_id,
                    'revoked_previous': plan['details']['revoke_previous'], 'credential': self.status(service)}

    def reconcile(self, plan_id: str, outcome: str, evidence: str) -> dict:
        plan = self.store.get_plan(plan_id)
        if outcome not in {'not-issued', 'orphan-revoked'} or not isinstance(evidence, str) or not 10 <= len(evidence) <= 1000:
            raise AuthError('inventory_review_required', 'Provide the actual provider inventory/cleanup outcome and a non-secret evidence reference.')
        with self.store.lease(plan['service']):
            plan = self.store.get_plan(plan_id)
            if plan['stage'] != 'issuing' or plan.get('operation'):
                raise AuthError('invalid_state', 'Only ambiguous issuance without a saved provider operation can be reconciled here.')
            plan.update(stage='reconciled', inventory_outcome=outcome, evidence_reference=evidence, reconciled_at=time.time())
            self.store.update_plan(plan)
        return {'status': 'reconciled', 'plan_id': plan_id,
                'boundary': 'Caller-reported inventory evidence; this command does not query the provider or prove the supplied outcome.'}
