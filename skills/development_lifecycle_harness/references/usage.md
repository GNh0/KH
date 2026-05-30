# Development Lifecycle Harness Usage Reference

This reference expands the portable operating contract for `development-lifecycle-harness`. Read it when the task is real work, when deciding whether this skill applies, or when a review needs evidence beyond the concise `SKILL.md`.

## When to use

Use when running UAF development work through design, isolated workspace setup, planning, TDD implementation, review, verification, and branch finishing.

Context summary: This is a personal UAF development workflow. It packages the useful planning, TDD, review, and branch-finishing methodology without requiring any external workflow plugin at runtime.

Do not use this skill only because it is available. Use it when the current task needs the behavior named by the trigger, and state whether the skill was actually executed, applied procedurally, or only considered.

## Inputs to collect

- User objective, success criteria, and any explicit completion conditions.
- Target workspace, write boundaries, and whether user-facing deliverables are expected.
- Workspace strategy: `current-checkout`, `project-local-worktree`, `host-worktree`, or `isolated-branch`.
- Default to isolated workspace for implementation in Git-backed projects. Use `current-checkout` only for documentation-only edits, a single-file small patch, or explicit user instruction.
- Token context budget inputs: `estimated_context_tokens`, expected tool calls, broad file reads, large outputs, subagent transcripts, and whether `token-optimizer` should be `used`, `considered_not_needed`, `passthrough`, or `blocked`.
- GoalState inputs: objective, success criteria, required evidence, current evidence, active task, missing evidence, and next recommended action.
- Development progress inputs for task-plan work: `run_id`, task IDs/titles, active task, RED/GREEN status, spec-review status, code-quality-review status, fix/re-review status, commit SHA, next task, and final report fields.
- Large-work bundle inputs: `large_work_orchestration_bundle.skill_statuses` for `request-complexity-router`, `host-agent-orchestration`, `goal-state-harness`, `development-lifecycle-harness`, `token-optimizer`, `memory-state-harness`, `parallel-orchestration-harness`, `subagent-review-pipeline`, `role-execution-audit-harness`, `compound-engineering-harness`, and `workflow-skill-distiller`.
- Large-work bundle status values: `applied`, `considered_not_needed`, `skipped_with_rationale`, or `blocked`; every status needs a short evidence note or rationale.
- Skill transition inputs: `skill_transition_handoff`, required next skills, Compound `next_skills`, memory candidates, subagent/reviewer evidence, and whether each required follow-up skill was applied, blocked, or left for next work.
- Required role, gate, state, artifact, or command evidence for this harness.
- Existing artifacts or state files that must be preserved rather than overwritten.
- Execution level: `procedure-policy`.
- Implementation targets:
  - `src.orchestration.agent_loop`
  - `src.core.snapshot_manager`
  - `src.harness.evaluator`
  - `src.tasks.workflows`
  - `src.skills.uaf_skill_catalog`
  - `src.orchestration.development_progress`

## Execution pattern

1. Read `SKILL.md` first and confirm the trigger applies to the current task.
2. Read this reference before performing non-trivial work with `development-lifecycle-harness`.
3. Apply the written workflow as a host-agent policy, then record the decision, boundary, or gate evidence that proves the policy was actually used.
4. For implementation work, choose `host-worktree`, `project-local-worktree`, or `isolated-branch` before editing unless the task qualifies for `current-checkout`.
5. For large project, SaaS, app, multi-file implementation, role-DAG, or long-running work, create `large_work_orchestration_bundle` evidence before implementation.
6. Fill `skill_statuses` for the bundle members. Mark optional members `considered_not_needed` only with a rationale; mark unavailable host capability `blocked` instead of silently omitting it.
7. For large or long-running work, or when estimated context will cross the threshold, apply `token-optimizer` as a context budget gate before broad reads, long commands, or subagent dispatch. Use `command-output-harness` for long test/build/lint logs.
8. Create or refresh `GoalState` through `goal-state-harness` before implementation, then update it after checks, review, QA, and release decisions.
9. For task-plan implementation, create `.kh/development/<run-id>/state/progress.json` and update it after each task loop stage: RED, GREEN, spec review, code-quality review, fix, re-review, commit, and next task.
10. For parallel or risky edits, record whether work used `.worktrees/`, an isolated branch, or an equivalent host workspace.
11. Preserve intermediate decisions in structured evidence rather than relying on terminal logs alone.
12. After review and before final completion on large work, validate `skill_transition_handoff` with `src.orchestration.skill_transitions` so memory, subagent, parallel, Compound, distiller, scenario, and context follow-ups cannot be silently skipped.
13. Run `python scripts/smoke_check.py` when validating this packaged skill in the repository.
14. Report the difference between capability available in the repository and behavior actually executed in the current run.

## Evidence to produce

- Skill name and execution level used for the run.
- Concrete input summary and target workspace or artifact paths.
- `large_work_orchestration_bundle` with `skill_statuses`, `parallel_strategy_decision`, `memory_candidates`, `compound_handoff`, and no-learning or skip rationales.
- `workspace_strategy` and its evidence: current checkout rationale, worktree path, host workspace id, or isolated branch name.
- `token_optimizer_status` and its evidence: savings statistics, `considered_not_needed` rationale, `passthrough` quality reason, or blocked reason.
- GoalState and goal ledger evidence: objective, status, success criteria, evidence required, evidence collected, missing evidence, and next recommended action.
- Development progress evidence: `.kh/development/<run-id>/state/progress.json`, active task, task statuses, RED/GREEN/review/fix/re-review/commit loop state, and stable final report fields.
- Skill transition evidence: `skill_transition_handoff`, `required_next_skills`, transition issues, or `skill_transition_policy_passed`.
- Implementation targets touched, imported, called, resolved by smoke check, or explicitly not needed.
- Output files, gate results, state records, or role results created by the skill.
- Verification command or review evidence, including failures and blocked states.
- Stable final report fields: `task_status`, `review_status`, `commit_sha`, `next_task`, `workspace_strategy`, `token_optimizer_status`, and `skill_statuses`.

## Failure handling

- If a required implementation target is missing, stop using this skill as executed evidence and report the missing target.
- If the workflow can only be applied procedurally, say so explicitly and record the policy or decision evidence.
- If parallel, role, gate, or state behavior is claimed, prove the actual runtime path instead of citing only repository support.
- If generated artifacts are incomplete, withhold completion until the missing artifact or exception is recorded.

## Quality bar

A valid use of `development-lifecycle-harness` must leave enough evidence for another agent to answer: why this skill applied, what ran or was applied, what changed, and what still needs attention.
