# Universal Agent Framework (UAF)

[English](README.md) | [Korean](README.ko.md)

KH UAF is a local-first skill and harness framework for Codex, Antigravity-style agents, Claude Code, and local workers.

It combines:

- host-readable skills in `skills/<skill-folder>/SKILL.md`
- Python contracts, dispatchers, role orchestration, gates, state, and validators under `src/`
- practical release checks, SIDE regression tasks, and a SWE-bench-style local benchmark

The goal is not to depend on a vendor-specific local skill folder. UAF packages its own portable skills and harnesses.

## KH Front-Door Routing

Users should not need to name KH, UAF, or any individual skill/harness for non-trivial work. If KH is installed and the request involves project files, code changes, deliverables, substantial documents, long command output, review, QA, verification, branch finishing, subagents, persistent state, or high-risk actions, the host should first run the KH front door before source exploration or edits:

```bash
python -m src.orchestration.kh_front_door --prompt "<user request>" --project "<target project>" --host codex --summary
```

1. Apply `automatic-intake-harness` to decide whether ordinary user wording needs KH intake.
2. Inspect the KH root guide or packaged skill catalog.
3. Route through `plugin-composition-policy` and `request-complexity-router`.
4. Select the minimal skill bundle automatically.
5. Record each selected, considered, skipped, or blocked skill with evidence.
6. Start source reads, edits, role DAG execution, or deliverable generation only after that intake step.

This is the contract that prevents KH from becoming a manual checklist. The front-door command resolves the current repo-local or installed cache skill source, rejects stale KH cache paths, classifies the request, composes the provider route, and returns machine-readable selected/considered/skipped/blocked skill evidence. `session-skill-audit` flags a P1 `missing_front_door` issue when a KH-capable session begins non-trivial work before the front door runs, unless the request was classified as light/direct or plugin composition did not select KH.

## What It Includes

- 39 packaged skills/harnesses with support files, smoke checks, and runnable demos.
- Codex plugin manifests: `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json`.
- Antigravity workspace/global plugin bootstrap files.
- `brainstorming-harness` for early product/project discovery and KH handoff before architecture or implementation.
- `compound-engineering-harness` for mandatory post-review learning capture, scoped memory candidates, system updates, and regression checks.
- KH-native replacements for Superpowers-style worktree isolation, task-plan execution, systematic debugging, verification-before-completion, and branch finishing.
- Runtime token optimization for workflow command output and subagent transcripts, including RTK-style command-family savings statistics without requiring RTK as a dependency.
- Runtime memory candidate recording and full-catalog session skill audits with per-skill acceptance checks so useful skills are not left as invisible chat advice.
- DAG role orchestration with CEO, advisor, architect, planner, controller, implementer, reviewers, QA, security, and release roles.
- Bounded local workflow dispatch with review, QA, security, release, and evidence gates.
- Goal state, scoped memory, resume handoff, snapshots, and runtime state.
- Type-aware user deliverables under the target project's `docs/` folder.
- Render/template/traceability/role-audit quality harnesses.
- `KH-Bench Verified`, a practical task benchmark separate from internal skill quality scores.
- `KH Practical Quality Gate`, the release gate that treats KH-Bench/SIDE/E2E results as the primary quality signal and static skill scores as a structure check.
- `scenario-evaluation-harness`, a deterministic SIDE-style loop for request routing, evidence, gate, and resume behavior.

By default, user-facing files are written to the target project, while UAF runtime state is written outside the project root under the KH-UAF runtime store. Set `UAF_PROJECT_LOCAL_STATE=1` only when you explicitly want `.uaf` and snapshot state inside the project.

## Project-Local Artifacts

KH UAF separates reusable skills from per-project workflow artifacts.

- Reusable KH skills live in the KH checkout or installed plugin cache, not inside every target project.
- User-facing design and delivery artifacts should go under the target project's `docs/` folder.
- Runtime state, goal ledger, memory candidates, snapshots, traces, and handoff metadata default to the external KH-UAF runtime store.
- Set `UAF_PROJECT_LOCAL_STATE=1` when a project should carry its own `.uaf/` state for portable project memory or resume handoff.
- Human-readable KH notes and handoffs are written in the target project like Superpowers-style local artifacts: `.kh/<skill>/<run-id>/content/*.md` for KH working notes, `.kh/<skill>/<run-id>/state/*.json` for run-local state, and shareable Markdown under `docs/kh/specs/`, `docs/kh/plans/`, `docs/kh/decisions/`, `docs/kh/qa/`, or `docs/kh/handoffs/` by document type.
- Git-backed implementation should prefer an isolated workspace by default. Use host worktrees when the host provides them; otherwise use project-local `.worktrees/<task>` or an isolated branch. Git worktrees should live under `.worktrees/` when KH creates project-local isolation. Use the current checkout only for docs-only edits, a single-file small patch, or explicit in-place user instruction, and report `workspace_strategy` in the final status.
- Multi-task development runs should keep machine-readable progress at `.kh/development/<run-id>/state/progress.json`. The progress state records active task, RED/GREEN evidence, spec/code-quality review status, fix/re-review status, commit SHA, next task, `workspace_strategy`, and `token_optimizer_status`.
- Hosts that support native progress surfaces can also read `.kh/development/<run-id>/state/host_panel.<host>.json`. KH writes this host progress panel contract for Codex, Antigravity-style Agent Manager, generic CLI shells, and future hosts so the same run state can appear in each host's native panel without depending on Superpowers.

KH does not require `.superpowers/` or `docs/superpowers/` paths. If Superpowers is also installed, those folders are Superpowers-owned project artifacts; KH-owned runtime state should use `.uaf/`, KH local run notes/state should use `.kh/`, and KH shareable deliverables should use `docs/kh/` or the task-specific `docs/` export path.

KH local Markdown notes should use `.kh/`; KH shareable summaries should use `docs/kh/`; Superpowers-owned artifacts should remain in `.superpowers/` and `docs/superpowers/`.

Recommended KH project artifact layout:

```text
<target-project>/
  .kh/
    brainstorm/<run-id>/
      content/
      state/
    goal/<run-id>/
      content/
      state/
    development/<run-id>/
      state/
        progress.json
        host_panel.codex.json
        host_panel.antigravity.json
  docs/
    kh/
      specs/
      plans/
      decisions/
      qa/
      handoffs/
  .worktrees/
    <task>/
```

## Quick Start

```bash
pip install -r requirements.txt
python cli.py run --project ./my_app --prompt "Create a small demo app"
```

The CLI defaults to the deterministic `offline` provider, so a smoke run does not require a local or hosted LLM.
Offline output is smoke-only. It proves packaging, dispatch, state, and gates can run, but it is not a task-faithful implementation of the prompt. Use `local`, `openai`, `codex`, or `claude` when the generated project must satisfy the actual user request.

Use a model-backed provider when needed:

```bash
python cli.py run --project ./my_app --prompt "Create a FastAPI backend" --provider local --base-url http://localhost:11434/v1
python cli.py run --project ./my_app --prompt "Create a FastAPI backend" --provider openai --model gpt-5
python cli.py run --project ./my_app --prompt "Create a FastAPI backend" --platform antigravity
```

## Codex Plugin Install

In Codex, open Plugins -> Manage -> Add marketplace:

```text
Source: https://github.com/GNh0/KH.git
Git ref: main
Sparse path: .agents/plugins
```

The marketplace file lives on `main`, but it installs the plugin from the `codex-runtime` branch. `main` keeps tests, audits, and development docs; `codex-runtime` is the slim plugin runtime branch intended for Codex cache installs.

After install or upgrade, start a new thread so Codex reloads the skills.

Upgrade note: Codex installs plugin cache entries by manifest version. When publishing a new plugin build, bump both `.codex-plugin/plugin.json` and the root `plugin.json` version. If the marketplace clone is current but the installed plugin still appears under an older cache path such as `kh-uaf/2.9.27`, install or upgrade again after the version bump.

To separate marketplace descriptor state from installed plugin cache state, run:

```bash
python -m src.orchestration.plugin_install_audit --summary
```

`ref = "main"` in the Codex marketplace config is expected for this repository: it reads `.agents/plugins/marketplace.json`. The plugin source ref inside that marketplace descriptor should point at `codex-runtime`. Treat a run as stale only when the installed cache version or active session skill paths still point at an older KH UAF version.
Use `--strict` when this diagnostic should fail CI or a release script on stale cache state.

Direct Windows clone:

```powershell
git clone https://github.com/GNh0/KH.git "$env:USERPROFILE\plugins\kh-uaf"
cd "$env:USERPROFILE\plugins\kh-uaf"
python -m src.skills.uaf_skill_catalog --check
```

The root `plugin.json` is the UAF runtime manifest. The Codex plugin manifest is `.codex-plugin/plugin.json`.

Repository hygiene: `tests/` and `docs/skillbook/` are development evidence for this repo, not required at plugin runtime. Marketplace installs should use the `codex-runtime` ref so the Codex plugin cache stays focused on `.codex-plugin/`, `skills/`, `src/`, and runtime manifests.

## Antigravity Plugin Install

Global Windows install:

```powershell
git clone https://github.com/GNh0/KH.git "$env:USERPROFILE\.gemini\config\plugins\kh-uaf"
cd "$env:USERPROFILE\.gemini\config\plugins\kh-uaf"
python -m src.skills.uaf_skill_catalog --check
```

Global macOS/Linux install:

```bash
git clone https://github.com/GNh0/KH.git ~/.gemini/config/plugins/kh-uaf
cd ~/.gemini/config/plugins/kh-uaf
python -m src.skills.uaf_skill_catalog --check
```

Workspace-local bootstrap path:

```text
<workspace-root>/.agents/plugins/kh-uaf/
```

Use the global clone when you want every packaged KH UAF skill available across workspaces.

## Core Flow

```text
cli.py run
  -> design document and domain profile
  -> WorkDesign and user deliverable plan
  -> role DAG and bounded worker dispatch
  -> review, QA, security, release, and evidence gates
  -> user-facing docs under docs/
  -> UAF state, memory, snapshots, role artifacts, and handoff under runtime state
```

## KH Loop

KH UAF maps the compound-engineering loop into explicit skills:

- Plan: `brainstorming-harness`, `architect-pipeline`, `domain-orchestration-harness`, and `goal-state-harness`.
- Work: `development-lifecycle-harness`, adapter contracts, role DAG execution, and bounded workflow dispatch.
- Work control: `worktree-isolation-harness`, `plan-execution-harness`, `quality-gates-harness`, and `systematic-debugging-harness`.
- Review: `review-gate-harness`, `qa-gate-harness`, `verification-before-completion-harness`, security checks, and release gates.
- Finish: `branch-finishing-harness`, health checks, release gates, commit/push/PR evidence, and cleanup decisions.
- Compound: `compound-engineering-harness`, `workflow-skill-distiller`, `memory-state-harness`, `context-state-harness`, goal ledger updates, and SIDE/scenario regression captures.

For heavy, multi-step, or evidence-gated work, create or refresh `GoalState` before execution and keep the goal ledger updated through review, QA, and release. For a new product, SaaS, feature, or unclear design request, start with `brainstorming-harness` before architecture or implementation and write visible run artifacts under `.kh/<skill>/<run-id>/content/` plus `.kh/<skill>/<run-id>/state/`, with shareable summaries under `docs/kh/handoffs/` or the relevant `docs/kh/<type>/` folder. After Plan, Work, and Review, run `compound-engineering-harness` when reusable learning, scoped memory candidates, or regression checks may be needed. For a completed workflow that reveals a reusable pattern, finish by distilling the pattern, adding scoped memory, or adding a scenario regression instead of leaving the learning only in chat.

Before plugin-specific rules run, `plugin-composition-policy` can act as the top-level lightweight broker when multiple plugins, tools, skills, connectors, or future capability providers may apply. It chooses `direct`, `single`, `hybrid`, or `clarify` by capability fit, not by whichever provider has the strongest MUST/ALWAYS trigger wording. In hybrid routes one controller owns the workflow while assistant providers handle delegated scopes such as repo/PR/CI, browser QA, knowledge docs, image generation, host automation, or memory/goal/resume.

KH now includes a Superpowers replacement layer for KH-owned projects. `worktree-isolation-harness`, `plan-execution-harness`, `systematic-debugging-harness`, `verification-before-completion-harness`, and `branch-finishing-harness` cover the worktree/TDD/debug/review/finish flows that otherwise made Superpowers useful as a controller. Superpowers can still be used as an assistant provider when explicitly selected, but KH projects should not select it solely because its own skill text says MUST/ALWAYS.

For large or long-running work, KH treats `token-optimizer` as a context budget gate. If `estimated_context_tokens`, broad file reads, long command output, expected tool calls, or subagent transcripts are likely to cross the threshold, the workflow must report `token_optimizer_status`: `used`, `considered_not_needed`, `passthrough`, or `blocked`. Compression is never allowed to lower answer quality or hide source-of-truth details; unsafe content stays `passthrough` or blocks the optimization path. Workflow usability runtime now calls `src.orchestration.runtime_token_optimizer.optimize_workflow_task_results(...)` for `WorkflowTaskResult` command output and agent transcripts, preserving raw metadata while attaching optimized display records, token savings, and RTK-style command-family stats under `metadata.token_optimizer`.

For large project, SaaS, app, multi-file implementation, role-DAG, or long-running work, KH now requires `large_work_orchestration_bundle` evidence before implementation. The bundle records `skill_statuses` for routing, host orchestration, GoalState, lifecycle, workspace isolation, plan execution, debugging, token optimization, memory, parallel strategy, subagent review, role execution audit, verification-before-completion, branch finishing, Compound, and workflow distillation. Each status must be `applied`, `considered_not_needed`, `skipped_with_rationale`, or `blocked`, and each entry carries `application_mode`: `runtime`, `procedural`, `considered`, or `blocked`. This keeps KH light for simple requests while making omissions visible during large work without pretending that procedural use produced runtime adapter evidence.

Skill transition validation makes the bundle active instead of decorative. After review and before final completion, `src.orchestration.skill_transitions.validate_skill_transitions(...)` checks that memory candidates route to `memory-state-harness`, subagent review routes to `role-execution-audit-harness`, parallel execution routes to `parallel-orchestration-harness`, and Compound handoffs close with a no-learning rationale or route to `workflow-skill-distiller`, `memory-state-harness`, `scenario-evaluation-harness`, or `context-state-harness`. This is the KH-native guard against having useful skills listed but never actually entering the run.

Subagents are also decision-gated. KH should record `subagent_strategy`: `dispatch`, `single-controller`, `review-only`, or `blocked` before opening subagents. Subagents are justified by independent work, bounded packets, real review value, and isolation; otherwise the controller should keep the work sequential. Token optimization for subagent packets and transcripts is a required decision, not automatic compression: short or exact reviewer output may be `considered_not_needed` or `passthrough`.

Python callers can use `src.orchestration.skill_application.build_large_work_orchestration_bundle(...)` and `validate_large_work_orchestration_bundle(...)` to create that lightweight evidence without hand-assembling the JSON. For transition checks, use `src.orchestration.skill_transitions.validate_skill_transitions(...)`. For task-plan execution, use `src.orchestration.development_progress.write_development_progress(...)` and `validate_development_progress(...)` to keep `.kh/development/<run-id>/state/progress.json` aligned with the final report fields.

The workflow usability layer makes those lifecycle records visible and resumable:

- `workflow-usability-harness` connects progress state, token provider policy, role command entrypoints, progress panels, and session-start context restore.
- `src.orchestration.workflow_usability_runtime.apply_workflow_usability_runtime(...)` is wired into AgentLoop/app bridge workflow dispatch, so real KH runs can emit session context, token provider policy, progress panel, progress state, and Compound handoff metadata automatically instead of relying on manual helper calls.
- `src.orchestration.runtime_token_optimizer.optimize_workflow_task_results(...)` attaches runtime token optimization records to task command outputs and subagent transcripts, reports workflow-level savings, and emits RTK-style command-family statistics while preserving failing command context and lifecycle evidence.
- `src.orchestration.runtime_memory.record_workflow_memory_candidates(...)` records scoped memory candidates from Compound/workflow usability into `MemoryStore` candidate logs without promoting them to durable memory unless the user approves the scope.
- `src.orchestration.runtime_memory.build_active_memory_preflight(...)` provides OpenClaw-style active memory recall before implementation, using KH scoped memory instead of global always-on memory.
- `src.orchestration.runtime_memory.build_explicit_cross_scope_memory_import(...)` handles user-named source project/chat memory as read-only `external_context`; applying it to the current scope requires explicit approval, preserves source scope/record metadata, and defaults to scoped candidates instead of durable memory.
- `src.orchestration.runtime_memory.write_pre_compaction_memory_flush(...)` stores compact decisions, blockers, next actions, and verification state before host context compression can erase them.
- `src.orchestration.memory_store.MemoryStore.write_prompt_memory_snapshot(...)` writes bounded Hermes-style `MEMORY.md` and `USER.md` prompt snapshots inside the scoped KH runtime memory directory.
- `src.orchestration.progress_compound_bridge.write_progress_compound_artifacts(...)` turns completed `progress.json` into `CompoundCapture`, `compound_handoff`, memory candidates, skill candidates, scenario candidates, and `docs/kh/handoffs/<run-id>-compound.md`.
- `src.orchestration.token_optimizer_provider.resolve_token_optimizer_provider(...)` records `token_optimizer_provider`: `kh`, `rtk`, `hybrid`, or `passthrough`. RTK is optional; hybrid falls back to KH and exact source-of-truth text stays passthrough.
- `src.orchestration.role_commands.resolve_role_command(...)` provides short `/kh:*` role command front doors such as `/kh:work`, `/kh:qa`, `/kh:ship`, `/kh:learn`, and `/kh:resume`.
- `src.orchestration.progress_panel.render_progress_panel(...)` gives long task-plan work a visible status panel with task status, review status, token optimizer status, commit SHA, and next task.
- `src.orchestration.progress_panel.build_host_progress_panel(...)` and `write_host_progress_panel(...)` produce `host_panel.<host>.json`, a stable JSON contract for Codex task panels, Antigravity-style Agent Manager/subagent panels, generic CLI shells, and future host UIs.
- `src.orchestration.session_start_context.build_session_start_context(...)` inspects `.kh`, `docs/kh`, scoped memory candidates, objective-ranked `memory_recall`, and only explicitly requested cross-scope memory imports at the start of the next session.
- `src.orchestration.session_postmortem.analyze_codex_session_jsonl(...)` reviews Codex rollout logs after a completed or interrupted session. It flags large-token runs that skipped the token gate, timed-out or still-running reviewers, secret-like command text, missing commit/push evidence, active goals incorrectly closed as final completion, user stop requests that were overridden by `goal_context`, failed verification paths that were not reported, and scope gaps between the original objective and the final milestone.
- `src.orchestration.session_skill_audit.analyze_session_skills(...)` audits a Codex rollout log against all packaged KH skills, separating required, applied, inspected, mentioned, and missing skill evidence.
- `src.orchestration.windows_dev_server.build_streamlit_launch_plan(...)` produces a Windows-safe Streamlit launch plan with normalized `Path`/`PATH`, redirected logs, visible/hidden window strategy, and a separate HTTP health check.

Completion is also guarded against partial milestones. A scaffold, first vertical slice, or pushed branch is not final completion while the goal remains active. KH postmortem records `scope_completion_delta` so the next task continues missing objective markers instead of turning a useful intermediate result into a false finish. If a promised verification route fails or is unavailable, such as Browser/Playwright QA, the final report must say that explicitly and distinguish it from narrower HTTP/status checks.

User interruption is a hard stop. If the user says stop, pause, cancel, `멈춰`, `스탑`, `중단`, or `goal 멈춰`, KH treats that as higher priority than any later automatic `goal_context` continuation. If the host goal tool allows blocking for this case, the active goal should be marked `blocked` with `blocked_reason=user_requested_stop`. If host policy disallows using `blocked` as a pause/cancel state, KH must not keep working just because the host goal stays active; it writes interruption checkpoint evidence and treats later automated `goal_context` as suspended until a fresh non-`goal_context` user resume request arrives. Postmortem `user_stop_guard` blocks sessions where tools or patches continue afterward.

Stop requests are also resume-safe. KH writes `.kh/development/<run-id>/state/interruption.json`, `.kh/development/<run-id>/content/interruption.md`, and a scoped durable `resume-checkpoint` memory record. On the next request, `session_start_context` reads the interruption checkpoint, bounded memory context, and objective-ranked memory recall before relying on compressed chat context, so work resumes from saved state instead of from memory alone. Memory writes reject duplicate entries, secret-like content, prompt-injection text, invisible control characters, and oversized raw dumps. Similar keywords from other projects or chats are not searched automatically; cross-scope memory requires an explicit source project/chat request and stays read-only unless the caller records approval to apply it.

Skill usage is separated from skill inspection. For example, reading `token_optimizer/SKILL.md` or quoting `token_optimizer_status` does not count as token optimizer usage; the postmortem requires runtime evidence such as `src.skills.token_optimizer`, command-output summarization, token-savings metadata, or explicit passthrough evidence.

External benchmarking remains explicit: role-stack office-hours/spec/CEO/eng review/QA/ship handoffs inform KH's front-door, review, QA, and release connections, while KH's Compound step adds reusable learning, memory candidates, and regression capture as a first-class post-review requirement.

The ongoing Superpowers benchmark notes live in `docs/skillbook/audits/2026-05-30-superpowers-benchmark.md`.

## Deliverables

UAF exports user-facing artifacts by task type, not by a fixed extension list.

- Software work: requirements, functional specification, development design, screen/API definition, data definition, test plan, and risk/policy workbooks.
- General orchestration: requirements, orchestration design, process flow, role/task breakdown, evidence plan, and risk/policy files.
- Product or mechanical work: product design document, dimension/BOM workbook, SVG concept drawing, and DXF handoff when the input supports it.
- Investment or analysis work: analysis report, scenario workbook, and risk/policy workbook.
- Manuals are conditional and are generated only when the task needs user or operations instructions.

Harness-only outputs such as traceability rows, render QA checks, role audit findings, and template quality checks stay in runtime metadata unless explicitly requested as user deliverables.

## Skills

Each packaged skill has this structure:

```text
skills/<skill-folder>/SKILL.md
skills/<skill-folder>/references/usage.md
skills/<skill-folder>/examples/minimal-workflow.md
skills/<skill-folder>/scripts/smoke_check.py
skills/<skill-folder>/scripts/demo.py
```

Useful commands:

```bash
python -m src.skills.uaf_skill_catalog --list
python -m src.skills.uaf_skill_catalog --read orchestration-role-graph
python -m src.skills.uaf_skill_catalog --check
python -m src.skills.uaf_skill_quality
python skills/token_optimizer/scripts/demo.py --output-dir ./tmp/token-demo
```

## KH-Bench Verified

Internal quality scores prove that packaged skills are well structured. `KH-Bench Verified` proves that UAF can execute practical tasks.

```bash
python -m src.benchmarks.kh_bench_verified --summary
python -m src.benchmarks.practical_quality_gate --summary
python -m unittest tests.test_kh_bench_verified
```

Each task runs in a clean workspace with a task-scoped `UAF_RUNTIME_ROOT`. The benchmark also forces `UAF_PROJECT_LOCAL_STATE=0` during task execution so ambient host settings cannot move runtime state into the project.

- `pre_validation`: checks expected to fail before execution
- `fail_to_pass`: checks that must pass after execution
- `pass_to_pass`: regression checks that must remain passing
- JSON score output with resolved rate, evidence, runtime contracts, artifacts, and unresolved task IDs

Current task categories cover coding workflow dispatch, product/domain deliverables, role DAG orchestration, snapshot rollback, goal/memory/handoff state, token-safe command-output compression, and SIDE regression cases for Markdown extraction and compact product-spec drawing exports.

The CLI uses the built-in `KHBaselineCandidateRunner` to score KH UAF itself. Python callers can pass a different candidate runner to `run_kh_bench_verified(...)`. External candidate runners receive only a sealed public task view; validators, expected artifacts, and baseline profile metadata stay inside the grader. Validators read concrete files, runtime artifacts, and report JSON rather than trusting runner-owned custom flags.

For publishing, prefer `python -m src.benchmarks.practical_quality_gate --summary` over reading `lowest_quality_score` alone. The static 10-point skill score is an advisory structure gate; release readiness is blocked by failed KH-Bench or SIDE regression tasks.

Run the full practical quality gate from the development checkout on `main`, where tests and audit fixtures are present. The `codex-runtime` branch is the slim install target for Codex marketplace cache and may not include development test files; use it to verify catalog, smoke/demo scripts, front-door routing, stale-cache detection, and runtime importability.

## Verification

Before publishing:

```bash
python -m json.tool plugin.json
python -m json.tool .codex-plugin/plugin.json
python -m src.skills.uaf_skill_catalog --check
python -m src.skills.uaf_skill_quality
python -m src.benchmarks.kh_bench_verified --summary
python -m src.benchmarks.practical_quality_gate --summary
python -m unittest discover -s tests
```

## Project Layout

```text
.codex-plugin/
.agents/plugins/
cli.py
plugin.json
SKILL.md
src/
  benchmarks/
  contracts.py
  core/
  harness/
  orchestration/
  platforms/
  skills/
  tasks/
skills/
docs/
tests/
```

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `AG_PLATFORM_MODE` | `local` | Dispatcher mode |
| `AG_LLM_PROVIDER` | `offline` | Default CLI provider |
| `AG_LLM_BASE_URL` | `http://localhost:11434/v1` | Local OpenAI-compatible endpoint |
| `AG_MAX_WORKERS` | `50` | Requested async worker limit |
| `UAF_RUNTIME_ROOT` | `%LOCALAPPDATA%/KH-UAF` | Runtime state root |
| `UAF_PROJECT_LOCAL_STATE` | unset | Set to `1` only when project-local `.uaf` state is desired |
