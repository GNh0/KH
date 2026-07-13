---
name: command-output-harness
description: Use when kh-uaf:always-on-front-door has already run and selected this skill; use it when compressing command output for agents, preserving exit codes, filtering noisy logs, or tracking token savings in UAF workflows.
---

# Command Output Harness

## KH Entry Contract

- Start every non-trivial turn through `always-on-front-door` unless this skill is that bootstrap step or the current turn was classified as light/direct.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, or a required follow-up gate selects it.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

This is a personal UAF command output harness. It provides compact command output behavior without requiring any external command proxy at runtime.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## Reference basis

- Command output patterns: command proxying, smart filtering, grouping, truncation, deduplication, raw passthrough, token-savings tracking, and exit-code preservation.

## Command lifecycle

1. Parse the requested command and classify the command family.
2. Before broad or noisy commands, build a retrieval budget plan: count/scope first, sample before full read, select fields/line ranges, require explicit limits, and write large structured output to a file.
3. Route to a command-family filter for test, build, git-read, dependency, Python, or generic output.
4. Execute the underlying command without changing its exit code semantics.
5. Supply required facts explicitly or derive them only from concrete test/build failure markers, then call `src.skills.token_optimizer.summarize_command_output`.
6. Validate every required fact in the compact candidate. If any fact is missing, discard the candidate and return the exact raw channels.
7. Put accepted compact output in the canonical model view with a stable raw reference/hash; keep raw recovery in caller-owned results or a project/chat/run-scoped external store.

## Filter rules

- Keep error messages, failing tests, changed files, exit status, and actionable paths.
- Drop repeated progress lines, banners, empty lines, duplicated stack frames, and known boilerplate.
- Prefer grouping by file, package, test name, or error type.
- If filtering fails, produces an unsafe empty result, does not shrink the canonical payload, or loses a required fact, return raw output unchanged with a fallback code.
- NUL/binary/high-entropy data, generic prose, source text, and command output without verifiable required facts are passthrough unless a specialized adapter supplies a verified contract.

## External Benchmark Recipe

Use this harness when raw logs are too large to read safely:

1. Capture command, stdout, stderr, exit code, and elapsed time.
2. Call `summarize_command_output` so family-specific filters preserve required facts.
3. Check metadata for raw size, filtered size, command family, token savings, and fallback reason.
4. Report the compact output only if failure facts remain present.
5. Return exact raw context when preservation checks detect missing facts; never repair a lossy candidate by appending selected lines and still claim compression.

Pressure scenario: if a pytest log has hundreds of passing tests and one failure in the middle, the failed test name, traceback, assertion, file/line, and exit code must survive compression.

## Required outputs

- Compact stdout/stderr summary that keeps failures, exit status, changed paths, and actionable lines.
- Raw size, filtered size, elapsed time, command family, and token savings estimate.
- Retrieval budget plan for broad commands that could emit large stdout.
- Fallback reason when output is returned raw.
- Preserved exit code and enough context to reproduce the failing command.
- Estimated chars/4 payload counts under `estimated_payload_*`, with `billing_tokens_available=false` and `billing_counterfactual_available=false`; command output and JSON lines cannot supply host-actual telemetry.
- `provider_receipts` for every accepted RTK item, emitted only after a runtime-invoked adapter callable and retained when the overall provider is hybrid. Caller receipt dictionaries are `claimed_unverified`.

## Common mistakes

- Do not summarize away the only failing assertion, traceback, or compiler error.
- Do not change command success semantics while filtering output.
- Do not return an empty summary for non-empty failing output.
- Do not run broad source, DB, or API output into stdout when selectors, limits, or output-file handling are missing.
- Do not over-compress file paths, test names, or line numbers needed for follow-up edits.

## UAF implementation targets

- `src.skills.token_optimizer.summarize_command_output`
- `src.skills.token_optimizer.filter_command_output`
- `src.skills.token_optimizer.truncate_logs`
- `src.skills.token_optimizer.build_retrieval_budget_plan`
- `src.skills.token_optimizer.validate_retrieval_budget_plan`
- `src.contracts.HarnessResult`
- `tests.test_command_output_runtime`
