---
name: architect-pipeline
description: Use when a substantial application, system, process, analysis, or cross-domain workflow needs a design blueprint before execution.
---
# Architect Pipeline Skill

This skill uses the Universal Agent Framework's architect and design-stage modules to generate a robust blueprint. The default output must stay domain-neutral: software projects can include architecture details, but operations, analysis, research, planning, and other topics must still receive orchestration design artifacts.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## Instructions
When the user asks you to design or execute a substantial workflow, you MUST follow these steps:
1. For a cohesive in-process run, call `src.core.architect.run_architect_pipeline`; it returns the design document, `DomainProfile`, `WorkDesign`, artifact manifest, deliverable exports, quality evidence, and evidence keys together.
2. Run the architect pipeline using the terminal when CLI operation is preferred:
   `python -m src.core.runner --mode architect --project_dir ./workspace --reqs "<User Requirement>" --framework "<Framework Name>"`
3. Read the generated `./workspace/design_doc.md` file carefully.
4. Use the workflow design stage to create `DomainProfile`, `WorkDesign`, internal `ArtifactManifest`, and user-facing Office deliverables under the target project's `docs/` folder.
5. **Parallel Dispatching Note**: The design must clearly outline bounded target outputs. For software these may be files; for other domains they may be reports, checklists, plans, or decision artifacts.
6. Follow the exact design patterns, orchestration boundaries, evidence requirements, and domain constraints written in the design outputs.
7. If there are license, policy, safety, or missing-evidence warnings, do NOT proceed as complete until alternatives or blockers are recorded.

## External Benchmark Recipe

Use this skill like a science-style analysis recipe:

1. Capture the objective, domain, constraints, source inputs, and expected deliverables before drafting.
2. Call `run_architect_pipeline(project_dir, requirements, framework)` for one cohesive output bundle.
3. Inspect `design_doc`, `work_design`, `manifest`, `deliverable_exports`, and `quality` before dispatching implementation.
4. Reject the design if roles, assumptions, evidence keys, or deliverable routing are missing.
5. Route domain outputs to `docs/` only when they are useful to the user; keep internal UAF evidence in runtime state.

Pressure scenario: if the design is a short paragraph with no assumptions, constraints, roles, artifacts, or review gates, the architect stage has failed even if a file exists.

## Required outputs

- `design_doc.md` or equivalent design text with objective, scope, assumptions, constraints, roles, and deliverables.
- `WorkDesign` metadata persisted through the UAF artifact store.
- User-facing design deliverables only when they are useful for the target work, under the target project's `docs/` folder.
- Evidence keys for saved design, artifact manifest, exported deliverables, and unresolved blockers.

## Common mistakes

- Do not make every architecture output software-specific; product, analysis, operations, and research work need domain-appropriate designs.
- Do not count a short note as a design blueprint when roles, constraints, gates, and deliverables are missing.
- Do not export internal harness reports as user-facing documents unless explicitly requested.
- Do not proceed to implementation when required design evidence or policy warnings are unresolved.

## UAF implementation targets

- `src.core.architect.SystemArchitect`
- `src.core.architect.run_architect_pipeline`
- `src.core.runner`
- `src.orchestration.agent_loop`
- `src.orchestration.deliverable_exports`
- `src.skills.pattern_analyzer`
- `src.skills.license_checker`
