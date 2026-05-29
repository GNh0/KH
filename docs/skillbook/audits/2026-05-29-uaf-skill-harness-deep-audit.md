# KH UAF Skill and Harness Deep Audit

This report audits every packaged `skills/<name>/SKILL.md` item as one host-visible skill/harness unit.

## Summary

- Total packaged skills/harnesses: 27
- Overall status: passed
- Execution levels: {"hybrid-harness": 7, "procedure-policy": 7, "python-module": 13}

## Skill Matrix

| Skill | Level | Status | Targets | Test evidence |
| --- | --- | --- | ---: | --- |
| `adapter-contract-harness` | `python-module` | `passed` | 3 | yes |
| `architect-pipeline` | `hybrid-harness` | `passed` | 6 | yes |
| `artifact-render-qa-harness` | `python-module` | `passed` | 4 | yes |
| `command-hook-policy-harness` | `procedure-policy` | `passed` | 5 | yes |
| `command-output-harness` | `procedure-policy` | `passed` | 5 | yes |
| `context-state-harness` | `python-module` | `passed` | 7 | yes |
| `deliverable-template-quality-harness` | `python-module` | `passed` | 5 | yes |
| `development-lifecycle-harness` | `procedure-policy` | `passed` | 5 | yes |
| `domain-orchestration-harness` | `hybrid-harness` | `passed` | 10 | yes |
| `goal-state-harness` | `python-module` | `passed` | 8 | yes |
| `guard-policy-harness` | `procedure-policy` | `passed` | 5 | yes |
| `harness-evaluator` | `python-module` | `passed` | 4 | yes |
| `health-check-harness` | `hybrid-harness` | `passed` | 6 | yes |
| `host-agent-orchestration` | `hybrid-harness` | `passed` | 6 | yes |
| `memory-state-harness` | `python-module` | `passed` | 7 | yes |
| `orchestration-role-graph` | `python-module` | `passed` | 7 | yes |
| `parallel-orchestration-harness` | `python-module` | `passed` | 6 | yes |
| `qa-gate-harness` | `hybrid-harness` | `passed` | 5 | yes |
| `quality-gates-harness` | `procedure-policy` | `passed` | 5 | yes |
| `review-gate-harness` | `hybrid-harness` | `passed` | 7 | yes |
| `role-execution-audit-harness` | `python-module` | `passed` | 5 | yes |
| `skill-catalog` | `python-module` | `passed` | 3 | yes |
| `snapshot-state-harness` | `python-module` | `passed` | 4 | yes |
| `subagent-review-pipeline` | `hybrid-harness` | `passed` | 6 | yes |
| `token-optimizer` | `procedure-policy` | `passed` | 4 | yes |
| `traceability-matrix-harness` | `python-module` | `passed` | 4 | yes |
| `workflow-skill-distiller` | `procedure-policy` | `passed` | 3 | yes |

## Detailed Target Checks

### adapter-contract-harness

- Execution level: `python-module`
- Status: `passed`
- Skill file: `skills/adapter_contract_harness/SKILL.md`

- `src.contracts.AdapterRequest`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.contracts.AdapterResult`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.platforms.dispatcher_factory`: resolved; tests: `tests/test_dispatcher.py`

### architect-pipeline

- Execution level: `hybrid-harness`
- Status: `passed`
- Skill file: `skills/architect_pipeline/SKILL.md`

- `src.core.architect.SystemArchitect`: resolved; tests: `tests/test_builtin_skill_runtime.py`, `tests/test_orchestration_roles.py`, `tests/test_uaf_skill_catalog.py`, `tests/test_workflows.py`
- `src.core.runner`: resolved; tests: `tests/test_browser_qa.py`, `tests/test_check_runners.py`, `tests/test_dispatcher.py`, `tests/test_gate_evaluators.py`, `tests/test_orchestration_roles.py`, `tests/test_runner_config.py`, `tests/test_task_runners.py`, `tests/test_workflows.py`
- `src.orchestration.agent_loop`: resolved; tests: `tests/test_agent_loop.py`, `tests/test_cli_config.py`, `tests/test_contracts.py`, `tests/test_runner_config.py`
- `src.orchestration.deliverable_exports`: resolved; tests: `tests/test_artifact_manifest.py`, `tests/test_quality_harnesses.py`, `tests/test_workflows.py`
- `src.skills.pattern_analyzer`: resolved; tests: `tests/test_builtin_skill_runtime.py`
- `src.skills.license_checker`: resolved; tests: `tests/test_builtin_skill_runtime.py`

### artifact-render-qa-harness

- Execution level: `python-module`
- Status: `passed`
- Skill file: `skills/artifact_render_qa_harness/SKILL.md`

- `src.orchestration.quality_harnesses.evaluate_deliverable_quality`: resolved; tests: `tests/test_quality_harnesses.py`, `tests/test_uaf_skill_catalog.py`
- `src.orchestration.deliverable_exports.export_office_deliverables`: resolved; tests: `tests/test_artifact_manifest.py`, `tests/test_quality_harnesses.py`, `tests/test_workflows.py`
- `tests.test_quality_harnesses`: resolved; tests: `tests/test_quality_harnesses.py`
- `tests.test_artifact_manifest`: resolved; tests: `tests/test_artifact_manifest.py`

### command-hook-policy-harness

- Execution level: `procedure-policy`
- Status: `passed`
- Skill file: `skills/command_hook_policy_harness/SKILL.md`

- `src.contracts.AdapterRequest`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.contracts.AdapterResult`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.platforms.dispatcher_factory`: resolved; tests: `tests/test_dispatcher.py`
- `src.orchestration.agent_loop`: resolved; tests: `tests/test_agent_loop.py`, `tests/test_cli_config.py`, `tests/test_contracts.py`, `tests/test_runner_config.py`
- `src.skills.uaf_skill_catalog`: resolved; tests: `tests/test_plugin_packaging.py`, `tests/test_uaf_skill_audit.py`, `tests/test_uaf_skill_catalog.py`

### command-output-harness

- Execution level: `procedure-policy`
- Status: `passed`
- Skill file: `skills/command_output_harness/SKILL.md`

- `src.skills.token_optimizer`: resolved; tests: `tests/test_builtin_skill_runtime.py`
- `src.skills.uaf_skill_catalog`: resolved; tests: `tests/test_plugin_packaging.py`, `tests/test_uaf_skill_audit.py`, `tests/test_uaf_skill_catalog.py`
- `src.tasks.workflows`: resolved; tests: `tests/test_evidence_producers.py`, `tests/test_workflows.py`
- `src.core.runner`: resolved; tests: `tests/test_browser_qa.py`, `tests/test_check_runners.py`, `tests/test_dispatcher.py`, `tests/test_gate_evaluators.py`, `tests/test_orchestration_roles.py`, `tests/test_runner_config.py`, `tests/test_task_runners.py`, `tests/test_workflows.py`
- `src.contracts.HarnessResult`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`

### context-state-harness

- Execution level: `python-module`
- Status: `passed`
- Skill file: `skills/context_state_harness/SKILL.md`

- `src.core.snapshot_manager`: resolved; tests: `tests/test_snapshot_manager.py`, `tests/test_uaf_skill_catalog.py`
- `src.contracts.AdapterRequest`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.contracts.AdapterResult`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.contracts.HandoffSnapshot`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.contracts.WorkflowDispatchResult`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.orchestration.handoff`: resolved; tests: `tests/test_artifact_manifest.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_handoff.py`, `tests/test_workflows.py`
- `src.orchestration.agent_loop`: resolved; tests: `tests/test_agent_loop.py`, `tests/test_cli_config.py`, `tests/test_contracts.py`, `tests/test_runner_config.py`

### deliverable-template-quality-harness

- Execution level: `python-module`
- Status: `passed`
- Skill file: `skills/deliverable_template_quality_harness/SKILL.md`

- `src.orchestration.quality_harnesses.evaluate_deliverable_quality`: resolved; tests: `tests/test_quality_harnesses.py`, `tests/test_uaf_skill_catalog.py`
- `src.orchestration.deliverable_exports.export_office_deliverables`: resolved; tests: `tests/test_artifact_manifest.py`, `tests/test_quality_harnesses.py`, `tests/test_workflows.py`
- `src.orchestration.artifacts.build_design_stage`: resolved; tests: `tests/test_artifact_manifest.py`, `tests/test_browser_qa.py`, `tests/test_contracts.py`, `tests/test_domain_profiles.py`, `tests/test_handoff.py`, `tests/test_quality_harnesses.py`, `tests/test_workflow_checks.py`, `tests/test_workflows.py`
- `tests.test_quality_harnesses`: resolved; tests: `tests/test_quality_harnesses.py`
- `tests.test_artifact_manifest`: resolved; tests: `tests/test_artifact_manifest.py`

### development-lifecycle-harness

- Execution level: `procedure-policy`
- Status: `passed`
- Skill file: `skills/development_lifecycle_harness/SKILL.md`

- `src.orchestration.agent_loop`: resolved; tests: `tests/test_agent_loop.py`, `tests/test_cli_config.py`, `tests/test_contracts.py`, `tests/test_runner_config.py`
- `src.core.snapshot_manager`: resolved; tests: `tests/test_snapshot_manager.py`, `tests/test_uaf_skill_catalog.py`
- `src.harness.evaluator`: resolved; tests: `tests/test_gate_evaluators.py`, `tests/test_sandbox.py`, `tests/test_uaf_skill_catalog.py`
- `src.tasks.workflows`: resolved; tests: `tests/test_evidence_producers.py`, `tests/test_workflows.py`
- `src.skills.uaf_skill_catalog`: resolved; tests: `tests/test_plugin_packaging.py`, `tests/test_uaf_skill_audit.py`, `tests/test_uaf_skill_catalog.py`

### domain-orchestration-harness

- Execution level: `hybrid-harness`
- Status: `passed`
- Skill file: `skills/domain_orchestration_harness/SKILL.md`

- `src.contracts.DomainProfile`: resolved; tests: `tests/test_artifact_manifest.py`, `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_domain_profiles.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_quality_harnesses.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.contracts.DomainRole`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.contracts.WorkDesign`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.contracts.DesignArtifact`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.contracts.ArtifactManifest`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.orchestration.domain_profiles.DomainProfileBuilder`: resolved; tests: `tests/test_artifact_manifest.py`, `tests/test_domain_profiles.py`, `tests/test_handoff.py`, `tests/test_quality_harnesses.py`
- `src.orchestration.artifacts.ArtifactStore`: resolved; tests: `tests/test_artifact_manifest.py`, `tests/test_browser_qa.py`, `tests/test_contracts.py`, `tests/test_domain_profiles.py`, `tests/test_handoff.py`, `tests/test_quality_harnesses.py`, `tests/test_workflow_checks.py`, `tests/test_workflows.py`
- `src.orchestration.deliverable_exports.export_office_deliverables`: resolved; tests: `tests/test_artifact_manifest.py`, `tests/test_quality_harnesses.py`, `tests/test_workflows.py`
- `src.tasks.workflows.async_project_workflow`: resolved; tests: `tests/test_evidence_producers.py`, `tests/test_workflows.py`
- `skills/domain_orchestration_harness/SKILL.md`: resolved; tests: `tests/test_contracts.py`, `tests/test_docs_branding.py`, `tests/test_plugin_packaging.py`, `tests/test_quality_harnesses.py`, `tests/test_uaf_skill_audit.py`, `tests/test_uaf_skill_catalog.py`, `tests/test_uaf_skill_validator.py`

### goal-state-harness

- Execution level: `python-module`
- Status: `passed`
- Skill file: `skills/goal_state_harness/SKILL.md`

- `src.contracts.GoalState`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_uaf_skill_catalog.py`, `tests/test_workflows.py`
- `src.orchestration.goal_evidence`: resolved; tests: `tests/test_evidence_producers.py`, `tests/test_gate_evaluators.py`, `tests/test_goal_evidence.py`, `tests/test_orchestration_roles.py`, `tests/test_workflows.py`
- `src.orchestration.goal_ledger`: resolved; tests: `tests/test_dispatcher.py`, `tests/test_goal_ledger.py`, `tests/test_handoff.py`, `tests/test_workflows.py`
- `src.orchestration.handoff`: resolved; tests: `tests/test_artifact_manifest.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_handoff.py`, `tests/test_workflows.py`
- `src.orchestration.agent_loop`: resolved; tests: `tests/test_agent_loop.py`, `tests/test_cli_config.py`, `tests/test_contracts.py`, `tests/test_runner_config.py`
- `src.platforms.dispatcher_factory`: resolved; tests: `tests/test_dispatcher.py`
- `src.tasks.workflows`: resolved; tests: `tests/test_evidence_producers.py`, `tests/test_workflows.py`
- `src.contracts.WorkflowDispatchResult`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`

### guard-policy-harness

- Execution level: `procedure-policy`
- Status: `passed`
- Skill file: `skills/guard_policy_harness/SKILL.md`

- `src.harness.sandbox`: resolved; tests: `tests/test_contracts.py`, `tests/test_sandbox.py`
- `src.platforms.dispatcher_factory`: resolved; tests: `tests/test_dispatcher.py`
- `src.contracts.AdapterRequest`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.contracts.AdapterResult`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `skills/command_hook_policy_harness/SKILL.md`: resolved; tests: `tests/test_contracts.py`, `tests/test_docs_branding.py`, `tests/test_plugin_packaging.py`, `tests/test_quality_harnesses.py`, `tests/test_uaf_skill_audit.py`, `tests/test_uaf_skill_catalog.py`, `tests/test_uaf_skill_validator.py`

### harness-evaluator

- Execution level: `python-module`
- Status: `passed`
- Skill file: `skills/harness_evaluator/SKILL.md`

- `src.harness.evaluator.Evaluator`: resolved; tests: `tests/test_gate_evaluators.py`, `tests/test_sandbox.py`, `tests/test_uaf_skill_catalog.py`
- `src.harness.sandbox.CodeSandbox`: resolved; tests: `tests/test_contracts.py`, `tests/test_sandbox.py`
- `src.core.runner`: resolved; tests: `tests/test_browser_qa.py`, `tests/test_check_runners.py`, `tests/test_dispatcher.py`, `tests/test_gate_evaluators.py`, `tests/test_orchestration_roles.py`, `tests/test_runner_config.py`, `tests/test_task_runners.py`, `tests/test_workflows.py`
- `src.contracts.HarnessResult`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`

### health-check-harness

- Execution level: `hybrid-harness`
- Status: `passed`
- Skill file: `skills/health_check_harness/SKILL.md`

- `src.skills.uaf_skill_validator`: resolved; tests: `tests/test_uaf_skill_validator.py`
- `src.skills.uaf_skill_catalog`: resolved; tests: `tests/test_plugin_packaging.py`, `tests/test_uaf_skill_audit.py`, `tests/test_uaf_skill_catalog.py`
- `src.skills.uaf_skill_audit`: resolved; tests: `tests/test_uaf_skill_audit.py`
- `src.harness.evaluator`: resolved; tests: `tests/test_gate_evaluators.py`, `tests/test_sandbox.py`, `tests/test_uaf_skill_catalog.py`
- `src.contracts.HarnessResult`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `tests`: resolved; tests: `tests/test_agent_loop.py`, `tests/test_app_bridge.py`, `tests/test_artifact_manifest.py`, `tests/test_browser_qa.py`, `tests/test_builtin_skill_runtime.py`, `tests/test_check_runners.py`, `tests/test_cli_config.py`, `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_docs_branding.py`, `tests/test_domain_profiles.py`, `tests/test_evidence_producers.py`, `tests/test_extension_registry.py`, `tests/test_file_ops.py`, `tests/test_gate_evaluators.py`, `tests/test_goal_evidence.py`, `tests/test_goal_ledger.py`, `tests/test_handoff.py`, `tests/test_llm_router.py`, `tests/test_memory_contracts.py`, `tests/test_memory_state.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_plugin_packaging.py`, `tests/test_quality_harnesses.py`, `tests/test_runner_config.py`, `tests/test_sandbox.py`, `tests/test_skill_catalog.py`, `tests/test_snapshot_manager.py`, `tests/test_task_runners.py`, `tests/test_uaf_skill_audit.py`, `tests/test_uaf_skill_catalog.py`, `tests/test_uaf_skill_validator.py`, `tests/test_workflow_checks.py`, `tests/test_workflows.py`

### host-agent-orchestration

- Execution level: `hybrid-harness`
- Status: `passed`
- Skill file: `skills/host_agent_orchestration/SKILL.md`

- `src.contracts.AdapterRequest`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.contracts.AdapterResult`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.orchestration.roles`: resolved; tests: `tests/test_app_bridge.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_domain_profiles.py`, `tests/test_orchestration_roles.py`, `tests/test_quality_harnesses.py`, `tests/test_workflows.py`
- `src.platforms.dispatcher_factory`: resolved; tests: `tests/test_dispatcher.py`
- `src.orchestration.agent_loop`: resolved; tests: `tests/test_agent_loop.py`, `tests/test_cli_config.py`, `tests/test_contracts.py`, `tests/test_runner_config.py`
- `src.skills.uaf_skill_catalog`: resolved; tests: `tests/test_plugin_packaging.py`, `tests/test_uaf_skill_audit.py`, `tests/test_uaf_skill_catalog.py`

### memory-state-harness

- Execution level: `python-module`
- Status: `passed`
- Skill file: `skills/memory_state_harness/SKILL.md`

- `src.contracts.MemoryScope`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_state.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.contracts.MemoryRecord`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.contracts.MemoryEvent`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.orchestration.memory_state`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_memory_state.py`, `tests/test_memory_store.py`, `tests/test_workflows.py`
- `src.orchestration.memory_store`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_memory_store.py`, `tests/test_workflows.py`
- `src.platforms.codex_thread_registry`: resolved; tests: `tests/test_codex_thread_registry.py`
- `src.tasks.workflows`: resolved; tests: `tests/test_evidence_producers.py`, `tests/test_workflows.py`

### orchestration-role-graph

- Execution level: `python-module`
- Status: `passed`
- Skill file: `skills/orchestration_role_graph/SKILL.md`

- `src.orchestration.roles`: resolved; tests: `tests/test_app_bridge.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_domain_profiles.py`, `tests/test_orchestration_roles.py`, `tests/test_quality_harnesses.py`, `tests/test_workflows.py`
- `src.orchestration.role_orchestrator`: resolved; tests: `tests/test_orchestration_roles.py`
- `src.orchestration.agent_loop`: resolved; tests: `tests/test_agent_loop.py`, `tests/test_cli_config.py`, `tests/test_contracts.py`, `tests/test_runner_config.py`
- `src.platforms.dispatcher_factory`: resolved; tests: `tests/test_dispatcher.py`
- `src.tasks.workflows`: resolved; tests: `tests/test_evidence_producers.py`, `tests/test_workflows.py`
- `src.contracts.AdapterRequest`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.contracts.AdapterResult`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`

### parallel-orchestration-harness

- Execution level: `python-module`
- Status: `passed`
- Skill file: `skills/parallel_orchestration_harness/SKILL.md`

- `src.orchestration.role_orchestrator`: resolved; tests: `tests/test_orchestration_roles.py`
- `src.orchestration.agent_loop`: resolved; tests: `tests/test_agent_loop.py`, `tests/test_cli_config.py`, `tests/test_contracts.py`, `tests/test_runner_config.py`
- `src.tasks.workflows`: resolved; tests: `tests/test_evidence_producers.py`, `tests/test_workflows.py`
- `src.contracts.AdapterRequest`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.contracts.AdapterResult`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.contracts.WorkflowTaskResult`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`

### qa-gate-harness

- Execution level: `hybrid-harness`
- Status: `passed`
- Skill file: `skills/qa_gate_harness/SKILL.md`

- `src.harness.evaluator`: resolved; tests: `tests/test_gate_evaluators.py`, `tests/test_sandbox.py`, `tests/test_uaf_skill_catalog.py`
- `src.harness.sandbox`: resolved; tests: `tests/test_contracts.py`, `tests/test_sandbox.py`
- `src.orchestration.roles`: resolved; tests: `tests/test_app_bridge.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_domain_profiles.py`, `tests/test_orchestration_roles.py`, `tests/test_quality_harnesses.py`, `tests/test_workflows.py`
- `src.contracts.WorkflowDispatchResult`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `tests`: resolved; tests: `tests/test_agent_loop.py`, `tests/test_app_bridge.py`, `tests/test_artifact_manifest.py`, `tests/test_browser_qa.py`, `tests/test_builtin_skill_runtime.py`, `tests/test_check_runners.py`, `tests/test_cli_config.py`, `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_docs_branding.py`, `tests/test_domain_profiles.py`, `tests/test_evidence_producers.py`, `tests/test_extension_registry.py`, `tests/test_file_ops.py`, `tests/test_gate_evaluators.py`, `tests/test_goal_evidence.py`, `tests/test_goal_ledger.py`, `tests/test_handoff.py`, `tests/test_llm_router.py`, `tests/test_memory_contracts.py`, `tests/test_memory_state.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_plugin_packaging.py`, `tests/test_quality_harnesses.py`, `tests/test_runner_config.py`, `tests/test_sandbox.py`, `tests/test_skill_catalog.py`, `tests/test_snapshot_manager.py`, `tests/test_task_runners.py`, `tests/test_uaf_skill_audit.py`, `tests/test_uaf_skill_catalog.py`, `tests/test_uaf_skill_validator.py`, `tests/test_workflow_checks.py`, `tests/test_workflows.py`

### quality-gates-harness

- Execution level: `procedure-policy`
- Status: `passed`
- Skill file: `skills/quality_gates_harness/SKILL.md`

- `src.harness.evaluator`: resolved; tests: `tests/test_gate_evaluators.py`, `tests/test_sandbox.py`, `tests/test_uaf_skill_catalog.py`
- `src.harness.sandbox`: resolved; tests: `tests/test_contracts.py`, `tests/test_sandbox.py`
- `src.core.runner`: resolved; tests: `tests/test_browser_qa.py`, `tests/test_check_runners.py`, `tests/test_dispatcher.py`, `tests/test_gate_evaluators.py`, `tests/test_orchestration_roles.py`, `tests/test_runner_config.py`, `tests/test_task_runners.py`, `tests/test_workflows.py`
- `tests`: resolved; tests: `tests/test_agent_loop.py`, `tests/test_app_bridge.py`, `tests/test_artifact_manifest.py`, `tests/test_browser_qa.py`, `tests/test_builtin_skill_runtime.py`, `tests/test_check_runners.py`, `tests/test_cli_config.py`, `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_docs_branding.py`, `tests/test_domain_profiles.py`, `tests/test_evidence_producers.py`, `tests/test_extension_registry.py`, `tests/test_file_ops.py`, `tests/test_gate_evaluators.py`, `tests/test_goal_evidence.py`, `tests/test_goal_ledger.py`, `tests/test_handoff.py`, `tests/test_llm_router.py`, `tests/test_memory_contracts.py`, `tests/test_memory_state.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_plugin_packaging.py`, `tests/test_quality_harnesses.py`, `tests/test_runner_config.py`, `tests/test_sandbox.py`, `tests/test_skill_catalog.py`, `tests/test_snapshot_manager.py`, `tests/test_task_runners.py`, `tests/test_uaf_skill_audit.py`, `tests/test_uaf_skill_catalog.py`, `tests/test_uaf_skill_validator.py`, `tests/test_workflow_checks.py`, `tests/test_workflows.py`
- `src.skills.uaf_skill_catalog`: resolved; tests: `tests/test_plugin_packaging.py`, `tests/test_uaf_skill_audit.py`, `tests/test_uaf_skill_catalog.py`

### review-gate-harness

- Execution level: `hybrid-harness`
- Status: `passed`
- Skill file: `skills/review_gate_harness/SKILL.md`

- `src.orchestration.roles`: resolved; tests: `tests/test_app_bridge.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_domain_profiles.py`, `tests/test_orchestration_roles.py`, `tests/test_quality_harnesses.py`, `tests/test_workflows.py`
- `src.orchestration.gate_evaluators`: resolved; tests: `tests/test_gate_evaluators.py`
- `src.orchestration.evidence_producers`: resolved; tests: `tests/test_evidence_producers.py`, `tests/test_gate_evaluators.py`
- `src.contracts.WorkflowDispatchResult`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.contracts.WorkflowTaskResult`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.platforms.dispatcher_factory`: resolved; tests: `tests/test_dispatcher.py`
- `tests`: resolved; tests: `tests/test_agent_loop.py`, `tests/test_app_bridge.py`, `tests/test_artifact_manifest.py`, `tests/test_browser_qa.py`, `tests/test_builtin_skill_runtime.py`, `tests/test_check_runners.py`, `tests/test_cli_config.py`, `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_docs_branding.py`, `tests/test_domain_profiles.py`, `tests/test_evidence_producers.py`, `tests/test_extension_registry.py`, `tests/test_file_ops.py`, `tests/test_gate_evaluators.py`, `tests/test_goal_evidence.py`, `tests/test_goal_ledger.py`, `tests/test_handoff.py`, `tests/test_llm_router.py`, `tests/test_memory_contracts.py`, `tests/test_memory_state.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_plugin_packaging.py`, `tests/test_quality_harnesses.py`, `tests/test_runner_config.py`, `tests/test_sandbox.py`, `tests/test_skill_catalog.py`, `tests/test_snapshot_manager.py`, `tests/test_task_runners.py`, `tests/test_uaf_skill_audit.py`, `tests/test_uaf_skill_catalog.py`, `tests/test_uaf_skill_validator.py`, `tests/test_workflow_checks.py`, `tests/test_workflows.py`

### role-execution-audit-harness

- Execution level: `python-module`
- Status: `passed`
- Skill file: `skills/role_execution_audit_harness/SKILL.md`

- `src.orchestration.quality_harnesses.audit_role_execution`: resolved; tests: `tests/test_quality_harnesses.py`, `tests/test_uaf_skill_catalog.py`
- `src.orchestration.role_orchestrator.RoleOrchestrator`: resolved; tests: `tests/test_orchestration_roles.py`
- `src.tasks.workflows.dispatch_project_workflow`: resolved; tests: `tests/test_evidence_producers.py`, `tests/test_workflows.py`
- `tests.test_quality_harnesses`: resolved; tests: `tests/test_quality_harnesses.py`
- `tests.test_workflows`: resolved; tests: `tests/test_workflows.py`

### skill-catalog

- Execution level: `python-module`
- Status: `passed`
- Skill file: `skills/skill_catalog/SKILL.md`

- `skills/<skill-name>/SKILL.md`: template; tests: none
- `src.skills.uaf_skill_catalog`: resolved; tests: `tests/test_plugin_packaging.py`, `tests/test_uaf_skill_audit.py`, `tests/test_uaf_skill_catalog.py`
- `src.skills.catalog`: resolved; tests: `tests/test_plugin_packaging.py`, `tests/test_skill_catalog.py`, `tests/test_uaf_skill_audit.py`, `tests/test_uaf_skill_catalog.py`

### snapshot-state-harness

- Execution level: `python-module`
- Status: `passed`
- Skill file: `skills/snapshot_state_harness/SKILL.md`

- `src.core.snapshot_manager.SnapshotManager`: resolved; tests: `tests/test_snapshot_manager.py`, `tests/test_uaf_skill_catalog.py`
- `src.orchestration.agent_loop`: resolved; tests: `tests/test_agent_loop.py`, `tests/test_cli_config.py`, `tests/test_contracts.py`, `tests/test_runner_config.py`
- `src.harness.sandbox`: resolved; tests: `tests/test_contracts.py`, `tests/test_sandbox.py`
- `tests.test_snapshot_manager`: resolved; tests: `tests/test_snapshot_manager.py`

### subagent-review-pipeline

- Execution level: `hybrid-harness`
- Status: `passed`
- Skill file: `skills/subagent_review_pipeline/SKILL.md`

- `src.tasks.workflows`: resolved; tests: `tests/test_evidence_producers.py`, `tests/test_workflows.py`
- `src.orchestration.roles`: resolved; tests: `tests/test_app_bridge.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_domain_profiles.py`, `tests/test_orchestration_roles.py`, `tests/test_quality_harnesses.py`, `tests/test_workflows.py`
- `src.orchestration.agent_loop`: resolved; tests: `tests/test_agent_loop.py`, `tests/test_cli_config.py`, `tests/test_contracts.py`, `tests/test_runner_config.py`
- `src.contracts.AdapterRequest`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.contracts.AdapterResult`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `src.skills.uaf_skill_catalog`: resolved; tests: `tests/test_plugin_packaging.py`, `tests/test_uaf_skill_audit.py`, `tests/test_uaf_skill_catalog.py`

### token-optimizer

- Execution level: `procedure-policy`
- Status: `passed`
- Skill file: `skills/token_optimizer/SKILL.md`

- `src.skills.token_optimizer`: resolved; tests: `tests/test_builtin_skill_runtime.py`
- `src.skills.catalog`: resolved; tests: `tests/test_plugin_packaging.py`, `tests/test_skill_catalog.py`, `tests/test_uaf_skill_audit.py`, `tests/test_uaf_skill_catalog.py`
- `src.skills.uaf_skill_catalog`: resolved; tests: `tests/test_plugin_packaging.py`, `tests/test_uaf_skill_audit.py`, `tests/test_uaf_skill_catalog.py`
- `src.contracts.HarnessResult`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`

### traceability-matrix-harness

- Execution level: `python-module`
- Status: `passed`
- Skill file: `skills/traceability_matrix_harness/SKILL.md`

- `src.orchestration.quality_harnesses.build_traceability_matrix_rows`: resolved; tests: `tests/test_quality_harnesses.py`, `tests/test_uaf_skill_catalog.py`
- `src.orchestration.quality_harnesses.evaluate_deliverable_quality`: resolved; tests: `tests/test_quality_harnesses.py`, `tests/test_uaf_skill_catalog.py`
- `src.contracts.WorkDesign`: resolved; tests: `tests/test_codex_thread_registry.py`, `tests/test_contracts.py`, `tests/test_dispatcher.py`, `tests/test_evidence_producers.py`, `tests/test_handoff.py`, `tests/test_memory_contracts.py`, `tests/test_memory_store.py`, `tests/test_orchestration_roles.py`, `tests/test_sandbox.py`, `tests/test_workflows.py`
- `tests.test_quality_harnesses`: resolved; tests: `tests/test_quality_harnesses.py`

### workflow-skill-distiller

- Execution level: `procedure-policy`
- Status: `passed`
- Skill file: `skills/workflow_skill_distiller/SKILL.md`

- `skills/<skill-name>/SKILL.md`: template; tests: none
- `src.skills.catalog`: resolved; tests: `tests/test_plugin_packaging.py`, `tests/test_skill_catalog.py`, `tests/test_uaf_skill_audit.py`, `tests/test_uaf_skill_catalog.py`
- `src.skills.uaf_skill_catalog`: resolved; tests: `tests/test_plugin_packaging.py`, `tests/test_uaf_skill_audit.py`, `tests/test_uaf_skill_catalog.py`
