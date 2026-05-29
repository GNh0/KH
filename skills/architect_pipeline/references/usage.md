# Architect Pipeline Skill Usage Reference

This reference expands the portable operating contract for `architect-pipeline`. Read it when the task is real work, when deciding whether this skill applies, or when a review needs evidence beyond the concise `SKILL.md`.

## When to use

Use when a substantial application, system, process, analysis, or cross-domain workflow needs a design blueprint before execution.

Context summary: This skill uses the Universal Agent Framework's architect and design-stage modules to generate a robust blueprint. The default output must stay domain-neutral: software projects can include architecture details, but operations, analysis, research, planning, and other topics must still receive orchestration design artifacts.

Do not use this skill only because it is available. Use it when the current task needs the behavior named by the trigger, and state whether the skill was actually executed, applied procedurally, or only considered.

## Inputs to collect

- User objective, success criteria, and any explicit completion conditions.
- Target workspace, write boundaries, and whether user-facing deliverables are expected.
- Required role, gate, state, artifact, or command evidence for this harness.
- Existing artifacts or state files that must be preserved rather than overwritten.
- Execution level: `hybrid-harness`.
- Implementation targets:
  - `src.core.architect.SystemArchitect`
  - `src.core.architect.run_architect_pipeline`
  - `src.core.runner`
  - `src.orchestration.agent_loop`
  - `src.orchestration.deliverable_exports`
  - `src.skills.pattern_analyzer`
  - `src.skills.license_checker`

## Execution pattern

1. Read `SKILL.md` first and confirm the trigger applies to the current task.
2. Read this reference before performing non-trivial work with `architect-pipeline`.
3. Prefer `run_architect_pipeline(project_dir, requirements, framework, libraries, metadata=...)`; expected output keys are `design_doc_path`, `design_doc`, `domain_profile`, `work_design`, `manifest`, `deliverable_exports`, `quality`, and `evidence`.
4. Combine the listed Python implementation targets with the written workflow contract, then record which parts ran as code and which parts were applied procedurally.
5. Preserve intermediate decisions in structured evidence rather than relying on terminal logs alone.
6. Run `python scripts/smoke_check.py` when validating this packaged skill in the repository.
7. Report the difference between capability available in the repository and behavior actually executed in the current run.

## Evidence to produce

- Skill name and execution level used for the run.
- Concrete input summary and target workspace or artifact paths.
- Implementation targets touched, imported, called, resolved by smoke check, or explicitly not needed.
- Output files, gate results, state records, or role results created by the skill.
- Verification command or review evidence, including failures and blocked states.

## Failure handling

- If a required implementation target is missing, stop using this skill as executed evidence and report the missing target.
- If the workflow can only be applied procedurally, say so explicitly and record the policy or decision evidence.
- If parallel, role, gate, or state behavior is claimed, prove the actual runtime path instead of citing only repository support.
- If generated artifacts are incomplete, withhold completion until the missing artifact or exception is recorded.

## Quality bar

A valid use of `architect-pipeline` must leave enough evidence for another agent to answer: why this skill applied, what ran or was applied, what changed, and what still needs attention.
