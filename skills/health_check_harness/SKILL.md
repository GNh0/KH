---
name: health-check-harness
description: Use when a UAF workflow needs a code quality dashboard, test health summary, static checks, or release readiness score.
---

# Health Check Harness

This is a UAF-native health harness for quality dashboard workflow patterns. It turns verification commands into a compact quality dashboard.

## Pattern basis

- Health workflow: quality dashboard, type checker, linter, tests, dead code checks, weighted scores, and trend-friendly summaries.
- UAF: validator checks, sandbox/evaluator results, workflow gate results, and release-manager metadata.

## Workflow

1. Detect project-appropriate checks from repository files and explicit workflow metadata.
2. Run only deterministic checks unless the user or adapter grants broader access.
3. Preserve command exit codes and summarize stdout/stderr without hiding failures.
4. Score health dimensions such as tests, syntax, skill catalog validity, sandbox policy, and documentation freshness.
5. Return both machine-readable JSON and a concise human summary.

## Required outputs

- `score`: numeric readiness score from 0 to 10.
- `checks`: list of checks, commands, status, and evidence.
- `failures`: actionable failed checks.
- `release_ready`: boolean derived from required checks.

## Common mistakes

- Do not score a workflow as release-ready when required checks were skipped or unavailable.
- Do not collapse failing command output into a generic failure without the command and exit code.
- Do not treat optional checks as blockers unless workflow metadata marks them required.
- Do not hide documentation/catalog failures because runtime tests passed.

## UAF implementation targets

- `src.skills.uaf_skill_validator`
- `src.skills.uaf_skill_catalog`
- `src.harness.evaluator`
- `src.contracts.HarnessResult`
- `tests`
