# SQL Formatting Provider Usage

## When to use

Use this packaged provider when a user requests SQL/T-SQL formatting or cleanup, no compatible host-local SQL formatting provider is available, and KH can read this skill package. A compatible host-local provider has precedence. This packaged provider is the fallback execution procedure; `sql-formatting-style-harness` remains the independent verifier.

The provider applies only to formatting-preserving work. Requests for query optimization, temp-table conversion, scalar-function conversion, schema changes, predicate rewrites, or business-logic changes need a separately scoped workflow and evidence. Formatting never authorizes those changes.

## Inputs to collect

- Exact original SQL text or a stable file path.
- User constraints, including formatting-only boundaries and encoding requirements.
- Provider provenance selected by front-door routing.
- The exact provider path and source from a call-id-correlated front-door result, plus the complete provider-selection JSON used by the CLI.
- The current packaged fallback derived from the running KH module/repository when the front door selected `packaged-kh-skill`; neither `CODEX_HOME` nor a caller-supplied skills root may redefine it.
- The canonical contract at `skills/sql_formatting_style_harness/references/style-contract.md`.
- A complete semantic/business-role plan for every multi-source formatted scope, plus every alias-changed single-source formatted scope.
- A writable candidate destination when file output is requested.
- The verifier entrypoint `src.skills.sql_formatting_style.verify_sql_formatting_style`.

## Runtime binding

- Execution level: `procedure-policy`.
- Implementation targets:
  - `src.skills.sql_formatting_provider.inspect_packaged_sql_formatting_provider` for packaged-provider compatibility.
  - `src.skills.sql_formatting_provider.guard_authoritative_sql_formatting_provider_path` for exact active-provider or current-fallback authority.
  - `src.skills.sql_formatting_provider.guard_and_bind_verified_sql_final_response` for the authoritative provider-path and exact candidate-to-final-response release boundary.
  - `src.orchestration.kh_front_door.build_kh_front_door` for provider precedence and provider-before-verifier ordering.
  - `src.skills.sql_formatting_style.verify_sql_formatting_style` for candidate verification.
- Verification: run the packaged provider smoke/demo checks and the focused catalog, provider, and quality tests; formatting output still requires a successful source-to-candidate verifier result.

## Execution pattern

1. Confirm provider precedence through a correlated front-door call/output carrying a valid local-runtime SQL-provider-selection receipt: the exact compatible host-local selection first, the module-derived current packaged KH fallback second, otherwise blocked. Standalone JSON, copied skills, caller paths, `CODEX_HOME`, or a skills-root override do not grant authority. Local integrity does not authenticate an external host; keep that boundary explicitly `unverified` unless an external host authenticator succeeds.
2. Record that the execution actor is the host LLM. The package does not contain a full headless formatter.
3. Read the exact source and canonical generic contract. Do not create a local contract copy. Apply the canonical relative `JOIN` layout to ordinary and derived-table sources, and use the contract's depth-aware `GROUP BY`/`ORDER BY` packing rules; visibly noncanonical source indentation is not style authority.
4. Generate one complete candidate file through the host LLM while preserving SQL behavior-sensitive tokens. The candidate must contain the full requested SQL or stored procedure, including every branch and `WORKTYPE`; do not drift into optimization or temp-table rewrites.
5. Record a complete alias plan for every multi-source formatted scope, even when aliases are preserved, and for every single-source formatted scope whose alias changes. Role-family membership must be reviewer-approved semantic input, not an inference from repeated table names or source order.
6. Record whether the candidate came from a live host LLM or a static demo fixture. Never blur those provenance states.
7. Pass original, candidate, and any required alias plan to the verifier.
8. Treat every user correction as a new candidate revision. Immediate exact contextual corrections such as `No, that's wrong.`, `That is not what I asked.`, `Try again.`, and their Korean equivalents invalidate only when they directly follow an active SQL formatting result. Update the candidate file, rerun the verifier, and retain only the new successful `formatted_sha256`.
9. Keep every lint, semantic-preservation, alias-plan, verifier, and release-readiness failure blocked. A stale failure must never be described or delivered as complete.
10. Write the exact original, candidate, draft response, and signed provider-selection JSON files. Run the front door and binder as exact standalone commands; reject comments, output-only echoes, pipelines, separators, redirection, missing exit evidence, and every nonzero exit. A `functions.exec` wrapper is evidence only in the exact flow `const r = await tools.shell_command(...); text(r);`; dead, unreturned, wrong-result, and nested unrelated calls fail closed. Run `python -m src.skills.sql_formatting_provider --original-file <source.sql> --candidate-file <candidate.sql> --response-file <response.md> --provider-path <SKILL.md> --selected-active-provider-path <SKILL.md> --provider-selection-file <selection.json> --session-id <session-id> --invocation-nonce <fresh-nonce>`. The CLI validates provider authority, reruns `verify_sql_formatting_style`, and emits `cli_inputs` plus a durable local runtime receipt. Public issuance, public validation, and session audit reopen all four files as bytes and verify their raw SHA-256 values before canonical decoding and semantic hash checks; BOM, newline-only, and JSON-whitespace changes therefore invalidate the receipt. JSON decoding rejects duplicate keys recursively. Receipt storage uses `src.orchestration.runtime_paths.runtime_root()` so `UAF_RUNTIME_ROOT` and writable fallback behavior remain consistent with UAF. Text shell evidence succeeds only on the complete line `Exit code: 0`; structured exit evidence requires an actual integer zero.
11. Publish `verification.json` from the exact verifier payload embedded in the final CLI binding receipt. It is the authoritative final verification artifact; a separate preflight verifier run must not masquerade as final evidence.
12. Paste-ready full SQL first: the response begins with exactly one `sql` fenced block containing the byte-exact complete candidate. Put any short explanation after the SQL block.

`attach_sql_formatting_cli_runtime_receipt` and `validate_sql_formatting_cli_runtime_receipt` share one full successful-release schema. Top-level status is exactly `passed`. The exact binding requires bound status, original/candidate/final-response SHA-256 values, a 64-hex verification id, and integer fence count 1. The exact provider guard requires accepted status, the source-correlated authority (`selected-active-provider` or `current-packaged-fallback`), provider/selected/fallback paths, provider id/source, and provider-selection hash correlated to CLI and front-door evidence. The verifier envelope requires actual boolean success, integer zero exit, string stdout/stderr, float execution time, ready metadata, passthrough token-optimizer evidence, and original/formatted/verification hashes correlated to the binding and candidate. Runtime external authenticity is exactly `unverified`; an HMAC recomputed over altered identity or release fields does not grant authority.

Required CLI arguments are `original_file`, `candidate_file`, `response_file`, `provider_selection_file`, `provider_path`, `selected_active_provider_path`, `session_id`, and `invocation_nonce`. Required resolved paths cover the four artifacts and both provider paths. Required canonical hashes are `original_text_sha256`, `candidate_text_sha256`, `response_text_sha256`, and `provider_selection_sha256`; required raw hashes are `original_file_sha256`, `candidate_file_sha256`, `response_file_sha256`, and `provider_selection_file_sha256`. All scalar values and runtime receipt identifiers must be actual JSON strings, never coerced from booleans, numbers, arrays, objects, or null. Schema and all exit fields, including independently recorded shell-wrapper evidence, must be actual integers, not booleans, floats, or numeric strings. Missing/unexpected fields, non-64-hex digests, path/hash mismatches, scope mismatches, non-success exits, the wrong module, or any type confusion fail issuance, public validation, and session audit independently of HMAC validity.

The signed provider selection also requires normalized top-level producer evidence: `schema_version=1`, string `host` and absolute `project`, exact provider id/path/selected path/source/compatibility correlations, `selection_status=selected`, and an executable gate with an allowed status and string reason. `can_execute=false` is never authoritative. Validators check original identity field types and values before `RuntimeProducerBoundary.validate_claim`, including exact `selection-<32hex>` and `sql-provider-<32hex>` IDs, `local_runtime_integrity`, `unverified`, durable boundary identity, producer names, claim kinds, and HMAC claim format. Recomputing a local HMAC over wrong identity fields does not make the receipt valid.

Public validation is non-consuming for legitimate independent review. The session audit is the single-use execution boundary: repeated selection or final receipt IDs are rejected, including replay after an immediate correction or new SQL request. That replay guarantee requires complete host session history; external host authenticity remains explicit and unverified by the local HMAC.

For a file-based check, the verifier can run as `python -m src.skills.sql_formatting_style --original <source.sql> --formatted <candidate.sql>`.

## Evidence to produce

- Provider id and provenance source.
- `execution_actor=host-llm` for real formatting work.
- `headless_python_formatter=false`.
- Original and candidate hashes or paths.
- Canonical contract path.
- Complete alias plans for all multi-source formatted scopes and alias-changed single-source formatted scopes, with `alias_role_plan_validation.status=verified`.
- Verifier success, exit code, issue codes, and verification id.
- Exact original/formatted/final-response SHA-256 values, non-empty verification id, ready release status, `binding.status=bound`, accepted provider authority, and `cli_inputs` argument/hash/session/nonce binding from one combined CLI receipt.
- A signed provider-selection receipt, reopened artifact hashes, and one final `verification.json` exactly equal to the verifier payload embedded in the binding receipt.
- A locally verifiable durable runtime claim bound to the module and provider selection, together with independent shell exit code 0. The claim does not authenticate the host-owned session JSONL.
- A blocked provider status when discovery reports missing or corrupt.

The runnable demo uses a bundled static candidate fixture. It truthfully records `host_llm_executed=false`, `candidate_provenance=bundled-static-demo-fixture`, and then invokes the real verifier. That demonstrates the handoff contract without pretending to execute a host model.

## Failure handling

- If the host-local provider is missing or corrupt, continue only when the packaged provider inspection is compatible.
- If the packaged provider or canonical contract is missing/corrupt, block formatting and do not select a provider.
- Reject a candidate provider path that is not the path in correlated front-door evidence or the module-derived packaged fallback, even when its content appears compatible or it self-declares selection.
- Reject missing/failed shell exit evidence, any nonzero shell result, fake echoed/commented/`Write-Output` command text, `--skills-root`, and any receipt whose session, nonce, input, provider-selection, module, or release hash does not match.
- If verification fails, do not repair silently in a loop; report the first token/style evidence and require a revised host candidate.
- After any user correction, invalidate the old verification before updating the candidate; rerun and bind the revised candidate before delivery.
- If final-response binding reports a failed, blocked, invalid, or stale verification result, do not hand-edit or excerpt the SQL. Keep delivery blocked, rerun verification when needed, and rebuild the response from the exact candidate file.
- If any multi-source formatted scope, or any alias-changed single-source formatted scope, lacks a complete alias plan, block readiness and retain the source.
- If the request exceeds formatting, separate the change and obtain the evidence required by the canonical contract.

## Quality bar

A valid run lets another reviewer identify the original, complete candidate, candidate actor, call-id-correlated provider selection, canonical contract, verifier outcome, exact final-response binding, successful host shell result, and locally verified runtime receipt. Provider and verifier roles must remain distinct, semantic-preservation boundaries remain mandatory, and local receipt integrity must not be described as cryptographic authentication of host session JSONL.
