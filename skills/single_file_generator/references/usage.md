# Single File Generator Usage Reference

This reference expands the portable operating contract for `single-file-generator`. Read it when the task is real work, when deciding whether this skill applies, or when a review needs evidence beyond the concise `SKILL.md`.

## When to use

Use when the task requires generating or modifying exactly one file, such as a single function, config file, script, or template.

Context summary: This skill provides the fastest possible path from prompt to file output. It uses no orchestration state, no role DAG, and no multi-gate pipeline. The focus is correctness of one file.

Do not use this skill only because it is available. Use it when the current task needs the behavior named by the trigger, and state whether the skill was actually executed, applied procedurally, or only considered.

Quality rule: the generated file must be syntactically valid and functionally correct for the stated purpose. A fast but broken file is not acceptable.

## Inputs to collect

- User objective: what the file should contain and do.
- File format: language, config format, or template type.
- Target path: where to write the output file.
- Whether this is creation (new file) or modification (existing file).
- Execution level: `python-module`.
- Implementation targets:
  - `src.tasks.runners.LocalTaskRunner`
  - `src.tasks.runners.DeterministicCodeGenerationAdapter`
  - `src.tasks.runners.LLMCodeGenerationAdapter`
  - `src.tasks.runners.GeneratedTaskArtifact`
  - `src.contracts.WorkflowTaskResult`
  - `tests.test_task_runners`

## Execution pattern

1. Read `SKILL.md` first and confirm the trigger applies to the current task.
2. Read this reference before performing non-trivial work with `single-file-generator`.
3. Determine file format from the prompt or explicit user specification.
4. Choose generation strategy: `DeterministicCodeGenerationAdapter` for offline/template mode, `LLMCodeGenerationAdapter` for model-backed generation.
5. Generate content through the chosen adapter.
6. Validate syntax: Python files through `ast.parse`, JSON through `json.loads`, YAML through safe load.
7. Write to workspace path.
8. Return `WorkflowTaskResult` with file path, size, and validation evidence.

## Evidence to produce

- `skill`: `single-file-generator`.
- `execution_level`: `python-module`.
- `file_path`: output path.
- `file_size_bytes`: content size.
- `format`: detected or specified format.
- `validation_method`: how syntax was checked.
- `validation_passed`: boolean.
- `generation_strategy`: `template` or `llm`.

## Failure handling

- If syntax validation fails, return `status: failed` with the parse error and generated content for debugging.
- If the target path is not writable, return `status: blocked` with the permission error.
- If the prompt is ambiguous about what file to generate, return `status: blocked` requesting clarification.
- If the generated file would exceed a reasonable size (>1MB for a single file), return `status: blocked`.

## Quality bar

- Generated Python files must pass `ast.parse()` without errors.
- Generated JSON files must pass `json.loads()`.
- Generated YAML files must be loadable by a YAML parser.
- File content must be non-empty and related to the user's request.
- File path must be within the allowed workspace boundary.
