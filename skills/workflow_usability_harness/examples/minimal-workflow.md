# Workflow Usability Harness Minimal Workflow

## Scenario

A KH task-plan run finished implementation and review for one feature. The project has `.kh/development/run-001/state/progress.json`, a few `docs/kh` notes, and one scoped memory candidate. The user asks the next session to continue and wants the work to feel as visible as a mature agent workflow.

The goal is not to run every KH skill heavily. The goal is to expose the right state, choose the right token provider, route role commands cleanly, and make the Compound handoff visible.

## Expected steps

1. Build `session_start_context` from the target project root.
2. Read recommended `.kh`, `docs/kh`, and memory candidate paths before making assumptions from chat.
3. Resolve `token_optimizer_provider`; for a normal KH run this is usually `kh`, while `hybrid` may select an optional RTK-style provider for noisy command output.
4. If the user asks for a role shortcut, resolve it through `/kh:*` role commands. For example `/kh:eng-review` routes to spec reviewer, code-quality reviewer, security reviewer, review gate, and role execution audit.
5. Render the progress panel so the user can see task status, review status, token optimizer status, commit SHA, and next task.
6. Convert the progress state to Compound artifacts.
7. Leave memory records as candidates unless durable promotion is explicitly approved.
8. Route next skills such as workflow distillation, memory-state, scenario evaluation, or context-state handoff.

## Expected evidence

- `actual_runtime_path`: `.kh/development/run-001/state/progress.json`.
- `actual_runtime_path`: `.kh/development/run-001/state/compound_capture.json`.
- `actual_runtime_path`: `.kh/development/run-001/state/compound_handoff.json`.
- `actual_runtime_path`: `.kh/development/run-001/state/compound_candidates.json`.
- `actual_runtime_path`: `docs/kh/handoffs/run-001-compound.md`.
- `token_optimizer_provider`: `kh`, `rtk`, or `hybrid`.
- `token_optimizer_status`: `used`, `considered_not_needed`, `passthrough`, or `blocked`.
- `role_command_entrypoint`: `/kh:work`, `/kh:qa`, `/kh:ship`, `/kh:learn`, or `/kh:resume` when used.
- `progress_panel`: user-visible status text.
- `memory_candidates`: scoped candidate records, not automatic global memory.
- `next_skills`: visible follow-up skills.

## Failure cases

- The run completes but `progress.json` never becomes `CompoundCapture`.
- The token optimizer is mentioned but no provider, status, strategy, or quality rationale is recorded.
- The workflow compresses requirements, review findings, or security notes and loses exact evidence.
- A role command creates a one-off prompt instead of resolving to packaged KH roles and skills.
- The next session relies only on chat context and ignores `.kh`, `docs/kh`, or memory candidates.
- The progress panel is missing review status, commit SHA, next task, or token optimizer status.

## Done criteria

The workflow is done when a new agent can open the project, call the session-start context helper, see recommended reads, view the progress panel, find the Compound handoff, and know which next KH skill should run. For completed work, the Compound handoff must either contain learning candidates with update and regression plans or an explicit no-reusable-learning rationale.

No durable memory is promoted by this minimal workflow. Durable memory requires explicit user approval and scope.
