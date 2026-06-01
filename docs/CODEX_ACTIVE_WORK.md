# Codex Active Work Ledger

This file is the repo-local working ledger for Codex sessions on UAF.
Read it first after context compaction, a new session, or any long pause.

## Update Rule

- Update this file before starting a substantial new UAF task.
- Update it after completing a substantial task or changing the recommended next step.
- Do not delete completed context that explains the current direction; move it to `Completed`.
- Keep the active section short enough to scan in under a minute.

## Current Objective

Make UAF a domain-general, evidence-driven orchestration framework while preserving the Python core and adding TypeScript only where it clearly helps.

## Current Verified State

- Latest active correction after 2.9.26 audit follow-up:
  - Problem: a host can list KH skills but still fail to use them because it reads stale plugin cache paths or starts source work without a single executable intake step.
  - Runtime fix: `src.orchestration.kh_front_door` now provides `python -m src.orchestration.kh_front_door --prompt "<user request>" --project "<target project>" --host codex --summary`.
  - The front door resolves repo-local or latest installed cache skills, flags stale host-provided KH skill paths, runs plugin composition and request classification, returns recommended skills, and separates runtime-applied front-door modules from skills selected for later execution.
  - Audit fix: `session-skill-audit` treats the front-door command as valid front-door evidence and exposes `runtime_applied_skills` separately from passive observed skills.
- Latest active correction for 2.9.26:
  - Problem: session `019e8078-4bde-7813-a1db-5025a3881511` explicitly requested KH plugin usage for `C_KONE110_codex`, but source/work commands started before KH front-door routing evidence.
  - Product rule: users should not need to name every KH skill/harness. A request to use KH, KH UAF, KH plugin, KH skills/harnesses, or `/kh:*` must trigger front-door auto routing first.
  - Front-door evidence means root guide or skill catalog inspection, `plugin-composition-policy`, `request-complexity-router`, automatic minimal skill bundle selection, and selected/considered/skipped/blocked evidence before source reads or edits.
  - `src.orchestration.session_skill_audit` now emits P1 `plugin-composition-policy/missing_front_door` when that contract is violated.
  - Audit record: `docs/kh/qa/2026-06-01-front-door-routing-audit.md`.
  - Branching note: `main` keeps tests/docs/audits; Codex marketplace installs runtime behavior from `codex-runtime`, so runtime prompt/code changes must be applied there too.
  - Verification: targeted unit tests passed (39 and 42 tests), full `python -B -m unittest discover -s tests` passed (469 tests), catalog check 38/38, skill quality lowest 9.3, practical quality gate release-ready with 8/8 KH-Bench tasks and confidence 10.0, JSON manifests valid, diff check clean.
- Repository: `GNh0/KH`, local path `C:\Users\User\Documents\Codex\KH`.
- Core direction approved by user: improve incrementally, taking useful ideas from external references while keeping KH/UAF branded as a personal skillbook.
- Python core should remain the stable center for now.
- TypeScript is best treated as a future sidecar for browser adapters, dashboards, and skill/template tooling.
- Latest verification after large-work orchestration bundle 2.9.9:
  - `python -m json.tool plugin.json`
  - `python -m json.tool .codex-plugin/plugin.json`
  - `python -m unittest tests.test_large_work_orchestration_bundle tests.test_request_classifier tests.test_goal_skill_integration tests.test_superpowers_benchmark_alignment tests.test_plugin_packaging` (62 tests)
  - `python -m src.skills.uaf_skill_catalog --check` (31 valid / 0 invalid)
  - `python -m unittest discover -s tests` (377 tests)
  - `python -m src.skills.uaf_skill_quality --summary` (`lowest_quality_score`: 9.6)
  - `python -m src.benchmarks.practical_quality_gate --summary` (`release_ready`: true, 8/8 KH-Bench tasks passed)
  - `git diff --check`
- Latest large-work routing policy:
  - Heavy project/SaaS/app/multi-file/role-DAG/long-running work requires `large_work_orchestration_bundle`.
  - Bundle `skill_statuses` must account for routing, host orchestration, GoalState, lifecycle, token optimization, memory, parallel strategy, subagent review, role execution audit, Compound, and workflow distillation.
  - Light and medium requests remain cheap; the bundle is not created for conceptual questions.
- Latest skill usability refinement after session review:
  - `large_work_orchestration_bundle.skill_statuses` now carries `application_mode`: `runtime`, `procedural`, `considered`, or `blocked`.
  - Use the minimal evidence template when a skill was applied as policy or considered: `skill`, `status`, `application_mode`, `evidence_note`, `evidence_keys`, and optional `blocked_reason`.
  - Do not require AdapterRequest, role results, or wave metadata unless runtime execution is claimed.
  - Memory work should default to memory candidates only unless durable promotion has explicit scope and approval.
- Latest verification after skill usability bundle 2.9.10:
  - `python -m json.tool plugin.json`
  - `python -m json.tool .codex-plugin/plugin.json`
  - `python -m unittest tests.test_skill_application_bundle tests.test_large_work_orchestration_bundle tests.test_request_classifier tests.test_plugin_packaging tests.test_goal_skill_integration` (59 tests)
  - `python -m src.skills.uaf_skill_catalog --check` (31 valid / 0 invalid)
  - `python -m unittest discover -s tests` (381 tests)
  - `python -m src.skills.uaf_skill_quality --summary` (`lowest_quality_score`: 9.6)
  - `python -m src.benchmarks.practical_quality_gate --summary` (`release_ready`: true, 8/8 KH-Bench tasks passed)
  - `git diff --check`
- Follow-up external benchmark target after Superpowers-run session `019e7441-eecf-7e23-b9ee-9aefa1c8fdf6` ends:
  - Completed as `docs/skillbook/audits/2026-05-30-superpowers-large-project-control-sample.md`.
  - Key follow-up implemented: `src.orchestration.development_progress`, `.kh/development/<run-id>/state/progress.json`, and standard subagent task packets.
  - Remaining future work: wire progress state into live KH workflow dispatch and add a small demo that writes progress during execution.
- Latest verification after Superpowers large-project control sample 2.9.11:
  - `python -m json.tool .codex-plugin/plugin.json`
  - `python -m json.tool plugin.json`
  - `python -m src.skills.uaf_skill_catalog --check` (31 valid / 0 invalid)
  - `python -B -c "import pathlib, tokenize; files=list(pathlib.Path('.').rglob('*.py')); [compile(tokenize.open(str(p)).read(), str(p), 'exec') for p in files]; print(f'compiled {len(files)} python files')"` (179 files)
  - `python -m unittest tests.test_plugin_packaging tests.test_skill_application_bundle tests.test_token_optimizer_gate_integration tests.test_development_progress tests.test_superpowers_benchmark_alignment` (29 tests)
  - `python -m unittest discover -s tests` (387 tests)
  - `python -m src.skills.uaf_skill_quality --summary` (`lowest_quality_score`: 9.6)
  - `python -m src.benchmarks.practical_quality_gate --summary` (`release_ready`: true, 8/8 KH-Bench tasks passed)
  - `python -m json.tool .agents/plugins/marketplace.json`
  - `git diff --check`
- Latest skill transition direction for 2.9.12:
  - Large-work bundle skills are now connected by `src.orchestration.skill_transitions`.
  - Required final evidence: `skill_transition_handoff`.
  - Transitions enforced: memory candidates -> `memory-state-harness`, subagent review -> `role-execution-audit-harness`, selected parallel execution -> `parallel-orchestration-harness`, and post-review work -> closed `compound-engineering-harness` or visible next skills.
  - Compound next skills are binding follow-ups for `workflow-skill-distiller`, `memory-state-harness`, `scenario-evaluation-harness`, or `context-state-harness`.
  - Subagents are not automatic for large work; record `subagent_strategy` before dispatch and record a token optimizer decision for packets/transcripts without forcing compression.
- Latest verification after skill transition policy 2.9.12:
  - `python -m json.tool .codex-plugin/plugin.json`
  - `python -m json.tool plugin.json`
  - `python -m unittest tests.test_skill_transitions tests.test_superpowers_benchmark_alignment tests.test_docs_branding tests.test_skill_application_bundle tests.test_plugin_packaging` (31 tests)
  - `python -m src.skills.uaf_skill_catalog --check` (31 valid / 0 invalid)
  - `python -B -c "import pathlib, tokenize; files=list(pathlib.Path('.').rglob('*.py')); [compile(tokenize.open(str(p)).read(), str(p), 'exec') for p in files]; print(f'compiled {len(files)} python files')"` (181 files)
  - `python -m src.skills.uaf_skill_quality --summary` (`lowest_quality_score`: 9.6)
  - `python -m src.benchmarks.practical_quality_gate --summary` (`release_ready`: true, 8/8 KH-Bench tasks passed)
  - `python -m unittest discover -s tests` (396 tests)
  - `git diff --check`
- Latest workflow usability layer direction for 2.9.13:
  - Added `workflow-usability-harness` as the visible KH front door for progress panels, progress-to-Compound handoff, token provider policy, role commands, and session-start context restore.
  - Added `src.orchestration.progress_compound_bridge` so completed `.kh/development/<run-id>/state/progress.json` can produce `CompoundCapture`, `compound_handoff`, memory candidates, skill candidates, scenario candidates, and `docs/kh/handoffs/<run-id>-compound.md`.
  - Added `token_optimizer_provider = kh | rtk | hybrid | passthrough`; RTK is optional, hybrid falls back to KH, and quality-sensitive text must pass through.
  - Added `/kh:*` role command entrypoints and visible progress/session-start helpers.
  - Packaged skill count is now 32.
- Latest verification after workflow usability layer 2.9.13:
  - `python -m json.tool .codex-plugin/plugin.json`
  - `python -m json.tool plugin.json`
  - `python -m src.skills.uaf_skill_catalog --check` (32 valid / 0 invalid)
  - `python -B -c "import pathlib, tokenize; files=list(pathlib.Path('.').rglob('*.py')); [compile(tokenize.open(str(p)).read(), str(p), 'exec') for p in files]; print(f'compiled {len(files)} python files')"` (189 files)
  - `python -m unittest tests.test_workflow_usability_layer tests.test_compound_engineering_harness tests.test_development_progress tests.test_token_optimizer_gate_integration tests.test_plugin_packaging tests.test_docs_branding tests.test_superpowers_benchmark_alignment` (42 tests)
  - `python -m unittest discover -s tests` (403 tests)
  - `python -m src.skills.uaf_skill_quality --summary` (`lowest_quality_score`: 9.6)
  - `python -m src.benchmarks.practical_quality_gate --summary` (`release_ready`: true, 8/8 KH-Bench tasks passed)
  - `git diff --check`
- Latest workflow usability runtime direction for 2.9.14:
  - Added `src.orchestration.workflow_usability_runtime` so AgentLoop, app bridge, local workflow, and native host dispatch paths can set `workflow_usability_auto` and automatically produce session-start context, token provider policy, valid `.kh/development/<run-id>/state/progress.json`, visible progress panel text, and progress-to-Compound artifacts.
  - `AgentLoop.build_dispatch_metadata(...)` and `create_app_request(...)` now enable `workflow_usability_auto`, default `token_optimizer_provider` to `kh`, and record `workspace_strategy` for real host/workflow runs.
  - `dispatch_project_workflow(...)`, `LocalDispatcher`, and `AntigravityDispatcher` now return `metadata["workflow_usability"]`; Antigravity pending mode exposes preflight metadata, while local/native paths write runtime artifacts when auto mode is enabled.
  - Automatic progress state is validated through `validate_development_progress(...)` before writing, so visible progress and Compound handoff cannot silently drift from KH lifecycle rules.
  - Plugin package version is now `2.9.14`.
- Latest verification after automatic workflow usability runtime 2.9.14:
  - `python -m unittest tests.test_agent_loop tests.test_app_bridge tests.test_dispatcher tests.test_workflows tests.test_workflow_usability_layer tests.test_plugin_packaging tests.test_docs_branding` (63 tests)
  - `python -m json.tool .codex-plugin/plugin.json`
  - `python -m json.tool plugin.json`
  - `python -m src.skills.uaf_skill_catalog --check` (32 valid / 0 invalid)
  - `python -m src.skills.uaf_skill_quality --summary` (`lowest_quality_score`: 9.6)
  - `python -B -c "import pathlib, tokenize; files=list(pathlib.Path('.').rglob('*.py')); [compile(tokenize.open(str(p)).read(), str(p), 'exec') for p in files]; print(f'compiled {len(files)} python files')"` (190 files)
  - `python -m unittest tests.test_token_optimizer_gate_integration tests.test_command_output_runtime tests.test_skill_transitions` (32 tests)
  - `python -m unittest discover -s tests` (405 tests)
  - `python -m src.benchmarks.practical_quality_gate --summary` (`release_ready`: true, 8/8 KH-Bench tasks passed, `practical_confidence_score`: 10.0)
  - `python -m src.orchestration.scenario_evaluator --summary` (30/30 passed, 66 meaningful signals)
  - `git diff --check`
- Latest plugin composition policy direction for 2.9.15:
  - Added `plugin-composition-policy` as the top-level lightweight broker before plugin-specific MUST/ALWAYS trigger wording is allowed to select a provider.
  - Added `src.orchestration.plugin_composition` with `CapabilityProvider`, `ProviderRole`, `PluginCompositionDecision`, and `compose_plugin_route(...)`.
  - Routing now supports `direct`, `single`, `hybrid`, and `clarify` decisions from a dynamic provider snapshot, not from plugins installed on one PC.
  - Provider mandatory wording is scoped to selected controller or delegated assistant roles; non-selected self-forcing providers are recorded in `ignored_self_forcing`.
  - Hybrid composition supports a workflow controller plus assistants for browser QA, repo/PR/CI, knowledge docs, image generation, host automation, and memory/goal/resume.
  - SIDE subagent review found over-broad explicit provider matching; regression fixes now prevent generic words like `browser`, `pr`, and `pro` from self-selecting unless invocation context is explicit.
  - Unavailable explicit provider requests are reported through `unavailable_capabilities["provider:<id>"]` before fallback.
  - Packaged skill count is now 33.
- Latest verification after plugin composition policy 2.9.15:
  - `python -m unittest tests.test_plugin_composition_policy tests.test_plugin_packaging tests.test_superpowers_benchmark_alignment` (29 tests)
  - `python -m src.skills.uaf_skill_catalog --check` (33 valid / 0 invalid)
  - `python -m json.tool .codex-plugin/plugin.json`
  - `python -m json.tool plugin.json`
  - `python -B -c "import pathlib, tokenize; files=list(pathlib.Path('.').rglob('*.py')); [compile(tokenize.open(str(p)).read(), str(p), 'exec') for p in files]; print(f'compiled {len(files)} python files')"` (194 files)
  - `python -m unittest tests.test_interactive_side_evaluator tests.test_uaf_skill_audit tests.test_uaf_skill_catalog tests.test_uaf_skill_quality` (33 tests)
  - `python -m src.orchestration.interactive_side_evaluator --summary --skills` (33/33 skill SIDE turns passed)
  - `python -m unittest discover -s tests` (417 tests)
  - `python -m src.skills.uaf_skill_quality --summary` (`lowest_quality_score`: 9.3)
  - `python -m src.benchmarks.practical_quality_gate --summary` (`release_ready`: true, 8/8 KH-Bench tasks passed, `practical_confidence_score`: 10.0)
  - `python -m src.orchestration.scenario_evaluator --summary` (30/30 passed, 66 meaningful signals)
  - `git diff --check`
- Latest repository packaging cleanup direction for 2.9.16:
  - `main` remains the development and verification repository with `tests/`, audits, and docs.
  - Codex marketplace metadata in `.agents/plugins/marketplace.json` now installs from the `codex-runtime` ref so plugin cache installs do not need to carry development-only test folders.
  - Removed legacy root sample project folders `test_cli_project/` and `test_project/`; `.gitignore` prevents regenerating them as tracked files.
  - Added `.gitattributes` export-ignore markers for development-only paths when an archive-based runtime package is produced.
  - Plugin manifest versions are now `2.9.16` to force cache refresh after the runtime packaging change.
- Latest verification after repository packaging cleanup 2.9.16:
  - `python -m unittest tests.test_plugin_packaging tests.test_plugin_composition_policy tests.test_docs_branding` (24 tests)
  - `python -m json.tool .codex-plugin/plugin.json`
  - `python -m json.tool plugin.json`
  - `python -m json.tool .agents/plugins/marketplace.json`
  - `python -m src.skills.uaf_skill_catalog --check` (33 valid / 0 invalid)
  - `git diff --check`
  - `python -m unittest discover -s tests` (419 tests)
  - `python -m src.skills.uaf_skill_quality --summary` (`lowest_quality_score`: 9.3)
  - `python -m src.benchmarks.practical_quality_gate --summary` (`release_ready`: true, 8/8 KH-Bench tasks passed, `practical_confidence_score`: 10.0)
  - `python -m src.orchestration.scenario_evaluator --summary` (30/30 passed, 66 meaningful signals)
- Latest full verification after host plugin packaging:
  - `python -m json.tool plugin.json`
  - `python -m json.tool .codex-plugin/plugin.json`
  - `python -m src.skills.uaf_skill_catalog --check`
  - `python -B -c "import pathlib; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in pathlib.Path('.').rglob('*.py')]"`
  - `python -m unittest discover -s tests -v` (152 tests)
- Latest full verification after Windows/source audit:
  - `python -m json.tool plugin.json`
  - `python -m json.tool .codex-plugin/plugin.json`
  - `python -m src.skills.uaf_skill_catalog --check`
  - `python -B -c "import pathlib, tokenize; files=list(pathlib.Path('.').rglob('*.py')); [compile(tokenize.open(str(p)).read(), str(p), 'exec') for p in files]; print(f'compiled {len(files)} python files')"`
  - `python -B -m unittest discover -s tests -v` (153 tests)
- Latest full verification after packaged skill behavior validation:
  - `python -m json.tool plugin.json`
  - `python -m json.tool .codex-plugin/plugin.json`
  - `python -m json.tool .agents/plugins/marketplace.json`
  - `python -m src.skills.uaf_skill_catalog --check`
  - `python -B -c "import pathlib, tokenize; files=list(pathlib.Path('.').rglob('*.py')); [compile(tokenize.open(str(p)).read(), str(p), 'exec') for p in files]; print(f'compiled {len(files)} python files')"`
  - `python -B -m unittest discover -s tests -v` (157 tests)
- Latest full verification after goal-state hardening:
  - `python -m json.tool plugin.json`
  - `python -m json.tool .codex-plugin/plugin.json`
  - `python -m json.tool .agents/plugins/marketplace.json`
  - `python -m src.skills.uaf_skill_catalog --check`
  - `python -B -c "import pathlib, tokenize; files=list(pathlib.Path('.').rglob('*.py')); [compile(tokenize.open(str(p)).read(), str(p), 'exec') for p in files]; print(f'compiled {len(files)} python files')"` (72 files)
  - `python -B -m unittest discover -s tests -v` (159 tests)
- Latest full verification after runtime-state isolation and work snapshot bundling:
  - `python -m json.tool plugin.json`
  - `python -m json.tool .codex-plugin/plugin.json`
  - `python -m json.tool .agents/plugins/marketplace.json`
  - `python -m src.skills.uaf_skill_catalog --check`
  - `python -B -c "import pathlib, tokenize; files=list(pathlib.Path('.').rglob('*.py')); [compile(tokenize.open(str(p)).read(), str(p), 'exec') for p in files]; print(f'compiled {len(files)} python files')"` (73 files)
  - `python -B -m unittest discover -s tests -v` (164 tests)
- Latest full verification after Office deliverable export and DAG role orchestration:
  - `python -m json.tool plugin.json`
  - `python -m json.tool .codex-plugin/plugin.json`
  - `python -m json.tool .agents/plugins/marketplace.json`
  - `python -m src.skills.uaf_skill_catalog --check` (23 valid / 0 invalid)
  - `python -B -c "import pathlib, tokenize; files=list(pathlib.Path('.').rglob('*.py')); [compile(tokenize.open(str(p)).read(), str(p), 'exec') for p in files]; print(f'compiled {len(files)} python files')"` (75 files)
  - `python -B -m unittest discover -s tests -v` (167 tests)
- Latest full verification after conditional revision-managed manual export:
  - `python -m json.tool plugin.json`
  - `python -m json.tool .codex-plugin/plugin.json`
  - `python -m json.tool .agents/plugins/marketplace.json`
  - `python -m src.skills.uaf_skill_catalog --check` (23 valid / 0 invalid)
  - `python -B -c "import pathlib, tokenize; files=list(pathlib.Path('.').rglob('*.py')); [compile(tokenize.open(str(p)).read(), str(p), 'exec') for p in files]; print(f'compiled {len(files)} python files')"` (75 files)
  - `python -B -m unittest discover -s tests -v` (168 tests)
- Latest full verification after type-aware deliverable routing:
  - `python -m json.tool plugin.json`
  - `python -m json.tool .codex-plugin/plugin.json`
  - `python -m json.tool .agents/plugins/marketplace.json`
  - `python -m src.skills.uaf_skill_catalog --check` (23 valid / 0 invalid)
  - `python -B -c "import pathlib, tokenize; files=list(pathlib.Path('.').rglob('*.py')); [compile(tokenize.open(str(p)).read(), str(p), 'exec') for p in files]; print(f'compiled {len(files)} python files')"` (75 files)
  - `python -B -m unittest discover -s tests -v` (169 tests)
  - `git diff --check`
- Latest full verification after role artifact, evidence gate, and retention hardening:
  - `python -m json.tool plugin.json`
  - `python -m json.tool .codex-plugin/plugin.json`
  - `python -m json.tool .agents/plugins/marketplace.json`
  - `python -m src.skills.uaf_skill_catalog --check` (23 valid / 0 invalid)
  - `python -B -c "import pathlib, tokenize; files=list(pathlib.Path('.').rglob('*.py')); [compile(tokenize.open(str(p)).read(), str(p), 'exec') for p in files]; print(f'compiled {len(files)} python files')"` (75 files)
  - `python -B -m unittest discover -s tests -v` (178 tests)
  - `git diff --check`
- Latest quality-harness direction:
  - Keep user-facing artifacts in `project/docs`.
  - Keep harness-only outputs such as template-quality findings, render QA details, traceability rows, and role execution audit in UAF runtime metadata/evidence.
  - Added packaged skills: `deliverable-template-quality-harness`, `artifact-render-qa-harness`, `traceability-matrix-harness`, and `role-execution-audit-harness`.
  - `docs/추적성_매트릭스.xlsx` is not generated by default; traceability is metadata-only unless explicitly requested as a user deliverable.

## Completed

- Added local task runner interface:
  - `src/tasks/runners.py`
  - `WorkflowTaskInput`
  - `LocalTaskRunner`
  - runner `WorkflowTaskResult` is source of truth
  - webhook reporting is side-effect metadata
  - runner evidence feeds `GoalState.evidence`
- Added code-generating local runner adapter:
  - `GeneratedTaskArtifact`
  - `DeterministicCodeGenerationAdapter`
  - `LLMCodeGenerationAdapter`
  - `LocalTaskRunner` writes generated artifacts after project-root path validation
  - local `AgentLoop` dispatch metadata now passes the active `LLMRouter` into workflow workers
  - workflow workers use `LLMCodeGenerationAdapter` when `metadata["llm_router"]` is present
  - runner evidence now includes `code generated`
- Added bounded command check runner:
  - `src/tasks/checks.py`
  - `CommandCheckInput`
  - `CommandCheckRunner`
  - successful commands emit requested evidence keys
  - failed/rejected commands preserve stdout/stderr/exit metadata without granting evidence
- Wired command checks into workflow metadata:
  - `metadata["command_checks"]` accepts bounded command check specs
  - command check evidence keys are added to `GoalState.evidence_required`
  - failed checks block QA/release through missing goal evidence
- Added rich command check presets:
  - `plugin-json`
  - `python-compile`
  - `python-unittest`
  - `skill-catalog`
  - `metadata["command_check_presets"]` expands named presets into bounded `CommandCheckInput` objects
- Added Browser/QA adapter boundary:
  - `src/tasks/browser_qa.py`
  - `BrowserQACheckInput`
  - `BrowserQACheckResult`
  - `BrowserQACheckRunner`
  - `BrowserQASidecarAdapter`
  - no-adapter mode returns structured blocked QA evidence results
  - JSON process sidecar protocol passes check JSON on stdin and reads result JSON from stdout
- Wired Browser/QA checks into workflow metadata:
  - `metadata["browser_qa_checks"]` accepts browser/app QA check specs
  - `metadata["browser_qa_adapter"]` can inject a concrete adapter
  - QA evidence keys are added to `GoalState.evidence_required`
  - failed or blocked QA checks block QA/release through missing goal evidence
- Added extension registry for host and LLM portability:
  - `src/orchestration/extension_registry.py`
  - `DispatcherFactory.register_dispatcher(...)`
  - `LLMRouter.register_provider(...)`
  - custom dispatch modes and LLM providers no longer require hardcoded branches
- Added typed workflow check stage:
  - `src/tasks/workflow_checks.py`
  - command specs, command presets, and Browser/QA specs are planned outside `workflows.py`
  - `metadata["browser_qa_sidecar"] = {"command": [...]}` creates a Browser/QA sidecar adapter without Python object injection
  - stage output centralizes check success, evidence aggregation, and workflow metadata
  - `workflows.py` remains the coordinator for dispatch, goal evaluation, ledger persistence, and result assembly
- Added post-gate evidence lifecycle:
  - gate `evidence_records` are collected into `metadata["gate_evidence"]`
  - final `GoalState.evidence` records gate evidence after gate evaluation
  - post-gate evidence does not change the current run's complete/block decision
- Added Antigravity native dispatch boundary:
  - `src/platforms/antigravity_native.py`
  - `AntigravityNativeDispatchResult`
  - `AntigravityNativeSidecarAdapter`
  - `AntigravityDispatcher(native_adapter=...)` can consume native task results
  - `metadata["antigravity_native_sidecar"] = {"command": [...]}` can launch a JSON process sidecar
  - sidecar protocol passes `AdapterRequest` JSON on stdin and reads `AntigravityNativeDispatchResult` JSON from stdout
  - no-adapter Antigravity mode keeps structured pending fallback without requiring webhook state
- Made webhook reporting opt-in:
  - local workflow no longer defaults to `http://127.0.0.1:8000/...`
  - when `AG_WEBHOOK_URL` is unset, task metadata records `webhook_report.status = skipped`
  - when `AG_WEBHOOK_URL` is set, POST success/failure is recorded without overriding runner result
- Added evidence producer helpers:
  - `src/orchestration/evidence_producers.py`
  - command, review, and QA result records normalize evidence keys
  - workflow task metadata now consumes `evidence_records` as well as flat `evidence`
- Split role gate evaluators:
  - `src/orchestration/gate_evaluators.py`
  - `roles.build_role_gate_results()` now delegates to focused gate evaluators
  - spec, code-quality, QA, security, and release gates emit structured findings and evidence records
- Added persistent goal ledger:
  - `src/orchestration/goal_ledger.py`
  - `.uaf/state/current_goal.json`
  - `.uaf/state/goal_events.jsonl`
  - workflow dispatch writes initial and evaluated goal states
- Added packaged skill validation:
  - `src/skills/uaf_skill_validator.py`
  - `python -m src.skills.uaf_skill_catalog --check`
- Added host plugin packaging:
  - `.codex-plugin/plugin.json` for Codex local plugin registration
  - `.agents/plugins/kh-uaf/` bootstrap plugin for Antigravity workspace discovery
  - `README.md` install sections for Codex and Antigravity
- Added UAF-native gate and state harness skills:
  - `review-gate-harness`
  - `qa-gate-harness`
  - `context-state-harness`
  - `guard-policy-harness`
  - `health-check-harness`
- Added `GoalState` contract and metadata propagation.
- Added goal evidence evaluation:
  - `src/orchestration/goal_evidence.py`
  - workflow evidence collection
  - QA/release blocking when required goal evidence is missing
  - conservative evidence alias matching for common key variants
  - workflow-provided aliases through `GoalState.metadata.evidence_aliases`
  - alias matches recorded under `metadata.evidence_alias_matches`
- Added scoped persistent memory support:
  - `MemoryScope`, `MemoryRecord`, and `MemoryEvent` contracts
  - project/conversation scope resolver in `src/orchestration/memory_state.py`
  - JSON/JSONL store in `src/orchestration/memory_store.py`
  - memory records, candidates, append-only events, scope state, and secret-like content rejection
  - workflow `enable_memory` support that attaches `memory_context` to workflow metadata and `GoalState.metadata`
  - goal ledger persists the memory context through the serialized goal
  - archived/deleted conversation cleanup policy with quarantine by default
  - optional `CodexThreadRegistry` that reads local Codex `threads.archived` state when the registry is available
  - `memory-state-harness` packaged skill
- Added domain-general orchestration and design artifact support:
  - `DomainProfile`, `DomainRole`, `WorkDesign`, `DesignArtifact`, and `ArtifactManifest` contracts
  - `src/orchestration/domain_profiles.py` for generic domain profile and work design construction
  - `src/orchestration/artifacts.py` for `.uaf/artifacts/design/` design files and `.uaf/state/artifact_manifest.json`
  - workflow dispatch now creates a mandatory design stage, records design artifact evidence, and attaches `domain_profile`, `work_design`, and `artifact_manifest` to `WorkflowDispatchResult.metadata`
  - `GoalState.metadata` and goal ledger state now carry the artifact manifest for resume-safe review/release decisions
  - `domain-orchestration-harness` packaged skill
- Added resume-safe handoff support:
  - `HandoffSnapshot` contract
  - `src/orchestration/handoff.py`
  - `.uaf/state/resume_handoff.json`
  - `.uaf/state/resume_handoff.md`
  - workflow metadata now includes `resume_handoff` when goal metadata is present
  - later host sessions can resume from goal ledger, artifact manifest, memory context, missing evidence, and next action without relying on chat context
- Rebranded external-methodology work records into a personal KH/UAF skillbook:
  - `docs/skillbook/specs/`
  - `docs/skillbook/plans/`
  - packaged skill list now uses `host-agent-orchestration` and `command-output-harness` instead of vendor/reference-branded names
- Reworked `README.md` to reflect current implementation level, references, verification, and roadmap.
- Reworked `AgentLoop` user-facing prompts and target-file prompt from mojibake into ASCII English so LLM target-file selection is usable.
- Fixed Windows SQLite registry cleanup:
  - `src.platforms.codex_thread_registry` now closes SQLite connections explicitly with `contextlib.closing`.
  - This prevents temporary `state.sqlite` files from remaining locked during test cleanup on Windows.
- Fixed file operation skill path boundary:
  - `src.skills.file_ops` now uses `os.path.commonpath` instead of string-prefix checks.
  - Added regression coverage for prefix-sibling workspace paths such as `workspace` vs `workspace_evil`.
- Added Codex repo marketplace packaging:
  - `.agents/plugins/marketplace.json` exposes `kh-uaf` as a Git-backed installable plugin source.
  - README now documents the Codex app Add marketplace fields for `GNh0/KH`, `main`, and `.agents/plugins`.
- Strengthened packaged skill behavior validation:
  - `src.skills.uaf_skill_validator` now requires trigger-focused `Use when` descriptions and an explicit behavior section.
  - Packaged `SKILL.md` files now also require `Required outputs` and `Common mistakes`, so skills explain concrete evidence/results and failure modes instead of staying as shallow topic notes.
  - `tests.test_uaf_skill_catalog` verifies packaged skill implementation target references resolve to repo modules, symbols, or skill files.
- Hardened goal-state verification:
  - command/check-stage failures now keep evaluated goals blocked even when the failed check has no evidence key.
  - unknown command-check presets now block goal completion instead of allowing an evidence-only complete state.
  - goal ledger and resume handoff snapshots expose `success_criteria` at the top level.
  - LocalDispatcher adapter metadata exposes `resume_handoff` next to `goal` and `goal_ledger`.
- Moved default runtime state out of target project roots:
  - `.uaf/` and `.snapshots/` now live under the UAF runtime store by default, normally `%LOCALAPPDATA%\KH-UAF\projects\<project-key>\`.
  - `UAF_RUNTIME_ROOT` overrides the runtime base.
  - `UAF_PROJECT_LOCAL_STATE=1` is the explicit opt-in for project-local runtime folders.
  - `SnapshotManager.commit_many(...)` creates one work-level snapshot bundle for multi-file tasks.
- Added domain-neutral Office deliverable export:
  - workflow design stage writes user-facing deliverables to the target project's `docs/` folder, not runtime `.uaf/`
  - default files: `요구정의서.docx`, `오케스트레이션_설계서.docx`, `산출물_정의서.docx`, `처리흐름도.docx`, `역할별_작업분해표.xlsx`, `증거계획서.xlsx`, `위험_정책_체크리스트.xlsx`
  - `사용_매뉴얼.docx` is conditional, includes front-loaded `리비전 버전 관리`, and is skipped by default for investment/analysis/reporting-only topics unless explicitly requested
  - export evidence is attached to workflow and goal evidence only after files are written
- Added type-aware deliverable routing:
  - `export_office_deliverables(...)` remains the compatibility entry point but now selects a deliverable profile before writing files
  - general orchestration keeps the default DOCX/XLSX planning exports
  - investment/analysis work exports `투자_분석보고서.docx`, `가정_시나리오.xlsx`, and `위험_정책_체크리스트.xlsx` without a manual by default
  - product/mechanical design exports `제품_설계서.docx`, `치수_BOM.xlsx`, `개념_설계도.svg`, and `개념_설계도.dxf`
  - `deliverable_exports["plan"]` records selected profile, artifact type, format, path, and evidence for each output
- Addressed UAF usage-review findings:
  - skill catalog now declares each packaged skill as `python-module`, `hybrid-harness`, or `procedure-policy`
  - role orchestration now writes runtime role-stage artifacts under `.uaf/artifacts/roles/` when project context is available
  - spec/code gates now require task evidence and fail on quality findings instead of accepting success status alone
  - evidence records keep `metadata.evidence_key` as trace metadata, while only `record.evidence` grants goal evidence
  - goal, artifact, memory, and snapshot stores have explicit trim/prune helpers; workflow metadata can request `retention_policy`
  - snapshot and CLI user-facing command output was moved to ASCII/UTF-8-safe text to avoid Windows console mojibake
  - current repo has no generated `app.js` / `data/kh-skills.json` dashboard duplication surface; future dashboards should derive from one source of truth
- Added DAG-based role orchestration:
  - `src/orchestration/role_orchestrator.py`
  - dependency-ready roles run in asyncio waves
  - default graph now has real parallel waves for advisor/product strategy and QA/security
  - role task results are stored in workflow metadata and goal metadata
  - blocked downstream roles are preserved as structured results and gate metadata

## Active Decision

The persistent goal ledger exists. The local execution path now has DAG role orchestration, runner, check, QA, sidecar, evidence, registry, evidence-alias, scoped persistent-memory, domain profile, work design, artifact manifest, documentation-grade type-aware deliverable export, and resume handoff boundaries. Antigravity and Browser/QA both have dependency-free JSON sidecar protocols, so host-specific packages can live outside the Python core.

Latest user review found that the general DOCX/XLSX exports existed but read like shallow workflow logs. The export generator now treats those files as user-facing documents:

- `요구정의서.docx`: functional requirements, quality requirements, acceptance criteria, assumptions, constraints, open questions, source trace.
- `오케스트레이션_설계서.docx`: role DAG, parallel execution strategy, runtime-state separation, gate flow, failure/blocked handling.
- `산출물_정의서.docx`: artifact purpose, generation conditions, quality criteria, verification intent.
- `처리흐름도.docx`: staged flow, decision points, and rework loop.
- `역할별_작업분해표.xlsx`, `증거계획서.xlsx`, `위험_정책_체크리스트.xlsx`: owner, inputs, completion criteria, verification method, evidence, mitigation, and blocking conditions.

Tests now assert those document-quality markers instead of only checking that the files exist and are valid Office packages.

Follow-up user review clarified that development work must not rely on the generic 요구정의서 alone because 기능정의서 is a standard required development artifact. UAF now has a `software-development` deliverable profile that exports:

- `요구정의서.docx`
- `기능정의서.docx` with 기능 목록, 기능 상세, 입출력 정의, 예외 및 검증 규칙, 인수 기준, traceability.
- `개발설계서.docx` with architecture, module design, data flow, error handling, security, verification strategy.
- `화면_API_정의서.docx` with screen definitions, user actions, API endpoints, request/response fields, errors.
- `데이터_정의서.xlsx`, `역할별_작업분해표.xlsx`, `테스트_검증계획서.xlsx`, `위험_정책_체크리스트.xlsx`.

Tests assert the mandatory 기능정의서 markers and prevent software prompts containing generic words like "product CRUD" from being misrouted to the product-design profile.

Latest template-quality review requires each exported document to follow broadly recognizable document shapes rather than only containing plausible sections. Tests now assert common markers for requirements documents, orchestration design, deliverable definition, process flow, operations manual, software FSD/SDD/screen-API/data dictionary/test plan, product design/BOM, investment report/scenario workbook, WBS, evidence plan, and risk register headers.

Quality harnesses now run after deliverable export. They emit `deliverable template quality passed`, `artifact render qa passed`, and `traceability matrix passed` as metadata evidence without writing harness-only XLSX reports into the target project's `docs/` folder. Role DAG execution is also audited through `role_execution_audit`, which checks execution model, success state, parallel waves, required roles, and role artifacts.

Active task: none. Recommended next improvement is optional host package scaffolding or additional domain-specific artifact producers only when the actual runtime or domain dependency is explicit.

There are two related layers:

1. Codex working continuity:
   - This file is the immediate working ledger for the assistant.
   - It exists so context compaction does not erase current direction and pending tasks.

2. UAF product feature:
   - Project-scoped persistent goal ledger lives under runtime `.uaf/state/`.
   - `current_goal.json` is the resumable state snapshot.
   - `goal_events.jsonl` is append-only audit history.

3. UAF scoped persistent memory:
   - Project/chat memory lives under runtime `.uaf/memory/`.
   - Projectless chat memory should use a conversation namespace outside a repo.
   - Archived conversation memory is retained.
   - Deleted/missing conversation memory is quarantined by default.
   - Codex desktop local registry can identify active vs archived threads when `state_5.sqlite` is available.

4. UAF domain design artifacts:
   - `DomainProfile` answers "what kind of work is this and which roles/gates apply?"
   - `WorkDesign` answers "what must be designed before execution?"
   - `ArtifactManifest` answers "which design artifacts exist and what evidence do they satisfy?"
   - These are stored in workflow metadata and the goal ledger so context compaction or a new session can recover the current design basis.

5. UAF resume handoff:
   - `resume_handoff.json` is the machine-readable continuation snapshot.
   - `resume_handoff.md` is the human-readable note for the next LLM session.
   - It records objective, status, workflow id, missing evidence, collected evidence, artifact basis, memory record count, and next action.

## Implementation Priority After Ledger

Improve existing execution paths in this order:

1. Optional concrete host packages
   - Current behavior: UAF has injected and JSON sidecar boundaries for Antigravity and Browser/QA.
   - Desired behavior: add actual Antigravity SDK and TypeScript/Playwright packages only when those runtime dependencies are explicit.

2. More workflow pipeline extraction
   - Check/QA stage is extracted.
   - Future extraction should target ledger persistence, gate evaluation, and result assembly if those areas grow.

3. More project-specific check presets
   - UAF has core presets; future work can add lint/security/release presets as real project conventions emerge.

4. External memory providers
   - UAF now has local scoped memory contracts and a JSON/JSONL store.
   - Future Hermes/OpenClaw adapters should implement the same `MemoryScope`/`MemoryRecord` contract without replacing the local store.

## Recommended Next Task

Implement the next concrete adapter or domain producer only when runtime/domain details are explicit:

1. Keep Python core contracts stable and avoid adding host-specific dependencies to the core package.
2. Add concrete sidecar packages only when the host runtime and dependency installation path are known.
3. Add domain-specific artifact producers only when their taxonomy and validation rules are known.
4. Add focused tests with fake adapters/sidecars before implementation.
5. Update README, skills, and this ledger.
6. Run full verification.

## Open Risks

- Default `LocalTaskRunner` writes deterministic generated artifacts; `LLMCodeGenerationAdapter` exists but must be explicitly injected.
- Antigravity dispatcher has an injected native boundary, but no concrete host SDK adapter is bundled.
- Browser/QA has a Python contract boundary, workflow integration, and JSON sidecar adapter, but no concrete Playwright package is bundled.
- Persistent memory has local contracts/store and Codex registry polling support, but no Hermes/OpenClaw provider adapter is bundled.
- Domain orchestration uses a generic builder; domain-specific artifact producers and validators are not bundled yet.
- Resume handoff stores local paths; redact these before sharing runtime `.uaf` state outside a local workspace.
- Check/QA pipeline is extracted; remaining workflow growth points are ledger persistence, gate evaluation, and result assembly.
