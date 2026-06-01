---
name: health-check-harness
description: Use when kh-uaf:always-on-front-door has already run and selected this skill; use it when a UAF workflow needs a code quality dashboard, test health summary, static checks, or release readiness score.
---

# Health Check Harness

## KH Entry Contract

- Start every non-trivial turn through `always-on-front-door` unless this skill is that bootstrap step or the current turn was classified as light/direct.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, or a required follow-up gate selects it.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

This is a UAF-native health harness for quality dashboard workflow patterns. It turns verification commands into a compact quality dashboard.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## Pattern basis

- Health workflow: quality dashboard, type checker, linter, tests, dead code checks, weighted scores, and trend-friendly summaries.
- UAF: validator checks, skill target audit, sandbox/evaluator results, workflow gate results, and release-manager metadata.

## Workflow

1. Detect project-appropriate checks from repository files and explicit workflow metadata.
2. Run only deterministic checks unless the user or adapter grants broader access.
3. Preserve command exit codes and summarize stdout/stderr without hiding failures.
4. Use `python -m src.skills.uaf_skill_audit --summary` or `--skill <name>` when auditing packaged skill targets without dumping the full JSON report.
5. Score health dimensions such as tests, syntax, skill catalog validity, sandbox policy, and documentation freshness.
6. Return both machine-readable JSON and a concise human summary.

## External Benchmark Recipe

Use this harness as a release dashboard, not a single "tests passed" line:

1. Build a check matrix with command, required/optional status, expected artifact, and failure owner.
2. Run each deterministic command fresh; do not reuse old terminal output.
3. For this repository, include catalog check, target audit, external benchmark review, and unit tests.
4. Convert every failed or skipped required check into a `failures[]` item with command, exit code, and next action.
5. Set `release_ready=false` unless every required check passed or was explicitly waived by policy.

Pressure scenario: if unit tests pass but `uaf_skill_audit --summary` reports a failed target, the dashboard is not release-ready.

## Required outputs

- `score`: numeric readiness score from 0 to 10.
- `checks`: list of checks, commands, status, and evidence.
- `skill_target_audit`: packaged skill/harness target resolution and test-evidence summary when the workflow is auditing this repository.
- `failures`: actionable failed checks.
- `release_ready`: boolean derived from required checks.

## Common mistakes

- Do not score a workflow as release-ready when required checks were skipped or unavailable.
- Do not collapse failing command output into a generic failure without the command and exit code.
- Do not treat optional checks as blockers unless workflow metadata marks them required.
- Do not hide documentation/catalog failures because runtime tests passed.
- Do not claim a packaged skill works when its `UAF implementation targets` cannot be resolved or executable skills have no test evidence.

## UAF implementation targets

- `src.skills.uaf_skill_validator`
- `src.skills.uaf_skill_catalog`
- `src.skills.uaf_skill_audit`
- `src.harness.evaluator`
- `src.contracts.HarnessResult`
- `tests`
