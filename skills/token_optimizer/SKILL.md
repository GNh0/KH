---
name: token-optimizer
description: Use when the current task contains a large reducible command, log, test, retrieval, or subagent payload that can be safely compressed, or when the user explicitly requests token optimization or telemetry. Do not invoke for short ordinary work or contract-sensitive SQL/C# alone.
---
# Token Optimizer Skill

## KH Entry Contract

- This skill is not a per-turn prerequisite. Do not read it merely to record `considered_not_needed` or `passthrough`.
- Select it only after visible context shows a large reducible payload, anticipated high-volume retrieval/output, or an explicit optimization/telemetry request.
- Contract-sensitive SQL, stored procedures, C# source, rules, and short ordinary requests are non-triggers unless a separate large reducible payload is also present.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.
- Keep selection, status, provider, and telemetry internal unless the user asks for them or optimization is blocked in a way that affects the requested work.

This skill is the UAF context budget gate for payloads that cross its trigger boundary. It prevents token exhaustion during large or long-running development workflows, complex debugging, subagent review loops, command validation, or code reading loops without taxing ordinary turns.

Default behavior is quality-first: the host may route any large or uncertain content through `optimize_context_content`, but the skill only compresses when required facts can be preserved. Token optimization must never reduce answer quality. Contract-sensitive text such as SQL, stored procedures, license headers, security comments, business rules, exact source-of-truth prose, and ordinary text that cannot be classified safely must pass through unchanged.
Large arbitrary prose also passes through by default; this is intentional because a generic summary can silently change meaning. Use command-family log filtering or explicit user-approved summarization when reduction is more important than exact wording.

## Context budget gate

After a trigger is present, use this as an early decision gate rather than waiting until logs are already too long. During heavy UAF development, design, review, QA, or subagent workflows, or whenever `estimated_context_tokens` is expected to cross the context budget threshold, the controller records `token_optimizer_status`:

- `used`: content was compressed, filtered, minified, or summarized with before/after statistics.
- `considered_not_needed`: the workflow stayed small enough, but the gate was explicitly checked.
- `passthrough`: content was large but contract-sensitive, source-of-truth, or unsafe to summarize without reducing answer quality.
- `blocked`: optimization was required but could not preserve required facts or would reduce answer quality.

When a host exposes more than one context optimization path, record `token_optimizer_provider` as `kh`, `rtk`, or `hybrid`. KH is the built-in Python provider. RTK may be reported only when the runtime invokes an RTK adapter callable itself and emits an internal per-item receipt correlated to the exact input and output hashes. Caller-supplied receipts are `claimed_unverified`; hashes prove correlation, not provider authenticity. Availability alone is not usage. KH filtering remains `provider=kh`. `passthrough` is a decision/status for source-of-truth content when compression would lower quality; it is not a provider.

The only model-facing workflow payload is `serialize_canonical_model_view(...)`. `optimize_workflow_task_results(...)` may return a compact replacement only when the caller explicitly enables that canonical view and supplies project/chat/run scope plus caller-owned raw results or an external raw store. The compact view replaces raw output and carries a stable raw reference/hash. It never appends compact records beside raw metadata. Without that path, return the original tasks unchanged.

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
1. Once the trigger matches, record the token optimizer decision before the large retrieval, subagent dispatch, or long command output. If the anticipated output proves small, use `considered_not_needed`; if a large mixed payload contains exact content that must be preserved, use `passthrough`; if safe preservation cannot be proven, use `blocked`.
2. For mixed content, call `src.skills.token_optimizer.optimize_context_content`; it classifies logs, Python code, and contract-sensitive text before deciding whether compression is safe.
3. Agent/subagent transcripts and general prose are passthrough unless a separate caller contract supplies and verifies every required fact. `summarize_agent_transcript` remains an explicit utility, not an automatic runtime compression path.
4. If you run a command and it produces an extremely long error log (hundreds of lines) that clutters your context, you can run the python script directly to truncate it:
   `python -c "from src.skills.token_optimizer import truncate_logs; print(truncate_logs('''<PASTE_LOG_HERE>'''))"`
5. Alternatively, if you need to pass a large python file to another agent (or summarize it), minify it first by stripping comments and docstrings via AST:
   `python -c "from src.skills.token_optimizer import minify_code; print(minify_code(open('file.py').read()))"`
6. Call `summarize_command_output` only for supported command families with caller-supplied required facts or concrete family-derived failure facts. Validate every fact in the candidate. Missing facts, NUL/binary/high-entropy output, generic prose, success output without required facts, or a nonshrinking candidate return exact passthrough.
7. For workflow task results, call `optimize_workflow_task_results(...)` with `token_optimizer_canonical_view=true`, `token_optimizer_raw_scope={project,chat,run}`, and either `token_optimizer_raw_owner=caller` or an external `raw_store`. Serialize only the returned tasks with `serialize_canonical_model_view(...)`; keep the original input or raw store outside model context.
8. For before/after reporting, call `compare_token_usage` or `aggregate_token_usage_stats`. Optimizer-local chars/4 fields use only `estimated_payload_*` names. Exact model-tokenizer counts are labeled exact when a real tokenizer callback is supplied. Host `token_count` and GoalState `tokensUsed` values are observed totals only when a runtime-invoked adapter callable supplies them. Caller strings named `trusted_host_token_event_jsonl` remain `claimed_unverified`. Keep `billing_tokens_available=false` and `billing_counterfactual_available=false`. Do not emit optimizer-local `actual_*` fields.
9. For real log files, prefer the module CLI: `python -m src.skills.token_optimizer --log-file path/to/log.txt --max-lines 40`.
10. A workflow that selected this skill must include internal `token_optimizer_status` and one concise `token_optimizer_status_reason`/`reason_code`. Do not attach no-op telemetry to ordinary tasks that never selected the skill.
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

These are internal harness outputs by default. Do not add a token-optimizer section to an ordinary user response unless the user requested telemetry or a blocked decision affects the work.

- `token_optimizer_status`: `used`, `considered_not_needed`, `passthrough`, or `blocked`.
- `token_optimizer_provider`: `kh`, `rtk`, or `hybrid` when provider policy is relevant. Use `token_optimizer_status=passthrough` for quality-preserving no-compression decisions.
- Compact log or code text that preserves errors, file paths, test names, and exit status context.
- Token-savings estimate or before/after size when used inside a harness result.
- Canonical whole-payload byte, character, and estimated-token counts when status is `used`, with `billing_tokens_available=false` and `billing_counterfactual_available=false`.
- Retrieval budget plan when a command/API/search/DB operation could emit large output.
- Stable raw references/hashes in compact command outputs, with raw recovery in caller-owned results or the scoped external raw store.
- One concise `token_optimizer_status_reason` and `reason_code` for every workflow-level token decision.
- `provider_receipts`, with one runtime-generated, hash-correlated invocation receipt per optimized RTK item, including hybrid runs, before any `provider=rtk` claim.
- Fallback note when truncation or minification cannot safely preserve actionable context.
- Passthrough note when content is contract-sensitive and should not be compressed.
- Preserved development evidence summary when optimizing a lifecycle run: `task_status`, `review_status`, `commit_sha`, `next_task`, exit code, sandbox retry, file references, and reviewer severity.

## Common mistakes

- Do not remove the only line that identifies the failure.
- Do not minify code that must preserve comments, formatting, or license headers.
- Do not use token optimization as a substitute for reading the relevant source.
- Do not summarize command output in a way that hides a non-zero exit code.
- Do not optimize SQL, stored procedures, contract text, license headers, security comments, or exact source-of-truth prose unless the user explicitly accepts loss.
- Do not serialize both raw and compact task views, and do not append no-op optimizer metadata to every task.
- Do not report RTK from `rtk_available=true` or caller-supplied receipt dictionaries; require a runtime-invoked adapter callable and internal receipt.
- Do not load this skill on every request merely to say it was considered, not needed, or passthrough.

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
