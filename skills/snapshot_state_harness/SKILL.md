---
name: snapshot-state-harness
description: Use when UAF workflows need rollback points, compressed file snapshots, state restore, or safe checkpoint metadata before generated code changes.
---

# Snapshot State Harness

This is a UAF-native rollback harness. It packages snapshot behavior inside this repository and does not require external host or skill installations at runtime.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.

## Workflow

1. Create a checkpoint before an agent writes generated code or modifies a risky file.
2. Prefer one work-level checkpoint with `SnapshotManager.commit_many(file_names, message)` before a batch of related edits.
3. Use `SnapshotManager.commit(file_name, code, message)` only for a truly single-file checkpoint.
4. Keep snapshot metadata in the project/chat-scoped UAF runtime store, normally `%LOCALAPPDATA%/KH-UAF/projects/<project-key>/.snapshots/commit_log.json`.
5. Restore a known version with `SnapshotManager.rollback_result(version_id)` when a generated change fails review, tests, or user approval; use `rollback(version_id)` only when a boolean is enough.
6. Prune old snapshots with `SnapshotManager.prune(max_snapshots)` when the workflow has an explicit retention policy.
7. Never allow snapshots to target files outside the project root or inside `.snapshots`.

## Safety rules

- Treat `.snapshots` as protected metadata.
- Validate paths with real path boundaries, not string prefixes.
- Do not create `.snapshots` in the target project root by default; use `UAF_PROJECT_LOCAL_STATE=1` only when project-local runtime state is explicitly requested.
- Keep one snapshot bundle per work batch instead of one archive per file when several files are being changed together.
- Keep snapshot version IDs unique even when multiple snapshots are created within the same second.
- Use fresh verification after rollback before claiming the workspace is restored.

## Required outputs

- Work-level snapshot bundle for related multi-file changes, or single-file snapshot for isolated edits.
- Snapshot metadata with version id, file list, message, timestamp, and compressed artifact path.
- Restore result that identifies restored files, removed files, failed files, and partial-restore errors.
- Retention/prune result when cleanup is requested.

## Common mistakes

- Do not create one archive per file when the work should be captured as one batch checkpoint.
- Do not write `.snapshots` into the project root by default.
- Do not allow snapshot targets outside the project root or inside snapshot metadata.
- Do not claim rollback succeeded without verifying the restored files.

## UAF implementation targets

- `src.core.snapshot_manager.SnapshotManager`
- `src.orchestration.agent_loop`
- `src.harness.sandbox`
- `tests.test_snapshot_manager`
