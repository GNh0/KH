# Workflow Usability Layer Audit

## Summary

This audit records the KH-native usability layer added after reviewing large task-plan workflows. The goal is to keep KH's evidence-driven lifecycle while making progress, token policy, role entrypoints, Compound handoff, and resume context visible enough that future sessions do not silently skip them.

## Added Capabilities

- `workflow-usability-harness`: packaged KH skill that ties progress state, token provider policy, role commands, progress panels, session-start context, and Compound handoff together.
- `src.orchestration.progress_compound_bridge`: converts completed `.kh/development/<run-id>/state/progress.json` into `CompoundCapture`, `compound_handoff`, memory candidates, skill candidates, scenario candidates, and `docs/kh/handoffs/<run-id>-compound.md`.
- `src.orchestration.token_optimizer_provider`: records `token_optimizer_provider` as `kh`, `rtk`, `hybrid`, or `passthrough`; RTK is optional and hybrid falls back to KH.
- `src.orchestration.role_commands`: exposes concise `/kh:*` command entrypoints for brainstorming, spec, CEO review, engineering review, work, QA, ship, learn, and resume flows.
- `src.orchestration.progress_panel`: renders visible task-plan progress with task status, review status, token optimizer status, commit SHA, and next task.
- `src.orchestration.session_start_context`: inspects `.kh`, `docs/kh`, latest progress/Compound state, and scoped memory candidates at session start.
- `src.orchestration.workflow_usability_runtime`: applies those helpers automatically inside AgentLoop, app bridge, local workflow, and native host dispatch paths when `workflow_usability_auto` is enabled.

## Benchmark Mapping

- Superpowers-style visible progress is mapped to `render_progress_panel(...)` and `.kh/development/<run-id>/state/progress.json`.
- External role-stack command ergonomics are mapped to KH-owned `/kh:*` role command entrypoints without introducing external runtime dependency.
- RTK-style token optimization is mapped to provider policy, not a hard dependency.
- Compound engineering is mapped to automatic progress-to-Compound handoff after Plan, Work, and Review.
- KH memory is mapped to scoped memory candidates only unless the user explicitly approves durable promotion.

## Required Operating Rule

For long task-plan runs, KH should not stop at a committed implementation. The controller should:

1. Render or report the progress panel.
2. Record `token_optimizer_provider` and `token_optimizer_status`.
3. Convert completed progress to Compound artifacts.
4. Leave memory, skill, and scenario candidates in state/docs.
5. At the next session, inspect `.kh`, `docs/kh`, and memory candidates before relying on chat context.

## Verification Targets

- `python -m unittest tests.test_workflow_usability_layer`
- `python -m unittest tests.test_uaf_skill_catalog tests.test_uaf_skill_audit tests.test_uaf_skill_quality`
- `python -m src.skills.uaf_skill_catalog --check`
- `python -m src.skills.uaf_skill_quality --summary`
