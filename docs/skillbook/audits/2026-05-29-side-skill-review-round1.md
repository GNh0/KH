# SIDE Skill Review Round 1

This audit records blind SIDE review feedback for all packaged KH UAF skills/harnesses. It is separate from the automated `quality_score`, which only checks packaging, target resolution, support files, smoke scripts, and local test evidence. SIDE scores represent practical usability from a fresh reviewer perspective.

## Summary

- Reviewed skills: 27
- Average SIDE score: 6.96 / 10
- Highest score: 9.0 (`goal-state-harness`)
- Lowest score: 4.0 (`command-hook-policy-harness`)
- Main problem: several skills passed automated checks while still feeling procedural, generic, or weakly executable.
- Round 1 remediation started: command policy runtime, command output runtime, token optimizer contract, and workflow distiller runtime were implemented with tests.

## Score Matrix

| Skill | SIDE score | Good points | Bad or inconvenient points | Round 1 action |
| --- | ---: | --- | --- | --- |
| `adapter-contract-harness` | 7.0 | Real adapter contracts and dispatcher exist. | Metadata schema and adapter-add examples are thin. | Backlog. |
| `architect-pipeline` | 7.0 | `SystemArchitect` and design/export path exist. | End-to-end artifact example is not concrete enough. | Backlog. |
| `artifact-render-qa-harness` | 8.0 | DOCX/XLSX/SVG/DXF structural checks exist. | No standalone render QA entrypoint; not true visual Office render. | Backlog. |
| `command-hook-policy-harness` | 4.0 | Policy direction is useful. | No executable command classifier or hook decision contract. | Added `src.skills.command_policy` and tests. |
| `command-output-harness` | 5.0 | `truncate_logs` keeps failure context. | No command result wrapper, size metadata, or exit-code contract. | Added `summarize_command_output` and tests. |
| `context-state-harness` | 6.0 | `ResumeHandoff` writes JSON/MD state. | Git state and restore validation are unclear. | Backlog. |
| `deliverable-template-quality-harness` | 8.0 | Template marker checks and tests exist. | Semantic quality is still shallow. | Backlog. |
| `development-lifecycle-harness` | 7.0 | Lifecycle direction is clear. | No dedicated lifecycle engine; examples are templated. | Backlog. |
| `domain-orchestration-harness` | 8.0 | `DomainProfile`, `WorkDesign`, artifacts, exports are real. | Minimal execution path is hard to find. | Backlog. |
| `goal-state-harness` | 9.0 | Strongest state/evidence contract. | Needs more JSON examples for blocked/success cases. | Backlog. |
| `guard-policy-harness` | 6.0 | Safety trigger is useful. | Destructive approval and path boundary engine were missing. | Added command policy boundary checks and tests. |
| `harness-evaluator` | 7.0 | Sandbox/evaluator behavior exists. | Return contract and safe snippet/project modes need clarity. | Backlog. |
| `health-check-harness` | 6.0 | Quality dashboard direction is useful. | Release readiness is too tied to packaged skill checks. | Backlog. |
| `host-agent-orchestration` | 8.0 | Adapter, dispatcher, role graph are connected. | Host-specific lifecycle details remain broad. | Backlog. |
| `memory-state-harness` | 8.0 | Scope, store, secret block, tests exist. | Example call flow is too abstract. | Backlog. |
| `orchestration-role-graph` | 7.0 | Role DAG and wave tests exist. | Too many roles; real expert behavior is not obvious. | Backlog. |
| `parallel-orchestration-harness` | 7.5 | Async worker fan-out/fan-in exists. | Worker limit and failure aggregation examples need depth. | Backlog. |
| `qa-gate-harness` | 6.0 | QA gate concept is clear. | Mostly evidence presence; browser/manual QA details are weak. | Backlog. |
| `quality-gates-harness` | 5.5 | Quality workflow intent is useful. | Feels procedural and overlaps other gates. | Backlog. |
| `review-gate-harness` | 6.5 | Structured review status exists. | Not enough diff/code finding examples. | Backlog. |
| `role-execution-audit-harness` | 8.0 | Concrete role artifact/wave audit exists. | Required role rationale needs clarity. | Backlog. |
| `skill-catalog` | 7.0 | Catalog CLI and execution levels are useful. | CLI examples and add-vs-validate boundary are thin. | Backlog. |
| `snapshot-state-harness` | 8.0 | SnapshotManager and rollback tests exist. | `commit_many` and restore summary examples need depth. | Backlog. |
| `subagent-review-pipeline` | 6.0 | Role review direction is useful. | Status naming and actual dispatch I/O are unclear. | Backlog. |
| `token-optimizer` | 6.5 | Log truncation and code minification are useful. | No HarnessResult wrapper or savings metadata. | Added `summarize_command_output`; fixed mojibake in runtime module. |
| `traceability-matrix-harness` | 7.0 | Evidence/deliverable mapping exists. | Row schema and requirement ID lifecycle need clarity. | Backlog. |
| `workflow-skill-distiller` | 5.0 | Trigger concept is right. | Too templated; no distillation decision API or scaffold. | Added distiller decision/scaffold module and tests. |

## Reviewer Experience Themes

### Good

- Core state, goal, memory, role, deliverable, and artifact modules are real enough to build workflows on.
- The repo has broad packaged skill coverage and smoke checks.
- Some modules, especially `goal-state-harness`, `domain-orchestration-harness`, `snapshot-state-harness`, and render/template quality checks, are already usable.

### Bad

- Automated quality scores were too optimistic because they rewarded support-file presence and importable targets more than practical execution depth.
- Several skills used generic support-file wording, so first-time users could not quickly see exact commands, inputs, outputs, and failure examples.
- Some skills claimed executable behavior while relying on procedure-only policy text.

### Inconvenient

- Execution level was not always honest enough for a new user.
- Examples repeated the same generic workflow instead of showing a real call and expected result.
- When something is “applied procedurally,” users need explicit evidence language so it is not mistaken for a module run.

## Round 1 Remediation Evidence

- `src.skills.command_policy.classify_command`
- `src.skills.command_policy.evaluate_guard_policy`
- `src.skills.command_policy.evaluate_write_boundary`
- `src.skills.token_optimizer.summarize_command_output`
- `src.skills.workflow_distiller.should_distill_workflow`
- `src.skills.workflow_distiller.build_skill_scaffold`
- `tests.test_command_policy_runtime`
- `tests.test_command_output_runtime`
- `tests.test_workflow_distiller_runtime`

## Next Review Loop

Run a new SIDE review after Round 1 changes and compare practical usability, especially for:

- command hook policy
- guard policy
- command output
- token optimizer
- workflow skill distiller
- quality/QA/review gate cluster

## External Token-Savings Test Feedback

An additional user-run SIDE test compared `token-optimizer.truncate_logs` against command-family output filtering on synthetic pytest, msbuild, agent trace, and Python-minify samples. The important result was that generic `truncate_logs` saved about 95% on a 609-line pytest log but lost critical failure facts because many `PASSED` `.py::` lines consumed the critical budget. Command-family filtering preserved the failure test name, file/line, assertion, actual/expected value, and exit code while saving more tokens.

Round 2 remediation added:

- `src.skills.token_optimizer.filter_command_output`
- `src.skills.token_optimizer.optimize_context_content`
- `src.skills.token_optimizer.is_contract_sensitive_text`
- command-family detection for test and build logs
- required-fact preservation checks with append/fallback behavior
- passthrough behavior for SQL, stored procedures, license headers, security comments, business rules, and contract-sensitive source text
- regression tests for pytest bulk pass logs, msbuild errors, SQL passthrough, and Python security/license comment passthrough
