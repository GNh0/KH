# Domain Orchestration Harness Usage Reference

This reference expands the portable operating contract for `domain-orchestration-harness`. Read it when the task is real work, when deciding whether this skill applies, or when a review needs evidence beyond the concise `SKILL.md`.

## When to use

Use when a UAF workflow must handle a non-code or cross-domain objective, require a design stage, persist design artifacts, or route work through review, QA/QC, risk, policy, and final decision gates.

Context summary: This harness makes UAF domain orchestration portable beyond software development. Substantial objectives should be classified into a `DomainProfile`, converted into a `WorkDesign`, and backed by internal design artifacts. User-facing deliverables should be exported only when they are useful for the approved objective, requested by the user, or required for final release evidence; otherwise record a no-export rationale.

Do not use this skill only because it is available. Use it when the current task needs the behavior named by the trigger, and state whether the skill was actually executed, applied procedurally, or only considered.

## Inputs to collect

- User objective, success criteria, and any explicit completion conditions.
- Target workspace, write boundaries, and whether user-facing deliverables are expected.
- Required role, gate, state, artifact, or command evidence for this harness.
- Existing artifacts or state files that must be preserved rather than overwritten.
- Execution level: `hybrid-harness`.
- Implementation targets:
  - `src.contracts.DomainProfile`
  - `src.contracts.DomainRole`
  - `src.contracts.WorkDesign`
  - `src.contracts.DesignArtifact`
  - `src.contracts.ArtifactManifest`
  - `src.orchestration.domain_profiles.DomainProfileBuilder`
  - `src.orchestration.artifacts.ArtifactStore`
  - `src.orchestration.deliverable_exports.export_office_deliverables`
  - `src.tasks.workflows.async_project_workflow`
  - `skills/domain_orchestration_harness/SKILL.md`

## Execution pattern

1. Read `SKILL.md` first and confirm the trigger applies to the current task.
2. Read this reference before performing non-trivial work with `domain-orchestration-harness`.
3. Combine the listed Python implementation targets with the written workflow contract, then record which parts ran as code and which parts were applied procedurally.
4. Preserve intermediate decisions in structured evidence rather than relying on terminal logs alone.
5. Run `python scripts/smoke_check.py` when validating this packaged skill in the repository.
6. Report the difference between capability available in the repository and behavior actually executed in the current run.

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

A valid use of `domain-orchestration-harness` must leave enough evidence for another agent to answer: why this skill applied, what ran or was applied, what changed, and what still needs attention.
