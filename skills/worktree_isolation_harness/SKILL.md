---
name: worktree-isolation-harness
description: Use when kh-uaf:always-on-front-door has already run and selected this skill; use it when a Git-backed UAF implementation needs an isolated workspace, host worktree, project-local .worktrees task folder, or explicit in-place exception.
---

# Worktree Isolation Harness

## KH Entry Contract

- Start every non-trivial turn through `always-on-front-door` unless this skill is that bootstrap step or the current turn was classified as light/direct.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, or a required follow-up gate selects it.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

This is the KH-native workspace isolation policy. It decides when to use a host-provided worktree, project-local `.worktrees/<task>`, isolated branch, or current checkout, and records the reason before edits begin.

It makes Superpowers-style worktree safety available inside KH without requiring an external worktree plugin.

## Support files

- Read `references/usage.md` before applying this skill to real Git-backed implementation.
- Use `examples/minimal-workflow.md` as a compact scenario for safe workspace selection.
- Run `python scripts/smoke_check.py` from this skill folder to verify support files and implementation targets.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the packaged KH skill demo path.

## Workflow

1. Detect whether the target project is Git-backed and whether host worktree support is available.
2. Inspect current dirty state and user-owned changes before choosing an edit location.
3. Choose `host-worktree`, `project-local-worktree`, `isolated-branch`, or `current-checkout`.
4. Default to isolation for TDD, multi-file changes, large changes, parallel work, generated code, or any task that may touch user-edited files.
5. Allow `current-checkout` only for docs-only edits, single-file small patches, read-only work, or explicit user in-place instruction.
6. Record `workspace_strategy`, path/branch, base SHA, dirty-state handling, and cleanup policy.
7. For subagents or parallel workers, require independent worktree/branch/workspace evidence or a non-overlap proof.
8. Include workspace strategy in final status and branch finishing evidence.

## Required outputs

- `workspace_strategy`: `host-worktree`, `project-local-worktree`, `isolated-branch`, or `current-checkout`.
- Path, branch name, base SHA, host workspace id, or in-place rationale.
- Dirty-state and unrelated-change handling.
- Isolation trigger rationale or explicit in-place exception.
- Cleanup or keep-alive policy for the created worktree/branch.
- Final report field showing where the work was performed.

## Common mistakes

- Do not edit a dirty user checkout for a large implementation without an explicit in-place reason.
- Do not dispatch parallel writers into the same mutable checkout without non-overlap proof.
- Do not create worktrees without recording cleanup or keep-alive policy.
- Do not confuse Codex host worktree support with raw Git worktree semantics in final reports.
- Do not remove a worktree before branch state and pushed/merged status are verified.

## UAF implementation targets

- `src.orchestration.development_progress.WORKSPACE_STRATEGIES`
- `skills/worktree_isolation_harness/SKILL.md`
- `skills/parallel_orchestration_harness/SKILL.md`
- `skills/development_lifecycle_harness/SKILL.md`
