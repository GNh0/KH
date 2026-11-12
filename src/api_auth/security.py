"""Windows current-user DPAPI. No plaintext persistence or alternate host auth store."""
import ctypes
from ctypes import wintypes
import json
import os
import re
from typing import overload


class AuthError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class UserCipher:
    def __init__(self):
        if os.name != 'nt':
            raise AuthError('secure_storage_unavailable', 'This release requires Windows current-user DPAPI; no plaintext fallback is used.')

    def _transform(self, value: bytes, *, decrypt: bool) -> bytes:
        class Blob(ctypes.Structure):
            _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
        crypt = ctypes.WinDLL('crypt32', use_last_error=True)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        buffer = ctypes.create_string_buffer(value)
        source = Blob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
        result = Blob()
        entropy_buffer = ctypes.create_string_buffer(b'KH/api-auth/v1')
        entropy = Blob(14, ctypes.cast(entropy_buffer, ctypes.POINTER(ctypes.c_ubyte)))
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        if decrypt:
            call = crypt.CryptUnprotectData
            call.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob), ctypes.c_void_p,
                             ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
            args = (ctypes.byref(source), None, ctypes.byref(entropy), None, None, 1, ctypes.byref(result))
        else:
            call = crypt.CryptProtectData
            call.argtypes = [ctypes.POINTER(Blob), wintypes.LPCWSTR, ctypes.POINTER(Blob), ctypes.c_void_p,
                             ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
            args = (ctypes.byref(source), 'KH API credential', ctypes.byref(entropy), None, None, 1, ctypes.byref(result))
        call.restype = wintypes.BOOL
        if not call(*args):
            raise AuthError('secure_storage_error', 'Windows could not protect or unlock this user credential.')
        try:
            return ctypes.string_at(result.data, result.size)
        finally:
            kernel.LocalFree(ctypes.cast(result.data, ctypes.c_void_p))

    def seal(self, value: dict) -> bytes:
        return self._transform(json.dumps(value, ensure_ascii=False).encode('utf-8'), decrypt=False)

    def open(self, value: bytes) -> dict:
        try:
            data = json.loads(self._transform(value, decrypt=True))
        except (UnicodeError, ValueError):
            raise AuthError('secure_storage_error', 'Stored credential is damaged.') from None
        if not isinstance(data, dict):
            raise AuthError('secure_storage_error', 'Stored credential has an invalid shape.')
        return data


SECRET_FIELDS = re.compile(r'(?i)(?:^|[_-])(?:api[_-]?key|keystring|(?:access|refresh|id|auth)[_-]?token|client[_-]?secret|secret|token|password|authorization|credentials?|private[_-]?key|value)(?:$|[_-])')


def secret_values(bundle: dict) -> list[str]:
    return [value for key, value in bundle.items() if key in {'secret', 'refresh_token', 'client_secret'}
            and isinstance(value, str) and value]


@overload
def safe_output(value: dict, secrets=()) -> dict: ...


@overload
def safe_output(value: list, secrets=()) -> list: ...


@overload
def safe_output(value: str, secrets=()) -> str: ...


@overload
def safe_output(value: object, secrets=()) -> object: ...


def safe_output(value, secrets=()):
    """Mask structured credentials and exact in-memory values, including echoed test responses."""
    if isinstance(value, dict):
        return {safe_output(str(key), secrets): '[REDACTED]' if SECRET_FIELDS.search(str(key)) else safe_output(item, secrets)
                for key, item in value.items()}
    if isinstance(value, list):
        return [safe_output(item, secrets) for item in value]
    if isinstance(value, str):
        for secret in sorted(set(secrets), key=len, reverse=True):
            if secret:
                value = value.replace(secret, '[REDACTED]')
        return value
    return value
