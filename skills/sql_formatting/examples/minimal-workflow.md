# SQL Formatting Provider Minimal Workflow

## Scenario

A user supplies a short T-SQL query and asks for formatting only. The host selects `sql-formatting` directly, and the provider module issues a signed selection for the packaged skill path derived from the running module. No front-door Python run is needed for this ordinary single-domain request.

## Expected steps

1. Select the packaged SQL provider directly from the request and skill description.
2. Inspect `skills/sql_formatting/SKILL.md` and its support files.
3. Run `python -m src.skills.sql_formatting_provider issue-direct-selection --host <host> --project <project>` and preserve its signed origin-specific JSON. Select packaged provenance with `execution_actor=host-llm` and `headless_python_formatter=false`, then guard the exact module-derived packaged path. Independent JSON, copied skills, `CODEX_HOME`, and caller-supplied skills roots do not define runtime authority. External host authenticity remains a separate explicit boundary.
4. Read the original query and the canonical `skills/sql_formatting_style_harness/references/style-contract.md`.
5. Let the host LLM write the complete formatted candidate file without optimization, temp-table conversion, or omitted stored-procedure branches.
6. For this formatting-only path, omit the plan when canonical aliases are unchanged; bind a plan for every alias-changed scope. Generation requires plans for every non-exempt multi-source scope.
7. If the user corrects anything, invalidate this verification, update the candidate file, and rerun the verifier.
8. Write `source.sql`, `candidate.sql`, `response.md`, `provider-selection.json`, and the complete ordered `verifier-history.json`. Invoke the direct issuer and `python -m src.skills.sql_formatting_provider --verifier-history-file verifier-history.json` as exact standalone commands. The public release requires a ready repair decision from that full history and rejects missing or non-ready history, a failed second attempt, and any third or later candidate. For `functions.exec`, assign the sole `tools.shell_command` result and emit that same result through `text(r)`. Accept only a locally verified runtime receipt whose arguments, canonical hashes, and four raw file SHA-256 values match after public/session reopening of the files as bytes, and whose correlated host shell output contains the exact line `Exit code: 0`. A duplicate JSON key, BOM, newline conversion, JSON whitespace-only rewrite, or repeated selection/final receipt ID invalidates the evidence. Runtime receipt storage follows `UAF_RUNTIME_ROOT` through `runtime_paths`.
9. Publish one `verification.json` from the exact verifier result embedded by the final binder; its verification id and hashes must equal the binding receipt.
10. Paste-ready full SQL first in exactly one `sql` fenced block; return it only if verification and binding both succeed.

The runtime receipt is issuable only after the complete successful release schema passes. Top-level status is exactly `passed`; strict binding, provider-guard, verifier, and CLI-input mappings must be present and correlated. Verification id and all content hashes are 64-hex strings, fence count is integer 1, provider authority follows the selected source, verifier success is the actual boolean `true`, and runtime external authenticity stays `unverified`. The CLI-input portion requires eight string arguments, six correlated string resolved paths, four canonical string hashes, and four raw string file hashes. Runtime schema and every CLI/runtime/verifier/shell exit value must be actual integers. Boolean, float, numeric-string coercion, unexpected fields, array, object, and null substitutions fail; the public validator and session audit repeat the exact-type checks even when the local runtime signature itself is valid.

The direct-packaged selection has an exact schema and proves the module-derived provider/contract paths, compatible packaged metadata, `selection_origin=direct-packaged`, and `selection_status=selected`. Governed front-door selections retain their route and execution-gate contract. Receipt IDs, local authority, external-authenticity marker, durable producer boundary, producer name, claim kind, and origin are fixed identities; a recomputed HMAC over different identities remains blocked.

The demo's actual_runtime_path differs at candidate generation: it uses a bundled static fixture and records `host_llm_executed=false`. It still executes the real verifier, proving source -> candidate -> verifier wiring without claiming live model work.

## Expected evidence

- Controller or assistant capability is `sql_formatting`.
- Provider metadata source is `packaged-kh-skill`.
- Authoritative provider path status is `accepted` with authority `current-packaged-fallback`.
- Direct skill order is `sql-formatting`, then `sql-formatting-style-harness`, without `always-on-front-door`.
- Original and candidate artifacts are readable and hashed.
- Candidate provenance distinguishes live host output from a demo fixture.
- Verifier output contains success, exit code, issue list, and contract metadata.
- The combined release receipt contains accepted provider authority, fresh release-ready verification, exact original/formatted/final-response/provider-selection hashes, matching `cli_inputs`, session id, nonce, module hash, and local runtime integrity evidence.
- Host session JSONL remains host evidence; the local runtime claim does not cryptographically authenticate it.
- `execution_level=procedure-policy` records that the host applies the provider procedure.
- `implementation_targets=src.skills.sql_formatting_provider.issue_direct_packaged_sql_provider_selection,src.skills.sql_formatting_style.verify_sql_formatting_style` records ordinary direct selection and verification ownership; governed routing may additionally record the front door.
- `verification=provider-smoke+provider-demo+catalog-provider-quality-tests+source-candidate-verifier` records the required evidence path.

## Failure cases

- A corrupt packaged provider produces `blocked_until_sql_formatting_provider`; no selected SQL provider is claimed.
- A missing canonical contract makes the packaged provider corrupt.
- A changed literal, predicate, expression, or comment causes verifier failure.
- Partial procedure/`WORKTYPE` output, retyped comment/casing/whitespace, caller-supplied verifier metadata, a failed/blocked/stale verifier result, explanation-first output, or more than one fenced block fails final-response binding.
- Any user correction makes the old verification stale until the candidate file is updated and verification reruns.
- Running only the verifier does not satisfy provider execution because the verifier does not generate candidates.
- A copied contract under `skills/sql_formatting/references/style-contract.md` fails provider inspection.
- A provider under `disabled-skills`, backups, staging, an arbitrary discovered clone, or an unrelated cache path fails the authoritative path guard even when it is repeated as the selected path.
- Echoed, commented, piped, redirected, chained, or `Write-Output` command text is not execution. Missing/nonzero shell exit evidence, `--skills-root`, a selection/path/hash mismatch, and a stale session/nonce all fail closed.
- A later user correction or new SQL request invalidates the prior selection and receipt until a newly correlated answer is bound.
- Any lint or release-readiness failure remains blocked; it is never delivered as complete.
- An initial verifier failure permits one repair only when structured issue evidence identifies what to change. A failed repair, missing issue evidence, or a third attempt returns a blocked reason and no SQL.

## Done criteria

- Ordinary SQL uses direct-packaged KH selection. An already-authenticated host-local selection may take precedence without running a discovery front door.
- The source-to-candidate actor and provenance are explicit.
- The canonical contract is referenced, not forked.
- Every generated multi-source or alias-changed scope has a complete plan; canonical unchanged formatting scopes are explicitly plan-free.
- The real verifier passes the candidate with exit code 0, ready release status, and a non-empty verification id.
- The response starts with one complete SQL fence whose UTF-8 SHA-256 equals verifier `formatted_sha256`.
- Missing/corrupt provider states fail closed and cannot appear as selected provider evidence.
