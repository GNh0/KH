---
name: command-output-harness
description: Use when compressing command output for agents, preserving exit codes, filtering noisy logs, or tracking token savings in UAF workflows.
---

# Command Output Harness

This is a personal UAF command output harness. It provides compact command output behavior without requiring any external command proxy at runtime.

## Reference basis

- Command output patterns: command proxying, smart filtering, grouping, truncation, deduplication, raw passthrough, token-savings tracking, and exit-code preservation.

## Command lifecycle

1. Parse the requested command and classify the command family.
2. Route to a known filter when one exists; otherwise mark it for passthrough.
3. Execute the underlying command without changing its exit code semantics.
4. Filter stdout and stderr according to the command family.
5. Print compact output that keeps actionable failures and summaries.
6. Track raw size, filtered size, command family, elapsed time, and savings estimate.

## Filter rules

- Keep error messages, failing tests, changed files, exit status, and actionable paths.
- Drop repeated progress lines, banners, empty lines, duplicated stack frames, and known boilerplate.
- Prefer grouping by file, package, test name, or error type.
- If filtering fails or produces an unsafe empty result, return raw output with metadata explaining the fallback.

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

- `src.skills.token_optimizer`
- `src.skills.uaf_skill_catalog`
- `src.tasks.workflows`
- `src.core.runner`
- `src.contracts.HarnessResult`
