# plan-execution-harness Minimal Workflow Example

## Scenario

A SaaS MVP plan has six tasks. Task 2 is complete, Task 3 should add validation helpers, and Task 4 depends on Task 3.

## Expected steps

1. Load the plan and existing progress state.
2. Set Task 3 to in_progress.
3. Decide workspace strategy and token optimizer status.
4. Write the failing validation test first and record RED.
5. Implement the helper and record GREEN.
6. Run spec review, code-quality review, fix/re-review if needed.
7. Commit the task if the branch policy calls for task commits.
8. Set `next_task` to Task 4 and update GoalState evidence.

## Expected evidence

- `actual_runtime_path`: `skills/plan_execution_harness/SKILL.md`
- `execution_level`: `hybrid-harness`
- `progress_path`: `.kh/development/<run-id>/state/progress.json`
- `task_status`: Task 3 complete
- `review_status`: passed
- `commit_sha`: present when committed
- `next_task`: Task 4

## Failure cases

- The agent runs several tasks but leaves no progress state.
- Code quality review finds a blocking issue and the task is still marked complete.
- A subagent is dispatched without owned files or forbidden files.
- A scaffold milestone is reported as the full MVP.

## Done criteria

- Every task transition is visible in progress state.
- Review and verification evidence are attached to the task.
- Resume can continue from `next_task`.
- Catalog validation and the skill smoke check pass.
