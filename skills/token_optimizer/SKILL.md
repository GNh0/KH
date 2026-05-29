---
name: token-optimizer
description: Use when terminal logs, command output, or Python code are too large for efficient LLM context handling.
---
# Token Optimizer Skill

This skill provides utilities to prevent token exhaustion during complex debugging or code reading loops.

Default behavior is quality-first: the host may route any large or uncertain content through `optimize_context_content`, but the skill only compresses when required facts can be preserved. Contract-sensitive text such as SQL, stored procedures, license headers, security comments, business rules, exact source-of-truth prose, and ordinary text that cannot be classified safely must pass through unchanged.
Large arbitrary prose also passes through by default; this is intentional because a generic summary can silently change meaning. Use command-family log filtering or explicit user-approved summarization when reduction is more important than exact wording.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## Instructions
1. For mixed content, call `src.skills.token_optimizer.optimize_context_content`; it classifies logs, Python code, and contract-sensitive text before deciding whether compression is safe.
2. If you run a command and it produces an extremely long error log (hundreds of lines) that clutters your context, you can run the python script directly to truncate it:
   `python -c "from src.skills.token_optimizer import truncate_logs; print(truncate_logs('''<PASTE_LOG_HERE>'''))"`
3. Alternatively, if you need to pass a large python file to another agent (or summarize it), minify it first by stripping comments and docstrings via AST:
   `python -c "from src.skills.token_optimizer import minify_code; print(minify_code(open('file.py').read()))"`
4. If command output needs a reusable UAF evidence record, call `src.skills.token_optimizer.summarize_command_output` so the exit code, command family, raw size, filtered size, and token savings metadata are preserved in `HarnessResult`.
5. For before/after reporting, call `src.skills.token_optimizer.compare_token_usage` for one item or `aggregate_token_usage_stats` for a workflow-level summary. Report `without_token_optimizer`, `with_token_optimizer`, `estimated_tokens_saved`, and `token_savings_ratio`.
6. For real log files, prefer the module CLI: `python -m src.skills.token_optimizer --log-file path/to/log.txt --max-lines 40`.

## External Benchmark Recipe

Use this skill as a quality-first context gate:

1. Route uncertain large content through `optimize_context_content`.
2. Compress logs through command-family filtering and required-fact preservation.
3. Minify Python only when comments, docstrings, and exact wording are not part of the contract.
4. Pass through SQL, stored procedures, license/security/business comments, contract text, and ordinary prose that cannot be safely classified.
5. Report token savings only when compression was actually applied.

Pressure scenario: if compression would remove the only assertion value or a business rule comment, return passthrough or append the missing fact; do not trade answer quality for token savings.

## Required outputs

- Compact log or code text that preserves errors, file paths, test names, and exit status context.
- Token-savings estimate or before/after size when used inside a harness result.
- Token usage before/after statistics when the skill is used as workflow evidence.
- Fallback note when truncation or minification cannot safely preserve actionable context.
- Passthrough note when content is contract-sensitive and should not be compressed.

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
- `src.skills.token_optimizer.compare_token_usage`
- `src.skills.token_optimizer.aggregate_token_usage_stats`
- `src.skills.token_optimizer.estimate_token_count`
- `src.contracts.HarnessResult`
- `tests.test_command_output_runtime`
