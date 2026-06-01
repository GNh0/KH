---
name: branch-finishing-harness
description: Use when kh-uaf:always-on-front-door has already run and selected this skill; use it when a UAF workflow has implementation changes and must decide whether to keep local, commit, push, open a PR, merge, or clean up.
---

# Branch Finishing Harness

## KH Entry Contract

- Start every non-trivial turn through `always-on-front-door` unless this skill is that bootstrap step or the current turn was classified as light/direct.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, or a required follow-up gate selects it.
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

1. Inspect current branch, worktree path, upstream, changed files, untracked files, and unrelated user changes.
2. Confirm the diff matches the requested scope and no generated/test-only clutter remains.
3. Require fresh verification evidence through `verification-before-completion-harness`.
4. Confirm review gate status and unresolved finding policy.
5. Choose integration state: local only, committed, pushed, PR-ready, merged, blocked, or cleanup-only.
6. Commit only the intended files with a precise message; do not stage unrelated changes.
7. Push or prepare PR only after commit and verification evidence are recorded.
8. Record worktree cleanup, branch cleanup, or keep-alive rationale.
9. Update progress state, GoalState, and final report with `commit_sha`, `push_status`, `workspace_strategy`, and `next_task`.

## Required outputs

- `branch_finish_status`: `local_only`, `committed`, `pushed`, `pr_ready`, `merged`, `blocked`, or `cleanup_only`.
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

## UAF implementation targets

- `src.orchestration.development_progress.DevelopmentRunProgress`
- `src.orchestration.progress_compound_bridge.write_progress_compound_artifacts`
- `src.orchestration.session_postmortem.analyze_codex_session_jsonl`
- `skills/branch_finishing_harness/SKILL.md`
