# Token Optimizer Skill Usage Reference

This reference expands the portable operating contract for `token-optimizer`. Read it when the task is real work, when deciding whether this skill applies, or when a review needs evidence beyond the concise `SKILL.md`.

## When to use

Use as a decision gate for every KH-routed turn after `always-on-front-door` has run. Actual compression is still quality-gated: use it only for large or compressible command output, transcripts, logs, or code where required facts can be preserved.

Context summary: This skill is the UAF context budget gate. It must produce an explicit used, considered_not_needed, passthrough, or blocked decision for each KH-routed turn. It prevents token exhaustion during large development, debugging, review, QA, subagent, command-validation, or code-reading loops.

Do not claim compression only because the skill is available. The decision gate is always executed for KH-routed work, but compression is applied only when it preserves required facts. State whether the skill was used, considered_not_needed, passthrough, or blocked.

Quality rule: token savings must never hide source-of-truth details and must never reduce answer quality. Treat `optimize_context_content` as the universal entrypoint for large or uncertain content, but allow it to return passthrough. For SQL, stored procedures, license headers, security comments, business rules, exact contract prose, or ordinary text that cannot be safely classified as compressible output, use passthrough and record why compression was skipped.

## Inputs to collect

- User objective, success criteria, and any explicit completion conditions.
- Target workspace, write boundaries, and whether user-facing deliverables are expected.
- Context budget risk: `estimated_context_tokens`, large files, repeated test logs, long command output, large task plans, task-packet size, subagent transcripts, expected tool calls, broad file reads, or multi-turn resume state.
- Retrieval budget risk: broad DB/API/search/file operations, missing selectors, missing field lists, missing limits, large stdout, or exact source-of-truth content that should stay in a file.
- Required role, gate, state, artifact, or command evidence for this harness.
- Existing artifacts or state files that must be preserved rather than overwritten.
- Execution level: `python-module`.
- Implementation targets:
  - `src.skills.token_optimizer.truncate_logs`
  - `src.skills.token_optimizer.minify_code`
  - `src.skills.token_optimizer.optimize_context_content`
  - `src.skills.token_optimizer.is_contract_sensitive_text`
  - `src.skills.token_optimizer.filter_command_output`
  - `src.skills.token_optimizer.summarize_command_output`
  - `src.skills.token_optimizer.summarize_agent_transcript`
  - `src.skills.token_optimizer.compare_token_usage`
  - `src.skills.token_optimizer.aggregate_token_usage_stats`
  - `src.skills.token_optimizer.build_retrieval_budget_plan`
  - `src.skills.token_optimizer.validate_retrieval_budget_plan`
  - `src.skills.token_optimizer.estimate_token_count`
  - `src.orchestration.runtime_token_optimizer.optimize_workflow_task_results`
  - `src.contracts.HarnessResult`
  - `tests.test_command_output_runtime`

## Execution pattern

1. Read `SKILL.md` first and confirm the trigger applies to the current task.
2. Read this reference before applying `token-optimizer` to real work.
3. For every KH-routed turn, decide the `token_optimizer_status` before the first broad file read, long-running command, implementation, or subagent dispatch.
4. For broad retrieval, call `build_retrieval_budget_plan(...)` before running the retrieval. Require count/scope first, sample before full read, required fields/selectors, explicit limits, and output-file handling for large results.
5. Prefer `optimize_context_content` as the default entrypoint. It passes through contract-sensitive text, source code, and general prose, and only invokes known command-family filters for logs with verifiable required facts. Direct `minify_code` remains an explicit caller utility, not automatic compression.
6. Keep agent/subagent transcripts and general prose as passthrough unless a separate caller contract supplies and verifies every required fact. `summarize_agent_transcript` is explicit utility behavior, not automatic workflow compression.
7. For workflow dispatch results, explicitly enable the canonical model view and provide project/chat/run raw scope plus caller-owned raw results or an external raw store. Serialize only the returned tasks through `serialize_canonical_model_view(...)`. Without both canonical serialization and recoverable raw ownership, return the original tasks unchanged and do not append optimizer metadata.
8. For file-based logs, run `python -m src.skills.token_optimizer --log-file <path> --max-lines <n>` instead of pasting very long output into `python -c`.
9. Preserve intermediate decisions in structured evidence rather than relying on terminal logs alone.
10. When optimization is applied, include before/after token usage statistics:
   - `estimated_payload_tokens_before`
   - `estimated_payload_tokens_after`
   - `estimated_payload_tokens_saved`
   - `estimated_payload_token_savings_ratio`
   - `where_saved`
   - `host_actual_tokens_available`
   - `host_actual_tokens_used`
   - `host_actual_token_source`
   - `host_actual_token_evidence`
   - `estimated_payload_bytes_before`
   - `estimated_payload_bytes_after`
   - `estimated_payload_bytes_delta`
   - `estimated_payload_characters_before`
   - `estimated_payload_characters_after`
   - `estimated_payload_characters_delta`
   - `billing_tokens_available`
   - `billing_counterfactual_available`
   - `by_strategy` for workflow summaries
   The `estimated_payload_*` fields describe optimizer-local measurements. `host_actual_*` fields describe observed Codex/host totals only when a runtime-invoked adapter callable supplies them. Caller strings or dictionaries are `claimed_unverified`. Host totals are never savings. Optimizer-local `actual_*` fields are not emitted.
11. Report `provider=rtk` only when a runtime-invoked adapter callable returns the compact output and the runtime emits an internal per-item receipt matching the exact canonical input/output hashes. Preserve every accepted item receipt in `provider_receipts`, including hybrid runs. `rtk_available=true` and caller-supplied receipts are never RTK-use evidence. KH's own family filter is `provider=kh`.
12. Every workflow-level token decision must include one concise status/reason record in external/internal state. Do not mutate each task with no-op telemetry.
13. If compression would hide an error, omit a requirement, weaken a review finding, or change user-facing meaning, do not compress; use `passthrough` or `blocked`.
14. Run `python scripts/smoke_check.py` when validating this packaged skill in the repository.
15. Report the difference between capability available in the repository and behavior actually executed in the current run.

## Evidence to produce

- Skill name and execution level used for the run.
- Concrete input summary and target workspace or artifact paths.
- `token_optimizer_status`: `used`, `considered_not_needed`, `passthrough`, or `blocked`.
- One concise `token_optimizer_status_reason` and `reason_code` for every status.
- Implementation targets touched, imported, called, resolved by smoke check, or explicitly not needed.
- Output files, gate results, state records, or role results created by the skill.
- Before/after token usage statistics for every optimized item or aggregate workflow, with optimizer-local telemetry separated from provider billing-token availability.
- Retrieval budget plan and validation result for broad DB/API/search/file reads.
- `host_actual_token_evidence` only when a runtime-invoked host adapter returns Codex session JSONL or GoalState events; otherwise record `claimed_unverified` or unavailable.
- `estimated_payload_tokens_saved` and `where_saved` so RTK-style gain reports can show where context was reduced.
- Canonical whole-task model payload counts and stable raw references for every accepted replacement.
- An internal RTK invocation receipt for every `provider=rtk` item; it verifies runtime invocation and payload correlation, not cryptographic provider authenticity. KH family filters stay labeled KH.
- Lifecycle evidence preserved during compression: `task_status`, `review_status`, `commit_sha`, `next_task`, RED/GREEN state, exit code, sandbox retry reason, file references, and reviewer severity.
- Verification command or review evidence, including failures and blocked states.

## Failure handling

- If a required implementation target is missing, stop using this skill as executed evidence and report the missing target.
- If the workflow can only be applied procedurally, say so explicitly and record the policy or decision evidence.
- If parallel, role, gate, or state behavior is claimed, prove the actual runtime path instead of citing only repository support.
- If generated artifacts are incomplete, withhold completion until the missing artifact or exception is recorded.
- If a retrieval would produce large stdout without selectors, field limits, count/sample preflight, or output-file handling, block or rewrite the retrieval before it runs.

## Quality bar

A valid use of `token-optimizer` must leave enough evidence for another agent to answer: why this skill applied, whether it was used or deliberately not used, which exact canonical payload reached the model, where raw recovery lives, whether every required fact survived, whether token counts are estimated or exact-model-tokenizer counts, and what still needs attention.
A valid run should also reduce upstream retrieval volume before output enters context whenever a count/sample/field/limit/output-file plan can preserve quality.
