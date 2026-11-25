# Skill Transition Policy Audit

Date: 2026-05-30

## Trigger

The user pointed out that skills which are only listed but not naturally entered by a workflow may never be used. That makes the skillbook weaker than the process it describes.

## Decision

KH large-work flows now treat key skills as connected handoffs:

- `memory_candidates` require `memory-state-harness`.
- Applied `subagent-review-pipeline` requires `role-execution-audit-harness`.
- Applied `subagent-review-pipeline` also requires an explicit token optimizer decision for task packets, transcripts, and reviewer outputs, but not automatic compression.
- Selected parallel execution requires `parallel-orchestration-harness`.
- Post-review work must close `compound-engineering-harness` with reusable learning, required next skills, a blocked state, or `no_reusable_learning_rationale`.
- Compound `next_skills` for `workflow-skill-distiller`, `memory-state-harness`, `scenario-evaluation-harness`, or `context-state-harness` stay visible as required follow-up work until resolved.

## External Benchmark Trace

Superpowers contributes strong activation rules around planning, TDD, worktrees, subagents, review, and verification. External role-stack flow contributes downstream handoffs from discovery/spec through CEO, engineering review, QA, and ship decisions. KH keeps those as KH-native transitions instead of importing external folder names or tool assumptions, then adds Compound learning, scoped memory, and scenario regression as the post-review step.

## Implementation

- Runtime helper: `src.orchestration.skill_transitions`.
- Required evidence: `skill_transition_handoff`.
- Subagent decision evidence: `subagent_strategy` with `dispatch`, `single-controller`, `review-only`, or `blocked`.
- Primary tests: `tests/test_skill_transitions.py`.
- Host visibility: `.codex-plugin/plugin.json`, `README.md`, `development-lifecycle-harness`, `request-complexity-router`, and `compound-engineering-harness`.

## Acceptance

A large-work final report is incomplete when it has a bundle but omits the transition result. Passing evidence is either `skill_transition_policy_passed` or a concrete `required_next_skills` list with blockers and next action.
