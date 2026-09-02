---
name: branch-finishing-harness
description: Use when a UAF workflow has implementation changes and must decide whether to keep local, commit, push, open a PR, merge, or clean up.
---

# Branch Finishing Harness

## KH Entry Contract

- Select this skill directly when its semantic trigger matches the current request; no separate routing preflight is required.
- An active KH directive does not select this skill by itself; the current request must still match this skill's trigger or require it as a workflow gate.
- Use this skill when its frontmatter trigger directly matches the current request or an already-selected workflow requires it.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

This is the KH-native branch finishing workflow. It turns the end of development into an explicit integration decision with verification, review, diff scope, commit/push evidence, and cleanup state.

It complements `verification-before-completion-harness`: verification proves the work, while branch finishing records what happened to the branch and workspace.

## Support files

- Read `references/usage.md` before applying this skill to real branch or worktree finishing.
- Use `examples/minimal-workflow.md` as a compact scenario for commit, push, and cleanup evidence.
- Run `python scripts/smoke_check.py` from this skill folder to verify support files and implementation targets.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the packaged KH skill demo path.

## Workflow

1. Run the filesystem-only `git_workspace_gate` for the exact target before starting any Git process.
2. If the target is not Git-backed, do not run `git status`, `git commit`, `git push`, or PR preparation; record `branch_finish_status=not_applicable_non_git` and finish with file/test evidence only.
3. If the gate passes, inspect current branch, worktree path, upstream, changed files, untracked files, and unrelated user changes.
4. Confirm the diff matches the requested scope and no generated/test-only clutter remains.
5. Require fresh verification evidence through `verification-before-completion-harness`.
6. Confirm review gate status and unresolved finding policy.
7. Choose integration state: local only, committed, pushed, PR-ready, merged, blocked, cleanup-only, or not-applicable-non-git.
8. Commit only the intended files with a precise message; do not stage unrelated changes.
9. Push or prepare PR only after commit, verification evidence, and explicit user/project authorization are recorded.
10. Record worktree cleanup, branch cleanup, or keep-alive rationale.
11. Update progress state, GoalState, and final report with `commit_sha`, `push_status`, `workspace_strategy`, and `next_task`.

## Required outputs

- `branch_finish_status`: `local_only`, `committed`, `pushed`, `pr_ready`, `merged`, `blocked`, `cleanup_only`, or `not_applicable_non_git`.
- `git_workspace_gate`: exact target, marker evidence, and `git_process_allowed` decision.
- Diff scope summary and unrelated-change handling.
- Verification evidence and review status used for the integration decision.
- Commit SHA, branch name, upstream, push result, and PR URL when applicable.
- Worktree/branch cleanup status or keep-alive rationale.
- Final `next_task` or explicit no-next-work state.

## Common mistakes

- Do not commit unrelated user changes.
- Do not push without fresh verification or an explicit risk note.
- Do not leave a stale worktree or subagent branch without a cleanup decision.
- Do not report PR-ready when review or QA gates are unresolved.
- Do not hide a failed push or dirty tree in a successful final report.
- Do not invoke or retry Git in a folder where the filesystem-only gate found no valid `.git` marker.

## UAF implementation targets

- `src.orchestration.development_progress.DevelopmentRunProgress`
- `src.orchestration.progress_compound_bridge.write_progress_compound_artifacts`
- `src.orchestration.session_postmortem.analyze_codex_session_jsonl`
- `src.orchestration.git_workspace_gate.inspect_git_workspace`
- `src.orchestration.git_workspace_gate.authorize_git_action`
- `skills/branch_finishing_harness/SKILL.md`
