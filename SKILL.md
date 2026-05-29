---
name: universal-agent-framework
description: "A pure-local, highly concurrent, and sandboxed AI/domain orchestration framework. Use this skill when the user asks to orchestrate a complex project, persist design artifacts, or parallelize multiple bounded tasks."
---

# Universal Agent Framework (UAF)

This is a local-first, zero-dependency, and hyper-concurrent agentic orchestration framework. It uses a Pure Python `asyncio` architecture to bypass traditional broker limits, can carry domain-neutral design artifacts through workflows, routes user-facing deliverables to the target project's `docs/` folder by work type, keeps harness-only quality evidence in metadata, and can safely test Python code on Windows via `multiprocessing`-based sandboxing.

## Requirements
- Python 3.9+
- OS: Windows / Linux / macOS
- Dependencies: `uvicorn`, `fastapi`, `httpx`, `requests` (installed via pip)

## Execution via CLI
Do NOT run internal scripts directly. Always use the built-in `cli.py` orchestrator. The CLI handles orchestration, dispatch metadata, and process garbage collection automatically. The webhook server is optional and only needed for external host callbacks.

### Commands

**1. Run a Complete Workflow**
To initialize the orchestrator and generate code for a project:
```bash
python cli.py run --project "./my_project_dir" --prompt "Create a scalable FastAPI backend"
python cli.py run --project "./my_project_dir" --prompt "Create a scalable FastAPI backend" --platform antigravity
```

**2. Advanced Overrides**
You can pass additional arguments to control the environment:
- `--workers <int>`: Cap the concurrent workers (Default: 50). The framework will auto-clamp this to safe limits based on CPU cores.
- `--platform local|antigravity`: Select the dispatcher mode. Use `antigravity` for app-host-driven subagent dispatch.
- `--no-sandbox`: Bypass AST and timeout checks for debugging.
- `--verbose`: Enable debug logging for the optional webhook server.

Example:
```bash
python cli.py run --project "./my_game" --prompt "Create a simple python snake game" --workers 100 --verbose
```

## Internal Architecture
If you need to extend or debug this framework, here is the structure:
- **`src/contracts.py`**: Shared contracts for Codex, Antigravity, Claude Code, and local adapters (`GoalState`, `HandoffSnapshot`, `MemoryScope`, `MemoryRecord`, `MemoryEvent`, `DomainProfile`, `DomainRole`, `WorkDesign`, `DesignArtifact`, `ArtifactManifest`, `HarnessResult`, `SkillManifest`, `AdapterRequest`, `AdapterResult`, `WorkflowTaskResult`, `WorkflowDispatchResult`).
- **`cli.py`**: The main entry point. Orchestrates the Server + Agent Loop.
- **`src/core/app_bridge.py`**: App-first integration helper for Codex and Antigravity Windows app hosts. Builds role-aware `AdapterRequest` objects without CLI parsing.
- **`src/orchestration/agent_loop.py`**: The central loop (Architect -> Dispatcher -> Evaluator).
- **`src/orchestration/evidence_producers.py`**: Normalizes command, review, and QA results into `GoalState.evidence` keys.
- **`src/orchestration/extension_registry.py`**: Shared registry for pluggable dispatchers, LLM providers, skill harnesses, and future host adapters.
- **`src/orchestration/gate_evaluators.py`**: Focused spec, code-quality, QA, security, and release gate evaluators that emit structured findings and evidence records.
- **`src/orchestration/role_orchestrator.py`**: DAG-based role runner that executes dependency-ready roles in parallel asyncio waves, writes runtime role-stage artifacts, and records role `WorkflowTaskResult` metadata.
- **`src/orchestration/goal_evidence.py`**: Goal evidence normalization and complete/blocked evaluation for QA and release gates.
- **`src/orchestration/goal_ledger.py`**: Project/chat-scoped runtime `.uaf/state/` persistence for resumable current goal state and append-only goal events.
- **`src/orchestration/handoff.py`**: Resume-safe handoff builder that writes runtime `.uaf/state/resume_handoff.json` and `.uaf/state/resume_handoff.md` from goal, artifact, and memory state.
- **`src/orchestration/domain_profiles.py`**: Domain-neutral profile and work-design builder for software, operations, analysis, design, and other topics.
- **`src/orchestration/artifacts.py`**: WorkDesign and DesignArtifact store that writes internal `.uaf/artifacts/design/` files and `.uaf/state/artifact_manifest.json` under the UAF runtime store by default.
- **`src/orchestration/deliverable_exports.py`**: Type-aware user-facing export router. Software development writes standard-template mandatory `docs/기능정의서.docx` plus 요구/개발설계/화면_API/data/test/risk artifacts; general orchestration writes documentation-grade `docs/요구정의서.docx`, `docs/오케스트레이션_설계서.docx`, `docs/산출물_정의서.docx`, `docs/처리흐름도.docx`, `docs/역할별_작업분해표.xlsx`, `docs/증거계획서.xlsx`, `docs/위험_정책_체크리스트.xlsx`, and conditional `docs/사용_매뉴얼.docx`; product design can write DOCX/XLSX plus SVG/DXF concept drawing artifacts; investment analysis writes analysis report and scenario/risk workbooks.
- **`src/orchestration/quality_harnesses.py`**: Metadata-only quality harnesses for deliverable template markers, artifact render/readability checks, internal traceability rows, and role execution audit evidence. These checks do not write harness-only spreadsheets into the target project's `docs/` folder.
- **`src/orchestration/memory_state.py`**: Project/conversation memory scope resolver for host-neutral persistent memory namespaces.
- **`src/orchestration/memory_store.py`**: JSON/JSONL memory store for scoped records, candidates, events, and cleanup policy.
- **`src/orchestration/llm_router.py`**: Built-in deterministic offline, OpenAI-compatible, and Anthropic routing plus custom LLM provider registration.
- **`src/orchestration/roles.py`**: Default UAF role graph (`ceo`, `advisor`, `system-architect`, `controller`, `implementer`, reviewers, QA, security, release).
- **`src/platforms/antigravity_native.py`**: Native Antigravity dispatch result contract for injected host adapters and JSON process sidecars.
- **`src/platforms/codex_thread_registry.py`**: Optional Codex desktop thread registry reader for active/archived thread memory cleanup.
- **`src/tasks/browser_qa.py`**: Browser/QA check contract boundary for injected browser adapters and JSON process sidecars, including future TypeScript/Playwright sidecars.
- **`src/tasks/checks.py`**: Bounded command check runner and named presets that convert subprocess results into evidence producer records.
- **`src/tasks/runners.py`**: Local bounded-task runner with deterministic and LLM-backed code-generation adapters. Runner output is the source of truth for `WorkflowTaskResult`; webhook reporting is side-effect metadata.
- **`src/tasks/workflow_checks.py`**: Typed workflow check stage for command and Browser/QA planning, execution, evidence aggregation, and success calculation.
- **`src/tasks/workflows.py`**: The `asyncio` queue-based worker engine. Replaces Celery.
- **`src/harness/sandbox.py`**: A secure code runner. Uses `multiprocessing` for absolute timeout guarantees on Windows.
- **`src/core/snapshot_manager.py`**: State rollback system utilizing pure `gzip` for 90% disk space reduction.
- **`src/skills/uaf_skill_audit.py`**: Deep packaged skill/harness audit helper. Resolves each `SKILL.md` implementation target and maps executable skills to test evidence.
- **`src/skills/uaf_skill_quality.py`**: Packaged skill quality gate. Verifies each skill's support-file wiring, bundled usage reference, minimal workflow example, executable smoke script, implementation target resolution, test evidence, and 10-point practical readiness thresholds.
- **`src/api/server.py`**: An optional FastAPI webhook receiver using `aiosqlite` with WAL mode for external host callbacks.
- **`skills/`**: Packaged UAF-native skill and harness catalog. Add a new skill by creating `skills/<skill-folder>/SKILL.md`, `references/usage.md`, `examples/minimal-workflow.md`, and `scripts/smoke_check.py`.

## Integration Contracts
External agents should exchange structured data through the contracts module instead of ad-hoc dictionaries:
- Use `HarnessResult` for sandbox/evaluator execution results.
- Use `SkillManifest` to normalize plugin and skill metadata.
- Use `AdapterRequest` and `AdapterResult` when implementing Codex, Antigravity, Claude Code, or local dispatch adapters.
- Use `ExtensionRegistry`, `DispatcherFactory.register_dispatcher(...)`, and `LLMRouter.register_provider(...)` for new host modes or LLM backends. Avoid hardcoding provider-specific branches unless the provider is part of the core runtime.
- Use `AntigravityNativeDispatchResult` and `AntigravityNativeSidecarAdapter` when bridging an Antigravity host-native adapter into UAF; keep no-adapter behavior as structured pending. Metadata can provide `antigravity_native_sidecar.command` to launch a sidecar without Python object injection.
- Use `GoalState` metadata to carry objective, required evidence, collected evidence, and complete/blocked status through the workflow.
- Use `MemoryScope`, `MemoryRecord`, and `MemoryEvent` for scoped persistent memory. Project memory lives under the UAF runtime `.uaf/memory/`; projectless chat memory must use a conversation namespace.
- Use `DomainProfile`, `WorkDesign`, `DesignArtifact`, and `ArtifactManifest` for domain-general orchestration. Every substantial workflow should persist a work design, route type-appropriate deliverables into the target project's `docs/` folder, and attach both the artifact manifest and `deliverable_exports` to `WorkflowDispatchResult.metadata` and `GoalState.metadata`.
- Use `DomainProfileBuilder`, `work_design_from_profile(...)`, `ArtifactStore`, and `export_office_deliverables(...)` when adding new domain or design-artifact producers. Do not hardcode one industry taxonomy into core orchestration. Deliverables should match the task type: reports for analysis, spreadsheet models for tabular/scenario work, drawings/CAD handoff files for product design, manuals only when user or operations instructions are actually needed. General DOCX/XLSX exports must include requirements, acceptance criteria, role DAG, parallel strategy, process/rework flow, completion criteria, verification methods, and blocking conditions, not just workflow logs. `deliverable_exports["plan"]` must describe profile, artifact type, format, path, and evidence.
- Use `deliverable_exports["quality"]` and `role_execution_audit` for harness evidence. Keep traceability rows, render QA checks, template findings, and role audit findings in runtime metadata unless the user explicitly requests those as user-facing deliverables.
- Use `src.orchestration.evidence_producers` to convert command, review, and QA outputs into normalized evidence records before adding them to task or gate metadata.
- Use `src.orchestration.gate_evaluators` for focused review/QA/security/release gate decisions; keep `src.orchestration.roles.build_role_gate_results(...)` as the public compatibility wrapper.
- Use `src.orchestration.role_orchestrator.RoleOrchestrator` when roles must actually execute rather than only appear in metadata. Dependency-ready roles should run in parallel waves, blocked roles should produce structured results, and workflow metadata should expose `role_orchestration`, `role_orchestration_stages`, and `role_task_results`. Project-backed roles should also write role-stage artifacts under runtime `.uaf/artifacts/roles/`.
- Do not treat a `success` status as review evidence by itself. Implementer tasks need normalized task evidence, and gate results should grant evidence only from passed `evidence_records[*].evidence`, not from trace-only `metadata.evidence_key`.
- Use `GoalLedger` for runtime `.uaf/state/current_goal.json` and `.uaf/state/goal_events.jsonl` persistence when goal metadata is present.
- Use `ResumeHandoff` when a future host session needs to continue without previous chat context. The workflow metadata key is `resume_handoff`, and the runtime files are `.uaf/state/resume_handoff.json` and `.uaf/state/resume_handoff.md`.
- Use `MemoryScopeResolver` and `MemoryStore` when attaching `memory_context` to workflow metadata or `GoalState.metadata`; store uncertain facts as candidates before promotion.
- Use `large_work_orchestration_bundle` for large project, SaaS, app, multi-file implementation, role-DAG, or long-running workflows. Its `skill_statuses` must account for `request-complexity-router`, `host-agent-orchestration`, `goal-state-harness`, `development-lifecycle-harness`, `token-optimizer`, `memory-state-harness`, `parallel-orchestration-harness`, `subagent-review-pipeline`, `role-execution-audit-harness`, `compound-engineering-harness`, and `workflow-skill-distiller` as `applied`, `considered_not_needed`, `skipped_with_rationale`, or `blocked`.
- Use `WorkflowTaskInput` and `LocalTaskRunner` for bounded local file tasks. Do not treat webhook success as the source of task truth.
- Use `GeneratedTaskArtifact`, `DeterministicCodeGenerationAdapter`, or `LLMCodeGenerationAdapter` when implementing local generation paths behind `LocalTaskRunner`.
- Local `AgentLoop` dispatch metadata passes the active `LLMRouter` to workflow workers so local file generation can use the LLM-backed adapter instead of only deterministic artifacts.
- Use `CommandCheckInput`, `CommandCheckRunner`, and `command_check_presets(...)` for bounded local verification commands. Pass commands as argument lists; do not rely on shell parsing.
- Use `BrowserQACheckInput`, `BrowserQACheckResult`, `BrowserQACheckRunner`, and `BrowserQASidecarAdapter` for browser/QA evidence boundaries. Inject a concrete browser adapter or configure `browser_qa_sidecar.command`; no-adapter mode should return a structured blocked result. Workflow metadata can pass `browser_qa_checks` so QA evidence participates in `GoalState` completion.
- Use `WorkflowCheckStage` when adding workflow-level check sources. Keep planning, execution, required evidence, and evidence aggregation outside `src.tasks.workflows`.
- Use workflow `metadata["retention_policy"]` to trim repeated-run state when requested: `goal_events`, `artifact_events`, `memory_events`, and `snapshots` are supported.
- Use `WorkflowDispatchResult.task_results` and `WorkflowDispatchResult.gate_results` for worker status, optional webhook reporting metadata, and reviewer/QA/security/release gate results.
- For Codex and Antigravity Windows app integrations, call `src.core.app_bridge.create_app_request(...)` and `dispatch_app_request(...)` directly instead of shelling through the CLI.
- Add new UAF skills and harnesses as `skills/<skill-name>/SKILL.md` plus support files under `references/`, `examples/`, and `scripts/`. The packaged skill folder is the source of truth.
- Keep each packaged `SKILL.md` operational: include behavior steps, `Required outputs`, `Common mistakes`, and `UAF implementation targets` so the catalog rejects shallow notes.
- Use `src.skills.uaf_skill_catalog` to list/read packaged UAF skill folders. External systems are development references only, not runtime dependencies.

## Packaged Harnesses
- **Core role graph**: `orchestration-role-graph` for CEO, advisor, product strategy, development architect, planner, controller, implementer, review, QA, security, and release roles.
- **Host orchestration**: `host-agent-orchestration` for agent profiles, subagents, tool permissions, lifecycle hooks, error recovery, and observability across Codex, Antigravity-style, Claude Code, and local runtimes.
- **Domain orchestration**: `domain-orchestration-harness` for mandatory WorkDesign, domain roles, artifact manifests, review, QA/QC, risk, policy, and final decision gates across arbitrary topics.
- **Personal skillbook workflow**: `development-lifecycle-harness`, `subagent-review-pipeline`, and `quality-gates-harness` for planning, TDD, review roles, debugging, and evidence-based completion.
- **Command operations**: `command-output-harness` and `command-hook-policy-harness` for compact command output, exit-code preservation, token-savings tracking, hook trust, and permission precedence.
- **Review, state, and goal/memory workflow**: `review-gate-harness`, `qa-gate-harness`, `context-state-harness`, `goal-state-harness`, `memory-state-harness`, `guard-policy-harness`, and `health-check-harness` for structured review, QA, context handoff, objective tracking, scoped persistent memory, safety policy, and health reporting.
- **Snapshot rollback**: `snapshot-state-harness` for project/chat-scoped runtime gzip checkpoints, rollback, retention pruning, and `.snapshots` metadata protection.

## Security Constraints
When utilizing this framework, remember that the sandbox enforces strict checks via AST parsing. If you are generating AI code that requires `os`, `sys`, or `subprocess`, the framework will intentionally block it unless you run it with `--no-sandbox`. 
