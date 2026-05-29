# Compound Engineering Harness Minimal Workflow Example

## Scenario

A KH workflow finishes a SaaS discovery improvement. Review finds that Superpowers was selected before KH for early product brainstorming because KH lacked a strong front-door trigger. The work now passes tests, but stopping at review would lose the reusable learning.

The agent must use `compound-engineering-harness` to capture the lesson, decide the system update, and connect it to a regression check.

## Expected steps

1. Load `SKILL.md` and confirm the trigger applies after Plan, Work, and Review.
2. Read `references/usage.md` before doing the work.
3. Record the completed objective and review findings.
4. Create a `CompoundLearning` for the front-door trigger problem.
5. Add a system update plan such as plugin prompt, skill wording, or scenario fixture.
6. Add a project-scoped memory candidate so the discovery preference survives context compression.
7. Add a regression check such as `tests.test_superpowers_benchmark_alignment`.
8. Validate with `validate_compound_capture`.
9. Build handoff with `build_compound_handoff`.
10. Route to `workflow-skill-distiller`, `memory-state-harness`, or `scenario-evaluation-harness`.
11. Run `python scripts/smoke_check.py` when validating the packaged skill folder itself.

## Expected evidence

- `skill`: `compound-engineering-harness`.
- `execution_level`: `hybrid-harness`.
- `support_reference_read`: `references/usage.md`.
- `implementation_targets`:
  - `src.orchestration.compound.CompoundLearning`
  - `src.orchestration.compound.CompoundMemoryCandidate`
  - `src.orchestration.compound.CompoundCapture`
  - `src.orchestration.compound.validate_compound_capture`
  - `src.orchestration.compound.build_compound_handoff`
  - `tests.test_compound_engineering_harness`
  - `skills/compound_engineering_harness/SKILL.md`
- `actual_runtime_path`: `src.orchestration.compound`.
- `memory_candidates`: project/conversation scoped candidate records, not global memory by default.
- `verification`: validation result, demo result, or explicit blocked reason.

## Failure cases

- The agent stops after tests and review without recording any learning.
- The agent says "nothing to learn" without a rationale.
- The agent creates a memory or skill with no trigger, evidence, or scope.
- The agent records a reusable lesson but does not add a regression check.
- The agent copies external folder conventions as mandatory KH paths.

## Done criteria

- The trigger match is explicit.
- Completed work and review evidence are recorded.
- Learning candidates or no-learning rationale exist.
- System update and regression check plans exist for reusable learning.
- The next KH skill is named.
- Missing or blocked work is represented as structured evidence, not hidden in prose.
