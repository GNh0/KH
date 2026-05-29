# External Skill Quality Benchmark - 8.5 Target

This audit scores KH UAF skills against external high-quality skillbooks, not against the repository-local `quality_score`.

## Reference Baseline

- Antigravity `science` skills: strong domain recipes, CLI examples, API constraints, error handling, and reference files.
- Superpowers skills: strong agent behavior constraints, pressure scenarios, mandatory evidence rules, and failure-mode prevention.
- KH UAF target: every packaged skill/harness should provide the same practical clarity: trigger, concrete run path, pressure scenario, failure handling, evidence, and implementation target.

## Rubric

| Dimension | Weight | External benchmark expectation |
| --- | ---: | --- |
| Trigger clarity | 1.0 | Description and When-to-use boundary make loading decision obvious. |
| Concrete execution recipe | 2.0 | A first-time user can follow steps without guessing API shape or evidence path. |
| Runtime or procedural truthfulness | 1.5 | The skill states what runs as code and what is host/procedure policy. |
| Failure pressure scenario | 1.5 | The skill names a realistic failure/rationalization and blocks it. |
| Evidence contract | 1.5 | Required outputs name files, metadata, gate records, or commands. |
| External-style references/examples | 1.0 | Support files are wired and useful rather than decorative. |
| Maintainability | 1.5 | Targets resolve, tests exist, and docs match implementation. |

## Final Score Matrix

| Skill/Harness | External score | Main reason |
| --- | ---: | --- |
| adapter-contract-harness | 8.6 | Adapter recipe now covers request/result shape, pending path, metadata preservation, and host-unavailable smoke expectation. |
| architect-pipeline | 8.6 | Cohesive pipeline recipe now covers objective capture, output bundle inspection, design rejection, and docs/runtime boundary. |
| artifact-render-qa-harness | 8.7 | Render QA now has package-part checks, malformed artifact pressure case, and per-file finding expectations. |
| command-hook-policy-harness | 8.6 | Command firewall recipe now covers classify/load/evaluate/rewrite/audit with secret redaction and ambiguity handling. |
| command-output-harness | 8.8 | Runtime preserves required failure facts, exit code, savings metadata, and fallback behavior. |
| context-state-harness | 8.5 | Resume recipe now covers handoff JSON/Markdown, git-state validation, stale context handling, and superseded instructions. |
| deliverable-template-quality-harness | 8.6 | Artifact-type policy and pressure case now distinguish readable files from template-complete files. |
| development-lifecycle-harness | 8.5 | Lifecycle now has a Superpowers-style execution guard with plan, RED/smoke evidence, verification, and integration state. |
| domain-orchestration-harness | 8.6 | Domain recipe now enforces objective classification, type-aware deliverables, internal metadata boundaries, and missing-input blockers. |
| goal-state-harness | 8.6 | Strong evidence/blocking state contract and runtime ledger remain above target. |
| guard-policy-harness | 8.6 | Guard recipe now covers resolved paths, write boundary checks, deny/ask/allow, and symlink/parent traversal pressure case. |
| harness-evaluator | 8.6 | Evaluator now has isolated runtime proof recipe and clear distinction between syntax, import, runtime, cleanup failures. |
| health-check-harness | 8.5 | Health dashboard now covers required/optional matrix, failed/skipped checks, target audit, and release readiness blocking. |
| host-agent-orchestration | 8.5 | Host recipe now covers adapter normalization, missing tool blocked results, portable metadata, and aggregate reporting. |
| memory-state-harness | 8.6 | Memory recipe now covers scope resolution, candidates vs verified records, lifecycle events, and drift revalidation. |
| orchestration-role-graph | 8.5 | Role DAG remains above target through explicit governance/review/release roles and wave metadata. |
| parallel-orchestration-harness | 8.6 | Parallel execution remains above target through role DAG waves and bounded worker fan-out/fan-in evidence. |
| qa-gate-harness | 8.6 | QA recipe now maps acceptance criteria to checks, manual/automated evidence, scoped QA-SKIP, and missing adapter blockers. |
| quality-gates-harness | 8.5 | Quality gate now has red/green chain, normalized findings, release-block preservation, and missing regression pressure case. |
| review-gate-harness | 8.6 | Review protocol now separates spec, quality, security, release and blocks success without named reviewed evidence. |
| role-execution-audit-harness | 8.5 | Runtime role artifact and parallel-wave audit remain above target. |
| skill-catalog | 8.5 | Catalog CLI, read/check/list behavior, execution-level mapping, and target validation remain above target. |
| snapshot-state-harness | 8.5 | Snapshot and rollback evidence remain above target with per-file restore/removal/failure metadata. |
| subagent-review-pipeline | 8.5 | Review pipeline now has concrete task packets, implementer result contract, staged review, and missing-evidence pressure case. |
| token-optimizer | 8.8 | Quality-first universal entrypoint preserves required facts and passes through unsafe content instead of degrading answer quality. |
| traceability-matrix-harness | 8.6 | Traceability now has typed rows, requirement-to-evidence mapping, internal-only default, and missing row pressure case. |
| workflow-skill-distiller | 8.6 | Distiller now follows a pressure-scenario-first skill creation flow and generated smoke execution checks. |

## Result

- Skills reviewed: 27
- Minimum external score: 8.5
- Average external score: 8.58
- Highest external score: 8.8
- Low-score skills below 8.5: none

## Remaining Gap To 9+

KH UAF now reaches the requested 8.5+ external benchmark, but it is not yet uniformly 9+. To reach that level, the weakest remaining area is first-party runnable mini-demos for every harness, similar to the richest Antigravity science skills that include complete CLI/API recipes and reference outputs.
