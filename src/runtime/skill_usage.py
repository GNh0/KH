"""Recognize owned native skill invocations without persisting arguments."""
import re

DOMAINS = {'.sql': 'sql-formatting', '.cs': 'csharp-designer-style-harness',
           '.srd': 'pb-to-csharp-migration-harness', '.srw': 'pb-to-csharp-migration-harness',
           '.sru': 'pb-to-csharp-migration-harness', '.srf': 'pb-to-csharp-migration-harness'}
COMMON_EVENTS = frozenset({'SessionStart', 'UserPromptSubmit', 'PreToolUse', 'PostToolUse',
                           'PreCompact', 'Stop', 'SessionEnd'})
HOOK_EVENTS = {'codex': COMMON_EVENTS | {'Interrupt'},
               'claude': COMMON_EVENTS | {'UserPromptExpansion', 'PostToolUseFailure'}}


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
        response = event.get('tool_response')
        if isinstance(response, dict) and (response.get('is_error') is True or response.get('isError') is True or
                                         response.get('error') or response.get('status') in ('error', 'failed', 'failure')):
            return None
        value = data.get('skill')
    else:
        return None
    if not isinstance(value, str) or len(value) > 160:
        return None
    match = re.fullmatch(r'(?:kh-skills|kh-uaf):([a-z0-9-]+)', value)
    return match[1] if match and match[1] in set(DOMAINS.values()) else None
