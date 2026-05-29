# Quality Gates Harness Usage Reference

This reference expands the portable operating contract for `quality-gates-harness`. Read it when the task is real work, when deciding whether this skill applies, or when a review needs evidence beyond the concise `SKILL.md`.

## When to use

Use when a UAF workflow needs failing-test-first implementation, systematic debugging, review gates, or evidence-based completion checks.

Context summary: This is a personal UAF quality harness for testing, debugging, and verification workflows. It complements the sandbox evaluator by defining when evidence is required.

Do not use this skill only because it is available. Use it when the current task needs the behavior named by the trigger, and state whether the skill was actually executed, applied procedurally, or only considered.

## Inputs to collect

- User objective, success criteria, and any explicit completion conditions.
- Target workspace, write boundaries, and whether user-facing deliverables are expected.
- Required role, gate, state, artifact, or command evidence for this harness.
- Existing artifacts or state files that must be preserved rather than overwritten.
- Execution level: `hybrid-harness`.
- Implementation targets:
  - `src.harness.evaluator`
  - `src.harness.sandbox`
  - `src.core.runner`
  - `src.orchestration.gate_evaluators.build_review_finding`
  - `src.orchestration.gate_evaluators.build_qa_check`
  - `src.orchestration.gate_evaluators.evaluate_qa_checks`
  - `tests`
  - `src.skills.uaf_skill_catalog`

## Execution pattern

1. Read `SKILL.md` first and confirm the trigger applies to the current task.
2. Read this reference before performing non-trivial work with `quality-gates-harness`.
3. Apply failing-first and verification rules procedurally, and use gate evaluator helpers when review or QA evidence must be structured.
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

A valid use of `quality-gates-harness` must leave enough evidence for another agent to answer: why this skill applied, what ran or was applied, what changed, and what still needs attention.
