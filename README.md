# Universal Agent Framework (UAF)

UAF is a Python-first, local-first orchestration framework for AI agents such as Codex, Antigravity, Claude Code, and other host runtimes.

The project packages reusable agent workflows as two things:

- Python contracts and dispatchers under `src/`
- Host-readable skills under `skills/<skill-folder>/SKILL.md`

The goal is to make domain profiling, mandatory design, persisted artifacts, role graphs, planning, worker dispatch, review gates, QA/QC gates, safety policy, snapshots, memory, and goal tracking portable across agent hosts without depending on one vendor-specific runtime folder.

## Design References

UAF intentionally borrows the strongest ideas from mature agent-workflow references, then adapts them to this repo's Python core and personal skillbook.

| Reference | What UAF takes from it |
|-----------|------------------------|
| External agent workflow references | Skill-as-workflow structure, role-specialized review/QA/release gates, guard policies, browser/QA direction, host adapter mindset, and skill quality checks. |
| Personal skillbook workflow | Explicit planning, TDD, systematic debugging, subagent-oriented development, and evidence-before-completion discipline. |
| Command operations patterns | Command output normalization, hook policy boundaries, metadata-first execution records, and fail-safe behavior. |

UAF does not vendor external reference repositories. The current implementation keeps the stable core in Python and leaves TypeScript as a good future sidecar option for browser adapters, dashboards, and skill template tooling.

## Personal Skillbook

Project planning records live under `docs/skillbook/`. This folder is not runtime state and does not represent an external dependency. It is KH/UAF's personal skillbook: design notes, implementation plans, and handoff decisions that explain why a harness exists and how it should evolve.

Runtime continuation state defaults to the user-local UAF runtime store, not the target project root. Packaged host-readable skills still live under `skills/`.

## Current State

What works today:

- CLI entrypoint for local project runs.
- Optional FastAPI webhook server for external host callbacks and reporting.
- Dataclass contracts for adapter requests, results, workflow results, and goal state.
- Scoped persistent memory contracts for project and conversation namespaces.
- DomainProfile, WorkDesign, DesignArtifact, and ArtifactManifest contracts for domain-neutral orchestration.
- Mandatory workflow design-stage persistence under the project-scoped runtime `.uaf/artifacts/design/` and `.uaf/state/artifact_manifest.json`.
- User-facing Office deliverable export under the target project's `docs/` folder: requirements brief, orchestration design, deliverable definition, process flow, role/task breakdown, evidence plan, risk/policy checklist, and conditional user manual.
- Resume-safe handoff snapshots under the project-scoped runtime `.uaf/state/resume_handoff.json` and `.uaf/state/resume_handoff.md`.
- Role graph metadata for architect, implementer, reviewers, QA, security, and release roles.
- DAG-based role orchestration with asyncio waves: CEO, advisor/product strategist, architect, planner, controller, implementers, review, QA/security, and release roles run as real `WorkflowTaskResult` producing stages when dependencies are satisfied.
- Focused review, QA, security, and release gate evaluators.
- Local and Antigravity dispatcher contracts.
- Antigravity native dispatch boundary with injected and JSON process sidecar adapters, plus pending fallback when no host adapter is configured.
- Extension registry for custom host dispatchers and LLM providers.
- Async workflow fan-out/fan-in harness.
- Local task runner with a swappable code-generation adapter for bounded file tasks.
- Bounded command check runner and curated presets that turn subprocess results into evidence records.
- Browser/QA runner boundary and JSON sidecar adapter that convert injected or process-backed adapter results into QA evidence records.
- Typed workflow check stage for command and Browser/QA planning, execution, evidence aggregation, and success calculation.
- Evidence producer helpers for command, review, and QA result metadata.
- Python sandbox and evaluator.
- Gzip snapshot manager with work-level multi-file snapshot bundles.
- Packaged skill catalog with validation.
- GoalState metadata attached to dispatch requests and workflow results.
- Goal evidence evaluation, including conservative aliases, that blocks QA/release gates when required evidence is missing.
- Workflow GoalState metadata now carries domain profile, work design, artifact manifest context, and user-facing deliverable export paths.
- Workflow task metadata can carry normalized evidence records into `GoalState.evidence`.
- Gate results carry structured findings and evidence records for downstream goal/release checks.
- Persistent project-scoped goal ledger under the UAF runtime store for resumable workflow state.
- Project/chat-scoped persistent memory store under the UAF runtime store, with JSON records, JSONL events, memory candidates, and cleanup policy.
- Optional Codex desktop thread registry reader for active/archived conversation memory cleanup when the local registry is available.
- Codex plugin manifest under `.codex-plugin/plugin.json`.
- Antigravity workspace plugin bootstrap under `.agents/plugins/kh-uaf/`.
- Unit tests covering the contracts, catalog, dispatcher, sandbox, snapshots, server, and workflow harness.

What is still intentionally incomplete:

- The default `LocalTaskRunner` remains deterministic when used alone, but `AgentLoop` local runs now pass the active `LLMRouter` into `LLMCodeGenerationAdapter` for file generation.
- The Antigravity dispatcher can consume an injected native adapter or JSON process sidecar, but no concrete external Antigravity host SDK package is bundled yet.
- Browser/QA execution has a Python contract boundary, workflow evidence integration, and JSON process sidecar adapter, but no bundled Playwright implementation yet.
- Workflow metadata can run bounded command checks, named presets, or browser/QA checks and feed the resulting evidence into `GoalState`.
- External memory providers such as Hermes or OpenClaw are not bundled; UAF now has the local contracts and store that a provider adapter can implement later.
- TypeScript tooling is not part of the core package yet.

## Quick Start

```bash
pip install -r requirements.txt
python cli.py run --project ./my_app --prompt "Create a FastAPI backend"
python cli.py run --project ./my_app --prompt "Create a FastAPI backend" --platform antigravity
```

Useful commands:

```bash
# List packaged skills
python -m src.skills.uaf_skill_catalog --list

# Read a specific skill
python -m src.skills.uaf_skill_catalog --read orchestration-role-graph
python -m src.skills.uaf_skill_catalog --read goal-state-harness

# Validate all packaged skills
python -m src.skills.uaf_skill_catalog --check

# Run tests
python -m unittest discover -s tests -v
```

## Codex Plugin Install

This repo can be installed as a Codex plugin because it includes `.codex-plugin/plugin.json`, points Codex at the packaged `skills/` directory, and exposes a repo marketplace at `.agents/plugins/marketplace.json`.

In the Codex app, open Plugins -> Manage -> Add marketplace and use:

```text
Source: GNh0/KH
Git ref: main
Sparse path: .agents/plugins
```

The sparse path is optional, but it keeps the marketplace checkout focused on the Codex marketplace file. After adding the marketplace, install `KH UAF` from the plugin directory and start a new thread.

The same marketplace can be added from the CLI:

```bash
codex plugin marketplace add GNh0/KH --ref main --sparse .agents/plugins
```

Recommended clone path on another PC:

```bash
git clone https://github.com/GNh0/KH.git ~/plugins/kh-uaf
cd ~/plugins/kh-uaf
python -m src.skills.uaf_skill_catalog --check
```

Then ask Codex in that environment:

```text
Register ~/plugins/kh-uaf as a local Codex plugin using .codex-plugin/plugin.json,
install the kh-uaf plugin, then start a new thread so the KH UAF skills are loaded.
```

On Windows, use a concrete path such as:

```powershell
git clone https://github.com/GNh0/KH.git "$env:USERPROFILE\plugins\kh-uaf"
cd "$env:USERPROFILE\plugins\kh-uaf"
python -m src.skills.uaf_skill_catalog --check
```

The root `plugin.json` remains the UAF runtime manifest. The Codex-specific plugin manifest lives at `.codex-plugin/plugin.json`.

## Antigravity Plugin Install

Antigravity can load KH UAF in two ways:

1. Global plugin: clone this repo into Antigravity's global plugin directory so the full `skills/` catalog is available across workspaces.
2. Workspace bootstrap: open this repo as a workspace; Antigravity can discover `.agents/plugins/kh-uaf/`, which points the agent back to the root UAF skillbook and harness.

Global install on Windows:

```powershell
git clone https://github.com/GNh0/KH.git "$env:USERPROFILE\.gemini\config\plugins\kh-uaf"
cd "$env:USERPROFILE\.gemini\config\plugins\kh-uaf"
python -m src.skills.uaf_skill_catalog --check
```

Global install on macOS/Linux:

```bash
git clone https://github.com/GNh0/KH.git ~/.gemini/config/plugins/kh-uaf
cd ~/.gemini/config/plugins/kh-uaf
python -m src.skills.uaf_skill_catalog --check
```

For a workspace-local install in another project, place or copy the plugin folder under:

```text
<workspace-root>/.agents/plugins/kh-uaf/
```

Antigravity's workspace bootstrap plugin included in this repo is intentionally small. It exposes the `kh-uaf` skill and tells the agent to use the root `skills/`, `SKILL.md`, and UAF validation commands. For full global access to every packaged KH UAF skill, use the global plugin clone path above.

## Core Flow

```text
cli.py run
  -> SystemArchitect writes design_doc.md
  -> AgentLoop attaches role graph metadata and GoalState
  -> Scoped memory context is loaded when memory is enabled
  -> DomainProfile and WorkDesign are created for the objective
  -> Design artifacts are persisted and attached as an ArtifactManifest
  -> DispatcherFactory selects local or Antigravity mode
  -> Workflow workers fan out file-level implementer tasks through LocalTaskRunner
  -> Goal evidence is evaluated before QA/release completion
  -> Goal ledger writes runtime .uaf/state/current_goal.json and goal_events.jsonl
  -> Resume handoff writes runtime .uaf/state/resume_handoff.json and resume_handoff.md
  -> Review, QA, security, and release gate metadata is collected
  -> WorkflowDispatchResult returns task_results, gate_results, metadata.goal, and metadata.resume_handoff
```

The default local worker now calls `LocalTaskRunner` for each bounded file task and treats the returned `WorkflowTaskResult` as the source of truth. Webhook posting is optional and only runs when `AG_WEBHOOK_URL` is set; the result is recorded as a reporting side effect under `task_result.metadata["webhook_report"]`. The runner validates target paths, writes generated artifacts through `DeterministicCodeGenerationAdapter`, and emits runner evidence including `code generated`. `LLMCodeGenerationAdapter` can be supplied when a host wants local generation to call an injected LLM router.

`src.tasks.checks.CommandCheckRunner` can run a bounded command list with `shell=False` from the project root and return a command evidence record. Successful checks emit the requested evidence key; failed or rejected checks preserve stdout/stderr and exit metadata without granting evidence. Workflow metadata can provide `command_checks`, and those evidence keys are added to `GoalState.evidence_required` for that run.

Workflow metadata can also provide `command_check_presets` for common checks. Current presets are `plugin-json`, `python-compile`, `python-unittest`, and `skill-catalog`; each expands into a bounded `CommandCheckInput` and contributes its evidence key to the active `GoalState`.

`src.tasks.browser_qa.BrowserQACheckRunner` is the browser/QA adapter boundary. It accepts `BrowserQACheckInput`, calls an injected adapter when available, and converts `BrowserQACheckResult` into QA evidence records. If no adapter is configured, it returns a structured blocked result without granting evidence. `BrowserQASidecarAdapter` can launch a configured process with the check JSON on stdin and read a `BrowserQACheckResult` JSON object from stdout, which lets a TypeScript/Playwright sidecar plug in without changing Python core contracts.

`src.tasks.workflow_checks.WorkflowCheckStage` owns command and Browser/QA check planning for workflows. It preserves metadata compatibility while keeping `src.tasks.workflows` focused on orchestration, goal evaluation, ledger persistence, and final result assembly. Browser sidecars can be configured with `metadata["browser_qa_sidecar"] = {"command": [...]}`.

`src.platforms.antigravity_native.AntigravityNativeDispatchResult` is the native host boundary for Antigravity-style integrations. `AntigravityDispatcher` uses it when a native adapter is injected, or when metadata provides `antigravity_native_sidecar.command`. The sidecar adapter sends `AdapterRequest` JSON on stdin and expects `AntigravityNativeDispatchResult` JSON on stdout. If neither adapter path is configured, the dispatcher returns a structured pending result and leaves external callbacks optional.

`src.orchestration.extension_registry.ExtensionRegistry` is the shared extension point for host and provider integration. `DispatcherFactory.register_dispatcher(...)` lets a host add another dispatch mode without changing the core switch logic, and `LLMRouter.register_provider(...)` lets another LLM backend supply a provider object behind the same `chat(system, user)` contract.

## Domain Orchestration and Design Artifacts

UAF now treats design as a mandatory workflow stage, not a software-only convention. A request can be software development, equipment planning, investment analysis, operations, education, legal review, research synthesis, or another topic. The core flow is still the same:

```text
understand objective
  -> identify domain and subdomains
  -> assign roles
  -> run ready role tasks through DAG-based asyncio waves
  -> create WorkDesign
  -> persist required design artifacts
  -> execute bounded tasks
  -> review, analysis, QA/QC, risk, policy, and final gates
  -> complete or block based on GoalState evidence
```

`src.orchestration.domain_profiles.DomainProfileBuilder` creates a generic `DomainProfile` when no domain taxonomy is known. It carries subdomains, roles, artifact types, review gates, risk/policy gates, and required evidence. `work_design_from_profile(...)` turns that profile into a `WorkDesign`.

`src.orchestration.artifacts.ArtifactStore` saves the work design and any supplied design artifacts under the UAF runtime store, normally `%LOCALAPPDATA%/KH-UAF/projects/<project-key>/.uaf/artifacts/design/`, then writes `.uaf/state/artifact_manifest.json` in the same project-scoped runtime slot. Set `UAF_RUNTIME_ROOT` to choose another runtime root, or set `UAF_PROJECT_LOCAL_STATE=1` only when you explicitly want `.uaf/` inside the target project. The manifest is attached to `WorkflowDispatchResult.metadata["artifact_manifest"]` and to `GoalState.metadata["artifact_manifest"]`, so resume-safe goal ledger state can prove which design artifacts existed when the workflow completed or blocked.

`src.orchestration.role_orchestrator.RoleOrchestrator` executes the role graph as a dependency DAG. Ready roles in the same wave are launched with `asyncio.create_task(...)`; the default graph now runs `advisor` and `product-strategist` in parallel after `ceo`, runs file implementers through the existing bounded worker queue, and runs `qa-verifier` and `security-reviewer` in parallel before `release-manager`. The workflow metadata records `role_orchestration`, `role_orchestration_stages`, and `role_task_results` so a host can see which roles actually executed, which roles were blocked, and how many parallel waves ran.

`src.orchestration.deliverable_exports.export_office_deliverables(...)` writes user-facing work products directly into the target project's `docs/` folder. These are not internal `.uaf` state files. The default export is domain-neutral and works for software, operations, research, planning, analysis, or any other orchestration topic:

- `docs/요구정의서.docx`
- `docs/오케스트레이션_설계서.docx`
- `docs/산출물_정의서.docx`
- `docs/처리흐름도.docx`
- `docs/역할별_작업분해표.xlsx`
- `docs/증거계획서.xlsx`
- `docs/위험_정책_체크리스트.xlsx`

`docs/사용_매뉴얼.docx` is conditional, not mandatory. It is generated when `export_manual` is true, when manual revision metadata is supplied, or when the workflow looks operational/procedural enough to need user or operations instructions. Analysis-style domains such as investment, valuation, portfolio review, research, or generic analysis skip the manual by default. When generated, the manual starts with a `리비전 버전 관리` section using `manual_revision` and `manual_revision_note` metadata, defaulting to `Rev. 1.0`.

The default design-stage evidence keys are `work design saved`, `artifact manifest saved`, and `required design artifacts saved`. Office export adds `requirements brief exported`, `orchestration design exported`, `deliverable definition exported`, `process flow exported`, `role task breakdown exported`, `evidence plan exported`, and `risk policy checklist exported`. Conditional manual export adds `manual exported` only when `사용_매뉴얼.docx` is actually written. These can be required by `GoalState.evidence_required` and are collected during workflow dispatch before QA/release gates evaluate completion.

## Persistent Memory

UAF separates short-lived workflow state from long-lived memory:

```text
%LOCALAPPDATA%/KH-UAF/projects/<project-key>/.uaf/
  state/
    current_goal.json
    goal_events.jsonl
  memory/
    project_memory.json
    memory_events.jsonl
    memory_candidates.jsonl
    scope_state.json
```

`GoalLedger` answers "what is currently being worked on?" while `MemoryStore` answers "what should this project or conversation remember later?" Project work uses project-scoped memory under the runtime `.uaf/memory/`. Projectless chats use a conversation namespace such as `conversations/<thread_id>/.uaf/memory/`. Global memory is intentionally not the default and should require explicit user promotion.

`MemoryScopeResolver` chooses project memory when a workspace root exists and conversation memory when there is only a thread id. `MemoryStore` persists verified `MemoryRecord` values, appends audit events, and keeps uncertain facts in `memory_candidates.jsonl` until they are promoted. Secret-like content such as API keys, tokens, private keys, and credentials is rejected before it is stored.

When workflow metadata sets `enable_memory`, dispatch loads memory context and attaches it to both `WorkflowDispatchResult.metadata["memory_context"]` and `GoalState.metadata["memory_context"]`, so the goal ledger can resume with the same scoped memory context.

`src.platforms.codex_thread_registry.CodexThreadRegistry` can read the local Codex desktop `threads` registry when available. It detects active and archived threads from the registry and drives conversation memory cleanup. Deleted thread memory is handled conservatively by absence from the registry: the default cleanup action is quarantine, not immediate hard delete.

## Resume Handoff

UAF writes a resume handoff whenever workflow goal metadata is present. The handoff is deliberately simple and project-scoped:

```text
%LOCALAPPDATA%/KH-UAF/projects/<project-key>/.uaf/
  state/
    current_goal.json
    goal_events.jsonl
    artifact_manifest.json
    resume_handoff.json
    resume_handoff.md
```

`src.orchestration.handoff.ResumeHandoff` reads the current goal, missing evidence, artifact manifest, and optional memory context. It writes a JSON snapshot for host tooling and a Markdown handoff note for the next LLM session. A later Codex, Antigravity, or other host run can inspect `resume_handoff.md` without the previous chat transcript and know the objective, status, missing evidence, artifact basis, and next recommended action.

## Default Roles

The canonical role graph lives in `src/orchestration/roles.py`.

```text
ceo
advisor
product-strategist
system-architect
implementation-planner
controller
implementer
spec-reviewer
code-quality-reviewer
qa-verifier
security-reviewer
release-manager
```

## GoalState

UAF now carries an explicit `GoalState` contract through orchestration metadata.

`GoalState` records:

- objective
- active, completed, or blocked status
- success criteria
- required evidence
- collected evidence
- progress notes
- blocked reason
- implementation metadata

Workflow dispatch now adds deterministic evidence such as `design_doc`, `target_files`, and `workflow dispatch completed`. The goal evidence evaluator compares those values with `GoalState.evidence_required`, marks the goal `complete` only when required evidence is present, and marks it `blocked` when evidence or workflow execution is missing. The evaluator supports conservative default aliases such as `design_doc`/`design doc` and `unit tests passed`/`tests passed`, plus workflow-provided aliases through `GoalState.metadata["evidence_aliases"]`. Alias hits are recorded under `metadata.evidence_alias_matches` so a release gate can audit why a required evidence key was accepted. QA and release gates use that evaluated goal before reporting completion.

When goal metadata is present, local workflow dispatch also writes a resume-safe ledger:

```text
%LOCALAPPDATA%/KH-UAF/projects/<project-key>/.uaf/
  state/
    current_goal.json
    goal_events.jsonl
```

`current_goal.json` stores the latest objective, status, task buckets, evidence, blocked reason, and next recommended action. `goal_events.jsonl` is append-only history for `goal_created`, `goal_updated`, `evidence_added`, `goal_completed`, and `goal_blocked` events. Runtime `.uaf/` folders are outside the target project by default; if `UAF_PROJECT_LOCAL_STATE=1` is used, local `.uaf/` should be ignored by git.

## Packaged Skills

The catalog scans `skills/` and exposes each `SKILL.md` through `src.skills.uaf_skill_catalog`.

### Orchestration and Adapters

| Skill | Purpose |
|-------|---------|
| `orchestration-role-graph` | Default CEO, advisor, planner, implementer, reviewer, QA, security, and release role contracts plus DAG execution metadata. |
| `adapter-contract-harness` | Shared request/result expectations for Codex, Antigravity, Claude, and local adapters. |
| `host-agent-orchestration` | Personal host agent/subagent/tool permission, hook, and observability patterns for Codex, Antigravity-style, Claude Code, and local runtimes. |
| `parallel-orchestration-harness` | DAG role waves, fan-out/fan-in task dispatch, worker limits, and aggregation rules. |
| `subagent-review-pipeline` | Implementer -> spec reviewer -> code quality reviewer flow. |

### Planning and Lifecycle

| Skill | Purpose |
|-------|---------|
| `architect-pipeline` | Convert a user requirement into a design document and target files. |
| `development-lifecycle-harness` | Planning, TDD, review, verification, and branch completion workflow. |
| `domain-orchestration-harness` | Domain-neutral WorkDesign, artifact manifest, review, QA/QC, risk, policy, and final decision workflow. |
| `quality-gates-harness` | TDD, systematic debugging, and evidence-before-completion requirements. |
| `workflow-skill-distiller` | Turn repeated workflows into reusable UAF skills. |

### Gates and State

| Skill | Purpose |
|-------|---------|
| `goal-state-harness` | Goal objective tracking, completion criteria, evidence requirements, and blocked-state reporting. |
| `memory-state-harness` | Scoped persistent memory, candidates, project/conversation namespace isolation, and cleanup policy. |
| `context-state-harness` | Context save/restore, handoff payloads, and continuation metadata. |
| `review-gate-harness` | Spec, code, and release review gate contracts for UAF workflows. |
| `qa-gate-harness` | QA checks, regression evidence, bug reports, and browser-adapter expectations. |
| `health-check-harness` | Code health dashboard inputs, readiness scoring, and trend signals. |

### Safety and Operations

| Skill | Purpose |
|-------|---------|
| `guard-policy-harness` | Destructive command warnings, edit boundary policy, and fail-safe execution rules. |
| `command-hook-policy-harness` | Hook trust, permission precedence, integrity checks, and passthrough behavior. |
| `command-output-harness` | Command output grouping, truncation, deduplication, and exit code preservation. |
| `snapshot-state-harness` | Work-level gzip checkpoint bundles, rollback semantics, and `.snapshots` protection rules. |
| `token-optimizer` | Long log and code output compression. |
| `harness-evaluator` | Python code sandbox evaluation. |
| `skill-catalog` | Packaged UAF skill listing, reading, and validation. |

## Skill Quality Checks

Every packaged skill is expected to have:

- valid YAML frontmatter
- a unique `name`
- a trigger-focused `description` that starts with `Use when`
- one top-level H1
- a behavior section such as `## Workflow`, `## Instructions`, `## Core Flow`, or equivalent
- a `## UAF implementation targets` section
- no unresolved `{{placeholder}}` tokens
- repository code references under implementation targets that resolve to importable modules, classes, functions, or existing skill files

Run:

```bash
python -m src.skills.uaf_skill_catalog --check
```

The check is repo-local and dependency-free. It now verifies both skill hygiene and the minimum behavior contract needed before treating a skill as installable.

## Windows App Integration

Windows app hosts can call the bridge directly instead of shelling through the CLI. The default app-oriented platform mode is `antigravity`.

```python
from src.core.app_bridge import create_app_request, dispatch_app_request

request = create_app_request(
    project_dir="C:/work/demo",
    files=["main.py"],
    design_doc="# design",
    app_host="codex",
    thread_id="thread-1",
)

result = dispatch_app_request(request)
```

For web or app hosts that cannot return results in-process, start the webhook server and set `AG_WEBHOOK_URL` to the callback endpoint. Local-only runs do not need the webhook server.

## Project Layout

```text
.codex-plugin/
  plugin.json
.agents/
  plugins/
    kh-uaf/
      plugin.json
      skills/
        kh-uaf/SKILL.md
cli.py
plugin.json
SKILL.md
requirements.txt
src/
  contracts.py
  core/
    app_bridge.py
    snapshot_manager.py
  orchestration/
    agent_loop.py
    evidence_producers.py
    extension_registry.py
    gate_evaluators.py
    goal_evidence.py
    goal_ledger.py
    memory_state.py
    memory_store.py
    roles.py
    llm_router.py
  platforms/
    antigravity_native.py
    codex_thread_registry.py
    dispatcher_factory.py
  tasks/
    browser_qa.py
    checks.py
    runners.py
    workflow_checks.py
    workflows.py
  harness/
    sandbox.py
    evaluator.py
  skills/
    uaf_skill_catalog.py
    uaf_skill_validator.py
skills/
  <skill-folder>/SKILL.md
tests/
```

## Environment

Set these only when you need to override the defaults.

| Variable | Default | Purpose |
|----------|---------|---------|
| `AG_WEBHOOK_URL` | unset | Optional subagent result webhook for external host callbacks. |
| `AG_API_KEY` | `antigravity-secret-key-v2` | API key used only when webhook reporting is enabled. |
| `AG_MAX_WORKERS` | `50` | Max async workers, clamped by CPU. |
| `AG_NO_SANDBOX` | `0` | Disable sandbox when set to `1`. |
| `AG_VERBOSE` | `0` | Verbose server logs. |
| `AG_PLATFORM_MODE` | `local` | Dispatcher platform mode for CLI and runner paths. |

## Verification

Use these before claiming a branch is ready:

```bash
python -m json.tool plugin.json
python -m json.tool .codex-plugin/plugin.json
python -m src.skills.uaf_skill_catalog --check
python -m unittest discover -s tests -v
python -B -c "import pathlib; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in pathlib.Path('.').rglob('*.py')]"
```

## Roadmap

Recommended next improvements:

1. Add concrete host packages for Antigravity SDK and TypeScript/Playwright once those runtimes are explicit.
2. Continue extracting the workflow pipeline into typed stages so runners, gates, ledger writes, and result assembly register without growing `workflows.py`.
3. Expand command check presets for project-specific lint, security, and release checks.
4. Feed other host-native adapter results through the same `GeneratedTaskArtifact`, `WorkflowTaskResult`, and evidence contracts.

The preferred direction is hybrid: keep UAF core contracts and orchestration in Python, then add TypeScript around host integrations, browser automation, dashboards, and template generation where it brings clear ecosystem advantages.
