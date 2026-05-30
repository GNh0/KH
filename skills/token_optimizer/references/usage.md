# Token Optimizer Skill Usage Reference

This reference expands the portable operating contract for `token-optimizer`. Read it when the task is real work, when deciding whether this skill applies, or when a review needs evidence beyond the concise `SKILL.md`.

## When to use

Use when large or long-running development workflows, subagent transcripts, terminal logs, command output, or Python code risk wasting LLM context.

Context summary: This skill is the UAF context budget gate. It prevents token exhaustion during large development, debugging, review, QA, subagent, command-validation, or code-reading loops.

Do not use this skill only because it is available. Use it when the current task needs the behavior named by the trigger, and state whether the skill was actually executed, applied procedurally, or only considered.

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
  - `src.contracts.HarnessResult`
  - `tests.test_command_output_runtime`

## Execution pattern

1. Read `SKILL.md` first and confirm the trigger applies to the current task.
2. Read this reference before performing non-trivial work with `token-optimizer`.
3. For heavy work, decide the `token_optimizer_status` before the first broad file read, long-running command, or subagent dispatch.
4. Prefer `optimize_context_content` as the default entrypoint. It passes through contract-sensitive text, minifies safe Python code, and uses command-family filters for logs.
5. For long agent or subagent transcripts, use `summarize_agent_transcript` so task, review, verification, and commit evidence survive compression. For short, exact, or contract-sensitive subagent output, record `considered_not_needed` or `passthrough` instead of compressing.
6. For file-based logs, run `python -m src.skills.token_optimizer --log-file <path> --max-lines <n>` instead of pasting very long output into `python -c`.
7. Preserve intermediate decisions in structured evidence rather than relying on terminal logs alone.
8. When optimization is applied, include before/after token usage statistics:
   - `without_token_optimizer`
   - `with_token_optimizer`
   - `estimated_tokens_saved`
   - `token_savings_ratio`
   - `by_strategy` for workflow summaries
9. When optimization is not applied during heavy work, report `considered_not_needed`, `passthrough`, or `blocked` with a short reason.
10. If compression would hide an error, omit a requirement, weaken a review finding, or change user-facing meaning, do not compress; use `passthrough` or `blocked`.
11. Run `python scripts/smoke_check.py` when validating this packaged skill in the repository.
12. Report the difference between capability available in the repository and behavior actually executed in the current run.

## Evidence to produce

- Skill name and execution level used for the run.
- Concrete input summary and target workspace or artifact paths.
- `token_optimizer_status`: `used`, `considered_not_needed`, `passthrough`, or `blocked`.
- Implementation targets touched, imported, called, resolved by smoke check, or explicitly not needed.
- Output files, gate results, state records, or role results created by the skill.
- Before/after token usage statistics for every optimized item or aggregate workflow.
- Lifecycle evidence preserved during compression: `task_status`, `review_status`, `commit_sha`, `next_task`, RED/GREEN state, exit code, sandbox retry reason, file references, and reviewer severity.
- Verification command or review evidence, including failures and blocked states.

## Failure handling

- If a required implementation target is missing, stop using this skill as executed evidence and report the missing target.
- If the workflow can only be applied procedurally, say so explicitly and record the policy or decision evidence.
- If parallel, role, gate, or state behavior is claimed, prove the actual runtime path instead of citing only repository support.
- If generated artifacts are incomplete, withhold completion until the missing artifact or exception is recorded.

## Quality bar

A valid use of `token-optimizer` must leave enough evidence for another agent to answer: why this skill applied, what ran or was applied, what changed, how many estimated tokens were saved compared with no optimizer, and what still needs attention.
