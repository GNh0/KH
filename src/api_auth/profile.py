"""Non-secret service definitions; public operations use one lifecycle interface."""
import hashlib
import json
import math
import re
import time
from urllib.parse import urlsplit

from src.api_auth.security import AuthError
from src.api_auth.transport import origin, validate_url


def identifier(value) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,62}', value):
        raise AuthError('invalid_profile', 'Service id must use lowercase letters, digits and hyphens, starting with a letter.')
    return value


def finite_number(value, field, *, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < minimum:
        raise AuthError('invalid_input', field + ' must be a finite nonnegative number.')
    return value


def validate_profile(value: dict, *, loopback=False) -> dict:
    fields = {'id', 'provider', 'base_url', 'check_path', 'auth', 'header', 'prefix', 'renew_before_seconds', 'rotation', 'api_origins'}
    if not isinstance(value, dict) or set(value) - fields:
        raise AuthError('invalid_profile', 'Unknown service field; credentials must be entered separately.')
    result = dict(value)
    identifier(result.get('id'))
    if result.get('provider', 'generic') not in {'generic', 'openai', 'google-cloud'}:
        raise AuthError('invalid_profile', 'Unknown provider adapter.')
    result.setdefault('provider', 'generic')
    result['base_url'] = validate_url(result.get('base_url', ''), loopback=loopback)
    parts = urlsplit(result['base_url'])
    if parts.query:
        raise AuthError('invalid_profile', 'Base URL cannot contain a query.')
    origins = result.setdefault('api_origins', [])
    if not isinstance(origins, list) or len(origins) > 32:
        raise AuthError('invalid_profile', 'Additional API origins must be a bounded list.')
    for allowed in origins:
        validate_url(allowed, loopback=loopback)
        parsed = urlsplit(allowed)
        if parsed.path not in {'', '/'} or parsed.query:
            raise AuthError('invalid_profile', 'Additional API origins must contain only scheme, host and optional port.')
    path = result.get('check_path')
    if not isinstance(path, str) or not path.startswith('/') or path.startswith('//') or '\\' in path:
        raise AuthError('invalid_profile', 'check_path must be an absolute path on the configured origin.')
    validate_url(result['base_url'] + path, loopback=loopback)
    if origin(result['base_url'] + path) != origin(result['base_url']):
        raise AuthError('invalid_profile', 'Check endpoint must remain on the configured origin.')
    result.setdefault('auth', 'bearer')
    if result['auth'] not in {'bearer', 'header'}:
        raise AuthError('invalid_profile', 'Supported authentication modes are bearer and header.')
    result.setdefault('header', 'Authorization' if result['auth'] == 'bearer' else 'x-goog-api-key')
    result.setdefault('prefix', 'Bearer ' if result['auth'] == 'bearer' else '')
    if not isinstance(result['header'], str) or not re.fullmatch(r'[A-Za-z0-9-]{1,100}', result['header']):
        raise AuthError('invalid_profile', 'Authentication header name is invalid.')
    if result['header'].lower() in {'host', 'content-length', 'connection', 'content-type'}:
        raise AuthError('invalid_profile', 'Authentication cannot replace a transport header.')
    if not isinstance(result['prefix'], str) or any(ord(c) < 32 for c in result['prefix']):
        raise AuthError('invalid_profile', 'Authentication prefix is invalid.')
    result.setdefault('renew_before_seconds', 7 * 86400)
    finite_number(result['renew_before_seconds'], 'renew_before_seconds')
    rotation = result.setdefault('rotation', {'mode': 'manual'})
    allowed = {'mode', 'token_url', 'management_service', 'project_id', 'service_account_id', 'resource_name',
               'scopes', 'lifetime_seconds', 'revoke_previous', 'issue_path', 'issue_body', 'secret_field',
               'id_field', 'expires_in_field', 'expires_at_field', 'revoke_path'}
    if not isinstance(rotation, dict) or set(rotation) - allowed:
        raise AuthError('invalid_profile', 'Unknown rotation field.')
    mode = rotation.get('mode')
    if mode not in {'manual', 'oauth2', 'http-json', 'openai-service-account', 'google-cloud-key'}:
        raise AuthError('invalid_profile', 'Unknown credential maintenance mode.')
    fields_by_mode = {
        'manual': {'mode'}, 'oauth2': {'mode', 'token_url'},
        'openai-service-account': {'mode', 'management_service', 'project_id', 'service_account_id', 'scopes', 'lifetime_seconds', 'revoke_previous'},
        'google-cloud-key': {'mode', 'management_service', 'resource_name', 'revoke_previous'},
        'http-json': {'mode', 'management_service', 'issue_path', 'issue_body', 'secret_field', 'id_field',
                      'expires_in_field', 'expires_at_field', 'revoke_path', 'revoke_previous'},
    }
    if set(rotation) - fields_by_mode[mode]:
        raise AuthError('invalid_profile', 'Rotation fields do not apply to the selected maintenance protocol.')
    if mode == 'oauth2':
        validate_url(rotation.get('token_url', ''), loopback=loopback)
    if mode in {'openai-service-account', 'google-cloud-key'}:
        identifier(rotation.get('management_service'))
        if rotation['management_service'] == result['id']:
            raise AuthError('invalid_profile', 'Management and workload credentials must be separate services.')
    if mode == 'http-json':
        if rotation.get('management_service'):
            identifier(rotation['management_service'])
            if rotation['management_service'] == result['id']:
                raise AuthError('invalid_profile', 'Omit management_service to explicitly use this service authority.')
        for field in ('issue_path', 'revoke_path'):
            if field == 'revoke_path' and not rotation.get('revoke_previous'):
                continue
            path = rotation.get(field)
            if not isinstance(path, str) or not path.startswith('/') or path.startswith('//') or '\\' in path or any(ord(c) < 33 for c in path):
                raise AuthError('invalid_profile', 'HTTP maintenance paths must remain on the registered authority origin.')
            remaining = path.replace('{old_id}', '') if field == 'revoke_path' else path
            if '{' in remaining or '}' in remaining:
                raise AuthError('invalid_profile', 'Only the old_id placeholder is supported in a revocation path.')
            if field == 'revoke_path' and '{old_id}' not in path:
                raise AuthError('invalid_profile', 'Revocation must target the approved old key identifier.')
        for field in ('secret_field', 'id_field', 'expires_in_field', 'expires_at_field'):
            parts = rotation.get(field)
            if parts is None and field != 'secret_field':
                continue
            if not isinstance(parts, list) or not 1 <= len(parts) <= 8 or not all(isinstance(s, str) and 0 < len(s) <= 128 for s in parts):
                raise AuthError('invalid_profile', 'Credential response fields must be explicit lists of JSON object keys.')
        if rotation.get('revoke_previous') and not rotation.get('id_field'):
            raise AuthError('invalid_profile', 'Automatic revocation requires the replacement key identifier field.')
        body = rotation.get('issue_body', {})
        def public_body(item):
            if isinstance(item, dict):
                return all(isinstance(key, str) and not re.search(r'(?i)(secret|password|api[_-]?key|access[_-]?token|refresh[_-]?token)', key)
                           and public_body(value) for key, value in item.items())
            if isinstance(item, list):
                return all(public_body(value) for value in item)
            return item is None or isinstance(item, (str, bool, int, float))
        if not isinstance(body, dict) or not public_body(body) or len(json.dumps(body)) > 16000:
            raise AuthError('invalid_profile', 'Issuance body must contain bounded non-secret public settings only.')
    if mode == 'openai-service-account':
        for key in ('project_id', 'service_account_id'):
            if not isinstance(rotation.get(key), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,120}', rotation[key]):
                raise AuthError('invalid_profile', 'OpenAI project/service-account identifiers are required.')
        scopes = rotation.get('scopes')
        if not isinstance(scopes, list) or not scopes or not all(isinstance(s, str) and s for s in scopes):
            raise AuthError('invalid_profile', 'Explicit replacement key scopes are required; implicit privilege expansion is not allowed.')
        finite_number(rotation.get('lifetime_seconds'), 'lifetime_seconds', minimum=1)
    if mode == 'google-cloud-key' and not re.fullmatch(r'projects/[0-9]+/locations/global/keys/[A-Za-z0-9-]+', str(rotation.get('resource_name', ''))):
        raise AuthError('invalid_profile', 'Google Cloud API key resource name is required.')
    if 'revoke_previous' in rotation and not isinstance(rotation['revoke_previous'], bool):
        raise AuthError('invalid_profile', 'revoke_previous must be boolean.')
    return result


def validate_bundle(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) - {'secret', 'refresh_token', 'client_id', 'client_secret', 'expires_at', 'remote_id'}:
        raise AuthError('invalid_credential', 'Credential input has unknown fields.')
    secret = value.get('secret')
    if not isinstance(secret, str) or not secret or len(secret) > 32000 or any(ord(c) < 33 for c in secret):
        raise AuthError('invalid_credential', 'Credential must be a nonempty single-line value.')
    for key in ('refresh_token', 'client_id', 'client_secret', 'remote_id'):
        if key in value and (not isinstance(value[key], str) or len(value[key]) > 32000 or any(ord(c) < 32 for c in value[key])):
            raise AuthError('invalid_credential', 'Credential metadata must contain bounded single-line strings.')
    remote = value.get('remote_id')
    if remote and any(isinstance(value.get(key), str) and value[key] and value[key] in remote
                      for key in ('secret', 'refresh_token', 'client_secret')):
        raise AuthError('invalid_credential', 'A remote key identifier cannot contain a credential value.')
    if value.get('expires_at') is not None:
        finite_number(value['expires_at'], 'expires_at', minimum=1)
    return dict(value)


def fingerprint(profile: dict) -> str:
    return hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def api_base(profile: dict, selected: str | None, *, loopback=False) -> str:
    value = validate_url(selected or profile['base_url'], loopback=loopback)
    parsed = urlsplit(value)
    if parsed.query:
        raise AuthError('invalid_request', 'API base cannot include a query.')
    allowed = {origin(profile['base_url']), *(origin(url) for url in profile.get('api_origins', []))}
    google = (profile['provider'] == 'google-cloud' and parsed.scheme == 'https' and
              parsed.port in {None, 443} and (parsed.hostname or '').endswith('.googleapis.com'))
    if origin(value) not in allowed and not google:
        raise AuthError('origin_not_allowed', 'This API origin is outside the registered credential authority.')
    return value


def expiry(bundle: dict, profile: dict) -> str:
    end = bundle.get('expires_at')
    if end is None:
        return 'unknown'
    return 'expired' if end <= time.time() else 'due' if end - time.time() <= profile['renew_before_seconds'] else 'valid'
