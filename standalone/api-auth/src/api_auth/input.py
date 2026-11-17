"""Secret handoff from an approved account session, never a separate user-entry window."""
import ctypes
from ctypes import wintypes
import json
import os
import sys

from src.api_auth.profile import validate_bundle
from src.api_auth.security import AuthError


def _clipboard_api():
    if os.name != 'nt':
        raise AuthError('secure_input_unavailable', 'Windows clipboard handoff is unavailable.')
    user = ctypes.WinDLL('user32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    user.GetClipboardSequenceNumber.restype = wintypes.DWORD
    user.OpenClipboard.argtypes = [wintypes.HWND]
    user.OpenClipboard.restype = wintypes.BOOL
    user.GetClipboardData.argtypes = [wintypes.UINT]
    user.GetClipboardData.restype = wintypes.HANDLE
    user.CloseClipboard.restype = wintypes.BOOL
    user.EmptyClipboard.restype = wintypes.BOOL
    kernel.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel.GlobalLock.restype = ctypes.c_void_p
    kernel.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel.GlobalSize.argtypes = [wintypes.HGLOBAL]
    kernel.GlobalSize.restype = ctypes.c_size_t
    return user, kernel


def clipboard_sequence() -> int:
    user, _kernel = _clipboard_api()
    return int(user.GetClipboardSequenceNumber())


def read_credential(*, stdin=False, clipboard=False, expected_sequence=None) -> dict:
    if stdin == clipboard:
        raise AuthError('authorized_session_required', 'Use one approved account-session handoff: a trusted in-memory pipe or an agent-owned clipboard copy. No separate key-entry window is opened.')
    if stdin:
        raw = sys.stdin.buffer.read(128000)
        if len(raw) >= 128000:
            raise AuthError('invalid_credential', 'Credential input exceeded the limit.')
        try:
            return validate_bundle(json.loads(raw))
        except (ValueError, UnicodeError):
            raise AuthError('invalid_credential', 'Trusted credential handoff must be UTF-8 JSON.') from None
    if not isinstance(expected_sequence, int) or expected_sequence <= 0:
        raise AuthError('clipboard_provenance_required', 'Supply the exact fresh sequence recorded after copying from the approved account session.')
    user, kernel = _clipboard_api()
    if user.GetClipboardSequenceNumber() != expected_sequence or not user.OpenClipboard(None):
        raise AuthError('clipboard_changed', 'Clipboard changed or is busy. Re-copy from the approved session; unrelated clipboard data was not read.')
    try:
        if user.GetClipboardSequenceNumber() != expected_sequence:
            raise AuthError('clipboard_changed', 'Clipboard ownership changed before the handoff.')
        handle = user.GetClipboardData(13)  # CF_UNICODETEXT
        if not handle or not 2 <= kernel.GlobalSize(handle) <= 65538:
            raise AuthError('invalid_credential', 'The copied credential is missing or exceeds the bound.')
        pointer = kernel.GlobalLock(handle)
        if not pointer:
            raise AuthError('secure_input_unavailable', 'Copied credential could not be accessed.')
        try:
            secret = ctypes.wstring_at(pointer, kernel.GlobalSize(handle) // 2).split('\0', 1)[0]
        finally:
            kernel.GlobalUnlock(handle)
        return validate_bundle({'secret': secret})
    finally:
        user.CloseClipboard()


def clear_owned_clipboard(expected_sequence: int) -> bool:
    user, _kernel = _clipboard_api()
    if user.GetClipboardSequenceNumber() != expected_sequence or not user.OpenClipboard(None):
        return False
    try:
        return bool(user.GetClipboardSequenceNumber() == expected_sequence and user.EmptyClipboard())
    finally:
        user.CloseClipboard()
