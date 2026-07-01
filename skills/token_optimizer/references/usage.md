# Token Optimizer Skill Usage Reference

This reference expands the portable operating contract for `token-optimizer`. Read it when the task is real work, when deciding whether this skill applies, or when a review needs evidence beyond the concise `SKILL.md`.

## When to use

Use as a decision gate for every non-trivial KH-routed turn after `always-on-front-door` has run. Actual compression is still quality-gated: use it only for large or compressible command output, transcripts, logs, or code where required facts can be preserved.

Context summary: This skill is the UAF context budget gate. It must produce an explicit used, considered_not_needed, passthrough, or blocked decision for non-trivial KH work. It prevents token exhaustion during large development, debugging, review, QA, subagent, command-validation, or code-reading loops.

Do not claim compression only because the skill is available. The decision gate is always executed for non-trivial KH work, but compression is applied only when it preserves required facts. State whether the skill was used, considered_not_needed, passthrough, or blocked.

Quality rule: token savings must never hide source-of-truth details and must never reduce answer quality. Treat `optimize_context_content` as the universal entrypoint for large or uncertain content, but allow it to return passthrough. For SQL, stored procedures, license headers, security comments, business rules, exact contract prose, or ordinary text that cannot be safely classified as compressible output, use passthrough and record why compression was skipped.

## Inputs to collect

- User objective, success criteria, and any explicit completion conditions.
- Target workspace, write boundaries, and whether user-facing deliverables are expected.
- Context budget risk: `estimated_context_tokens`, large files, repeated test logs, long command output, large task plans, task-packet size, subagent transcripts, expected tool calls, broad file reads, or multi-turn resume state.
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
  - `src.skills.token_optimizer.estimate_token_count`
  - `src.orchestration.runtime_token_optimizer.optimize_workflow_task_results`
  - `src.contracts.HarnessResult`
  - `tests.test_command_output_runtime`

## Execution pattern

1. Read `SKILL.md` first and confirm the trigger applies to the current task.
2. Read this reference before performing non-trivial work with `token-optimizer`.
3. For every non-trivial KH turn, decide the `token_optimizer_status` before the first broad file read, long-running command, implementation, or subagent dispatch.
4. Prefer `optimize_context_content` as the default entrypoint. It passes through contract-sensitive text, minifies safe Python code, and uses command-family filters for logs.
5. For long agent or subagent transcripts, use `summarize_agent_transcript` so task, review, verification, and commit evidence survive compression. For short, exact, or contract-sensitive subagent output, record `considered_not_needed` or `passthrough` instead of compressing.
6. For workflow dispatch results, use `src.orchestration.runtime_token_optimizer.optimize_workflow_task_results(...)` so command output and subagent transcripts are optimized as runtime evidence under `WorkflowTaskResult.metadata.token_optimizer` without deleting raw metadata.
7. For file-based logs, run `python -m src.skills.token_optimizer --log-file <path> --max-lines <n>` instead of pasting very long output into `python -c`.
8. Preserve intermediate decisions in structured evidence rather than relying on terminal logs alone.
9. When optimization is applied, include before/after token usage statistics:
   - `without_token_optimizer`
   - `with_token_optimizer`
   - `estimated_tokens_saved`
   - `token_savings_ratio`
   - `estimated_payload_without_optimizer`
   - `estimated_payload_with_optimizer`
   - `estimated_payload_tokens_saved`
   - `estimated_payload_token_savings_ratio`
   - `where_saved`
   - `host_actual_tokens_available`
   - `host_actual_tokens_used`
   - `host_actual_token_source`
   - `host_actual_token_evidence`
   - `actual_usage_scope`
   - `actual_tokens_saved`
   - `actual_token_savings_ratio`
   - `actual_bytes_saved`
   - `actual_byte_savings_ratio`
   - `token_count_method`
   - `token_count_is_estimate`
   - `billing_tokens_available`
   - `by_strategy` for workflow summaries
   - RTK-style `by_command_family` stats for optimized command output
   The `estimated_payload_*` fields describe the raw-vs-compact optimizer payload counted by KH. `host_actual_*` fields describe observed Codex/host token evidence such as session `token_count` events or `goal.tokensUsed`. Legacy `actual_*` fields are retained for compatibility and must not be described as provider billing token savings.
10. Every workflow-level token decision must include `token_optimizer_status_reason`. When optimization is not applied, also report `not_used_reason` so a user can tell whether it was too small, quality-sensitive passthrough, provider/policy blocked, or no optimizable command output/transcript was present.
11. If compression would hide an error, omit a requirement, weaken a review finding, or change user-facing meaning, do not compress; use `passthrough` or `blocked`.
12. Run `python scripts/smoke_check.py` when validating this packaged skill in the repository.
13. Report the difference between capability available in the repository and behavior actually executed in the current run.

## Evidence to produce

- Skill name and execution level used for the run.
- Concrete input summary and target workspace or artifact paths.
- `token_optimizer_status`: `used`, `considered_not_needed`, `passthrough`, or `blocked`.
- `token_optimizer_status_reason`, plus `not_used_reason` for every non-`used` status.
- Implementation targets touched, imported, called, resolved by smoke check, or explicitly not needed.
- Output files, gate results, state records, or role results created by the skill.
- Before/after token usage statistics for every optimized item or aggregate workflow, with optimizer-local telemetry separated from provider billing-token availability.
- `host_actual_token_evidence` when a Codex session JSONL or GoalState update exposes actual host token usage.
- `estimated_payload_tokens_saved` and `where_saved` so RTK-style gain reports can show where context was reduced.
- Runtime workflow `token_optimization` summary and per-task `metadata.token_optimizer` records when optimizing `WorkflowTaskResult` objects.
- RTK-style command-family savings statistics for command output, even when KH is the provider.
- Lifecycle evidence preserved during compression: `task_status`, `review_status`, `commit_sha`, `next_task`, RED/GREEN state, exit code, sandbox retry reason, file references, and reviewer severity.
- Verification command or review evidence, including failures and blocked states.

## Failure handling

- If a required implementation target is missing, stop using this skill as executed evidence and report the missing target.
- If the workflow can only be applied procedurally, say so explicitly and record the policy or decision evidence.
- If parallel, role, gate, or state behavior is claimed, prove the actual runtime path instead of citing only repository support.
- If generated artifacts are incomplete, withhold completion until the missing artifact or exception is recorded.

## Quality bar

A valid use of `token-optimizer` must leave enough evidence for another agent to answer: why this skill applied, whether it was used or deliberately not used, the exact not-used reason when skipped/passthrough/blocked, what ran or was applied, what changed, how many optimizer-local payload tokens/bytes were saved compared with no optimizer, whether those token counts are local estimates or provider billing tokens, and what still needs attention.
