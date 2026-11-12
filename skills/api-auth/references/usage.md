# Shared API tool

Run `python -B <absolute-KH-root>/scripts/kh_api.py <command>`. All KH skills use this one tool. Loading the skill starts no daemon, timer, MCP or connection. Commands connect only when their actual operation needs it. Credentials live under `%LOCALAPPDATA%/KH/api-auth-v1`, encrypted with Windows current-user DPAPI; plugin upgrades do not own that directory. `KH_API_DATA` selects an absolute isolated data directory for an explicitly scoped test. There is no plaintext or non-Windows fallback in this release.

## Registration and reuse

For a normal user-owned OpenAI project key:

```powershell
python -B <KH-root>/scripts/kh_api.py init openai --provider openai
python -B <KH-root>/scripts/kh_api.py registration-plan openai --source-url https://platform.openai.com/api-keys --session-label <observed-host-session> --account-label <actual-account> --create-key-if-needed --clipboard-source
# Explain the displayed scope and obtain actual user approval in the conversation.
python -B <KH-root>/scripts/kh_api.py authorize-registration --plan <registration-plan-id>
# Use the approved official browser/session, handle login/MFA if necessary, then copy the key without exposing it to the model.
python -B <KH-root>/scripts/kh_api.py clipboard-state
python -B <KH-root>/scripts/kh_api.py register openai --approved-plan <registration-plan-id> --clipboard --clipboard-sequence <fresh-sequence>
python -B <KH-root>/scripts/kh_api.py check openai
python -B <KH-root>/scripts/kh_api.py request openai --path /models
```

Registration is conversational: identify the actual service/account and host-owned session, ask whether to register using it (including key creation only if needed and approved), then the agent performs the official account/authorization/key-management flow. The user intervenes only when login, MFA or service consent cannot be handled by the approved agent session. There is no separate key-entry window. The acquisition session remains managed by its host; this helper does not scrape global cookies or native Codex/Claude tokens. Session/account labels record the approved scope and are not independent identity attestation.

The acquired secret reaches the helper through a trusted in-memory pipe or an agent-owned fresh clipboard copy from that approved page. `--clipboard-source` records only the initial clipboard sequence, not its content. After copying, read the new sequence with `clipboard-state` and supply it to `register`; it must differ from the baseline and still match when read. After encrypted persistence, the helper clears only that unchanged sequence. A changed user clipboard is preserved. Keep the source key page until encrypted storage is confirmed; if storage failed, the clipboard is not destroyed and the caller must preserve/reconcile the acquired key before retrying.

Never put the key in chat, screenshot output, generated command literals or plaintext files. A connector pipe must keep the value inside trusted runtime memory, not return it to the model first. If the available host cannot perform a secret-safe handoff, report that capability limit rather than inventing support. Candidate credentials are encrypted before testing. If first registration cannot connect, resume its same approved plan with `renew --approved-plan <id>`; `check` alone does not silently activate a pending registration. Existing active credentials require a new approved replacement plan. A restart/cold CLI process uses the same vault. Unknown expiry stays unknown; a trusted API handoff may include a verified expiry timestamp.

When the approved official page provides expiry/remote metadata separately from its Copy button, record only the verified values for that same key with `record-metadata <service> --expected-revision <status-revision> --expires-at <Unix-timestamp> --remote-id <observed-id>`. Omit unknown fields. This preserves the credential and updates local metadata; it does not query or change the remote key. A stale revision, unfinished maintenance or conflicting known key id is rejected. The trusted caller must establish the page/key match; do not infer expiry from the key string or invent a timestamp from a date-only display.

For a Google Cloud API key, specify the actual API's read-only check URL with `init <service> --provider google-cloud --check-url <HTTPS-URL>`. For example, the voices-list endpoint is appropriate only for a task using Cloud Text-to-Speech with that API enabled. The header is `x-goog-api-key`. Most Google Cloud administration requires OAuth/IAM authority, not a workload API key.

`status [service]` reads metadata without connecting. A service id identifies a reusable credential/account, not a model. `request` accepts a path, HTTP method and optional JSON `--body-file`; that file is task input, not an authentication file. `--api-base` reuses the same credential at the registered origin or its configured `api_origins`. Google Cloud profiles also allow HTTPS/443 hosts ending exactly in `.googleapis.com`, so Gemini and other permitted Google APIs can use one registration without another key entry. Provider enablement, API restrictions, IAM and account permissions still apply. Arbitrary other hosts, user-info URLs and redirects are rejected. Responses omit credential fields and mask known in-memory secrets. Responses are bounded to 1 MiB, requests use socket timeouts, and failed mutations are not automatically replayed. For SSE, NDJSON or incremental UTF-8 responses, use the shared [streaming path](streaming.md). Uploads, bidirectional transports and other SDK-specific protocols need their actual source-grounded adapter.

## Review and approve maintenance

```powershell
python -B <KH-root>/scripts/kh_api.py plan openai --reason expiry_due
# Show the returned plan and obtain actual explicit user approval.
python -B <KH-root>/scripts/kh_api.py renew --approved-plan <returned-plan-id>
```

The initial plan expires after 15 minutes without approval. Its nonce binds service, credential revision, immutable registered profile and management revision. A completed plan cannot issue again. Approval attribution is supplied by the trusted caller/current conversation; the CLI cannot independently verify chat consent. Do not create an approval merely because a plan exists. The supplied consent applies to the displayed save/reconnect/revocation steps; further privilege or account changes are not implied.

Manual replacement displays the latest completed registration/replacement's source URL, account and host-owned session for fresh approval. Verify these against the current observed session; change them together with `plan --source-url ... --session-label ... --account-label ...` when needed. `--create-key-if-needed` explicitly includes creation. Prepare with `plan --clipboard-source` before clipboard acquisition, obtain actual consent, record it with `authorize --plan <id>`, then perform the account actions and use `renew --approved-plan <id> --clipboard --clipboard-sequence <fresh-sequence>`. A planned manual scope cannot accept a secret or execute until authorized. `--replace-input` lets the agent correct a manual pending candidate from that approved session. OAuth refresh and managed key reissue use encrypted credentials internally. The new candidate is saved before verification; only a successful check activates it. A failed verification retains it and the previous active credential. Resume that same plan without another issuance. After activation, approved previous-key revocation is attempted; a failure leaves the plan resumable at revocation, without another refresh or issuance. If an issuance response was lost before its result/operation was saved, stop and inspect provider inventory. A crash cannot safely establish that no key was created.

An unresolved operation blocks other plans for the same service, including nonces prepared earlier. After actually checking provider inventory and, when needed, revoking an issued orphan within the authorized scope, use `reconcile --plan <id> --outcome not-issued|orphan-revoked --evidence-reference <non-secret-reference>`. This records a caller-supported outcome; it is not an automated inventory check or proof of consent. Unfinished non-secret operation records survive local credential deletion so `forget` cannot silently erase an ambiguous remote issuance.

`forget <service> --confirm-service <service>` removes local credentials after an explicit user request. Truly ambiguous issuance remains blocked pending inventory reconciliation. Other unfinished plans become non-executable `abandoned` records with public remote/operation follow-up references; they do not deadlock a later re-registration. Remote credentials are not revoked by local deletion. Registered endpoint/authority definitions are immutable while credentials exist; use a new service id for a changed target.

## Non-secret service profiles

Use `configure --file <absolute-profile.json>` with these fields:

- `id`: lowercase identifier; `provider`: `generic`, `openai` or `google-cloud`.
- `base_url` and `check_path`: HTTPS API base and a read-only authenticated verification path.
- `auth`: `bearer` or `header`; optional `header` and `prefix` override their defaults.
- `api_origins`: optional additional exact HTTPS origins for APIs sharing this credential; configure them before registration. A different model on the same API needs no new profile.
- `renew_before_seconds`: warning window before a known `expires_at`, default seven days.
- `rotation`: one of the modes below. No secret values belong in profiles.

Rotation modes:

- `manual`: the agent obtains a replacement through the conversation-approved official account/session and hands it off internally. This is the default for user-owned OpenAI keys, whose key creation uses the official dashboard unless another documented authority is available.
- `oauth2`: provide `token_url`, such as Google's documented OAuth token endpoint. Registration includes access token, refresh token, client id and client secret if the provider requires it. Refresh uses form-encoded `grant_type=refresh_token`; rotated refresh credentials are saved with the candidate. Only Bearer responses are supported. See [OAuth refresh](https://www.rfc-editor.org/rfc/rfc6749.html#section-6).
- `http-json`: configure a documented `issue_path` (POST), non-secret `issue_body`, `secret_field` (list of response object keys), optional `id_field`, `expires_in_field`/`expires_at_field`, and `revoke_path` (DELETE path containing `{old_id}`) if revocation is approved. With `management_service`, the operation uses its separate authority; without it, the plan explicitly uses the workload's own authority and revokes with the newly verified credential. Example field mapping: `["result", "credential"]`. This mode lets another compatible service join by profile configuration, without a KH code change or release. Unsupported signed/SDK-specific protocols need a justified adapter or direct manual replacement.
- `openai-service-account`: provide `management_service` (a separately registered Admin key service), `project_id`, `service_account_id`, explicit `scopes`, positive `lifetime_seconds`, and optional `revoke_previous`. The management service base is `https://api.openai.com/v1`. OpenAI can issue a key for an existing service account; its project key management endpoints do not create user-owned keys. Existing scopes/roles and governance must be checked before choosing replacement scopes. The old key's remote id is required for revocation. See [OpenAI key lifecycle](https://developers.openai.com/api/docs/guides/api-keys) and [service-account key creation](https://developers.openai.com/api/reference/cli/resources/admin/subresources/organization/subresources/projects/subresources/service_accounts/subresources/api_keys/methods/create).
- `google-cloud-key`: provide `management_service` (separate OAuth bearer credentials), `resource_name` (`projects/<number>/locations/global/keys/<id>`) and optional `revoke_previous`. The management service base is `https://apikeys.googleapis.com/v2`. The adapter reads the current key, copies its restrictions, service-account binding and annotations, creates a replacement, polls the returned operation, retrieves its key string, verifies it against the workload API, then performs any approved deletion. Required IAM permissions include the relevant read/create/getKeyString/delete operations. See [create](https://docs.cloud.google.com/api-keys/docs/reference/rest/v2/projects.locations.keys/create), [key resource](https://docs.cloud.google.com/api-keys/docs/reference/rest/v2/projects.locations.keys), and [getKeyString](https://docs.cloud.google.com/api-keys/docs/reference/rest/v2/projects.locations.keys/getKeyString).

Management credentials must be registered and valid before planning a workload key reissue; renew that management service through the same lifecycle if necessary. No key type is assumed to have administrative authority merely because it can make model/API requests.

If management credentials change while a verified candidate or previous-key revocation is pending, `plan` presents a fresh approval bound to the new authority for the remaining steps. Approval supersedes the old plan without another issuance. An unknown issuance still requires inventory reconciliation first. Manual/OAuth modes cannot be configured with an unrelated revocation protocol.

## Verification and host boundaries

`--stdin` accepts secret JSON only from a trusted in-memory pipe (`secret`, optional `refresh_token`, `client_id`, `client_secret`, `expires_at`, `remote_id`). It never accepts a secret CLI flag or a credential input-file path. Do not construct a real key literal in model-generated code to feed this option.

`--loopback-fixture` permits HTTP only to a literal loopback IP for independent tests; external HTTP and redirects remain blocked. A fixture proves the common protocol/state behavior and actual local encryption, not a user's live OpenAI/Google account permissions. Live verification needs the approved account/session, a secret-safe internal handoff and the actual configured API. If a host cannot provide that handoff, report the boundary; do not require a separate key-entry application or expose the credential. No native Codex/Claude key store or app-managed MCP state is changed.

Return codes: `0` for a completed command (including an explicitly pending approval plan), `2` for a reported API/connection/registration state needing action, `1` for errors/cancellation. Read the JSON status as well as the code. Short-lived connections and task-owned browser helpers/test servers must be closed through their owning handles; preserve needed approved user sessions.
