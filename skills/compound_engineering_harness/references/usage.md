# Compound Engineering Harness Usage Reference

This reference expands the portable operating contract for `compound-engineering-harness`. Read it when KH UAF has finished meaningful Plan, Work, and Review activity and needs to decide what learning should survive into the next run.

## When to use

Use after Plan, Work, and Review when completed work may produce reusable lessons, system updates, or regression checks.

Context summary: external compound-engineering loops define the missing fourth step: the feature is not the only output; the system should become better at building the next feature. Role-stack skillbooks contribute strong role, design, review, QA, release, and learning commands. Superpowers contributes strong planning, TDD, worktree, subagent, and verification behavior. KH keeps those benefits but stores learning as UAF evidence, scoped memory, skill updates, and deterministic regressions.

Do not use this skill only because it is available. Use it when the current work produced a reusable lesson, exposed a repeated failure mode, or needs an explicit no-learning rationale before finishing.

## Inputs to collect

- User objective and completed work summary.
- Plan artifacts, changed files, role results, gate results, or verification evidence.
- Review findings, QA findings, release blockers, or explicit no-findings notes.
- What worked, what did not, and what should be reused.
- Retrieval target: skill, scenario, memory, goal/context ledger, plugin prompt, or no reusable learning.
- Scope: project, conversation, repo, skillbook, or global installation.
- Scoped memory candidates that should survive context compression, with evidence and confidence.
- Regression target: command, SIDE scenario, smoke script, unit test, or manual checklist.
- Execution level: `hybrid-harness`.
- Implementation targets:
  - `src.orchestration.compound.CompoundLearning`
  - `src.orchestration.compound.CompoundMemoryCandidate`
  - `src.orchestration.compound.CompoundCapture`
  - `src.orchestration.compound.validate_compound_capture`
  - `src.orchestration.compound.build_compound_handoff`
  - `tests.test_compound_engineering_harness`
  - `skills/compound_engineering_harness/SKILL.md`

## Execution pattern

1. Read `SKILL.md` first and confirm the trigger applies.
2. Gather completed work and review evidence.
3. Ask or infer what worked, what failed, and what future agent behavior should change.
4. Build one `CompoundLearning` per reusable insight.
5. If learning exists, require both `system_updates` and `regression_checks`.
6. Add scoped memory candidates for project/conversation learnings that should be recalled later.
7. If any candidate is global, require explicit promotion rather than inferring it from one project.
8. If no learning exists, require `no_reusable_learning_rationale`.
9. Validate the `CompoundCapture`.
10. Build a handoff with `build_compound_handoff`.
11. Route to the next KH skill: usually `workflow-skill-distiller`, `scenario-evaluation-harness`, `memory-state-harness`, or `context-state-harness`.
12. Run `python scripts/smoke_check.py` when validating this packaged skill folder itself.

## Evidence to produce

- Skill name and execution level used for the run.
- Completed objective and review summary.
- Learning candidates with trigger, reusable insight, evidence, and tags.
- System update plan and regression check plan, or explicit no-learning rationale.
- Scoped memory candidates for project/conversation learning when useful.
- Next KH skill handoff.
- Validation result, blocked reason, and missing fields if incomplete.

## Failure handling

- If completed work is missing, block capture and request a work summary.
- If review findings are missing, require an explicit no-findings note.
- If a learning exists without a system update plan, block handoff.
- If a learning exists without regression checks, block handoff.
- If the learning is one-off, record no-learning rationale instead of creating noisy memory or skills.
- If the target scope is unclear, default to project/conversation scope and avoid global memory.
- If global memory is requested without explicit promotion, block the handoff and keep the candidate scoped.

## Quality bar

A valid use of `compound-engineering-harness` must leave enough evidence for another agent to answer: what was learned, why it matters, where it will be found next time, how KH will verify it, and which UAF skill or harness owns the follow-up.
