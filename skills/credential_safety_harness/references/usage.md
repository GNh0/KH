# Credential Safety Harness Usage Reference

## When to use

Use this harness when a KH workflow, helper script, API call, MCP server, plugin, or subagent needs a credential, API key, token, connection string, or secret-bearing environment variable.

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
7. If the calling workflow can proceed without the credential, record `credential_safety_status=passthrough` with the reason.

## Evidence to produce

- `credential_safety_status`.
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
- Application path: run the credential policy module before any API call, MCP launch, config read, environment dump, or connector action that may expose a secret.
- Completion rule: do not report this skill as applied until the plan status is `safe`, `blocked`, or `approval_required` and the evidence proves presence without printing secret values.
