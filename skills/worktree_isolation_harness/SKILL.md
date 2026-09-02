---
name: worktree-isolation-harness
description: Use when a Git-backed UAF implementation needs an isolated workspace, host worktree, project-local .worktrees task folder, or explicit in-place exception.
---

# Worktree Isolation Harness

## KH Entry Contract

- Select this skill directly when its semantic trigger matches the current request; no separate routing preflight is required.
- An active KH directive does not select this skill by itself; the current request must still match this skill's trigger or require it as a workflow gate.
- Use this skill when its frontmatter trigger directly matches the current request or an already-selected workflow requires it.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

This is the KH-native workspace isolation policy. It decides when to use a host-provided worktree, project-local `.worktrees/<task>`, isolated branch, or current checkout, and records the reason before edits begin.

It makes Superpowers-style worktree safety available inside KH without requiring an external worktree plugin.

## Support files

- Read `references/usage.md` before applying this skill to real Git-backed implementation.
- Use `examples/minimal-workflow.md` as a compact scenario for safe workspace selection.
- Run `python scripts/git_workspace_gate.py --project <target>` before any `git` command. This probe reads filesystem metadata only and never starts `git.exe`.
- Run `python scripts/smoke_check.py` from this skill folder to verify support files and implementation targets.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the packaged KH skill demo path.

## Workflow

1. Run the filesystem-only Git workspace gate against the exact target path.
2. If `git_process_allowed=false`, record `workspace_strategy=current-checkout`, mark Git/worktree actions not applicable, and do not run `git status`, `git branch`, `git worktree`, `git commit`, or `git push`.
3. Only when the gate verifies a `.git` directory or a valid worktree `.git` file, inspect current dirty state and host worktree support.
4. Choose `host-worktree`, `project-local-worktree`, `isolated-branch`, or `current-checkout`.
5. Default to isolation for TDD, multi-file changes, large changes, parallel work, generated code, or any task that may touch user-edited files.
6. Allow `current-checkout` only for non-Git work, docs-only edits, single-file small patches, read-only work, or explicit user in-place instruction.
7. Record `workspace_strategy`, path/branch, base SHA, dirty-state handling, and cleanup policy.
8. For subagents or parallel workers, require independent worktree/branch/workspace evidence or a non-overlap proof.
9. Include workspace strategy in final status and branch finishing evidence.

## Required outputs

- `workspace_strategy`: `host-worktree`, `project-local-worktree`, `isolated-branch`, or `current-checkout`.
- Path, branch name, base SHA, host workspace id, or in-place rationale.
- Dirty-state and unrelated-change handling.
- Isolation trigger rationale or explicit in-place exception.
- Cleanup or keep-alive policy for the created worktree/branch.
- Final report field showing where the work was performed.
- `git_workspace_gate`: status, marker kind/path, `git_process_allowed`, and blocked/not-applicable reason.

## Common mistakes

- Do not edit a dirty user checkout for a large implementation without an explicit in-place reason.
- Do not start `git.exe` merely to discover that a folder is not a repository. Probe `.git` through `git_workspace_gate.py` first.
- Do not retry Git commands in a non-Git folder; record them as not applicable.
- Do not dispatch parallel writers into the same mutable checkout without non-overlap proof.
- Do not create worktrees without recording cleanup or keep-alive policy.
- Do not confuse Codex host worktree support with raw Git worktree semantics in final reports.
- Do not remove a worktree before branch state and pushed/merged status are verified.

## UAF implementation targets

- `src.orchestration.development_progress.WORKSPACE_STRATEGIES`
- `src.orchestration.git_workspace_gate.inspect_git_workspace`
- `src.orchestration.git_workspace_gate.authorize_git_action`
- `src.orchestration.git_workspace_gate.authorize_git_argv`
- `skills/worktree_isolation_harness/SKILL.md`
- `skills/parallel_orchestration_harness/SKILL.md`
- `skills/development_lifecycle_harness/SKILL.md`
