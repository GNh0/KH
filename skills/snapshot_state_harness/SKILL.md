---
name: snapshot-state-harness
description: Use when UAF workflows need rollback points, compressed file snapshots, state restore, or safe checkpoint metadata before generated code changes.
---

# Snapshot State Harness

This is a UAF-native rollback harness. It packages snapshot behavior inside this repository and does not require Gemini, Antigravity, RTK, or Superpowers installations at runtime.

## Workflow

1. Create a checkpoint before an agent writes generated code or modifies a risky file.
2. Store the file content with `SnapshotManager.commit(file_name, code, message)`.
3. Keep snapshot metadata inside the project-local `.snapshots/commit_log.json`.
4. Restore a known version with `SnapshotManager.rollback(version_id)` when a generated change fails review, tests, or user approval.
5. Never allow snapshots to target files outside the project root or inside `.snapshots`.

## Safety rules

- Treat `.snapshots` as protected metadata.
- Validate paths with real path boundaries, not string prefixes.
- Keep snapshot artifacts project-local so Windows app hosts can run without external service state.
- Use fresh verification after rollback before claiming the workspace is restored.

## UAF implementation targets

- `src.core.snapshot_manager.SnapshotManager`
- `src.orchestration.agent_loop`
- `src.harness.sandbox`
- `tests.test_snapshot_manager`
