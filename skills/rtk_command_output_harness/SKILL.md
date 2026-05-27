---
name: rtk-command-output-harness
description: Use when compressing command output for agents, preserving exit codes, filtering noisy logs, or tracking token savings in UAF workflows.
---

# RTK Command Output Harness

This is a UAF-native command-output harness derived from RTK. It should provide the same class of behavior without requiring the `rtk` binary at runtime.

## Reference basis

- RTK: command proxying, smart filtering, grouping, truncation, deduplication, raw passthrough, token-savings tracking, and exit-code preservation.

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

## UAF implementation targets

- `src.skills.token_optimizer`
- `src.skills.uaf_skill_catalog`
- `src.tasks.workflows`
- `src.core.runner`
- `src.contracts.HarnessResult`
