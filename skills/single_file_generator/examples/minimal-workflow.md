# Single File Generator Minimal Workflow Example

## Scenario

A host agent receives a task where this trigger is relevant: Use when the task requires generating or modifying exactly one file, such as a single function, config file, script, or template.

The agent must decide whether `single-file-generator` applies, run or apply it according to its execution level, and leave auditable evidence.

## Expected steps

1. Load `SKILL.md` and confirm the trigger applies (task produces exactly one file).
2. Read `references/usage.md` before doing the work.
3. Determine the output file format and target path.
4. Select generation strategy based on available provider (template vs LLM).
5. Generate file content using the chosen adapter.
6. Validate syntax for the detected format.
7. Write the file to the workspace.
8. Return result with file_path, file_size_bytes, and validation status.
9. Run `python scripts/smoke_check.py` when validating the packaged skill folder itself.

## Expected evidence

- `skill`: `single-file-generator`.
- `execution_level`: `python-module`.
- `support_reference_read`: `references/usage.md`.
- `implementation_targets`:
  - `src.tasks.runners.LocalTaskRunner`
  - `src.tasks.runners.DeterministicCodeGenerationAdapter`
  - `src.tasks.runners.LLMCodeGenerationAdapter`
  - `src.tasks.runners.GeneratedTaskArtifact`
  - `src.contracts.WorkflowTaskResult`
  - `tests.test_task_runners`
- `actual_runtime_path`: the concrete module, workflow, policy gate, or procedural step used in this run.
- `verification`: command output, test result, artifact path, or explicit blocked reason.

## Failure cases

- The agent claims single-file generation but produces multiple files.
- The agent generates a file that fails syntax validation but reports success.
- The agent uses full orchestration overhead for a single-file task.
- The agent overwrites an existing file without confirming the user intent.
- The agent generates an empty file and claims success.

## Done criteria

- Exactly one file generated at the correct workspace path.
- File passes format-appropriate syntax validation.
- Result metadata includes file path, size, format, and validation status.
- No orchestration state (GoalState, Memory, Snapshot) was created.
