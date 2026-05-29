# SIDE Skill Review Round 3

Round 3 focused on runtime gaps that were not visible from catalog or quality-score checks.

## Findings Applied

| Area | Finding | Remediation |
| --- | --- | --- |
| Token and command output | Aggressive compression could drop traceback and line-number facts. | Required-fact preservation now keeps failing test names, traceback, line numbers, assertions, build errors, and exit code even under tight budgets. |
| Token and code minify | Security/license/business comments without a colon could be stripped. | Contract-sensitive detection now covers broader security, license, business-rule, and contract wording. |
| Workflow distiller | Generated smoke checks could fail from a generated skill folder. | Generated smoke checks now locate the repo root from parents, current working directory, or `UAF_REPO_ROOT`, and verify `skills/` refs exist. |
| Traceability | Dict rows from `as_dict=True` could not be evaluated directly. | Deliverable quality now accepts both spreadsheet rows and typed dict traceability rows. |
| Artifact render QA | Fake Office ZIPs could pass with only one XML part. | DOCX/XLSX render checks now require core Office package parts before passing. |
| Deliverable templates | Unknown artifact types could pass because marker lists were empty. | Unknown types now fail unless explicitly exempt or marked template-not-applicable; SVG/DXF drawing artifacts are explicit non-template types. |
| QA role path | Helper blocked empty checks, but role-DAG QA could still pass without checks. | `qa-verifier` now uses explicit QA check records; workflows generate command/browser/task-evidence checks or a scoped no-op `QA-SKIP`. |
| Release blocked detail | Security findings could be lost when release was blocked by dependency. | Blocked release gates now preserve upstream security findings. |
| Role audit | Product strategist and implementer were not audited consistently. | Role audit now requires default role graph roles, including product strategist, and requires implementer when implementation work exists. |
| Adapter contract | Antigravity pending path dropped request memory/evidence metadata. | Pending/native adapter results now preserve memory context, evidence, and portable request metadata. |
| Context handoff | Git state, decisions, and remaining work were not first-class fields. | `HandoffSnapshot` now serializes and renders `git_state`, `decisions`, and `remaining_work`. |
| Harness evaluator | Evaluator returned only a custom dict. | `Evaluator.evaluate_code_result` now returns the standard `HarnessResult` contract. |
| Health audit CLI | `uaf_skill_audit --help` dumped full audit JSON. | `uaf_skill_audit` now has argparse help, `--summary`, and `--skill`. |
| Architect pipeline | Design doc and design-stage/export evidence were split across APIs. | `run_architect_pipeline` now returns design doc, domain/work design, manifest, deliverable exports, quality evidence, and evidence keys together. |

## Verification

- `python -m unittest tests.test_architect_pipeline tests.test_command_policy_runtime tests.test_command_output_runtime tests.test_quality_harnesses tests.test_workflow_distiller_runtime tests.test_handoff tests.test_sandbox tests.test_uaf_skill_audit tests.test_dispatcher tests.test_workflows tests.test_orchestration_roles tests.test_gate_evaluators`
- Result: 110 tests passed.
- `python -m src.skills.uaf_skill_catalog --check`
- Result: 27 valid / 0 invalid.
