---
name: runtime-cleanup
description: Manage processes, terminal sessions, REPL kernels and other runtime resources used during a task; release completed task-owned work and diagnose accumulation while preserving needed or shared services.
---

# Runtime cleanup

Apply while starting, using and finishing runtime resources. Retain work still needed for the current task or an explicitly requested handover. Resource ownership and remaining purpose determine cleanup; an executable name, idle CPU, old PID or a completed chat alone does not.

## Own the lifetime

Use the current host's process/session handles and remember what this task actually started, its purpose and when it can end. Reuse appropriate sessions instead of launching duplicate helpers. Keep this small record in the working context; no extra project files or background cleanup daemon are required.

For a disposable Windows command that can spawn helpers, use the [owned-command runner](references/windows-runner.md) when normal host execution cannot ensure descendant cleanup. It starts a new command tree and verifies that tree is empty afterward. Host-managed servers and existing user processes are outside that ownership.

## Finish or stop

After required outputs have been retrieved, or on failure/cancellation:

1. Close task-owned timers, watchers, browser/driver contexts, streams, files and database connections through their actual APIs. Preserve user-requested interactive applications and deliverables.
2. Stop no-longer-needed background commands through their owning host session, then wait for exit and inspect the result. If ordinary shutdown fails, terminate only the proven task-owned tree through its retained handle/container. Preserve a needed server until its actual lifetime ends.
3. For a persistent JS/CUA REPL used by this task, first close its owned resources. Use the host's documented reset/disposal tool once bindings are no longer needed. Reset clears interpreter state; verify what the tool actually promises rather than claiming its server process exited. Do not start an unused kernel merely to reset it, or reset another chat's state.
4. Check that owned commands ended and disposable outputs were cleaned using [workspace files](../work-execution/references/workspace-files.md). Report retained resources and their purpose, or cleanup failures with the owning session/PID and reason. Do not declare cleanup complete from a signal being sent alone.

Task completion includes this cleanup when runtime resources were used. A task that started no resources needs no process scan or reset ceremony. Re-check retained resources when continuing the task.

## Diagnose accumulation

Read process image/path, creation time, parent/child relationships, current session use and sampled CPU/memory. Protect secrets in command lines and environment values. Distinguish command wrappers, interpreter kernels, persistent tool servers and application-owned caches; classify untraceable ownership as unknown. Active-chat count and process count measure different things, but unexplained retained groups still need investigation.

Use supported host/MCP session lifecycle controls for host-managed servers. Skill guidance and the runner cannot dispose arbitrary Codex-internal MCP caches. Establish a concrete host-level remedy before changing configuration or shutting down shared providers. Never sweep by `node`, `node_repl`, `cmd`, memory size or process age, and do not use working-set trimming or forced GC as proof of resource release.
