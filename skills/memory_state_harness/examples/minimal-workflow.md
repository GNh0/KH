# Memory State Harness Minimal Workflow Example

## Scenario

A host agent receives a task where this trigger is relevant: Use when a UAF workflow needs scoped persistent memory, memory candidates, project/conversation namespace isolation, or archive/delete cleanup policy.

The agent must decide whether `memory-state-harness` applies, run or apply it according to its execution level, and leave auditable evidence.

## Expected steps

1. Load `SKILL.md` and confirm the trigger applies.
2. Read `references/usage.md` before doing the work.
3. Collect the user objective, workspace boundary, expected outputs, and evidence requirements.
4. Follow the `python-module` execution pattern for this skill.
5. Write or report the resulting artifact, state entry, gate result, or decision evidence.
6. Run `python scripts/smoke_check.py` when validating the packaged skill folder itself.

## Expected evidence

- `skill`: `memory-state-harness`.
- `execution_level`: `python-module`.
- `support_reference_read`: `references/usage.md`.
- `implementation_targets`:
  - `src.contracts.MemoryScope`
  - `src.contracts.MemoryRecord`
  - `src.contracts.MemoryEvent`
  - `src.orchestration.memory_state`
  - `src.orchestration.memory_store`
  - `src.orchestration.runtime_memory`
  - `src.orchestration.session_start_context`
  - `src.orchestration.interruption_state`
  - `src.platforms.codex_thread_registry`
  - `src.tasks.workflows`
- `actual_runtime_path`: the concrete module, workflow, policy gate, or procedural step used in this run.
- `verification`: command output, test result, artifact path, or explicit blocked reason.

## Failure cases

- The agent claims the skill was executed but only read `SKILL.md`.
- The agent reports parallel, role, state, or gate behavior without runtime-path evidence.
- The agent creates user-facing artifacts in hidden state folders or hidden state in the user output folder.
- The agent omits failed worker, gate, policy, or verification results from the final aggregate.

## Done criteria

- The trigger match is explicit.
- Required inputs and boundaries are recorded.
- The execution level is stated accurately.
- Evidence proves what actually ran or was applied.
- Missing or blocked work is represented as structured evidence, not hidden in prose.
