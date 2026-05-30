---
name: verification-before-completion-harness
description: Use when a UAF workflow is about to claim completion, commit, push, ship, or hand off work and must prove fresh verification evidence first.
---

# Verification Before Completion Harness

This is the KH-native completion guard. It replaces broad "trust me, it passed" claims with fresh verification evidence tied to the active goal, changed files, review status, and final integration action.

It is inspired by external verification-before-completion workflows, but it is KH-native: it uses UAF evidence, GoalState, progress state, QA gates, and session postmortem guards instead of external plugin runtime rules.

## Support files

- Read `references/usage.md` before applying this skill to real work; it expands inputs, verification strategy, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact acceptance scenario for completion claims.
- Run `python scripts/smoke_check.py` from this skill folder to verify support files and implementation targets.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the packaged KH skill demo path.

## Workflow

1. Identify the exact completion claim: local done, committed, pushed, PR-ready, released, or blocked.
2. Read the active `GoalState`, development progress state, changed files, and review/QA status.
3. Select the smallest fresh verification command that proves the changed behavior and the broader command that protects integration.
4. Run or require the verification immediately before the completion claim; stale output from an earlier step is not enough.
5. Preserve command, exit code, pass/fail, sandbox retry reason, and important failure text through `command-output-harness` or `token-optimizer` when output is large.
6. Block completion when verification is missing, failed, stale, narrower than the claim, or replaced by a weaker check without disclosure.
7. Update GoalState evidence, progress state, and final report fields with `verification_status`, `review_status`, `commit_sha`, `workspace_strategy`, and `next_task`.
8. If final verification cannot run, report `blocked` or `done_with_residual_risk` with the exact missing tool, permission, environment, or command.

## Required outputs

- `verification_status`: `passed`, `failed`, `blocked`, or `not_applicable_with_rationale`.
- Fresh verification command list with command, exit code, timestamp or current-run marker, and pass/fail result.
- Evidence mapping from user requirement or changed behavior to verification output.
- `completion_claim`: local only, committed, pushed, PR-ready, released, blocked, or partial.
- `residual_risk` when any promised verification path failed, was skipped, or was replaced by a narrower check.
- Updated final fields: `task_status`, `review_status`, `commit_sha`, `next_task`, `workspace_strategy`, and `token_optimizer_status` when relevant.

## Common mistakes

- Do not claim completion from stale test output.
- Do not treat a narrower HTTP/status check as full Browser, QA, build, or integration verification.
- Do not hide failed verification in a successful final summary.
- Do not commit or push before the requested completion evidence is either passed or explicitly blocked.
- Do not compress command output so aggressively that the failing test, exit code, or file path disappears.

## UAF implementation targets

- `src.orchestration.session_postmortem.analyze_codex_session_jsonl`
- `src.orchestration.gate_evaluators.evaluate_release_gate`
- `src.orchestration.development_progress.derive_review_status`
- `skills/verification_before_completion_harness/SKILL.md`
