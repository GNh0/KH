---
name: sql-formatting
description: Use when SQL or T-SQL must be formatted by the host without changing behavior and the result must be checked by the packaged verifier.
---

# SQL Formatting Provider

## KH Entry Contract

- Start non-trivial work through `always-on-front-door` when KH selected this provider.
- Provider selection is execution evidence only after this skill is read and applied to an exact SQL source.
- A listing, catalog entry, or `selected_not_executed_skills` record is not provider execution.
- Use a compatible host-local provider first, this packaged KH provider second, and block when neither is available.

## Support files

- Read `references/usage.md` before applying the provider.
- Use `examples/minimal-workflow.md` for the source-to-candidate-to-verifier contract.
- Run `python scripts/smoke_check.py` to validate packaging and implementation targets.
- Run `python scripts/demo.py --output-dir <tmp>` for a deterministic provider handoff demo.
- Run `python scripts/prepare_candidate.py ...` to apply a source-bound alias plan and JOIN whitespace mechanically before verification.

## Provider boundary

Execution actor: host LLM.

This provider is a dependency-free, host-readable procedure. It does not implement a headless Python formatter and must not claim that Python generated a formatted candidate. The host LLM reads the exact source, user constraints, and the single canonical generic contract at `skills/sql_formatting_style_harness/references/style-contract.md`, then produces the candidate.

`sql-formatting-style-harness` is a separate verifier. It checks the candidate after generation; it is not a substitute formatting actor.

Provider authority is path-bound to correlated front-door provider selection evidence carrying a valid KH local-runtime producer receipt. A self-authored JSON object, copied skill, or repeated path cannot grant authority. A host-local provider is authoritative only when the signed front-door output selected that exact active path. A packaged provider is authoritative only at the fallback derived from the running KH module/repository, never from `CODEX_HOME` or a caller-supplied skills root. The local receipt proves producer integrity and correlation only; `external_authenticity=unverified` remains explicit until an external host authenticator validates it.

## Workflow

1. Preserve the exact source SQL, encoding, literals, comments, and caller constraints.
2. Read `skills/sql_formatting_style_harness/references/style-contract.md`; do not copy or fork its rules into this provider.
3. Record provider provenance and `execution_actor=host-llm`. Preserve the exact correlated front-door provider-selection JSON. Guard the exact selected host-local path or the module-derived packaged fallback. Reject missing/uncorrelated selection, caller-local `CODEX_HOME` or skills-root overrides, self-declared clones, unrelated cache entries, disabled copies, backups, staging files, and stale discovered versions even when their content is compatible.
4. Have the host LLM write one complete formatted candidate file without semantic changes. Formatting must not drift into optimization, temp-table conversion, predicate changes, or partial stored-procedure/`WORKTYPE` output.
5. Complete alias plans for every multi-source formatted scope, plus every single-source formatted scope whose alias changes. The structural first source is `A`. Walk source declarations in SQL order: the first new support role family is `B`, the next is `C`, then `D`; when one family has multiple members, number every member from `1` (`B1`, `B2`, ...). Bind every required scope and declaration to declared, reviewer-approved semantic/business-role evidence. After the host has completed all non-alias formatting, call `bind_sql_alias_role_plan(host_candidate_sql, plan)` once against the exact pre-alias candidate that will be passed to `prepare_candidate.py`; it records that candidate's SHA-256 and the ordered declaration fingerprint for every planned scope. Apply that bound plan with `apply_sql_alias_role_plan(...)`. If the pre-alias candidate changes, discard and regenerate the plan rather than rebinding a stale plan.
6. Put each complete JOIN clause and its `ON`/continuation `AND` or `OR` terms on their required lines, then run the packaged `prepare_candidate.py`/`normalize_sql_join_layout(...)` path to set their leading whitespace. Every line-leading same-join `ON`/`AND`/`OR` aligns to the `I` column of that join's actual `JOIN` token; never derive the column from a fixed space count or from the current `ON` indentation. Inline, `BETWEEN`, `CASE`, and nested-query operators are excluded. The helper does not split inline clauses or rebuild derived-table inner layout. Run the packaged `src.skills.sql_formatting_style.verify_sql_formatting_style` against the exact source and the exact prepared candidate that will be returned. Presentation-only failures must be repaired from structured issue evidence and reverified in a bounded loop before asking the user. Semantic ambiguity remains blocked for clarification. Any unresolved lint, semantic-preservation, alias-plan, verifier, or release-readiness failure remains blocked.

For file-based work, prepare the candidate with the packaged command:

```powershell
python scripts/prepare_candidate.py --candidate <host-candidate.sql> --output <prepared-candidate.sql> --alias-role-plan <alias-role-plan.json>
```
7. Every user correction invalidates the previous verification. This includes an immediate short contextual correction such as `No, that's wrong.`, `That is not what I asked.`, `Try again.`, or the equivalent Korean phrases when it directly follows an active SQL formatting result. Do not apply those phrases broadly to unrelated turns. Update the same candidate file, rerun the verifier, and use only the new successful `formatted_sha256`; never patch or retype final SQL after verification.
8. Invoke the front door as one exact standalone Python command. Comments, `echo`/`Write-Output`, pipelines, separators, redirection, missing shell status, and every nonzero exit are not execution. Text shell evidence is successful only when the complete line is exactly `Exit code: 0`; structured evidence requires an actual integer zero.
9. Invoke `python -m src.skills.sql_formatting_provider` with the original, candidate, response, exact selected provider path, signed provider-selection JSON file, session id, and a fresh invocation nonce. `--skills-root` is not supported. The CLI reruns `verify_sql_formatting_style` and emits a durable local runtime receipt binding the invocation scope, canonical content hashes, raw file SHA-256 values for all four artifacts, provider-selection hash, module hash, exact verifier result, and successful exit status. Receipt state resolves through `src.orchestration.runtime_paths.runtime_root`, including `UAF_RUNTIME_ROOT` and writable fallback policy. The host shell output must independently report exit code 0.
10. Public issuance, public validation, and session audit must reopen the original, candidate, response, and provider-selection files as bytes, verify each raw file SHA-256, then decode/hash them with the CLI's canonical contract. Reject missing artifacts, duplicate JSON keys at any depth, and any post-receipt byte change, including a BOM, newline conversion, or JSON whitespace-only reserialization. Passed hashes alone are never authoritative. For `functions.exec`, session evidence is recognized only when the sole shell call is assigned and that exact result is emitted by `text(result)`.
11. Paste-ready full SQL first. Return exactly one `sql` fenced block containing the complete bound candidate, with any short explanation after it. Otherwise return blocked evidence and keep the source authoritative.

The public runtime-receipt issuer, validator, and session audit enforce one full successful release schema before trusting the local HMAC. Top-level `status` is exactly `passed`; `binding`, `provider_path_guard`, `verification`, and `cli_inputs` are required mappings with no unexpected release/binding/guard/verifier-envelope fields. Binding hashes and verification id are exact 64-hex strings, `sql_fence_count` is an actual integer equal to 1, and verifier success/exit/string metadata is type-exact and correlated to the binding and candidate hashes. Provider guard status, authority, provider id/source, selection hash, selected path, and current packaged fallback are exact and correlated to CLI inputs plus front-door evidence. Runtime `external_authenticity` remains exactly `unverified`.

The successful `cli_inputs` schema requires all eight CLI arguments, resolved paths for the four artifacts plus both provider paths, the four canonical hashes, and the four raw file hashes. Every scalar argument, path, hash, module, scope id, nonce, and receipt id must be an actual JSON string; values are never coerced. Every digest must be a 64-hex SHA-256, argument paths must correlate to resolved paths, and session id/nonce arguments must correlate to the receipt scope. Integer schema, verifier exit, CLI exit, runtime exit, and independently recorded shell-wrapper exit fields require `type(value) is int`, explicitly excluding booleans, floats, and numeric strings; successful exits equal zero. Issuance fails before signing; validation and session audit report exact-type errors even when the local HMAC is otherwise valid. This local integrity check does not authenticate the external host session.

Front-door SQL selection has its own exact schema before signing: integer schema version; non-empty string host/project; exact SQL provider id, source, compatibility, provider path, selected-active path, and `selection_status=selected`; one correlated SQL route; and an execution gate with `can_execute is True` plus allowed string status and non-empty string reason. Blocked or type-confused selections cannot gain authority from a valid HMAC. Selection receipt IDs match `selection-<32 lowercase hex>` and CLI receipt IDs match `sql-provider-<32 lowercase hex>`. Both receipts require exact local authority, unverified external-authenticity marker, durable boundary kind/id, producer name, claim kind, and HMAC claim shape before the shared runtime verifier is called.

Public receipt validation is intentionally non-consuming so independent reviewers can validate the same evidence. Session audit supplies the execution-history boundary: a selection or final receipt ID may appear only once, and a correction or new SQL request requires a newly issued selection and final release. Replay detection depends on the complete host session history; authenticity of that external history remains outside the local HMAC boundary.

## Required outputs

- Original SQL source or a stable path/hash identifying it.
- Formatted candidate with `execution_actor=host-llm`.
- Provider provenance: host-local or packaged KH fallback.
- Canonical contract path.
- Complete alias plans for every multi-source formatted scope and every alias-changed single-source formatted scope.
- Verifier result from `src.skills.sql_formatting_style.verify_sql_formatting_style`.
- A combined CLI release receipt including accepted provider authority, fresh verifier evidence, verification id, exact original/formatted/final-response SHA-256 values, and `cli_inputs` that bind the actual file arguments, session id, nonce, and provider-selection hash.
- One authoritative final verification artifact copied from the exact verifier result embedded in the final CLI binding receipt. Do not publish a separately rerun preflight result as final evidence.
- A valid durable local runtime claim plus independently recorded host shell exit code 0. This proves local integrity and correlation only; session JSONL authenticity remains an external host boundary and is not cryptographically authenticated by KH.
- Explicit blocked reason when no compatible provider exists or verification fails.

## Common mistakes

- Do not describe the verifier as the formatter.
- Do not replace the packaged candidate preparation or verifier with an ad hoc formatter and a matching ad hoc checker. A checker that repeats the formatter's own indentation formula can validate the same defect and is not release evidence.
- Do not verify one SQL string and then reindent, patch, or retype the SQL delivered to the user. Run the packaged preparation and verifier on the exact final candidate file and bind that exact hash to the response.
- Do not claim the demo fixture was generated by a live host LLM.
- Do not add a second style contract under this skill.
- Do not silently fall back to manual style rules when provider discovery fails.
- Do not search disabled skills, backups, staging paths, old plugin caches, or arbitrary copies for provider or style authority. Only the exact host-local provider selected by a correlated front-door receipt or the module-derived current packaged fallback is valid.
- Do not use `CODEX_HOME`, `--skills-root`, an uncorrelated front-door JSON object, or a nonzero/unknown shell result to establish provider authority or successful execution.
- Do not trust receipt hashes when a required CLI artifact is missing, unreadable, path-mismatched, or changed after receipt issuance; session audit reopens and rehashes every artifact.
- Do not emit a candidate when provider selection is missing or corrupt.
- Do not claim readiness when any multi-source formatted scope, or any alias-changed single-source formatted scope, has a missing or incomplete alias plan.
- Do not deliver partial SQL, multiple SQL fences, explanation-first output, a retyped candidate, a failed/blocked verifier result, caller-supplied verifier metadata, or a stale verification result.
- Do not carry verification across a user correction; update the candidate, rerun verification, and bind again.

## UAF implementation targets

- `skills/sql_formatting/SKILL.md`
- `skills/sql_formatting_style_harness/references/style-contract.md`
- `src.skills.sql_formatting_provider.inspect_packaged_sql_formatting_provider`
- `src.skills.sql_formatting_provider.guard_authoritative_sql_formatting_provider_path`
- `src.skills.sql_formatting_provider.bind_verified_sql_final_response`
- `src.skills.sql_formatting_provider.guard_and_bind_verified_sql_final_response`
- `src.skills.sql_formatting_style.apply_sql_alias_role_plan`
- `src.skills.sql_formatting_style.bind_sql_alias_role_plan`
- `src.skills.sql_formatting_style.normalize_sql_join_layout`
- `src.skills.sql_formatting_style.verify_sql_formatting_style`
