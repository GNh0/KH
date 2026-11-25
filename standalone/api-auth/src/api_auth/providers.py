"""Official OAuth/OpenAI/Google key maintenance protocols. No discovery guesswork."""
import time
import uuid
import re
import math
from datetime import datetime
from urllib.parse import quote

from src.api_auth.profile import validate_bundle
from src.api_auth.security import AuthError
from src.api_auth.transport import Transport


def headers(profile: dict, bundle: dict) -> dict:
    return {profile['header']: profile['prefix'] + bundle['secret']}


def require(response):
    if not response.ok:
        raise AuthError(response.category, 'Credential maintenance endpoint returned HTTP ' + str(response.status) + '.')
    if not isinstance(response.data, dict):
        raise AuthError('invalid_response', 'Credential maintenance response must be a JSON object.')
    return response.data


def refresh(transport: Transport, profile: dict, bundle: dict) -> dict:
    if not bundle.get('refresh_token'):
        raise AuthError('user_input_required', 'A refresh credential is required; enter it through the registration UI.')
    form = {'grant_type': 'refresh_token', 'refresh_token': bundle['refresh_token']}
    if bundle.get('client_id'):
        form['client_id'] = bundle['client_id']
    if bundle.get('client_secret'):
        form['client_secret'] = bundle['client_secret']
    data = require(transport.send('POST', profile['rotation']['token_url'], {}, form, form=True))
    if not isinstance(data.get('token_type', 'Bearer'), str) or data.get('token_type', 'Bearer').lower() != 'bearer':
        raise AuthError('invalid_response', 'Only Bearer access tokens are supported by this adapter.')
    token = data.get('access_token')
    result = {**bundle, 'secret': token}
    if data.get('refresh_token'):
        result['refresh_token'] = data['refresh_token']
    if 'expires_in' in data:
        life = data['expires_in']
        if isinstance(life, bool) or not isinstance(life, (int, float)) or life <= 0:
            raise AuthError('invalid_response', 'Token response expiry is invalid.')
        result['expires_at'] = time.time() + life
    else:
        result.pop('expires_at', None)
    return validate_bundle(result)


def openai_issue(transport: Transport, profile: dict, manager: dict) -> dict:
    config = profile['rotation']
    base = manager['profile']['base_url']
    path = '/organization/projects/' + config['project_id'] + '/service_accounts/' + config['service_account_id'] + '/api_keys'
    data = require(transport.send('POST', base + path, headers(manager['profile'], manager['active']),
                                  {'name': 'KH ' + profile['id'], 'scopes': config['scopes'],
                                   'expires_in_seconds': config['lifetime_seconds']}))
    return validate_bundle({'secret': data.get('value'), 'remote_id': data.get('id'), 'expires_at': data.get('expires_at')})


def http_issue(transport: Transport, profile: dict, authority: dict) -> dict:
    """A documented JSON issuance contract is configuration, not another KH provider release."""
    config = profile['rotation']
    data = require(transport.send('POST', authority['profile']['base_url'] + config['issue_path'],
                                  headers(authority['profile'], authority['active']), config.get('issue_body', {})))
    def field(name, required=False):
        parts = config.get(name)
        if parts is None:
            return None
        value = data
        for part in parts:
            if not isinstance(value, dict) or part not in value:
                if required:
                    raise AuthError('invalid_response', 'Issuance response omitted a required configured field.')
                return None
            value = value[part]
        return value
    result = {'secret': field('secret_field', True)}
    remote = field('id_field', config.get('revoke_previous', False))
    if remote is not None:
        result['remote_id'] = remote
    end, life = field('expires_at_field'), field('expires_in_field')
    if end is not None:
        if isinstance(end, str):
            try:
                date = datetime.fromisoformat(end.replace('Z', '+00:00'))
                if date.tzinfo is None:
                    raise ValueError()
                end = date.timestamp()
            except ValueError:
                raise AuthError('invalid_response', 'Issuance response expiry must include a timezone.') from None
        result['expires_at'] = end
    elif life is not None:
        if isinstance(life, bool) or not isinstance(life, (int, float)) or not math.isfinite(life) or life <= 0:
            raise AuthError('invalid_response', 'Issuance lifetime is invalid.')
        result['expires_at'] = time.time() + life
    return validate_bundle(result)


def google_poll(transport: Transport, base: str, auth: dict, operation: dict, save_operation) -> dict:
    name = operation.get('name')
    if not isinstance(name, str) or not re.fullmatch(r'operations/[A-Za-z0-9_-][A-Za-z0-9._-]*', name):
        raise AuthError('invalid_response', 'Google operation name is invalid.')
    save_operation(name)
    deadline = time.monotonic() + 45
    for _ in range(20):
        if operation.get('done'):
            if operation.get('error'):
                raise AuthError('provider_operation_failed', 'Google key operation failed; inspect the key inventory before retrying.')
            response = operation.get('response')
            if not isinstance(response, dict):
                raise AuthError('invalid_response', 'Google key operation omitted its result.')
            return response
        time.sleep(0.25)
        if time.monotonic() >= deadline:
            break
        operation = require(transport.send('GET', base + '/' + name, auth))
    raise AuthError('operation_pending', 'Google key operation is still pending; resume this same approved plan.')


def google_issue(transport: Transport, profile: dict, manager: dict, old_name: str, plan: dict, persist) -> dict:
    base = manager['profile']['base_url']
    auth = headers(manager['profile'], manager['active'])
    if plan.get('operation'):
        operation = require(transport.send('GET', base + '/' + plan['operation'], auth))
    else:
        old = require(transport.send('GET', base + '/' + old_name, auth))
        body = {'displayName': 'KH ' + profile['id'], 'restrictions': old.get('restrictions', {})}
        for field in ('serviceAccountEmail', 'annotations'):
            if field in old:
                body[field] = old[field]
        parent = old_name.rsplit('/keys/', 1)[0]
        key_id = 'kh-' + uuid.uuid4().hex[:24]
        operation = require(transport.send('POST', base + '/' + parent + '/keys?keyId=' + key_id, auth, body))
    def save(name):
        plan['operation'] = name
        persist(plan)
    result = google_poll(transport, base, auth, operation, save)
    name = result.get('name')
    parent = old_name.rsplit('/keys/', 1)[0]
    if not isinstance(name, str) or not re.fullmatch(re.escape(parent) + r'/keys/[A-Za-z0-9-]+', name):
        raise AuthError('invalid_response', 'Google returned a key outside the approved project.')
    data = require(transport.send('GET', base + '/' + name + '/keyString', auth))
    return validate_bundle({'secret': data.get('keyString'), 'remote_id': name})


def revoke(transport: Transport, profile: dict, manager: dict, old_id: str, plan: dict, persist):
    base = manager['profile']['base_url']
    auth = headers(manager['profile'], manager['active'])
    if profile['rotation']['mode'] == 'http-json':
        path = profile['rotation']['revoke_path'].replace('{old_id}', quote(old_id, safe=''))
        response = transport.send('DELETE', base + path, auth)
        if response.status != 404:
            require(response)
        return
    if profile['rotation']['mode'] == 'openai-service-account':
        url = base + '/organization/projects/' + profile['rotation']['project_id'] + '/api_keys/' + quote(old_id, safe='')
        result = transport.send('DELETE', url, auth)
        if result.status != 404:
            require(result)
        return
    if profile['rotation']['mode'] != 'google-cloud-key':
        raise AuthError('invalid_profile', 'No revocation protocol is configured for this maintenance mode.')
    if plan.get('revoke_operation'):
        result = require(transport.send('GET', base + '/' + plan['revoke_operation'], auth))
    else:
        response = transport.send('DELETE', base + '/' + old_id, auth)
        if response.status == 404:
            return
        result = require(response)
    def save(name):
        plan['revoke_operation'] = name
        persist(plan)
    google_poll(transport, base, auth, result, save)
