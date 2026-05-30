# plan-execution-harness Usage Reference

## When to use

Use when a written UAF task plan must be executed task by task with progress state, RED/GREEN checks, reviews, commits, and next-task handoff.

This harness is appropriate after brainstorming/spec/architecture produced an approved plan, or when a user hands over a task list and wants the agent to work through it. It should remain lightweight for tiny one-step edits; use a short in-place progress note rather than a full task state when that is enough.

## Inputs to collect

- Written plan path or task list.
- Objective, success criteria, required evidence, and active GoalState.
- Task IDs, dependencies, owned files, forbidden files, verification commands, and expected artifacts.
- Workspace strategy, branch policy, subagent strategy, and token optimizer decision.
- Review requirements, commit cadence, and final integration expectation.

## Execution pattern

1. Normalize the plan into explicit tasks with acceptance criteria.
2. Create or refresh `.kh/development/<run-id>/state/progress.json`.
3. Decide workspace isolation before edits.
4. Execute one task at a time unless independent write sets justify parallel dispatch.
5. For behavior changes, perform RED, implement, then GREEN.
6. Run spec review first, code-quality review second, then fix and re-review if needed.
7. Commit task-sized slices when the project workflow asks for commits.
8. Update progress state after each transition so a later session can resume without full chat context.
9. Use the progress panel for long runs and route completed review state to Compound.

## Evidence to produce

- Progress state file path and current task snapshot.
- Per-task RED/GREEN, review, fix, re-review, verification, and commit evidence.
- Subagent packets and reviewer output when used.
- Token optimizer decision for long commands, large task packets, or transcripts.
- Next task and missing evidence.
- Compound handoff, memory candidates, skill candidates, scenario candidates, or no-learning rationale.

## Failure handling

- If a task is blocked, update progress state with blocker category and next action.
- If review fails, return to fix/re-review instead of advancing.
- If subagent limits or host capability block dispatch, switch to single-controller and record rationale.
- If plan scope is too broad, pause execution and split the plan.

## Quality bar

A valid plan execution run should make progress visible, resumable, reviewable, and bounded. Another agent should be able to open progress state and know exactly which task is active, what passed, what failed, what was committed, and what comes next.
