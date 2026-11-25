"""Bounded HTTPS requests with no credential forwarding through redirects."""
from dataclasses import dataclass
from contextlib import contextmanager
from collections.abc import Iterator
import http.client
import ipaddress
import json
import math
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

from src.api_auth.security import AuthError


def validate_url(url: str, *, loopback=False) -> str:
    if not isinstance(url, str) or len(url) > 4096 or any(ord(c) < 33 for c in url):
        raise AuthError('invalid_profile', 'Endpoint must be a complete HTTPS URL without whitespace.')
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError:
        raise AuthError('invalid_profile', 'Endpoint URL is invalid.') from None
    if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise AuthError('invalid_profile', 'Endpoint cannot contain user information or a fragment.')
    local = False
    try:
        local = ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        pass
    if parsed.scheme != 'https' and not (loopback and local and parsed.scheme == 'http'):
        raise AuthError('invalid_profile', 'HTTPS is required; HTTP is allowed only for an explicitly enabled loopback fixture.')
    if port is not None and not 1 <= port <= 65535:
        raise AuthError('invalid_profile', 'Endpoint port is invalid.')
    sensitive = {'key', 'api_key', 'apikey', 'access_token', 'refresh_token', 'secret', 'token'}
    if any(key.lower() in sensitive for key, _value in urllib.parse.parse_qsl(parsed.query)):
        raise AuthError('invalid_profile', 'Configure authentication separately, never embed credentials in endpoint URLs.')
    return url.rstrip('/')


def origin(url: str) -> tuple:
    parts = urllib.parse.urlsplit(url)
    return parts.scheme, parts.hostname, parts.port or (443 if parts.scheme == 'https' else 80)


@dataclass
class Response:
    status: int
    data: object
    category: str

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


@dataclass
class StreamLimits:
    timeout_seconds: float = 180
    idle_timeout: float = 30
    max_bytes: int = 64 * 1024 * 1024
    max_event_bytes: int = 8 * 1024 * 1024
    max_events: int = 10000

    def __post_init__(self):
        for name in ('timeout_seconds', 'idle_timeout'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= 3600:
                raise AuthError('invalid_stream_limits', 'Stream timeouts must be finite positive seconds, at most one hour.')
        for name, maximum in (('max_bytes', 256 * 1024 * 1024), ('max_event_bytes', 32 * 1024 * 1024), ('max_events', 100000)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
                raise AuthError('invalid_stream_limits', 'Stream byte/event limits must be positive bounded integers.')
        if self.max_event_bytes > self.max_bytes:
            raise AuthError('invalid_stream_limits', 'An event cannot exceed the total stream byte limit.')


@dataclass
class StreamResponse:
    status: int
    content_type: str
    chunks: Iterator[bytes]
    request_id: str | None = None
    closed: bool = False


def category(status: int, data) -> str:
    if 200 <= status < 300:
        return 'connected'
    if status == 401:
        return 'authentication_rejected'
    if status == 429:
        return 'quota_or_rate_limit'
    if 300 <= status < 400:
        return 'redirect_blocked'
    if status >= 500:
        return 'service_error'
    error = data.get('error') if isinstance(data, dict) else None
    codes: list[object] = [error] if isinstance(error, str) else []
    if isinstance(error, dict):
        codes.extend(error.get(field) for field in ('code', 'status', 'reason'))
        details = error.get('details', [])
        if isinstance(details, list):
            codes.extend(item.get('reason') for item in details if isinstance(item, dict))
    rejected = {'API_KEY_EXPIRED', 'API_KEY_INVALID', 'KEY_EXPIRED', 'INVALID_GRANT', 'INVALID_API_KEY'}
    if status in {400, 403} and any(isinstance(code, str) and code.upper() in rejected for code in codes):
        return 'authentication_rejected'
    return 'permission_denied' if status == 403 else 'request_error'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Transport:
    def __init__(self, *, loopback=False):
        self.loopback = loopback
        self.opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))

    def send(self, method: str, url: str, headers: dict, body=None, *, form=False) -> Response:
        validate_url(url, loopback=self.loopback)
        data = None
        headers = dict(headers)
        if body is not None:
            if form:
                data = urllib.parse.urlencode(body).encode('ascii')
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
            else:
                data = json.dumps(body).encode('utf-8')
                headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            try:
                response = self.opener.open(request, timeout=15)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                status = response.code
                raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise AuthError('response_too_large', 'API response exceeded the 1 MiB bound.')
            try:
                value = json.loads(raw) if raw else {}
            except (ValueError, UnicodeError):
                value = {'message': 'Non-JSON response omitted.'}
            return Response(status, value, category(status, value))
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError):
            # Exception URLs/messages may contain provider credentials. Do not surface them.
            raise AuthError('network_error', 'API connection failed; credentials were not assumed expired.') from None

    @contextmanager
    def open_stream(self, method: str, url: str, headers: dict, body, limits: StreamLimits):
        """Own one HTTP connection until consumption, cancellation or a callback failure."""
        validate_url(url, loopback=self.loopback)
        parts = urllib.parse.urlsplit(url)
        host = parts.hostname
        if host is None:
            raise AuthError('invalid_profile', 'Streaming endpoint needs a host.')
        payload = None
        outgoing = {**headers, 'Accept-Encoding': 'identity'}
        if body is not None:
            try:
                payload = json.dumps(body, allow_nan=False).encode('utf-8')
            except (ValueError, TypeError, RecursionError):
                raise AuthError('invalid_request', 'Streaming request must be finite JSON.') from None
            if len(payload) > 1024 * 1024:
                raise AuthError('request_too_large', 'Streaming JSON request exceeds the 1 MiB input bound.')
            outgoing['Content-Type'] = 'application/json'
        deadline = time.monotonic() + limits.timeout_seconds
        connection = None
        response = None
        active_socket = None
        stream = None

        def remaining():
            value = deadline - time.monotonic()
            if value <= 0:
                raise AuthError('stream_timeout', 'Stream duration limit reached; no retry was sent.')
            return min(limits.idle_timeout, value)

        try:
            try:
                if parts.scheme == 'https':
                    connection = http.client.HTTPSConnection(host, parts.port or 443, timeout=remaining(), context=ssl.create_default_context())
                else:
                    connection = http.client.HTTPConnection(host, parts.port or 80, timeout=remaining())
                path = parts.path or '/'
                if parts.query:
                    path += '?' + parts.query
                connection.request(method, path, body=payload, headers=outgoing)
                active_socket = connection.sock
                if active_socket:
                    active_socket.settimeout(remaining())
                response = connection.getresponse()
            except (TimeoutError, socket.timeout):
                raise AuthError('stream_timeout', 'Stream connection or idle timeout reached; no retry was sent.') from None
            except (OSError, http.client.HTTPException):
                raise AuthError('network_error', 'Stream connection failed; no credential rotation or retry was performed.') from None
            if response.getheader('Content-Encoding', 'identity').lower() not in {'identity', ''}:
                raise AuthError('unsupported_stream_encoding', 'The stream did not honor identity transfer encoding.')

            def chunks():
                count = 0
                expected = incoming.length
                while True:
                    timeout = remaining()
                    try:
                        if active_socket:
                            active_socket.settimeout(timeout)
                        block = incoming.read1(min(4096, limits.max_bytes + 1 - count))
                    except (TimeoutError, socket.timeout):
                        raise AuthError('stream_timeout', 'Stream idle or duration limit reached; no retry was sent.') from None
                    except (OSError, http.client.HTTPException):
                        raise AuthError('network_error', 'Stream connection failed; no retry was sent.') from None
                    if not block:
                        if expected is not None and count != expected:
                            raise AuthError('truncated_stream', 'Stream ended before its declared content length.')
                        return
                    count += len(block)
                    if count > limits.max_bytes:
                        raise AuthError('stream_too_large', 'Stream exceeded its total byte bound.')
                    yield block

            incoming = response
            stream = StreamResponse(response.status, response.getheader('Content-Type', ''), chunks(),
                                    request_id=response.getheader('x-request-id'))
            yield stream
        finally:
            if response is not None:
                response.close()
            if connection is not None:
                connection.close()
            if active_socket is not None:
                active_socket.close()
            if stream is not None:
                stream.closed = True
