---
name: token-optimizer
description: Use when kh-uaf:always-on-front-door has already run; run it as an explicit decision gate for every non-trivial KH turn, then record used, considered_not_needed, passthrough, or blocked with before/after token telemetry and not-used rationale.
---
# Token Optimizer Skill

## KH Entry Contract

- Start every non-trivial turn through `always-on-front-door` unless this skill is that bootstrap step or the current turn was classified as light/direct.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, or a required follow-up gate selects it.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

This skill is the UAF context budget gate. Every non-trivial KH turn must pass through its decision gate, even when no compression is eventually applied. It prevents token exhaustion during large or long-running development workflows, complex debugging, subagent review loops, command validation, or code reading loops.

Default behavior is quality-first: the host may route any large or uncertain content through `optimize_context_content`, but the skill only compresses when required facts can be preserved. Token optimization must never reduce answer quality. Contract-sensitive text such as SQL, stored procedures, license headers, security comments, business rules, exact source-of-truth prose, and ordinary text that cannot be classified safely must pass through unchanged.
Large arbitrary prose also passes through by default; this is intentional because a generic summary can silently change meaning. Use command-family log filtering or explicit user-approved summarization when reduction is more important than exact wording.

## Context budget gate

Use this as an early decision gate for every non-trivial KH turn, not only as a rescue step after logs get too long. During heavy UAF development, design, review, QA, or subagent workflows, or whenever `estimated_context_tokens` is expected to cross the context budget threshold, the controller must decide whether the run needs optimization and record `token_optimizer_status`:

- `used`: content was compressed, filtered, minified, or summarized with before/after statistics.
- `considered_not_needed`: the workflow stayed small enough, but the gate was explicitly checked.
- `passthrough`: content was large but contract-sensitive, source-of-truth, or unsafe to summarize without reducing answer quality.
- `blocked`: optimization was required but could not preserve required facts or would reduce answer quality.

When a host exposes more than one context optimization path, record `token_optimizer_provider` as `kh`, `rtk`, or `hybrid`. KH is the built-in Python provider. RTK-style command optimization is optional. Hybrid may use RTK for high-noise command output when available and fall back to KH otherwise. `passthrough` is a decision/status for source-of-truth content when compression would lower quality; it is not a provider.

## Retrieval preflight

Before broad DB/API/search/file retrieval, reduce at the source instead of waiting to compress after the output is already in context:

- Count or scope first.
- Sample before full read.
- Select only required fields, columns, file names, line ranges, or evidence keys.
- Require explicit limits or selectors for broad scans.
- Write large or structured results to an output file and read only needed fields back.
- Keep exact source-of-truth content as passthrough and use file references instead of lossy summaries.

Use `src.skills.token_optimizer.build_retrieval_budget_plan` and `validate_retrieval_budget_plan` to record this decision when a workflow may otherwise dump large output into the model.

## Development evidence quality bar

For Superpowers-style or KH lifecycle work, compression must preserve the evidence that makes the run trustworthy:

- task plan position, `task_status`, `review_status`, `commit_sha`, and `next_task`.
- RED/GREEN state, failing-first check name, verification command, exit code, sandbox retry reason, and final pass/fail result.
- subagent role, compact task packet fields, changed files, file references, line references, reviewer severity, required fixes, and unresolved concerns.
- workspace strategy, worktree path or branch, approval/escalation reason, blocked reason, and release/integration state.

If any of those facts would be lost, do not compress that item; use `passthrough` or `blocked`.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## Instructions
1. At the start of every non-trivial KH-routed turn, record the token optimizer decision gate before broad reads, subagent dispatch, long command output, or implementation. If nothing is compressible yet, use `considered_not_needed`; if exact content must be preserved, use `passthrough`; if safe preservation cannot be proven, use `blocked`.
2. For mixed content, call `src.skills.token_optimizer.optimize_context_content`; it classifies logs, Python code, and contract-sensitive text before deciding whether compression is safe.
3. For long agent transcripts or subagent transcripts, call `src.skills.token_optimizer.summarize_agent_transcript` so lifecycle quality evidence is preserved while chatter is removed. Do not assume every subagent transcript should be compressed; short, exact, or contract-sensitive reviewer output may be `considered_not_needed` or `passthrough`.
4. If you run a command and it produces an extremely long error log (hundreds of lines) that clutters your context, you can run the python script directly to truncate it:
   `python -c "from src.skills.token_optimizer import truncate_logs; print(truncate_logs('''<PASTE_LOG_HERE>'''))"`
5. Alternatively, if you need to pass a large python file to another agent (or summarize it), minify it first by stripping comments and docstrings via AST:
   `python -c "from src.skills.token_optimizer import minify_code; print(minify_code(open('file.py').read()))"`
6. If command output needs a reusable UAF evidence record, call `src.skills.token_optimizer.summarize_command_output` so the exit code, command family, raw size, filtered size, and token savings metadata are preserved in `HarnessResult`.
7. For real workflow task results, call `src.orchestration.runtime_token_optimizer.optimize_workflow_task_results` or let `workflow-usability-harness` call it automatically. This attaches optimized command/subagent records under `metadata.token_optimizer` without deleting raw task metadata.
8. For before/after reporting, call `src.skills.token_optimizer.compare_token_usage` for one item or `aggregate_token_usage_stats` for a workflow-level summary. Report legacy compatibility fields (`without_token_optimizer`, `with_token_optimizer`, `estimated_tokens_saved`, `token_savings_ratio`) plus RTK-style payload estimates (`estimated_payload_without_optimizer`, `estimated_payload_with_optimizer`, `estimated_payload_tokens_saved`, `estimated_payload_token_savings_ratio`, `where_saved`) and host evidence (`host_actual_tokens_available`, `host_actual_tokens_used`, `host_actual_token_source`, `host_actual_token_evidence`). Keep legacy optimizer-local `actual_*` fields for backward compatibility, but do not describe them as provider billing tokens; they are payload-derived estimates unless the host evidence says otherwise.
9. For real log files, prefer the module CLI: `python -m src.skills.token_optimizer --log-file path/to/log.txt --max-lines 40`.
10. Final workflow status must include `token_optimizer_status` and `token_optimizer_status_reason`. If status is not `used`, also include `not_used_reason` explaining whether the content was too small, passed through for quality, blocked by provider/policy, or had no optimizable command output/transcript.
11. For broad retrieval, call `build_retrieval_budget_plan` before executing the command. Block or revise the retrieval when fields, selectors, limits, or output paths are missing.
12. If compression would hide an error, omit a requirement, weaken a review finding, or change user-facing meaning, do not compress; use `passthrough` or `blocked`.

## External Benchmark Recipe

Use this skill as a quality-first context gate:

1. Route uncertain large content through `optimize_context_content`.
2. Compress logs through command-family filtering and required-fact preservation.
3. Minify Python only when comments, docstrings, and exact wording are not part of the contract.
4. Pass through SQL, stored procedures, license/security/business comments, contract text, and ordinary prose that cannot be safely classified.
5. Report token savings only when compression was actually applied.

Pressure scenario: if compression would remove the only assertion value or a business rule comment, return passthrough or append the missing fact; do not trade answer quality for token savings.

## Required outputs

- `token_optimizer_status`: `used`, `considered_not_needed`, `passthrough`, or `blocked`.
- `token_optimizer_provider`: `kh`, `rtk`, or `hybrid` when provider policy is relevant. Use `token_optimizer_status=passthrough` for quality-preserving no-compression decisions.
- Compact log or code text that preserves errors, file paths, test names, and exit status context.
- Token-savings estimate or before/after size when used inside a harness result.
- Token usage before/after statistics when the skill is used as workflow evidence, including RTK-style estimated payload telemetry, host actual token evidence when available from `goal.tokensUsed` or session `token_count`, and a clear `billing_tokens_available` flag.
- Retrieval budget plan when a command/API/search/DB operation could emit large output.
- Runtime workflow evidence under `metadata.token_optimizer` for command outputs and agent transcripts when the workflow has `WorkflowTaskResult` objects.
- `token_optimizer_status_reason` for every workflow-level token decision, and `not_used_reason` whenever status is `considered_not_needed`, `passthrough`, or `blocked`.
- RTK-style `by_command_family` savings statistics when command output is optimized through KH runtime.
- Fallback note when truncation or minification cannot safely preserve actionable context.
- Passthrough note when content is contract-sensitive and should not be compressed.
- Preserved development evidence summary when optimizing a lifecycle run: `task_status`, `review_status`, `commit_sha`, `next_task`, exit code, sandbox retry, file references, and reviewer severity.

## Common mistakes

- Do not remove the only line that identifies the failure.
- Do not minify code that must preserve comments, formatting, or license headers.
- Do not use token optimization as a substitute for reading the relevant source.
- Do not summarize command output in a way that hides a non-zero exit code.
- Do not optimize SQL, stored procedures, contract text, license headers, security comments, or exact source-of-truth prose unless the user explicitly accepts loss.

## UAF implementation targets

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
- `src.orchestration.token_optimizer_provider.resolve_token_optimizer_provider`
- `src.orchestration.runtime_token_optimizer.optimize_workflow_task_results`
- `src.contracts.HarnessResult`
- `tests.test_command_output_runtime`
