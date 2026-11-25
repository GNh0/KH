# KH UAF Skill Quality Scorecard

This scorecard records the practical quality gate for the packaged KH UAF skillbook after the 2.8.0 hardening pass.

## Gate

- Total packaged skills/harnesses: 27
- Minimum score for every skill: 8.0 / 10
- Minimum score for core runtime, quality, state, and orchestration harnesses: 9.0 / 10
- Latest local result: passed
- Lowest score: 10.0 / 10
- Low-quality list: empty

## Rubric

| Component | Max | Evidence expected |
| --- | ---: | --- |
| Trigger discovery | 1.0 | `Use when` frontmatter, concise trigger, searchable body. |
| Workflow procedure | 1.5 | Explicit workflow/instruction section, required outputs, wired support files. |
| Runtime implementation | 2.0 | Resolved UAF implementation targets, execution level, smoke execution. |
| Verification evidence | 2.0 | Smoke execution, deep target audit, and repository test evidence. |
| Failure safety | 1.0 | Common mistakes, failure handling, do-not constraints, blocked/fallback paths. |
| Examples and references | 1.0 | Usage reference and minimal workflow with evidence, failure cases, done criteria. |
| Integration observability | 1.0 | UAF evidence, role/gate/state/artifact/dispatch/contract visibility. |
| Maintainability | 0.5 | Linked support files, parseable scripts, no unresolved targets. |

## Skill Matrix

| Skill | Level | Required | Score | Rating |
| --- | --- | ---: | ---: | --- |
| `adapter-contract-harness` | `python-module` | 9.0 | 10.0 | excellent |
| `architect-pipeline` | `hybrid-harness` | 8.0 | 10.0 | excellent |
| `artifact-render-qa-harness` | `python-module` | 9.0 | 10.0 | excellent |
| `command-hook-policy-harness` | `procedure-policy` | 8.0 | 10.0 | excellent |
| `command-output-harness` | `procedure-policy` | 8.0 | 10.0 | excellent |
| `context-state-harness` | `python-module` | 8.0 | 10.0 | excellent |
| `deliverable-template-quality-harness` | `python-module` | 9.0 | 10.0 | excellent |
| `development-lifecycle-harness` | `procedure-policy` | 8.0 | 10.0 | excellent |
| `domain-orchestration-harness` | `hybrid-harness` | 9.0 | 10.0 | excellent |
| `goal-state-harness` | `python-module` | 9.0 | 10.0 | excellent |
| `guard-policy-harness` | `procedure-policy` | 8.0 | 10.0 | excellent |
| `harness-evaluator` | `python-module` | 8.0 | 10.0 | excellent |
| `health-check-harness` | `hybrid-harness` | 9.0 | 10.0 | excellent |
| `host-agent-orchestration` | `hybrid-harness` | 8.0 | 10.0 | excellent |
| `memory-state-harness` | `python-module` | 9.0 | 10.0 | excellent |
| `orchestration-role-graph` | `python-module` | 9.0 | 10.0 | excellent |
| `parallel-orchestration-harness` | `python-module` | 9.0 | 10.0 | excellent |
| `qa-gate-harness` | `hybrid-harness` | 9.0 | 10.0 | excellent |
| `quality-gates-harness` | `procedure-policy` | 8.0 | 10.0 | excellent |
| `review-gate-harness` | `hybrid-harness` | 9.0 | 10.0 | excellent |
| `role-execution-audit-harness` | `python-module` | 9.0 | 10.0 | excellent |
| `skill-catalog` | `python-module` | 8.0 | 10.0 | excellent |
| `snapshot-state-harness` | `python-module` | 9.0 | 10.0 | excellent |
| `subagent-review-pipeline` | `hybrid-harness` | 9.0 | 10.0 | excellent |
| `token-optimizer` | `procedure-policy` | 9.0 | 10.0 | excellent |
| `traceability-matrix-harness` | `python-module` | 9.0 | 10.0 | excellent |
| `workflow-skill-distiller` | `procedure-policy` | 8.0 | 10.0 | excellent |

## Notes

- This is a local readiness score, not an adoption or popularity score.
- A skill cannot pass by name alone; it needs support files, smoke execution, resolved implementation targets, and test evidence.
- Procedure-policy skills are allowed, but they must still expose clear runtime/procedural evidence paths and failure handling.
- Harness-only quality reports stay in runtime metadata. User-facing deliverables belong under a target project's `docs/` only when the user task actually requires those artifacts.
