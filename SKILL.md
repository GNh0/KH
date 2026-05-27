---
name: universal-agent-framework
description: "A pure-local, highly concurrent, and sandboxed AI coding orchestration framework. Use this skill when the user asks to orchestrate a complex coding project or when you need to parallelize multiple file generations."
---

# Universal Agent Framework (UAF)

This is a local-first, zero-dependency, and hyper-concurrent agentic coding framework. It uses a Pure Python `asyncio` architecture to bypass traditional broker limits and can safely test Python code on Windows via `multiprocessing`-based sandboxing.

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
- **`src/contracts.py`**: Shared contracts for Codex, Antigravity, Claude Code, and local adapters (`GoalState`, `HarnessResult`, `SkillManifest`, `AdapterRequest`, `AdapterResult`, `WorkflowTaskResult`, `WorkflowDispatchResult`).
- **`cli.py`**: The main entry point. Orchestrates the Server + Agent Loop.
- **`src/core/app_bridge.py`**: App-first integration helper for Codex and Antigravity Windows app hosts. Builds role-aware `AdapterRequest` objects without CLI parsing.
- **`src/orchestration/agent_loop.py`**: The central loop (Architect -> Dispatcher -> Evaluator).
- **`src/orchestration/evidence_producers.py`**: Normalizes command, review, and QA results into `GoalState.evidence` keys.
- **`src/orchestration/extension_registry.py`**: Shared registry for pluggable dispatchers, LLM providers, skill harnesses, and future host adapters.
- **`src/orchestration/gate_evaluators.py`**: Focused spec, code-quality, QA, security, and release gate evaluators that emit structured findings and evidence records.
- **`src/orchestration/goal_evidence.py`**: Goal evidence normalization and complete/blocked evaluation for QA and release gates.
- **`src/orchestration/goal_ledger.py`**: Project-local `.uaf/state/` persistence for resumable current goal state and append-only goal events.
- **`src/orchestration/llm_router.py`**: Built-in OpenAI-compatible and Anthropic routing plus custom LLM provider registration.
- **`src/orchestration/roles.py`**: Default UAF role graph (`ceo`, `advisor`, `system-architect`, `controller`, `implementer`, reviewers, QA, security, release).
- **`src/platforms/antigravity_native.py`**: Native Antigravity dispatch result contract for injected host adapters and JSON process sidecars.
- **`src/tasks/browser_qa.py`**: Browser/QA check contract boundary for injected browser adapters and JSON process sidecars, including future TypeScript/Playwright sidecars.
- **`src/tasks/checks.py`**: Bounded command check runner and named presets that convert subprocess results into evidence producer records.
- **`src/tasks/runners.py`**: Local bounded-task runner with deterministic and LLM-backed code-generation adapters. Runner output is the source of truth for `WorkflowTaskResult`; webhook reporting is side-effect metadata.
- **`src/tasks/workflow_checks.py`**: Typed workflow check stage for command and Browser/QA planning, execution, evidence aggregation, and success calculation.
- **`src/tasks/workflows.py`**: The `asyncio` queue-based worker engine. Replaces Celery.
- **`src/harness/sandbox.py`**: A secure code runner. Uses `multiprocessing` for absolute timeout guarantees on Windows.
- **`src/core/snapshot_manager.py`**: State rollback system utilizing pure `gzip` for 90% disk space reduction.
- **`src/api/server.py`**: An optional FastAPI webhook receiver using `aiosqlite` with WAL mode for external host callbacks.
- **`skills/`**: Packaged UAF-native skill and harness catalog. Add a new skill by creating `skills/<skill-folder>/SKILL.md`.

## Integration Contracts
External agents should exchange structured data through the contracts module instead of ad-hoc dictionaries:
- Use `HarnessResult` for sandbox/evaluator execution results.
- Use `SkillManifest` to normalize plugin and skill metadata.
- Use `AdapterRequest` and `AdapterResult` when implementing Codex, Antigravity, Claude Code, or local dispatch adapters.
- Use `ExtensionRegistry`, `DispatcherFactory.register_dispatcher(...)`, and `LLMRouter.register_provider(...)` for new host modes or LLM backends. Avoid hardcoding provider-specific branches unless the provider is part of the core runtime.
- Use `AntigravityNativeDispatchResult` and `AntigravityNativeSidecarAdapter` when bridging an Antigravity host-native adapter into UAF; keep no-adapter behavior as structured pending. Metadata can provide `antigravity_native_sidecar.command` to launch a sidecar without Python object injection.
- Use `GoalState` metadata to carry objective, required evidence, collected evidence, and complete/blocked status through the workflow.
- Use `src.orchestration.evidence_producers` to convert command, review, and QA outputs into normalized evidence records before adding them to task or gate metadata.
- Use `src.orchestration.gate_evaluators` for focused review/QA/security/release gate decisions; keep `src.orchestration.roles.build_role_gate_results(...)` as the public compatibility wrapper.
- Use `GoalLedger` for `.uaf/state/current_goal.json` and `.uaf/state/goal_events.jsonl` persistence when goal metadata is present.
- Use `WorkflowTaskInput` and `LocalTaskRunner` for bounded local file tasks. Do not treat webhook success as the source of task truth.
- Use `GeneratedTaskArtifact`, `DeterministicCodeGenerationAdapter`, or `LLMCodeGenerationAdapter` when implementing local generation paths behind `LocalTaskRunner`.
- Local `AgentLoop` dispatch metadata passes the active `LLMRouter` to workflow workers so local file generation can use the LLM-backed adapter instead of only deterministic artifacts.
- Use `CommandCheckInput`, `CommandCheckRunner`, and `command_check_presets(...)` for bounded local verification commands. Pass commands as argument lists; do not rely on shell parsing.
- Use `BrowserQACheckInput`, `BrowserQACheckResult`, `BrowserQACheckRunner`, and `BrowserQASidecarAdapter` for browser/QA evidence boundaries. Inject a concrete browser adapter or configure `browser_qa_sidecar.command`; no-adapter mode should return a structured blocked result. Workflow metadata can pass `browser_qa_checks` so QA evidence participates in `GoalState` completion.
- Use `WorkflowCheckStage` when adding workflow-level check sources. Keep planning, execution, required evidence, and evidence aggregation outside `src.tasks.workflows`.
- Use `WorkflowDispatchResult.task_results` and `WorkflowDispatchResult.gate_results` for worker status, optional webhook reporting metadata, and reviewer/QA/security/release gate results.
- For Codex and Antigravity Windows app integrations, call `src.core.app_bridge.create_app_request(...)` and `dispatch_app_request(...)` directly instead of shelling through the CLI.
- Add new UAF skills and harnesses as `skills/<skill-name>/SKILL.md`. The packaged skill folder is the source of truth.
- Use `src.skills.uaf_skill_catalog` to list/read packaged UAF skill folders. External Gemini, Antigravity, RTK, and Superpowers systems are development references only, not runtime dependencies.

## Packaged Harnesses
- **Core role graph**: `orchestration-role-graph` for CEO, advisor, product strategy, development architect, planner, controller, implementer, review, QA, security, and release roles.
- **Antigravity-derived**: `antigravity-agent-orchestration` for agent profiles, subagents, tool permissions, lifecycle hooks, error recovery, and observability.
- **Superpowers-derived**: `development-lifecycle-harness`, `subagent-review-pipeline`, and `quality-gates-harness` for planning, TDD, review roles, debugging, and evidence-based completion.
- **RTK-derived**: `rtk-command-output-harness` and `command-hook-policy-harness` for compact command output, exit-code preservation, token-savings tracking, hook trust, and permission precedence.
- **gstack-derived and goal-aware**: `review-gate-harness`, `qa-gate-harness`, `context-state-harness`, `goal-state-harness`, `guard-policy-harness`, and `health-check-harness` for structured review, QA, context handoff, objective tracking, safety policy, and health reporting.
- **Snapshot rollback**: `snapshot-state-harness` for project-local gzip checkpoints, rollback, and `.snapshots` metadata protection.

## Security Constraints
When utilizing this framework, remember that the sandbox enforces strict checks via AST parsing. If you are generating AI code that requires `os`, `sys`, or `subprocess`, the framework will intentionally block it unless you run it with `--no-sandbox`. 
