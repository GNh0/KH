"""Best-effort write guard for read-only review roles on hosts without a read-only shell.

Codex enforces the auditor's sandbox itself. Claude only removes the typed edit tools, so a
reviewer could still write through Bash/PowerShell; this guard denies the common write forms.
It is a conservative lexical check, not a sandbox: unknown programs that write are not detected.
"""
import re

READ_ONLY_ROLES = frozenset({'kh-rule-auditor'})
EDIT_TOOLS = frozenset({'Edit', 'Write', 'MultiEdit', 'NotebookEdit', 'apply_patch'})
SHELL_TOOLS = frozenset({'Bash', 'PowerShell', 'exec_command'})
# Discarded output streams are not file writes.
DISCARDED = re.compile(r'\d?>&\d|\d?>\s*(?:/dev/null|\$null|nul)\b', re.I)
QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")
# Shell syntax outside quotes; quoted search patterns such as "=>" or "rm " are not commands.
SHELL_FORMS = re.compile(
    r'>|\btee\b|\bsed\s+(?:-[a-z]*i|--in-place)|\bperl\s+-[a-z]*i'
    r'|\b(?:rm|rmdir|mv|cp|del|erase|copy|move|ren|rename|mkdir|md|touch|truncate|install|chmod|chown|ln)\b'
    r'|\b(?:Set|Add|Clear)-Content\b|\bOut-File\b|\b(?:New|Remove|Move|Copy|Rename)-Item\b|\bSet-ItemProperty\b'
    r'|\bgit\s+(?:add|rm|mv|commit|push|pull|fetch|merge|rebase|reset|restore|checkout|switch|stash|apply|am|clean|tag|branch\s+-[dDmM]|cherry-pick|revert|worktree|config)\b'
    r'|\b(?:npm|pnpm|yarn|pip|pip3|uv|dotnet|msbuild|choco|winget)\s+(?:install|add|remove|uninstall|build|publish|restore|update|upgrade)\b'
    r'|\bkh_context\.py\s+(?:apply|resume|remember|checkpoint|forget|compound-add|compound-remove)\b'
    r'|\bsqlcmd\b|\bInvoke-Sqlcmd\b',
    re.I)
# Inline interpreter code is quoted, so file-writing calls are matched in the whole command.
CODE_FORMS = re.compile(r'\bWrite(?:All)?(?:Text|Bytes|Lines)\b|\.write_(?:text|bytes)\s*\(|\bopen\s*\([^)]*[\'"][wax+]', re.I)


def role_name(event: dict) -> str:
    """Plugin agents arrive namespaced (for example ``kh-skills:kh-rule-auditor``)."""
    value = event.get('agent_type')
    return value.rsplit(':', 1)[-1] if isinstance(value, str) else ''


def readonly_violation(event: dict) -> str:
    """Return a denial reason when a read-only role attempts an observable write."""
    if role_name(event) not in READ_ONLY_ROLES:
        return ''
    tool = event.get('tool_name', '')
    if tool in EDIT_TOOLS:
        return tool + ' is not available to the read-only reviewer.'
    if tool not in SHELL_TOOLS:
        return ''
    data = event.get('tool_input', {})
    command = data.get('command', data.get('cmd', '')) if isinstance(data, dict) else data
    if not isinstance(command, str):
        return ''
    found = SHELL_FORMS.search(DISCARDED.sub(' ', QUOTED.sub("''", command))) or CODE_FORMS.search(command)
    if found is None:
        return ''
    return ('The read-only reviewer cannot run commands that write files, change the repository or apply DB work '
            '(matched "' + found[0].strip() + '"). Report the required repair to the main agent instead.')
