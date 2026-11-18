"""Recognize owned native invocations and explicit requests without storing arguments."""
import hashlib
from pathlib import Path
import re
from urllib.parse import unquote

from src.context.transcript import _host_block

DOMAINS = {'.sql': 'sql-formatting', '.cs': 'csharp-designer-style-harness',
           '.srd': 'pb-to-csharp-migration-harness', '.srw': 'pb-to-csharp-migration-harness',
           '.sru': 'pb-to-csharp-migration-harness', '.srf': 'pb-to-csharp-migration-harness'}
COMMON_EVENTS = frozenset({'SessionStart', 'UserPromptSubmit', 'PreToolUse', 'PostToolUse',
                           'PreCompact', 'Stop', 'SubagentStop', 'SessionEnd'})
HOOK_EVENTS = {'codex': COMMON_EVENTS | {'Interrupt'},
               'claude': COMMON_EVENTS | {'UserPromptExpansion', 'PostToolUseFailure'}}
QUOTES = {'"': '"', "'": "'", '“': '”', '‘': '’'}


def _literal_prefix(text: str, index: int) -> str:
    # Python literal prefixes (including raw pairs) and SQL N. This is syntax,
    # not a list of example prompts; natural-language apostrophes stay separate.
    # https://docs.python.org/3.14/reference/lexical_analysis.html#string-prefixes
    match = re.search(r'(?i)(?<!\w)([rubftn]|r[bft]|[bft]r)$', text[max(0, index - 3):index])
    return match[1].casefold() if match else ''


def _quote_delimiter(text: str, index: int) -> str:
    char = text[index]
    return char * 3 if char in "\"'" and text.startswith(char * 3, index) else QUOTES[char]


def _quoted_end(text: str, index: int, prefix: str) -> int:
    """Mask a literal as one span, including nested f/t replacement expressions."""
    delimiter = _quote_delimiter(text, index)
    stack = [('literal', delimiter, bool(set(prefix) & {'f', 't'}))]
    index += len(delimiter)
    while stack and index < len(text):
        kind, closing, interpolated = stack[-1]
        char = text[index]
        if kind in {'replacement', 'group'}:
            if char in QUOTES:
                delimiter = _quote_delimiter(text, index)
                stack.append(('literal', delimiter, bool(set(_literal_prefix(text, index)) & {'f', 't'})))
                index += len(delimiter)
                continue
            if char == '#':
                newline = text.find('\n', index)
                index = len(text) if newline < 0 else newline + 1
                continue
            if char in '([{':
                stack.append(('group', {'(': ')', '[': ']', '{': '}'}[char], False))
            elif char == closing:
                stack.pop()
            elif kind == 'replacement' and char == ':':
                stack[-1] = ('format', '}', False)
            index += 1
        elif kind == 'format':
            # Format-spec text can contain quote/hash fill/flag characters.
            # Only a nested replacement starts another Python expression.
            if char == '{':
                stack.append(('replacement', '}', False))
            elif char == '}':
                stack.pop()
            index += 1
        elif char == '\\':
            # A backslash does not escape a replacement brace, even in raw f/t
            # literals. Preserve that brace for the next structural scan step.
            index += 1 if interpolated and text[index + 1:index + 2] == '{' else 2
        elif text.startswith(closing, index):
            index += len(closing)
            stack.pop()
        elif interpolated and char == '{':
            if text.startswith('{{', index):
                index += 2
            else:
                stack.append(('replacement', '}', False))
                index += 1
        else:
            index += 1
    return min(index, len(text))


def _invocation_text(prompt: str) -> str:
    """Keep request syntax outside quoted examples, code and Markdown quotations."""
    lines = []
    fence = ''
    quoted_paragraph = False
    for line in prompt.splitlines(keepends=True):
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if fence:
            if (marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and
                    not line[marker.end():].strip()):
                fence = ''
            lines.append(' ' * len(line))
        elif marker:
            fence = marker[1]
            quoted_paragraph = False
            lines.append(' ' * len(line))
        elif line.lstrip().startswith('>'):
            quoted_paragraph = bool(line.lstrip()[1:].strip())
            lines.append(' ' * len(line))
        elif quoted_paragraph and line.strip() and not re.match(r'^\s*(?:#{1,6}\s|[-*+]\s|\d+[.)]\s)', line):
            lines.append(' ' * len(line))  # Markdown permits lazy paragraph continuation.
        else:
            quoted_paragraph = False
            lines.append(line)
    text = ''.join(lines)
    output = list(text)
    index = 0
    while index < len(text):
        char = text[index]
        prefix = _literal_prefix(text, index) if char in "\"'" else ''
        if char == '`':
            end = index + 1
            while end < len(text) and text[end] == '`':
                end += 1
            close = text.find(text[index:end], end)
            end = len(text) if close < 0 else close + end - index
        elif char in QUOTES and not (
                char == "'" and index and text[index - 1].isalnum() and
                not prefix):
            end = _quoted_end(text, index, prefix)
        else:
            index += 1
            continue
        output[index:end] = ' ' * len(output[index:end])
        index = end
    return ''.join(output)


def explicit_skill_requests(event: dict, host: str, *, plugin_root: Path) -> set[str]:
    """Recognize invocation tokens; delivery/application need separate evidence."""
    if host != 'codex' or event.get('hook_event_name') != 'UserPromptSubmit':
        return set()
    prompt = event.get('prompt')
    if not isinstance(prompt, str) or _host_block(prompt):
        return set()
    text = _invocation_text(prompt)
    domains = set(DOMAINS.values())
    requested = set()
    # A linked selection belongs to its actual path, never merely its displayed name.
    for match in list(re.finditer(r'\[\$[A-Za-z0-9_:-]+\]', text)):
        destination = re.match(r'\s*\(([^)]*)\)', text[match.end():])
        raw = unquote(destination[1].strip().strip('<>')) if destination else ''
        if raw.startswith('skill://'):
            raw = raw[len('skill://'):]
        path = Path(raw)
        if path.is_absolute():
            for name in domains:
                try:
                    if path.resolve() == (plugin_root / 'skills' / name / 'SKILL.md').resolve():
                        requested.add(name)
                except (OSError, ValueError, RuntimeError):
                    pass  # An unresolved selection is not evidence that KH was selected.
        end = match.end() + (destination.end() if destination else 0)
        # Reference-style, incomplete and other unresolved linked selections must
        # not fall back to a bare invocation merely because their label is named.
        text = text[:match.start()] + ' ' * (end - match.start()) + text[end:]
    for match in re.finditer(r'\$([A-Za-z0-9_:-]+)', text):
        value = match[1]
        if ':' in value:
            owner, value = value.split(':', 1)
            if owner != 'kh-uaf':
                continue
        if value in domains:
            requested.add(value)
    return requested


def named_write_targets(prompt: str, domains: set[str], cwd: str) -> set[str]:
    """Accept a direct edit instruction with a literal destination. Mentions and code samples stay passive."""
    if not domains or len(prompt) > 16000 or _host_block(prompt):
        return set()
    text = prompt.strip().rstrip('.! ').strip()
    invocation = re.match(r'^(?:\[\$[\w:-]+\]\([^)]+\)|\$[\w:-]+|/[\w:-]+)\s+', text)
    if invocation:
        text = text[invocation.end():].strip()
    # Require the entire remaining directive. In particular, a comparison file,
    # quoted example or negative instruction cannot silently become an output.
    file = r'(?:"([^"\r\n]+)"|`([^`\r\n]+)`|\x27([^\x27\r\n]+)\x27|([^\s\x27"`]+?\.(?i:sql|cs|srd|srw|sru|srf)))'
    target = r'--target\s+' + file
    if re.fullmatch(target + r'(?:\s+' + target + ')*', text):
        matches = list(re.finditer(target, text))
    else:
        if '\n' in text:
            return set()
        purpose = r'[^\s?\n][^?\n]{0,180}'
        match = re.fullmatch(r'(?:edit|modify|update|create|format)\s+' + file + r'(?:\s+to\s+(?P<purpose>' + purpose + '))?', text, re.I)
        if match is None:
            match = re.fullmatch(file + r'(?:에서|의|을|를)?\s*(?:(?P<purpose>' + purpose + r')\s+)?(?:수정|작성|생성|포맷)(?:해(?:줘|주세요|라)?|하세요|하자)?', text)
        if match is None:
            return set()
        detail = match.groupdict().get('purpose') or ''
        if re.search(r'(?i)[`"\x27$;/\\]|\.(?:sql|cs|sr\w)\b|\b(?:not|never|skip|without|instead|example|except|review|whether|if)\b|말고|하지|대신|예시|검토|제외|여부|않|[?]', detail):
            return set()
        matches = [match]
    paths = set()
    root = Path(cwd).resolve()
    for match in matches:
        raw = next(part for part in match.groups() if part)
        if any(char in raw for char in '*?<>|$') or '://' in raw:
            return set()
        try:
            path = (root / raw).resolve()
        except (ValueError, OSError, RuntimeError):
            return set()
        if DOMAINS.get(path.suffix.casefold()) not in domains or not path.is_relative_to(root):
            return set()
        paths.add(str(path))
    return paths


def matching_prompt(record: dict, event: dict) -> bool:
    recorded, submitted = record.get('prompt_id'), event.get('prompt_id')
    if recorded is not None or submitted is not None:
        return isinstance(recorded, str) and bool(recorded) and recorded == submitted
    prompt = event.get('prompt')
    if not isinstance(prompt, str) or not prompt:
        return False
    return record.get('prompt_sha256') == hashlib.sha256(prompt.encode('utf-8')).hexdigest()


def successful_tool_result(event: dict) -> bool:
    if event.get('hook_event_name') == 'PostToolUseFailure':
        return False
    response = event.get('tool_response')
    if not isinstance(response, dict):
        return True
    return not (any(response.get(key) for key in ('error', 'isError', 'is_error')) or
                response.get('success') is False or response.get('ok') is False or
                str(response.get('status', '')).casefold() in {'failed', 'failure', 'error', 'cancelled', 'canceled'} or
                any(key in response and response[key] != 0 for key in ('exit_code', 'exitCode', 'returncode')))


def native_skill_usage(event: dict, host: str) -> str | None:
    if host != 'claude':
        return None  # Codex has no documented matching native skill-load event.
    name = event.get('hook_event_name')
    if name == 'UserPromptExpansion':
        if event.get('expansion_type') != 'slash_command' or event.get('command_source') != 'plugin':
            return None
        value = event.get('command_name')
    elif name == 'PostToolUse' and str(event.get('tool_name', '')).casefold() == 'skill':
        data = event.get('tool_input')
        if not isinstance(data, dict):
            return None
        if not successful_tool_result(event):
            return None
        value = data.get('skill')
    else:
        return None
    if not isinstance(value, str) or len(value) > 160:
        return None
    match = re.fullmatch(r'(?:kh-skills|kh-uaf):([a-z0-9-]+)', value)
    return match[1] if match and match[1] in set(DOMAINS.values()) else None
