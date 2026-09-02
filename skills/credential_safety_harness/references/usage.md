# Credential Safety Harness Usage Reference

## When to use

Use this harness when the task itself reads, creates, updates, transmits, validates, or could expose a credential, API key, token, connection string, or secret-bearing environment variable.

Do not select or read it merely because an already-configured MCP, database, API, plugin, connector, or subagent is used through its normal interface. Connection status and SQL execution through an existing MCP do not expose or manage credentials.

This harness is not a secret manager. It only defines the agent-safe protocol for verifying presence and prompting the user to add a missing value outside chat.

## Inputs to collect

- Credential name, such as `OPENAI_API_KEY`, `NCBI_API_KEY`, or `SQL_CONNECTION_STRING`.
- Why the credential is needed.
- Environment file path, defaulting to `~/.env` unless the project has an approved local path.
- Host platform: `powershell` for Windows or `bash` for POSIX shells.
- Whether the next step can proceed without the credential.
- Execution level: `python-module`.
- Implementation targets:
  - `src.skills.credential_safety.CredentialSafetyPlan`
  - `src.skills.credential_safety.build_credential_safety_plan`
  - `src.skills.credential_safety.classify_credential_command`
  - `src.skills.credential_safety.validate_credential_safety_plan`

## Execution pattern

1. Normalize the credential name to uppercase letters, digits, and underscores.
2. Build a plan with `build_credential_safety_plan(...)`.
3. Validate the plan with `validate_credential_safety_plan(...)`.
4. Before executing any command that touches `.env` or environment variables, classify it with `classify_credential_command(...)`.
5. If classification is `unsafe_secret_exposure`, block the command and return the reason.
6. If the safe presence check fails, provide the generated hidden-input command and ask the user to run it outside chat.
7. If a selected credential-bearing workflow can proceed without the credential, record internal `credential_safety_status=passthrough` with the reason.

## Evidence to produce

- Internal `credential_safety_status` after the harness was selected.
- The credential variable name, not its value.
- The check command and validation result.
- `safe_presence_check` or `unsafe_secret_exposure` classification.
- Blocked reason and remediation.

## Failure handling

- If the credential name contains shell control characters, block and ask for a valid environment variable name.
- If a command would print or read secret values into context, block it.
- If the platform is unsupported, block and ask for a supported shell mode.
- If a credential is missing, do not run dependent tools until the user confirms it was added outside chat.

## Quality bar

A valid use proves that KH can determine presence without seeing the secret. A failed use exposes, stores, echoes, summarizes, or asks the user to paste the secret value.

## Runtime binding

- Execution level: python-module
- Implementation targets:
  - `src.skills.credential_safety.CredentialSafetyPlan`
  - `src.skills.credential_safety.build_credential_safety_plan`
  - `src.skills.credential_safety.classify_credential_command`
  - `src.skills.credential_safety.validate_credential_safety_plan`
- Application path: run the credential policy module before credential setup/change, a secret-bearing config read, environment dump, or command that may expose a secret. Normal calls through an already-configured MCP/API/connector bypass this harness.
- Completion rule: do not report this skill as applied until the plan status is `safe`, `blocked`, or `approval_required` and the evidence proves presence without printing secret values.
