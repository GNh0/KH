# Command Output Harness Usage Reference

This reference expands the portable operating contract for `command-output-harness`. Read it when the task is real work, when deciding whether this skill applies, or when a review needs evidence beyond the concise `SKILL.md`.

## When to use

Use when compressing command output for agents, preserving exit codes, filtering noisy logs, or tracking token savings in UAF workflows.

Context summary: This is a personal UAF command output harness. It provides compact command output behavior without requiring any external command proxy at runtime.

Do not use this skill only because it is available. Use it when the current task needs the behavior named by the trigger, and state whether the skill was actually executed, applied procedurally, or only considered.

## Inputs to collect

- User objective, success criteria, and any explicit completion conditions.
- Target workspace, write boundaries, and whether user-facing deliverables are expected.
- Required role, gate, state, artifact, or command evidence for this harness.
- Existing artifacts or state files that must be preserved rather than overwritten.
- Broad command risk: expected rows/lines, required fields, selectors, limits, output file path, and whether exact source text must remain passthrough.
- Execution level: `python-module`.
- Implementation targets:
  - `src.skills.token_optimizer.summarize_command_output`
  - `src.skills.token_optimizer.filter_command_output`
  - `src.skills.token_optimizer.truncate_logs`
  - `src.skills.token_optimizer.build_retrieval_budget_plan`
  - `src.skills.token_optimizer.validate_retrieval_budget_plan`
  - `src.contracts.HarnessResult`
  - `tests.test_command_output_runtime`

## Execution pattern

1. Read `SKILL.md` first and confirm the trigger applies to the current task.
2. Read this reference before performing non-trivial work with `command-output-harness`.
3. For broad commands, call `build_retrieval_budget_plan` before execution and require selectors, fields, limits, or output-file handling.
4. Call `summarize_command_output` only for a known command family with caller-supplied required facts or concrete family-derived failure facts. It validates every fact and returns exact passthrough if any fact is missing.
5. Treat `truncate_logs` as fallback, not the preferred path for pytest/build/linter/runtime output.
6. For model delivery, replace raw output in the canonical model view and include only a stable raw reference/hash. Keep the original raw output in caller-owned results or a project/chat/run-scoped external store.
7. Treat NUL/binary/high-entropy output, generic prose, source text, and success output without explicit required facts as passthrough.
8. Preserve intermediate decisions in structured evidence rather than relying on terminal logs alone.
9. Run `python scripts/smoke_check.py` when validating this packaged skill in the repository.
10. Report the difference between capability available in the repository and behavior actually executed in the current run.
11. Treat chars/4 counts as `estimated_payload_*` only, with `billing_tokens_available=false` and `billing_counterfactual_available=false`. Accept host-observed totals only from a runtime-invoked host adapter; caller JSONL is `claimed_unverified`.
12. Preserve one internal invocation entry in `provider_receipts` for every accepted RTK item, including RTK items inside a hybrid run. A runtime-invoked adapter callable is required; caller receipt dictionaries are claims only.

## Evidence to produce

- Skill name and execution level used for the run.
- Concrete input summary and target workspace or artifact paths.
- Implementation targets touched, imported, called, resolved by smoke check, or explicitly not needed.
- Output files, gate results, state records, or role results created by the skill.
- Retrieval budget plan and validation result when command output volume can be controlled before execution.
- Verification command or review evidence, including failures and blocked states.

## Failure handling

- If a required implementation target is missing, stop using this skill as executed evidence and report the missing target.
- If the workflow can only be applied procedurally, say so explicitly and record the policy or decision evidence.
- If parallel, role, gate, or state behavior is claimed, prove the actual runtime path instead of citing only repository support.
- If generated artifacts are incomplete, withhold completion until the missing artifact or exception is recorded.
- If a command would dump large unbounded stdout, rewrite it to a bounded query/search or file-output command before execution.

## Quality bar

A valid use of `command-output-harness` must leave enough evidence for another agent to answer: why this skill applied, what ran or was applied, what changed, and what still needs attention. It should also prove that preventable large stdout was bounded before execution instead of only compressed after the fact.
