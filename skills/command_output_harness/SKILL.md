---
name: command-output-harness
description: Use when compressing command output for agents, preserving exit codes, filtering noisy logs, or tracking token savings in UAF workflows.
---

# Command Output Harness

This is a personal UAF command output harness. It provides compact command output behavior without requiring any external command proxy at runtime.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.

## Reference basis

- Command output patterns: command proxying, smart filtering, grouping, truncation, deduplication, raw passthrough, token-savings tracking, and exit-code preservation.

## Command lifecycle

1. Parse the requested command and classify the command family.
2. Route to a command-family filter for test, build, git-read, dependency, Python, or generic output.
3. Execute the underlying command without changing its exit code semantics.
4. Call `src.skills.token_optimizer.summarize_command_output` to filter stdout and stderr according to the command family.
5. Print compact output that keeps actionable failures and summaries.
6. Track raw size, filtered size, command family, elapsed time, and savings estimate.

## Filter rules

- Keep error messages, failing tests, changed files, exit status, and actionable paths.
- Drop repeated progress lines, banners, empty lines, duplicated stack frames, and known boilerplate.
- Prefer grouping by file, package, test name, or error type.
- If filtering fails or produces an unsafe empty result, return raw output with metadata explaining the fallback.
- After filtering failing output, verify required facts such as failing test names, file paths, line numbers, error codes, assertion values, traceback, build failure markers, and exit code remain present; append or fallback when they do not.

## External Benchmark Recipe

Use this harness when raw logs are too large to read safely:

1. Capture command, stdout, stderr, exit code, and elapsed time.
2. Call `summarize_command_output` so family-specific filters preserve required facts.
3. Check metadata for raw size, filtered size, command family, token savings, and fallback reason.
4. Report the compact output only if failure facts remain present.
5. Return raw or appended context when preservation checks detect missing facts.

Pressure scenario: if a pytest log has hundreds of passing tests and one failure in the middle, the failed test name, traceback, assertion, file/line, and exit code must survive compression.

## Required outputs

- Compact stdout/stderr summary that keeps failures, exit status, changed paths, and actionable lines.
- Raw size, filtered size, elapsed time, command family, and token savings estimate.
- Fallback reason when output is returned raw.
- Preserved exit code and enough context to reproduce the failing command.

## Common mistakes

- Do not summarize away the only failing assertion, traceback, or compiler error.
- Do not change command success semantics while filtering output.
- Do not return an empty summary for non-empty failing output.
- Do not over-compress file paths, test names, or line numbers needed for follow-up edits.

## UAF implementation targets

- `src.skills.token_optimizer.summarize_command_output`
- `src.skills.token_optimizer.filter_command_output`
- `src.skills.token_optimizer.truncate_logs`
- `src.contracts.HarnessResult`
- `tests.test_command_output_runtime`
