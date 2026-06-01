# SIDE Skill Review Round 2

Round 2 reviewed the working tree after the first remediation pass. This audit records practical first-time-user feedback, not the automated packaging `quality_score`.

## Summary

- Reviewed skills: 27
- Average SIDE score before Round 2 remediation: 7.11 / 10
- Strongest current skills: `token-optimizer`, `skill-catalog`, `domain-orchestration-harness`, `orchestration-role-graph`, `parallel-orchestration-harness`, `qa-gate-harness`, `review-gate-harness`
- Weakest current skills: `deliverable-template-quality-harness`, `health-check-harness`, `subagent-review-pipeline`, `architect-pipeline`, `context-state-harness`, `role-execution-audit-harness`
- Repeated theme: smoke checks prove packaging and imports, but first-time users still need runnable examples, concise CLIs, and docs that match exact runtime contracts.

## Score Matrix

| Skill | R2 SIDE score | Good | Bad / inconvenient | R2 remediation |
| --- | ---: | --- | --- | --- |
| `adapter-contract-harness` | 7.0 | Real contracts and dispatcher path. | Docs imply richer fields than dataclasses expose. | Backlog: adapter registration example. |
| `architect-pipeline` | 6.5 | CLI help and `SystemArchitect` exist. | End-to-end design/export path not one clear command; source text has mojibake. | Backlog: end-to-end dry-run/example output. |
| `artifact-render-qa-harness` | 7.0 | Structural DOCX/XLSX/SVG/DXF checks. | Coupled to template quality; missing artifact still emitted template-pass evidence. | Fixed missing-artifact template evidence. |
| `command-hook-policy-harness` | 6.5 | Classifier, guard policy, redaction work. | Not a full hook engine or policy loader. | Backlog: hook decision object/loader. |
| `command-output-harness` | 7.0 | `HarnessResult`, exit code, savings metadata. | Needs command-family filters and preservation checks. | Added command-family filter and required-fact guard. |
| `context-state-harness` | 6.5 | Resume handoff and runtime state exist. | Git state/context-id/restore validation gap. | Backlog. |
| `deliverable-template-quality-harness` | 6.0 | Integrated with deliverable exports. | Mojibake markers and semantic quality weakness. | Fixed contradiction for render failure evidence; marker cleanup remains. |
| `development-lifecycle-harness` | 6.5 | Clear lifecycle policy. | Mostly methodology wrapper. | Backlog: runnable lifecycle transcript. |
| `domain-orchestration-harness` | 8.0 | Strong real profile/design/export path. | API signatures not obvious. | Backlog: 15-line runnable example. |
| `goal-state-harness` | 7.5 | Strong evidence/blocking model. | Exact function signatures and JSON examples missing. | Backlog. |
| `guard-policy-harness` | 6.5 | Direct command/path checks work. | Needs examples and packaging confidence after commit. | Added runtime; commit pending. |
| `harness-evaluator` | 7.0 | Evaluator works directly. | Return contract is dict vs `HarnessResult`. | Backlog. |
| `health-check-harness` | 6.0 | Audit/validator targets exist. | `--help` ran full audit; no compact dashboard. | Added `uaf_skill_quality --help` and `--summary`. |
| `host-agent-orchestration` | 7.0 | Contracts, dispatcher, role graph exist. | External host/subagent proof is limited. | Backlog. |
| `memory-state-harness` | 7.0 | Store/scope/secret tests are strong. | No safe demo CLI. | Backlog. |
| `orchestration-role-graph` | 8.0 | Role orchestrator and parallel waves exist. | Default runner emits placeholder artifacts. | Backlog. |
| `parallel-orchestration-harness` | 8.0 | Bounded worker fan-out exists. | No dry-run adapter. | Backlog. |
| `qa-gate-harness` | 8.0 | Concrete `build_qa_check` and `evaluate_qa_checks`. | Empty checks could pass. | Empty checks now block by default. |
| `quality-gates-harness` | 7.5 | Hybrid gate helpers wired. | Failing-first behavior still host discipline. | Backlog: gate-run object. |
| `review-gate-harness` | 8.0 | Structured findings and review sequence. | Security findings did not block release. | Security findings now fail security/release gates. |
| `role-execution-audit-harness` | 6.5 | Prevents fake role execution claims. | Required role list and artifact checks need alignment. | Backlog. |
| `skill-catalog` | 8.0 | Real CLI, list/check/read work. | `--list` too large; read omits support docs. | Backlog. |
| `snapshot-state-harness` | 7.0 | Real snapshots and external runtime storage. | Rollback returned bool only. | Added `rollback_result` summary. |
| `subagent-review-pipeline` | 6.0 | Role/gate concept clear. | No focused run pipeline API; status mismatch. | Status docs aligned; API remains backlog. |
| `token-optimizer` | 8.5 | Direct API and savings metadata. | No quality-first universal entrypoint; generic truncation can lose pytest facts. | Added `optimize_context_content`, contract passthrough, required-fact guard. |
| `traceability-matrix-harness` | 7.0 | Internal metadata policy good. | Rows were list-only and mostly planned. | Added typed `as_dict=True` row schema and gate status. |
| `workflow-skill-distiller` | 7.5 | Decision/scaffold API exists. | Generated smoke check shallow and execution level fixed. | Added execution-level input and import-resolving smoke scaffold. |

## External Token Feedback Applied

The user provided a separate token-savings test. The key result was that generic `truncate_logs` can save many tokens while losing critical pytest failure facts. Round 2 remediation now makes `summarize_command_output` use command-family filters and required-fact preservation checks, and makes `optimize_context_content` pass through contract-sensitive content such as SQL, stored procedures, license headers, security comments, business rules, and exact source-of-truth prose.

## Fresh Verification After R2 Remediation

- `python -m unittest tests.test_command_output_runtime tests.test_builtin_skill_runtime tests.test_gate_evaluators tests.test_quality_harnesses tests.test_snapshot_manager tests.test_workflow_distiller_runtime tests.test_uaf_skill_quality tests.test_uaf_skill_catalog`
- Result: 60 tests passed.
