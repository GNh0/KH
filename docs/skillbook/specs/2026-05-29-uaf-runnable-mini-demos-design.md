# KH UAF Runnable Mini-Demo Design

## Objective

Raise KH UAF from external 8.5+ documentation quality toward 9+ practical quality by giving every packaged skill/harness a runnable mini-demo that proves the skill's success path, blocked/failure path, output contract, host metadata, and artifact behavior when applicable.

## Scope

- Add `skills/<skill>/scripts/demo.py` for every packaged skill.
- Add one shared implementation module, `src.skills.demo_scenarios`, so demo behavior is consistent and testable.
- Keep each per-skill script tiny and runnable from the skill folder or repository root.
- Add a unittest suite that runs every demo and validates JSON schema, contract shape, failure/blocked case, and artifact paths.
- For deliverable/artifact-oriented harnesses, generate real local DOCX/XLSX/SVG/DXF demo files and run structural validation.

## SIDE Scenario Coverage

- Software delivery: lifecycle, TDD/quality gates, review, QA, release evidence.
- Product/mechanical delivery: domain orchestration, artifact render QA, template quality, traceability.
- Command/token safety: command hook, guard policy, command output, token optimizer.
- State and recovery: goal, context, memory, snapshot, health.
- Host orchestration: adapter contract, host agent orchestration, role graph, parallel orchestration, role execution audit, subagent review.
- Skill operations: skill catalog, workflow skill distiller, evaluator.

## Demo Output Contract

Every demo prints JSON:

- `skill`
- `success_case`
- `blocked_or_failure_case`
- `contracts`
- `host_metadata`
- `artifacts`
- `verification`

The success and blocked/failure cases must contain real UAF-shaped data such as `HarnessResult`, `AdapterResult`, `WorkflowDispatchResult`, `WorkflowTaskResult`, or gate result dictionaries.

## Verification

- RED test first: fail until every packaged skill has a runnable demo.
- GREEN implementation: add shared demo runner and per-skill wrappers.
- Regression checks:
  - `python -m unittest tests.test_skill_demos`
  - `python -m src.skills.uaf_skill_catalog --check`
  - `python -m src.skills.uaf_skill_quality --summary`
  - `python -m unittest discover -s tests`
