# Token Optimizer Skill Usage Reference

This reference expands the portable operating contract for `token-optimizer`. Read it when the task is real work, when deciding whether this skill applies, or when a review needs evidence beyond the concise `SKILL.md`.

## When to use

Use when terminal logs, command output, or Python code are too large for efficient LLM context handling.

Context summary: This skill provides utilities to prevent token exhaustion during complex debugging or code reading loops.

Do not use this skill only because it is available. Use it when the current task needs the behavior named by the trigger, and state whether the skill was actually executed, applied procedurally, or only considered.

Quality rule: token savings must never hide source-of-truth details. Treat `optimize_context_content` as the universal entrypoint for large or uncertain content, but allow it to return passthrough. For SQL, stored procedures, license headers, security comments, business rules, exact contract prose, or ordinary text that cannot be safely classified as compressible output, use passthrough and record why compression was skipped.

## Inputs to collect

- User objective, success criteria, and any explicit completion conditions.
- Target workspace, write boundaries, and whether user-facing deliverables are expected.
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
  - `src.contracts.HarnessResult`
  - `tests.test_command_output_runtime`

## Execution pattern

1. Read `SKILL.md` first and confirm the trigger applies to the current task.
2. Read this reference before performing non-trivial work with `token-optimizer`.
3. Prefer `optimize_context_content` as the default entrypoint. It passes through contract-sensitive text, minifies safe Python code, and uses command-family filters for logs.
4. For file-based logs, run `python -m src.skills.token_optimizer --log-file <path> --max-lines <n>` instead of pasting very long output into `python -c`.
4. Preserve intermediate decisions in structured evidence rather than relying on terminal logs alone.
5. Run `python scripts/smoke_check.py` when validating this packaged skill in the repository.
6. Report the difference between capability available in the repository and behavior actually executed in the current run.

## Evidence to produce

- Skill name and execution level used for the run.
- Concrete input summary and target workspace or artifact paths.
- Implementation targets touched, imported, called, resolved by smoke check, or explicitly not needed.
- Output files, gate results, state records, or role results created by the skill.
- Verification command or review evidence, including failures and blocked states.

## Failure handling

- If a required implementation target is missing, stop using this skill as executed evidence and report the missing target.
- If the workflow can only be applied procedurally, say so explicitly and record the policy or decision evidence.
- If parallel, role, gate, or state behavior is claimed, prove the actual runtime path instead of citing only repository support.
- If generated artifacts are incomplete, withhold completion until the missing artifact or exception is recorded.

## Quality bar

A valid use of `token-optimizer` must leave enough evidence for another agent to answer: why this skill applied, what ran or was applied, what changed, and what still needs attention.
