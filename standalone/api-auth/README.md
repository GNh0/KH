# Standalone API authentication and streaming

This skill and its Python harness run independently of KH. They manage external API credentials, approved maintenance and bounded HTTP streaming. No KH skills, hooks, agents, daemon or MCP server are required.

Copy this complete `api-auth` folder into the host's supported personal skill directory, such as `~/.codex/skills/api-auth` or `~/.claude/skills/api-auth`. Keep `SKILL.md`, `references/`, `scripts/` and `src/` together. Read [the skill](SKILL.md) for the account/session approval and secret-handoff workflow, [usage](references/usage.md) and [streaming](references/streaming.md) for commands.

The runtime requires Windows and Python 3.11+. Run `python -B <absolute-api-auth-root>/scripts/api_auth.py --help` from any working directory. Loading the skill starts no process or network connection.

Existing registrations remain under `%LOCALAPPDATA%/KH/api-auth-v1`. This legacy path and the existing DPAPI entropy are intentionally preserved so extraction does not require registering keys again. No credential database is copied, renamed or migrated by this package. `API_AUTH_DATA` selects an absolute test/store directory; `KH_API_DATA` remains a compatibility alias. Never point tests at the actual credential store.

For development, from this skill's source directory run its separate regression suite with `python -B -m unittest discover -s tests/domain` and type checks with `pyright --project pyrightconfig.json`. Development tests/configuration are not included in the installation ZIP. The suite uses a real loopback protocol fixture and Windows current-user DPAPI. It does not establish live OpenAI/Google account permissions or successful provider issuance. Live requests still need the actual authorized task scope.

Build a self-contained installation ZIP with `python -B <repository-root>/scripts/build_api_skill.py --out <absolute-output.zip>` outside the source tree. The ZIP contains the skill and its runtime, excluding tests, caches and user credentials.
