# Token Optimizer Skill Minimal Workflow Example

## Scenario

A host agent receives a KH-routed request. The token gate must run even if the request is light/direct and no compression is ultimately applied; actual optimization is used only when content can be safely reduced without losing required facts.

The agent must decide whether `token-optimizer` applies, run or apply it according to its execution level, and leave auditable evidence.

## Expected steps

1. Load `SKILL.md` and confirm the trigger applies.
2. Read `references/usage.md` before doing the work.
3. Collect the user objective, workspace boundary, expected outputs, and evidence requirements.
4. Record `token_optimizer_status` as `used`, `considered_not_needed`, `passthrough`, or `blocked` before broad reads, subagent packets, long commands, or implementation.
5. When content is compressible, call `optimize_context_content`, `summarize_agent_transcript`, `summarize_command_output`, or `python -m src.skills.token_optimizer --log-file <path>` according to the content type.
6. Write or report the resulting compact output, `HarnessResult`, before/after size, `not_used_reason`, passthrough reason, or blocked reason.
7. Run `python scripts/smoke_check.py` when validating the packaged skill folder itself.

## Expected evidence

- `skill`: `token-optimizer`.
- `execution_level`: `python-module`.
- `support_reference_read`: `references/usage.md`.
- `implementation_targets`:
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
  - `src.orchestration.token_optimizer_provider.resolve_token_optimizer_provider`
  - `src.orchestration.runtime_token_optimizer.optimize_workflow_task_results`
  - `src.contracts.HarnessResult`
  - `tests.test_command_output_runtime`
- `actual_runtime_path`: the concrete module, workflow, policy gate, or procedural step used in this run.
- `verification`: command output, test result, artifact path, or explicit blocked reason.

## Failure cases

- The agent claims the skill was executed but only read `SKILL.md`.
- The agent omits `token_optimizer_status` or `not_used_reason` when no compression was applied.
- The agent reports provider billing-token savings when only local payload estimates were available.
- The agent reports parallel, role, state, or gate behavior without runtime-path evidence.
- The agent creates user-facing artifacts in hidden state folders or hidden state in the user output folder.
- The agent omits failed worker, gate, policy, or verification results from the final aggregate.

## Done criteria

- The trigger match is explicit.
- Required inputs and boundaries are recorded.
- The execution level is stated accurately.
- Evidence proves what actually ran or was applied.
- Missing or blocked work is represented as structured evidence, not hidden in prose.
