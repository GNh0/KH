---
name: single-file-generator
description: "Use when the task requires generating or modifying exactly one file, such as a single function, config file, script, or template."
---

# Single File Generator Skill

This skill provides a zero-overhead path for tasks that produce exactly one output file. It skips all orchestration infrastructure and directly generates the requested file content using either a deterministic template or LLM-backed generation.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## When to use

- "Write a Python function that does X"
- "Create a config.yaml for Y"
- "Generate a Dockerfile for Z"
- "Write a test file for module M"
- Any task where the output is a single, self-contained file

## Workflow

1. Receive prompt specifying the file to generate.
2. Determine output file path and format from the prompt context.
3. Select generation strategy: deterministic template (offline) or LLM-backed generation.
4. Generate file content directly without role DAG or state infrastructure.
5. Write the file to the target workspace path.
6. Validate basic correctness (syntax check for known formats: Python AST, JSON parse, YAML load).
7. Return result with the file path, content size, and validation status.

## Required outputs

- `status`: `passed`, `failed`, or `blocked`.
- `file_path`: absolute or workspace-relative path of the generated file.
- `file_size_bytes`: size of the generated content.
- `format_validation`: result of syntax/format check (if applicable).
- `generation_strategy`: `template` or `llm`.

## Common mistakes

- Do not use this skill for multi-file generation; use quick-task-harness or full orchestration instead.
- Do not skip format validation for known file types (Python, JSON, YAML, TOML).
- Do not overwrite existing files without checking whether the user requested creation vs. modification.
- Do not generate empty files and report success.
- Do not use full orchestration overhead for a single-file task.

## UAF implementation targets

- `src.tasks.runners.LocalTaskRunner`
- `src.tasks.runners.DeterministicCodeGenerationAdapter`
- `src.tasks.runners.LLMCodeGenerationAdapter`
- `src.tasks.runners.GeneratedTaskArtifact`
- `src.contracts.WorkflowTaskResult`
- `tests.test_task_runners`
