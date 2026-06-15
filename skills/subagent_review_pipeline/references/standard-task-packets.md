# Standard Task Packets

Use these packet shapes when KH coordinates host subagents for development work. Keep each packet self-contained, bounded, and small enough for `token-optimizer` to preserve review evidence.

## Implementer Packet

Required fields:

- `role`: `implementer`
- `objective`: one bounded task outcome
- `workspace_assignment`: `preassigned` for ordinary delegated implementation, or `worker_decides` when the purpose is to test KH/front-door/worktree autonomy
- `target_repo`: exact repository path the worker must evaluate when `workspace_assignment=worker_decides`
- `workspace`: exact worktree, host workspace, or branch path only when `workspace_assignment=preassigned`; use `not_preassigned` when the worker must decide
- `workspace_strategy`: `host-worktree`, `project-local-worktree`, `isolated-branch`, `current-checkout`, or `worker_must_select`; `current-checkout` requires the in-place exception reason
- `worker_workspace_decision_required`: true when `workspace_assignment=worker_decides`; the worker must run/apply the KH worktree isolation policy, choose the workspace strategy, and report evidence before editing
- `base_sha`: starting SHA when available
- `base_branch`: starting branch when available
- `plan_file`: source plan or task document
- `task_section`: heading or line reference for the assigned task
- `owned_files`: files the implementer may edit
- `forbidden_files`: files or paths the implementer must not edit
- `kh_front_door_evidence`: command, runtime-applied skills, execution gate, or explicit blocked/direct rationale
- `selected_harness_evidence`: for every selected immediate harness, one of `applied`, `skipped_with_rationale`, `considered_not_needed`, or `blocked`
- `token_optimizer_status`: `used`, `considered_not_needed`, `passthrough`, or `blocked` for task packet, command output, and transcript handling
- `token_optimizer_provider`: `kh`, `rtk`, `hybrid`, or `passthrough` when relevant
- `nested_subagents_available`: true, false, or not-applicable with host/runtime rationale
- `final_user_language_policy`: final user-facing output should match the user's requested or apparent language; internal subagent reports may stay in English unless the user requests otherwise
- `tdd_sequence`: RED command, GREEN command, broader verification command, or no-test rationale
- `checks`: exact commands to run
- `expected_artifacts`: files, docs, state records, or evidence keys expected after the task
- `commit_message`: required commit message when the controller wants per-task commits
- `report_fields`: `status`, `changed_files`, `commands_run`, `evidence`, `commit_sha`, `workspace_assignment`, `workspace_strategy`, `workspace_decision_source`, `worktree_isolation_evidence`, `kh_front_door_evidence`, `selected_harness_evidence`, `token_optimizer_status`, `token_optimizer_provider`, `nested_subagents_available`, `final_user_language_policy`, `harness_usage`, `concerns`

Required loop:

```text
RED -> GREEN -> self-check -> report -> controller spec review
```

## Spec Reviewer Packet

Required fields:

- `role`: `spec-reviewer`
- `objective`: verify the implementer output against the assigned task and user constraints
- `workspace`: exact worktree, host workspace, or branch path from the implementer report or controller assignment
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
- Do not preassign worktree paths when the packet purpose is to test KH harness autonomy. Pass `workspace_assignment=worker_decides`, `workspace=not_preassigned`, the exact `target_repo`, base branch/SHA, allowed strategies, dirty-state constraints, and a required report field for the worker-side worktree isolation decision.
- Do not accept an implementer report as complete when it omits `kh_front_door_evidence`, `workspace_strategy`, `token_optimizer_status`, or selected-harness evidence. Return it for a usage audit before integrating code changes.
- Do not accept an autonomy-test implementer report as complete when `workspace_decision_source` or `worktree_isolation_evidence` is missing; the worker must prove whether it selected `host-worktree`, `project-local-worktree`, `isolated-branch`, or `current-checkout`.
- Treat `current-checkout` as an explicit exception, not the default. The report must name the dirty-state handling, non-overlap proof, and why a worktree or isolated branch was not used.
- Treat `token_optimizer_status=considered_not_needed` as valid only when the report states the packet, command output, and transcript stayed small enough and no compression was applied.
- Update progress after each implementer report, review result, fix, re-review, and commit.
- Preserve `workspace_strategy`, `task_status`, `review_status`, `commit_sha`, `next_task`, and `token_optimizer_status` in the final response.
- Final user-facing controller output should match the user's requested or apparent language. Internal task packets, harness evidence, and subagent reports may stay in English unless the user requests otherwise.
- Decide `token_optimizer_status` for task packets, command output, and subagent transcripts. Use `token-optimizer` only when content is large or token-expensive enough and do not compress away reviewer severity, failing command output, or commit evidence.
