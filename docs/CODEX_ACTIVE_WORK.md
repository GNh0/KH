# Codex Active Work Ledger

This file is the repo-local working ledger for Codex sessions on UAF.
Read it first after context compaction, a new session, or any long pause.

## Update Rule

- Update this file before starting a substantial new UAF task.
- Update it after completing a substantial task or changing the recommended next step.
- Do not delete completed context that explains the current direction; move it to `Completed`.
- Keep the active section short enough to scan in under a minute.

## Current Objective

Make UAF progress from a contract-heavy orchestration skeleton into an execution-capable local agent framework while preserving the Python core and adding TypeScript only where it clearly helps.

## Current Verified State

- Repository: `GNh0/KH`, local path `C:\Users\User\Documents\Codex\KH`.
- Core direction approved by user: improve incrementally, taking useful ideas from gstack/Superpowers-style skill repositories.
- Python core should remain the stable center for now.
- TypeScript is best treated as a future sidecar for browser adapters, dashboards, and skill/template tooling.
- Latest full verification after scoped persistent memory support:
  - `python -m json.tool plugin.json`
  - `python -m src.skills.uaf_skill_catalog --check`
  - `python -m unittest discover -s tests -v` (132 tests)
  - `python -B -c "import pathlib; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in pathlib.Path('.').rglob('*.py')]"`

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
- Added gstack-derived UAF-native harness skills:
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
- Reworked `README.md` to reflect current implementation level, references, verification, and roadmap.
- Reworked `AgentLoop` user-facing prompts and target-file prompt from mojibake into ASCII English so LLM target-file selection is usable.

## Active Decision

The persistent goal ledger exists. The local execution path now has runner, check, QA, sidecar, evidence, registry, evidence-alias, and scoped persistent-memory boundaries. Antigravity and Browser/QA both have dependency-free JSON sidecar protocols, so host-specific packages can live outside the Python core.

Active task: none. Recommended next improvement is optional host package scaffolding only when the actual Antigravity SDK or Playwright runtime is introduced.

There are two related layers:

1. Codex working continuity:
   - This file is the immediate working ledger for the assistant.
   - It exists so context compaction does not erase current direction and pending tasks.

2. UAF product feature:
   - Repo-local persistent goal ledger lives under `.uaf/state/`.
   - `current_goal.json` is the resumable state snapshot.
   - `goal_events.jsonl` is append-only audit history.

3. UAF scoped persistent memory:
   - Project memory lives under `.uaf/memory/`.
   - Projectless chat memory should use a conversation namespace outside a repo.
   - Archived conversation memory is retained.
   - Deleted/missing conversation memory is quarantined by default.
   - Codex desktop local registry can identify active vs archived threads when `state_5.sqlite` is available.

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

Implement next host-specific package when runtime details are explicit:

1. Keep Python core contracts stable and avoid adding host-specific dependencies to the core package.
2. Add concrete sidecar packages only when the host runtime and dependency installation path are known.
3. Add focused tests with fake adapters/sidecars before implementation.
4. Update README, skills, and this ledger.
5. Run full verification.

## Open Risks

- Default `LocalTaskRunner` writes deterministic generated artifacts; `LLMCodeGenerationAdapter` exists but must be explicitly injected.
- Antigravity dispatcher has an injected native boundary, but no concrete host SDK adapter is bundled.
- Browser/QA has a Python contract boundary, workflow integration, and JSON sidecar adapter, but no concrete Playwright package is bundled.
- Persistent memory has local contracts/store and Codex registry polling support, but no Hermes/OpenClaw provider adapter is bundled.
- Check/QA pipeline is extracted; remaining workflow growth points are ledger persistence, gate evaluation, and result assembly.
