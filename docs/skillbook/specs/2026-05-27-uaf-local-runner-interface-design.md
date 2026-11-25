# UAF Local Runner Interface Design

## Goal

Replace the local workflow worker's placeholder sleep-plus-webhook behavior with a runner interface that returns concrete `WorkflowTaskResult` values.

## Scope

This phase adds a local runner contract and wires it into existing workflow dispatch:

- `src/tasks/runners.py`
- `WorkflowTaskInput` dataclass for one bounded file task
- `LocalTaskRunner` for deterministic local task execution metadata
- worker source of truth becomes the runner result
- webhook posting remains a side effect recorded in task metadata
- runner evidence is added to goal evidence evaluation

This phase does not implement real LLM code generation or native Antigravity invocation. It creates the local runner seam those implementations can use next.

## Runner Contract

`WorkflowTaskInput` fields:

- `project_dir`
- `file_name`
- `design_doc`
- `platform_mode`
- `role`
- `metadata`

`LocalTaskRunner.run(task)` returns `WorkflowTaskResult`.

Rules:

1. Resolve `file_name` under `project_dir`.
2. Reject absolute or traversal paths outside the project.
3. Return `status="success"` for accepted bounded tasks.
4. Include runner metadata:
   - `runner`
   - `target_path`
   - `artifact_exists`
   - `evidence`
5. Return `status="failed"` for invalid task paths.

## Webhook Reporting

The worker should still POST a compact task result payload to the configured webhook. The POST result should be recorded as `metadata["webhook_report"]`.

Webhook failure must not override a successful runner result. This is the main behavioral change from the placeholder implementation.

## Goal Evidence

Workflow evidence should include runner-provided evidence from each `WorkflowTaskResult.metadata["evidence"]`. This lets `GoalState.evidence_required` ask for evidence such as `task runner completed`.

## Tests

Tests should prove:

- `LocalTaskRunner` returns a successful `WorkflowTaskResult` for a safe target file.
- `LocalTaskRunner` fails a traversal path.
- webhook failures are recorded without overriding a successful runner result.
- runner evidence can satisfy `GoalState.evidence_required`.
- Local dispatcher exposes runner result metadata through adapter metadata.
