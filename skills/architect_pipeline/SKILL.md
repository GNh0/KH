---
name: architect-pipeline
description: Use when a substantial application, system, process, analysis, or cross-domain workflow needs a design blueprint before execution.
---
# Architect Pipeline Skill

This skill uses the Universal Agent Framework's architect and design-stage modules to generate a robust blueprint. The default output must stay domain-neutral: software projects can include architecture details, but operations, analysis, research, planning, and other topics must still receive orchestration design artifacts.

## Instructions
When the user asks you to design or execute a substantial workflow, you MUST follow these steps:
1. Run the architect pipeline using the terminal:
   `python -m src.core.runner --mode architect --project_dir ./workspace --reqs "<User Requirement>" --framework "<Framework Name>"`
2. Read the generated `./workspace/design_doc.md` file carefully.
3. Use the workflow design stage to create `DomainProfile`, `WorkDesign`, internal `ArtifactManifest`, and user-facing Office deliverables under the target project's `docs/` folder.
4. **Parallel Dispatching Note**: The design must clearly outline bounded target outputs. For software these may be files; for other domains they may be reports, checklists, plans, or decision artifacts.
5. Follow the exact design patterns, orchestration boundaries, evidence requirements, and domain constraints written in the design outputs.
6. If there are license, policy, safety, or missing-evidence warnings, do NOT proceed as complete until alternatives or blockers are recorded.

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
- `src.core.runner`
- `src.orchestration.agent_loop`
- `src.orchestration.deliverable_exports`
- `src.skills.pattern_analyzer`
- `src.skills.license_checker`
