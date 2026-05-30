# branch-finishing-harness Minimal Workflow Example

## Scenario

A KH feature worktree has finished implementation and review. The user asked to push the result. There are two intended changed files and one unrelated local note file.

## Expected steps

1. Inspect branch, upstream, status, and changed files.
2. Exclude the unrelated note file from staging.
3. Confirm fresh verification and review status.
4. Stage the intended files only.
5. Commit with a scoped message and record the commit SHA.
6. Push the branch and record the remote ref.
7. Record whether the worktree should remain for follow-up or be cleaned later.

## Expected evidence

- `actual_runtime_path`: `skills/branch_finishing_harness/SKILL.md`
- `execution_level`: `hybrid-harness`
- Implementation targets:
  - `src.orchestration.development_progress.DevelopmentRunProgress`
  - `src.orchestration.progress_compound_bridge.write_progress_compound_artifacts`
  - `src.orchestration.session_postmortem.analyze_codex_session_jsonl`
- `branch_finish_status`: `pushed`
- `commit_sha`: present
- `push_status`: `pushed`
- `unrelated_changes`: excluded
- `workspace_strategy`: present

## Failure cases

- All files are staged with `git add .` even though unrelated user files exist.
- The branch is pushed after failed verification without a risk note.
- The final answer says pushed when only a local commit exists.
- A worktree is removed before the branch state is verified.

## Done criteria

- Integration state is explicit and supported by Git evidence.
- Unrelated changes are preserved.
- Verification and review status are attached to the branch decision.
- Catalog validation and the skill smoke check pass.
