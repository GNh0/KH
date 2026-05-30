# Standard Task Packets

Use these packet shapes when KH coordinates host subagents for development work. Keep each packet self-contained, bounded, and small enough for `token-optimizer` to preserve review evidence.

## Implementer Packet

Required fields:

- `role`: `implementer`
- `objective`: one bounded task outcome
- `workspace`: exact worktree, host workspace, or branch path
- `base_sha`: starting SHA when available
- `plan_file`: source plan or task document
- `task_section`: heading or line reference for the assigned task
- `owned_files`: files the implementer may edit
- `forbidden_files`: files or paths the implementer must not edit
- `tdd_sequence`: RED command, GREEN command, broader verification command, or no-test rationale
- `checks`: exact commands to run
- `expected_artifacts`: files, docs, state records, or evidence keys expected after the task
- `commit_message`: required commit message when the controller wants per-task commits
- `report_fields`: `status`, `changed_files`, `commands_run`, `evidence`, `commit_sha`, `concerns`

Required loop:

```text
RED -> GREEN -> self-check -> report -> controller spec review
```

## Spec Reviewer Packet

Required fields:

- `role`: `spec-reviewer`
- `objective`: verify the implementer output against the assigned task and user constraints
- `workspace`: exact worktree, host workspace, or branch path
- `base_sha`
- `head_sha`
- `plan_file`
- `task_section`
- `scope`: spec compliance only
- `do_not_edit`: true
- `checks`: read-only commands or exact verification commands
- `report_fields`: `status`, `missing_requirements`, `file_references`, `review_status`, `ready_for_quality_review`

Required loop:

```text
inspect diff -> compare with task packet -> run/read checks -> pass or return to implementer
```

## Code Quality Reviewer Packet

Required fields:

- `role`: `code-quality-reviewer`
- `objective`: review maintainability, integration risk, test quality, and security after spec compliance passes
- `workspace`: exact worktree, host workspace, or branch path
- `base_sha`
- `head_sha`
- `prior_spec_review`: pass evidence or blocking note
- `scope`: quality, risk, tests, maintainability, security
- `do_not_edit`: true
- `checks`: read-only commands or exact verification commands
- `report_fields`: `status`, `findings`, `severity`, `file_references`, `required_fixes`, `ready_to_merge`

Required loop:

```text
inspect diff -> inspect relevant files -> run/read checks -> findings -> fix request or ready-to-merge
```

## Controller Requirements

- Write `.kh/development/<run-id>/state/progress.json` before dispatching the first task when the run has a task plan.
- Record `subagent_strategy`: `dispatch`, `single-controller`, `review-only`, or `blocked` before creating implementer packets.
- Dispatch subagents only when the task split is independent enough, review benefit is real, context packets can stay bounded, and isolation is available.
- Prefer `single-controller` when the work is sequential, tiny, shared-state heavy, or the host cannot provide safe isolation.
- Update progress after each implementer report, review result, fix, re-review, and commit.
- Preserve `workspace_strategy`, `task_status`, `review_status`, `commit_sha`, `next_task`, and `token_optimizer_status` in the final response.
- Decide `token_optimizer_status` for task packets, command output, and subagent transcripts. Use `token-optimizer` only when content is large or token-expensive enough and do not compress away reviewer severity, failing command output, or commit evidence.
