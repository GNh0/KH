# SQL Formatting Failure Audit - Thread 01a021d4

## Scope and numbering

- Session: `rollout-2026-08-21T09-59-09-01a021d4-2fa2-7582-8def-efadbc347fff.jsonl`
- Audited range: zero-based JSONL indices `179-553`, equivalent to physical lines `180-554`.
- KH baseline: current repository manifests report `2.9.141`.
- This is a read-only behavioral audit. No database execution is implied.

## Verdict

**P0 release failure and hostile UX failure.** The assistant spent 715 seconds before the first SQL answer, reached two explicit verifier-blocked results, never produced the required final-response binding, and then delivered three different SQL fences whose hashes did not match the only named final candidate. User corrections were handled by unverified retyping, including an alias rewrite without authenticated source-bound role evidence and a JOIN/derived-table layout that the user explicitly rejected.

## Findings

### P0 - SQL was emitted after two blocked verifier results

- The cleanup request starts at index `179` (`2026-08-21T01:10:53.828Z`).
- Verifier output at index `330` reports `success=false`, `exit_code=1`, `mechanical_status=blocked`, and `release_readiness.status=blocked`. It includes token-preservation, predicate, list-layout, and alias-plan source-binding failures.
- The revised verifier output at index `375` again reports `success=false`, `exit_code=1`, and `release_readiness.status=blocked`. Style lint and structural alias-plan matching pass, but preservation still fails with `token_stream_changed` and `predicates_changed`.
- Despite both failures, index `491` emits a full SQL fence. This directly violates the 2.9.141 contract: failed or blocked verifier output is not deliverable, and release requires `success=true`, integer `exit_code=0`, and `release_readiness.status=ready`.
- Whether the second failure came from a verifier defect or a bad candidate is immaterial at the delivery boundary: a blocked verifier must fail closed.

### P0 - No final-response hash binding; every delivered SQL body was different

The verifier identified `candidate_final.sql` as:

`4e83f57890fc70da2b60297dea11070e0802d2a977332418dcc75d02a12d0e2e`

The delivered SQL-fence hashes, including the fence body's trailing LF, were:

| Session index | Physical line | SHA-256 |
|---:|---:|---|
| `491` | `492` | `65dcff0bc2b7fcd36ec1d3868d369711e89a40eac9308a7f7302fb78c0eaee50` |
| `512` | `513` | `2d503b92bdd7bd213be2b59d7095987d9232abee2db63945b0ac0530a69eccd2` |
| `542` | `543` | `af9da2291d9c0ab2913759c6e24f61282d7777b9965680ad4a0e662604f892f2` |

None equals `4e83f578...`. Index `479` only requests provider CLI help; no successful binder invocation or release receipt follows. The 2.9.141 boundary requires exactly one SQL fence, byte-exact equality with the verified candidate, matching `formatted_sha256`, and a successful combined provider-path/final-response receipt. All three deliveries were therefore unbound and unreleasable.

### P1 - Alias normalization used self-authored reviewer approval instead of a valid source-bound rationale

- KH SQL cleanup includes canonical alias normalization when a complete source-bound semantic role plan exists; a separate user request to normalize aliases is not required.
- At index `243`, the assistant announces that aliases will be reorganized, but it does not first establish the source-bound semantic roles needed to justify the proposed `A/B/C/D` mapping.
- The plan shown at index `348` assigns those roles and self-authors `review://SQL-20260821/...` evidence. That URI is not user evidence or an independent review result and cannot authenticate the business-role assertions.
- The verifier at index `375` says only that the plan structurally matched and explicitly reports `semantic_authentication=caller_declared_not_authenticated`; structural agreement is not proof that the declared roles were derived from the source query's semantics.
- Index `512` therefore delivers an alias-normalized rewrite without authenticated source-bound role evidence. The defect is not that alias normalization occurred; it is that the assistant treated self-authored approval as sufficient, proceeded after failed verification, manually retyped the SQL, and changed the required relative JOIN layout.
- Self-authored reviewer approval is wrong. A host may instead provide a `source_bound_role_rationale` tied to the exact SQL and scope, with exact role coverage and a concrete rationale derived from the query. That rationale is explicitly host/caller-declared and not externally authenticated; it can authorize semantics-preserving alias style only while token, predicate, plan, style, and final-binding gates all pass. Genuine `review://` evidence remains a compatibility path and must not be fabricated.

### P1 - Generic JOIN rules overrode the user's cleanup style, then the repair violated both

- The 2.9.141 generic contract uses relative geometry: each `JOIN` is eight columns from its scope's `FROM`; `ON` and same-join continuation `AND`/`OR` align to the `I` in `JOIN`; derived-table joins use the same rule, inner clauses begin four columns inside the join clause, and the closing parenthesis plus alias align with the join clause.
- Index `491` largely follows that generic geometry, but it was not bound to a successful verifier and did not establish that the generic fallback matched the user's requested local cleanup style.
- Index `512` changes the layout after user rejection: inner joins are only five columns from the inner `FROM`, and the outer join is not indented eight columns from the outer `FROM`. It is neither the verified candidate nor canonical 2.9.141 layout.
- Index `542` asserts that the problem is understood, then places `JOIN` at the same level as `FROM` and `ON` four spaces inside it. That contradicts the 2.9.141 relative rule. It also emits only a fragment rather than the complete query.
- At index `548`, the user explicitly rejects the derived-table shape shown at index `542`; index `553` finally stops.
- The contract itself says exact user constraints are authoritative. Once the screenshot/style correction showed a conflict with the packaged fallback, release required a user-approved exemplar or host-local style contract, not another guessed layout.

### P1 - Corrections invalidated verification, but SQL was retyped without reruns

- User rejection at index `500` is followed by a new SQL fence at index `512` with no fresh successful verification or binding.
- The later screenshot correction at index `529` is followed by another SQL fence at index `542`, again without verification or binding.
- 2.9.141 explicitly invalidates prior verification after every contextual SQL correction. Each revision must update the candidate, rerun the verifier, and bind the exact new hash. Hand-edited or partial post-verification SQL is prohibited.

### P1 - Unnecessary latency dominated a formatting-only request

- Request index `179`: `2026-08-21T01:10:53.828Z`.
- First SQL answer index `491`: `2026-08-21T01:22:49.174Z`.
- Elapsed time: **715.346 seconds** (reported as 715 seconds).
- Before the first answer, the session had accumulated **76 tool calls**; **49** occurred after this cleanup request. Two verifier results were already blocked.
- The user complained about the delay at index `482`; the first SQL answer still arrived about 28.8 seconds later.
- The delay came from routing repetition, contract/test/source inspection, artifact churn, verifier debugging, and a provider `--help` call, not database execution. Index `498` correctly states that no DB query was executed, but incorrectly frames the verification itself as the problem. The UX failure was unbounded process with no successful release path.

## Generalized release acceptance criteria

1. **Exact intake:** Bind the exact user SQL and explicit style constraints before formatting. Do not silently replace the source with a reconstructed baseline.
2. **User-style precedence:** Use a selected host-local style when available. If the packaged relative JOIN rule conflicts with a user correction or exemplar, stop and resolve the style contract before emitting SQL.
3. **Alias normalization evidence:** Apply KH canonical alias normalization when a complete source-bound semantic role plan can be established. Prefer a host/caller-declared `source_bound_role_rationale` with a `query://` or `sql://` source, exact role coverage, and a non-empty rationale bound to the exact SQL scope. It is not reviewer approval and is not externally authenticated; self-authored `review://` approval remains forbidden. Ambiguous role assertions still fail closed.
4. **Canonical JOIN evidence:** When the KH fallback applies, verify `JOIN = FROM + 8 columns`, `ON/AND/OR = JOIN.I column`, and equivalent derived-table hierarchy at every query depth.
5. **Fail-closed verification:** Deliver SQL only when the exact final candidate reports `success=true`, integer `exit_code=0`, no blocking issues, and `release_readiness.status=ready`. A failed verifier permits only blocked evidence, never SQL.
6. **Exact final binding:** The response must start with exactly one complete SQL fence whose byte-exact body hash equals the verifier's `formatted_sha256`; the provider guard/binder and host shell must both exit 0 and produce a correlated receipt.
7. **Correction freshness:** Every user correction invalidates prior evidence. Revised or partial SQL requires a new candidate, verifier result, hash, and binding receipt.
8. **Latency gate:** A formatting-only request must not enter open-ended implementation spelunking. Set and enforce a simple-formatting response SLO (recommended: first paste-ready result or explicit blocked reason within 60 seconds), with at most one bounded repair loop before surfacing the blocker.
9. **Session-audit detection:** A session auditor must recognize both blocked verifier outputs and report SQL-after-failure even when calls are wrapped by the active host tool. Raw session evidence at indices `330`, `375`, and `491` must deterministically produce the failed-before-output finding.

## Release decision

**Reject.** No SQL fence in indices `179-553` is eligible for release. Acceptance requires a source-bound canonical alias plan with valid host/caller rationale or genuine legacy reviewer evidence, the correct relative JOIN layout, a successful exact-candidate verifier result after all corrections, and hash-bound final response evidence with no manual retyping.

## 2.9.142 release verification

- `python -m unittest -q tests.test_sql_formatting_provider`: 65 tests passed.
- `python -m unittest -q tests.test_sql_formatting_style_harness`: 184 tests passed.
- `python -m unittest -q tests.test_kh_front_door_always_on`: 39 tests passed.
- `python -m unittest -q tests.test_plugin_packaging`: 21 tests passed.
- SQL provider and style-harness `smoke_check.py`: both passed.
- SQL provider `demo.py`: passed with 8 validated artifacts.
- SQL style-harness `demo.py`: passed with 10 validated artifacts.
- `python -m src.skills.uaf_skill_catalog --check`: 44 valid, 0 invalid.
- `git diff --check`: passed.

Residual limitation: the public provider guard now requires correlated verifier history and enforces the one-repair limit, but a host that bypasses the guard and directly emits SQL remains outside this local enforcement boundary. Verifier history is correlated to the final SQL hashes at execution time; the raw history-file hash is not separately embedded in the signed receipt schema.
