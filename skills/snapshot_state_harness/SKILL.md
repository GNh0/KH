---
name: snapshot-state-harness
description: Use when UAF workflows need rollback points, compressed file snapshots, state restore, or safe checkpoint metadata before generated code changes.
---

# Snapshot State Harness

This is a UAF-native rollback harness. It packages snapshot behavior inside this repository and does not require external host or skill installations at runtime.

## Workflow

1. Create a checkpoint before an agent writes generated code or modifies a risky file.
2. Prefer one work-level checkpoint with `SnapshotManager.commit_many(file_names, message)` before a batch of related edits.
3. Use `SnapshotManager.commit(file_name, code, message)` only for a truly single-file checkpoint.
4. Keep snapshot metadata in the project/chat-scoped UAF runtime store, normally `%LOCALAPPDATA%/KH-UAF/projects/<project-key>/.snapshots/commit_log.json`.
5. Restore a known version with `SnapshotManager.rollback(version_id)` when a generated change fails review, tests, or user approval.
6. Prune old snapshots with `SnapshotManager.prune(max_snapshots)` when the workflow has an explicit retention policy.
7. Never allow snapshots to target files outside the project root or inside `.snapshots`.

## Safety rules

- Treat `.snapshots` as protected metadata.
- Validate paths with real path boundaries, not string prefixes.
- Do not create `.snapshots` in the target project root by default; use `UAF_PROJECT_LOCAL_STATE=1` only when project-local runtime state is explicitly requested.
- Keep one snapshot bundle per work batch instead of one archive per file when several files are being changed together.
- Keep snapshot version IDs unique even when multiple snapshots are created within the same second.
- Use fresh verification after rollback before claiming the workspace is restored.

## UAF implementation targets

- `src.core.snapshot_manager.SnapshotManager`
- `src.orchestration.agent_loop`
- `src.harness.sandbox`
- `tests.test_snapshot_manager`
