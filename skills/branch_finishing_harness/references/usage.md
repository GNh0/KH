# branch-finishing-harness Usage Reference

## When to use

Use when a UAF workflow has implementation changes and must decide whether to keep local, commit, push, open a PR, merge, or clean up.

This harness applies at the end of a feature branch, worktree task, review-fix loop, release candidate, or cleanup request. It should also be used when the user asks whether the work is ready, whether it was pushed, or whether worktrees/subagents can be cleaned up.

## Inputs to collect

- Branch name, upstream, base SHA, current HEAD, worktree path, and workspace strategy.
- `git status --short`, changed file list, staged file list, and untracked file list.
- User-owned unrelated changes and files that must not be touched.
- Verification-before-completion evidence and review/QA gate state.
- Commit message intent, push target, PR target, merge policy, and cleanup policy.
- GoalState evidence and progress state fields.
- Execution level: `hybrid-harness`.
- Implementation targets:
  - `src.orchestration.development_progress.DevelopmentRunProgress`
  - `src.orchestration.progress_compound_bridge.write_progress_compound_artifacts`
  - `src.orchestration.session_postmortem.analyze_codex_session_jsonl`
  - `skills/branch_finishing_harness/SKILL.md`

## Execution pattern

1. Inspect branch/worktree and establish whether it is safe to finish.
2. Check diff scope against the requested task. If unrelated changes are present, keep them out of the finish operation or block for user direction.
3. Require fresh verification evidence or a documented blocked/risk state.
4. Choose exactly one integration state for this turn: local only, committed, pushed, PR-ready, merged, blocked, or cleanup-only.
5. Stage only intended files, commit with a precise message, and record the SHA.
6. Push or prepare PR only if requested by user policy or project workflow.
7. Record cleanup decisions for worktrees, temporary branches, generated logs, and stale subagents.
8. Update GoalState/progress and final report fields.

## Evidence to produce

- Diff scope and dirty-tree status before finishing.
- Verification and review status used for the decision.
- Commit SHA, push ref, PR URL, or blocked reason.
- Cleanup status for worktree, branch, subagents, and temporary artifacts.
- Final integration state and next task.

## Failure handling

- If Git metadata cannot be written, check safe.directory and permissions before assuming repo corruption.
- If push fails because of network/auth, report local commit SHA and blocked push reason.
- If verification failed, do not claim ready; report local-only or blocked state.
- If unrelated user changes are present, keep them unstaged and mention them as excluded.

## Quality bar

A valid branch finish makes it unambiguous what was changed, what was verified, what was committed or pushed, what remains local, and what cleanup has or has not happened.

## Runtime binding

- Execution level: hybrid-harness
- Implementation targets:
  - `src.orchestration.development_progress.DevelopmentRunProgress`
  - `src.orchestration.progress_compound_bridge.write_progress_compound_artifacts`
  - `src.orchestration.session_postmortem.analyze_codex_session_jsonl`
- Application path: run the procedural branch decision after verification evidence and before commit, push, PR, merge, cleanup, or local-only handoff.
- Completion rule: do not report branch finishing as applied until the branch action, verification state, dirty-worktree treatment, and follow-up/blocked rationale are recorded.
