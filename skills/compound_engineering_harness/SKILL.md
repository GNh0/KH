---
name: compound-engineering-harness
description: Use when Plan, Work, and Review are complete and the work may produce reusable lessons, scoped memory candidates, system updates, or regression checks.
---

# Compound Engineering Harness

This is KH UAF's explicit Compound step. External skillbooks provide strong planning, worktree, role, review, QA, and release discipline; KH adds the required final learning loop so each completed workflow can improve the next run.

Reference basis: external compound engineering loops, role-stack review/QA/release patterns, and Superpowers planning/TDD/review/worktree patterns.

## Support files

- Read `references/usage.md` before applying this skill to real completed work; it expands the benchmark mapping, inputs, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact acceptance scenario for capture after review.
- Run `python scripts/smoke_check.py` from this skill folder to verify support files and implementation targets.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo.

## When To Use

Use this harness after meaningful Plan, Work, and Review activity when:

- A bug, review finding, failed route, prompt behavior, or workflow pattern should be easier next time.
- A repeated workflow should become a skill, scenario, memory candidate, prompt rule, or quality gate.
- A role-stack review/QA/release lesson should be captured in KH-native evidence.
- A Superpowers-style planning/TDD/worktree/review rule should become a KH regression or skill improvement.

Do not skip this step only because the feature already works. The Compound step is about improving the system that builds the next feature.

## Core Flow

1. Summarize the completed objective, changed behavior, and review findings.
2. Ask what worked, what failed, and what reusable insight should survive context compression.
3. Classify the learning target:
   - skill update
   - new skill candidate
   - scenario regression
   - memory candidate
   - goal/context ledger update
   - prompt/plugin default update
   - no reusable learning
4. If a reusable learning exists, create a `CompoundCapture` with `CompoundLearning` records.
5. Add scoped `memory_candidates` for project/conversation lessons that should survive context compression, but require explicit promotion for global memory.
6. Require a system update plan and a regression check plan for every reusable learning.
7. If there is no reusable learning, record an explicit `no_reusable_learning_rationale`.
8. Hand off to `workflow-skill-distiller`, `scenario-evaluation-harness`, `memory-state-harness`, or `context-state-harness` as appropriate.
9. Verify the learning by running or adding a check that would catch the same failure next time.
10. For large work, ensure the final lifecycle report includes `skill_transition_handoff` so the selected next KH skill is either completed, blocked, or visible as required next work.
11. For task-plan runs, accept progress-to-Compound handoffs from `workflow-usability-harness` so completed `progress.json` becomes `CompoundCapture`, memory candidates, skill candidates, scenario candidates, and `docs/kh/handoffs/<run-id>-compound.md`.

## Large Work Bundle Reporting

When this skill is part of `large_work_orchestration_bundle`, record `skill_statuses["compound-engineering-harness"]` as `applied`, `considered_not_needed`, `skipped_with_rationale`, or `blocked`. Large work must leave `compound_handoff`: a learning capture, scoped memory candidate, scenario regression, distiller handoff, or explicit no-reusable-learning rationale.

The lifecycle transition validator treats this handoff as binding. If `compound_handoff.next_skills` names `workflow-skill-distiller`, `memory-state-harness`, `scenario-evaluation-harness`, or `context-state-harness`, that skill must be applied, blocked with rationale, or left in `required_next_skills`. This prevents Compound from becoming a recap that never affects the next run.

## Evidence Contract

A valid Compound run leaves:

- `compound_capture`
- `review_summary`
- `learning_candidates` when reusable learning exists
- `system_update_plan` when reusable learning exists
- `regression_check_plan` when reusable learning exists
- `memory_candidates` when project/conversation learning should persist
- `no_reusable_learning_rationale` when nothing reusable exists
- next KH skill selection
- `skill_transition_handoff` when used inside a large-work lifecycle

The agent must not claim compound learning if it only writes a recap and does not connect the learning to a future retrieval, skill, state, or regression path.

## External Benchmark Recipe

Use this harness as the KH-native answer to the missing fourth step in many agent skillbooks:

1. After Review, list concrete mistakes, wins, and repeated patterns.
2. Turn each reusable lesson into frontmatter/searchable wording, a skill update, a scenario, or scoped memory candidate.
3. Pick the next KH skill that will apply the learning.
4. Add a regression or smoke check when the learning is testable.
5. Record a no-learning rationale for trivial one-off work.

Pressure scenario: the implementation passes tests and review, but the agent stops without capturing the repeated mistake. The harness must block "compound complete" until learning evidence or no-learning rationale exists.

## UAF implementation targets

- `src.orchestration.compound.CompoundLearning`
- `src.orchestration.compound.CompoundMemoryCandidate`
- `src.orchestration.compound.CompoundCapture`
- `src.orchestration.compound.validate_compound_capture`
- `src.orchestration.compound.build_compound_handoff`
- `src.orchestration.progress_compound_bridge.write_progress_compound_artifacts`
- `tests.test_compound_engineering_harness`
- `skills/compound_engineering_harness/SKILL.md`

## Boundaries

- Do not copy external project paths such as `docs/solutions/` as a KH requirement.
- Do not update global or cross-project memory for a project-local lesson.
- Do not create a new skill for a one-off event.
- Do not leave reusable learning only in chat.
- Do not treat a passed test suite as proof that Compound happened.

## Required outputs

- Objective and completed work summary.
- Review findings or explicit no-findings note.
- Learning candidates or no-learning rationale.
- System update plan and regression check plan when learning exists.
- Next KH skill handoff.
- `CompoundCapture` validation result.

## Common mistakes

- Stopping at Review because the feature works.
- Capturing a vague lesson that future agents cannot find.
- Adding memory without scope, evidence, or cleanup policy.
- Creating skills without trigger-focused frontmatter.
- Skipping the verification question: would KH catch this automatically next time?
