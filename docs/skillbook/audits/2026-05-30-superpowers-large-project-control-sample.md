# Superpowers Large Project Control Sample

Date: 2026-05-30
Control session: `019e7441-eecf-7e23-b9ee-9aefa1c8fdf6`
Target project: `C:\Users\User\Documents\Codex\SaaS Project`
Purpose: learn from a completed Superpowers-run PipePilot SaaS implementation and convert transferable workflow lessons into KH-native contracts.

This is not a KH compliance audit. The session is an external control sample showing what felt effective during a real project-sized implementation.

## Observed Run Shape

- Controller session files inspected: 1.
- Related project session files inspected: 71 total.
- Classified child runs: 19 implementer sessions, 20 spec-reviewer sessions, 21 code-quality-reviewer sessions, and 10 other/approval-related sessions.
- Controller evidence volume: 258 assistant messages, 61 user messages, 1,012 tool calls, 802 shell command calls.
- Implementation branch observed in the target worktree: `feat/pipepilot-mvp`.
- Final target branch HEAD observed: `8ea0594 fix: address final MVP review gaps`.
- Task plan coverage observed: tasks 1 through 12 were referenced, with task-by-task implementation/review/commit progression.

## Token Optimizer Evidence

KH `token-optimizer` was used for this audit as the context budget gate.

- Raw JSONL inspected: 28,140,522 bytes, estimated 6,979,848 tokens.
- Normalized lifecycle transcript: estimated 446,926 tokens.
- Optimized lifecycle transcript: estimated 339,132 tokens.
- Normalized transcript savings: 107,794 estimated tokens, 24.12%.
- Raw JSONL avoidance savings: 6,640,716 estimated tokens, 95.14%.
- Preserved after optimization: task status, review status, commit evidence, next task, RED/GREEN evidence, workspace/worktree evidence, verification commands, and sandbox retry evidence.

The modest normalized savings are expected. This transcript is dense with lifecycle evidence, and the optimizer correctly kept review and verification facts instead of chasing maximum compression.

## What Superpowers Made Easy

| Pattern | Evidence from control sample | KH takeaway |
| --- | --- | --- |
| Project-local worktree isolation | The work happened in `.worktrees/feat-pipepilot-mvp` on `feat/pipepilot-mvp`. | Keep KH default as `project-local-worktree` or `host-worktree` for serious implementation. |
| Visible task loop | The controller advanced Task 1, Task 2, Task 3, etc. with repeated status updates and commits. | KH needs a machine-readable `.kh/development/<run-id>/state/progress.json` in addition to chat updates. |
| Role packets | Implementer, spec reviewer, and code-quality reviewer prompts carried workspace, branch, plan section, owned files, checks, and reporting requirements. | KH should standardize prompt packet fields in `subagent-review-pipeline`. |
| RED/GREEN discipline | Implementers were asked to write tests first, observe failure, implement, and rerun targeted tests. | KH development progress should record RED and GREEN per task. |
| Review then fix then re-review | Review findings caused targeted fixes, new checks, re-review, and separate fix commits. | KH progress must represent fix and re-review stages, not only done/pending. |
| Evidence before completion | Final claims referenced test/lint/build/Prisma/browser or review evidence. | KH final report fields should remain fixed: `task_status`, `review_status`, `commit_sha`, `next_task`, `workspace_strategy`, and `token_optimizer_status`. |

## What KH Already Covers

- `large_work_orchestration_bundle` makes skill omission visible for large work.
- `token-optimizer` can preserve lifecycle evidence while reducing transcript size.
- `development-lifecycle-harness` already requires worktree strategy, GoalState, TDD/smoke evidence, review, verification, and branch finishing.
- `subagent-review-pipeline` already separates implementer, spec reviewer, and code-quality reviewer responsibilities.
- `compound-engineering-harness` adds the Plan -> Work -> Review -> Compound loop that Superpowers-style flows can skip unless prompted.

## Gaps Closed By This Follow-Up

- Added `src.orchestration.development_progress` to build, validate, read, and write `.kh/development/<run-id>/state/progress.json`.
- Added validation for task loop fields: RED, GREEN, spec review, code-quality review, fix, re-review, commit SHA, and next task.
- Added stable final report helper fields for task-plan runs.
- Added `skills/subagent_review_pipeline/references/standard-task-packets.md` with implementer, spec-reviewer, code-quality-reviewer, and controller packet requirements.
- Updated `development-lifecycle-harness` and `subagent-review-pipeline` to require progress updates during multi-task runs.
- Bumped plugin manifests to 2.9.11 so marketplace/cache upgrades can surface the new behavior.

## Remaining Follow-Ups

- Wire `development_progress` into live workflow dispatch when KH itself is the controller, not only as a utility contract.
- Add a demo run that creates `.kh/development/<run-id>/state/progress.json` while executing a small two-task plan.
- Consider adding a host-side progress renderer so Codex/Antigravity can display KH progress similarly to the observed task panel.
- Add a SIDE scenario that checks whether a large SaaS request selects worktree, progress JSON, token gate, subagent review packets, and Compound handoff together.

## Compound Capture

Reusable learning: real users respond well when large work has visible task progression and independent review loops. KH should keep its richer evidence gates, memory, and Compound loop, but make the common development path feel as direct as the Superpowers control sample.

System update: development progress state and standard task packets were added.

Regression checks: `tests.test_development_progress` and existing Superpowers alignment tests should catch drift.
