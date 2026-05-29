# Universal Agent Framework (UAF)

[English](README.md) | [Korean](README.ko.md)

KH UAF is a local-first skill and harness framework for Codex, Antigravity-style agents, Claude Code, and local workers.

It combines:

- host-readable skills in `skills/<skill-folder>/SKILL.md`
- Python contracts, dispatchers, role orchestration, gates, state, and validators under `src/`
- practical release checks, SIDE regression tasks, and a SWE-bench-style local benchmark

The goal is not to depend on a vendor-specific local skill folder. UAF packages its own portable skills and harnesses.

## What It Includes

- 31 packaged skills/harnesses with support files, smoke checks, and runnable demos.
- Codex plugin manifests: `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json`.
- Antigravity workspace/global plugin bootstrap files.
- `brainstorming-harness` for early product/project discovery and KH handoff before architecture or implementation.
- `compound-engineering-harness` for mandatory post-review learning capture, scoped memory candidates, system updates, and regression checks.
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

After install or upgrade, start a new thread so Codex reloads the skills.

Upgrade note: Codex installs plugin cache entries by manifest version. When publishing a new plugin build, bump both `.codex-plugin/plugin.json` and the root `plugin.json` version. If the marketplace clone is current but the installed plugin still appears under an older cache path such as `kh-uaf/2.8.0`, install or upgrade again after the version bump.

Direct Windows clone:

```powershell
git clone https://github.com/GNh0/KH.git "$env:USERPROFILE\plugins\kh-uaf"
cd "$env:USERPROFILE\plugins\kh-uaf"
python -m src.skills.uaf_skill_catalog --check
```

The root `plugin.json` is the UAF runtime manifest. The Codex plugin manifest is `.codex-plugin/plugin.json`.

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
- Review: `review-gate-harness`, `qa-gate-harness`, `quality-gates-harness`, security checks, and release gates.
- Compound: `compound-engineering-harness`, `workflow-skill-distiller`, `memory-state-harness`, `context-state-harness`, goal ledger updates, and SIDE/scenario regression captures.

For heavy, multi-step, or evidence-gated work, create or refresh `GoalState` before execution and keep the goal ledger updated through review, QA, and release. For a new product, SaaS, feature, or unclear design request, start with `brainstorming-harness` before architecture or implementation and write visible run artifacts under `.kh/<skill>/<run-id>/content/` plus `.kh/<skill>/<run-id>/state/`, with shareable summaries under `docs/kh/handoffs/` or the relevant `docs/kh/<type>/` folder. After Plan, Work, and Review, run `compound-engineering-harness` when reusable learning, scoped memory candidates, or regression checks may be needed. For a completed workflow that reveals a reusable pattern, finish by distilling the pattern, adding scoped memory, or adding a scenario regression instead of leaving the learning only in chat.

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
