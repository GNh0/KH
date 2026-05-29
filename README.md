# Universal Agent Framework (UAF)

UAF is a Python-first, local-first orchestration framework for Codex, Antigravity, Claude Code, and other agent hosts.

It packages two things:

- runtime contracts, dispatchers, gates, state, and harnesses under `src/`
- host-readable skills under `skills/<skill-folder>/SKILL.md`

The intent is to make planning, domain profiling, role orchestration, worker dispatch, review/QA gates, snapshots, memory, goal state, and user-facing deliverables portable across agent hosts without depending on one vendor-specific local skill folder.

## What It Includes

- Packaged KH UAF skill catalog with 27 skills/harnesses.
- CLI runner for local project workflows.
- Codex plugin manifest at `.codex-plugin/plugin.json`.
- Codex marketplace file at `.agents/plugins/marketplace.json`.
- Antigravity workspace bootstrap at `.agents/plugins/kh-uaf`.
- Local/Antigravity dispatcher contracts.
- DAG-based role orchestration with CEO, advisor, architect, planner, controller, implementer, reviewer, QA, security, and release roles.
- Goal ledger, scoped memory store, resume handoff, and runtime state under the UAF runtime store by default.
- Type-aware user deliverables under the target project's `docs/` folder.
- Metadata-only quality, render QA, traceability, and role execution audit harnesses.
- Deterministic `offline` provider for install-time smoke runs without a local LLM.
- OpenAI-compatible, Anthropic, and custom LLM provider hooks.

Internal state is not written into the target project root by default. User-facing files go under the target project's `docs/`; UAF runtime state normally lives under `%LOCALAPPDATA%/KH-UAF/projects/<project-key>/.uaf/`.

## Quick Start

```bash
pip install -r requirements.txt
python cli.py run --project ./my_app --prompt "Create a small demo app"
```

The CLI defaults to `--provider offline`, so a first smoke run does not require Ollama, OpenAI, Anthropic, or a local API server.

Use a configured model when you want real generation:

```bash
python cli.py run --project ./my_app --prompt "Create a FastAPI backend" --provider local --base-url http://localhost:11434/v1
python cli.py run --project ./my_app --prompt "Create a FastAPI backend" --provider openai --model gpt-5
python cli.py run --project ./my_app --prompt "Create a FastAPI backend" --platform antigravity
```

Useful commands:

```bash
python -m src.skills.uaf_skill_catalog --list
python -m src.skills.uaf_skill_catalog --read orchestration-role-graph
python -m src.skills.uaf_skill_catalog --check
python -m src.skills.uaf_skill_quality
python -m unittest discover -s tests
```

## Codex Plugin Install

This repo can be installed as a Codex plugin because it includes `.codex-plugin/plugin.json`.

In Codex, open Plugins -> Manage -> Add marketplace and use:

```text
Source: https://github.com/GNh0/KH.git
Git ref: main
Sparse path: .agents/plugins
```

The sparse path points at `.agents/plugins/marketplace.json`, which exposes the `KH UAF` plugin entry. After installing or upgrading the plugin, start a new thread so the skills reload.

The same marketplace can be added from a CLI-capable environment:

```bash
codex plugin marketplace add https://github.com/GNh0/KH.git --ref main --sparse .agents/plugins
```

Recommended direct clone path on Windows:

```powershell
git clone https://github.com/GNh0/KH.git "$env:USERPROFILE\plugins\kh-uaf"
cd "$env:USERPROFILE\plugins\kh-uaf"
python -m src.skills.uaf_skill_catalog --check
```

The root `plugin.json` is the UAF runtime manifest. The Codex plugin manifest is `.codex-plugin/plugin.json`.

## Antigravity Plugin Install

Antigravity can use KH UAF as a global plugin or through a workspace bootstrap.

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

For workspace-local bootstrapping, use:

```text
<workspace-root>/.agents/plugins/kh-uaf/
```

The workspace bootstrap is intentionally small. It exposes a `kh-uaf` skill that points the host back to this repo's root `skills/`, `SKILL.md`, and validation commands. For full access to every packaged KH UAF skill across workspaces, use the global clone path.

## Core Flow

```text
cli.py run
  -> SystemArchitect writes design_doc.md
  -> AgentLoop attaches role graph and GoalState metadata
  -> DomainProfile and WorkDesign are created
  -> user-facing deliverables are routed to docs/
  -> DispatcherFactory selects local or Antigravity mode
  -> role DAG and bounded workers execute tasks
  -> review, QA, security, release, and evidence gates run
  -> GoalLedger, memory, artifacts, and resume handoff are written to runtime state
```

The local path can run with the deterministic `offline` provider for smoke testing. Real model-backed work should use `local`, `openai`, `codex`, `claude`, or a custom provider registered through `LLMRouter.register_provider(...)`.

## Deliverables

UAF exports user-facing work products by task type, not by a fixed extension checklist.

- Software work: `요구정의서.docx`, `기능정의서.docx`, `개발설계서.docx`, `화면_API_정의서.docx`, data/test/risk XLSX files.
- General orchestration: requirements, orchestration design, process flow, role/task breakdown, evidence plan, and risk/policy files.
- Product/mechanical work: design notes, dimension/BOM workbook, SVG concept drawing, DXF handoff when the input supports it.
- Investment/analysis work: report, scenario workbook, and risk/policy workbook.
- Manuals are conditional. `사용_매뉴얼.docx` is generated only when the task needs user/operations instructions or manual revision metadata is supplied.

Harness-only outputs such as traceability rows, render QA checks, role audit findings, and template quality checks stay in runtime metadata unless the user explicitly asks for them as deliverables.

## Packaged Skills

The catalog scans `skills/` and exposes each `SKILL.md` through `src.skills.uaf_skill_catalog`.

Main groups:

| Group | Skills |
| --- | --- |
| Orchestration/adapters | `orchestration-role-graph`, `adapter-contract-harness`, `host-agent-orchestration`, `parallel-orchestration-harness`, `subagent-review-pipeline` |
| Planning/lifecycle | `architect-pipeline`, `development-lifecycle-harness`, `domain-orchestration-harness`, `quality-gates-harness`, `workflow-skill-distiller` |
| Quality/artifacts | `deliverable-template-quality-harness`, `artifact-render-qa-harness`, `traceability-matrix-harness`, `role-execution-audit-harness`, `health-check-harness` |
| Gates/state | `goal-state-harness`, `memory-state-harness`, `context-state-harness`, `review-gate-harness`, `qa-gate-harness` |
| Safety/operations | `guard-policy-harness`, `command-hook-policy-harness`, `command-output-harness`, `snapshot-state-harness`, `token-optimizer`, `harness-evaluator`, `skill-catalog` |

To add a new packaged skill, create:

```text
skills/<skill-folder>/SKILL.md
skills/<skill-folder>/references/usage.md
skills/<skill-folder>/examples/minimal-workflow.md
skills/<skill-folder>/scripts/smoke_check.py
```

Then run the catalog and quality checks.

## Maintainer Quality Gate

Before publishing KH UAF, validate this repo's packaged `skills/` directory:

```bash
python -m src.skills.uaf_skill_catalog --check
python -m src.skills.uaf_skill_quality
```

The quality check is a KH UAF release gate, not a general external-skill ranking tool. It checks support-file wiring, smoke execution, implementation-target resolution, and test evidence for the skills packaged in this repository. The detailed rubric and latest scorecard live under `docs/skillbook/audits/`.

## Project Layout

```text
.codex-plugin/
  plugin.json
.agents/
  plugins/
    marketplace.json
    kh-uaf/
cli.py
plugin.json
SKILL.md
requirements.txt
src/
  contracts.py
  core/
  orchestration/
  platforms/
  tasks/
  harness/
  skills/
skills/
  <skill-folder>/SKILL.md
docs/
  skillbook/
tests/
```

## Environment

Set these only when you need to override defaults.

| Variable | Default | Purpose |
| --- | --- | --- |
| `AG_PLATFORM_MODE` | `local` | Dispatcher mode for CLI and runner paths. |
| `AG_LLM_PROVIDER` | `offline` | Default CLI provider; use `local`, `openai`, `codex`, or `claude` when configured. |
| `AG_LLM_BASE_URL` | `http://localhost:11434/v1` | OpenAI-compatible local endpoint for `--provider local`. |
| `AG_WEBHOOK_URL` | unset | Optional subagent result webhook for external host callbacks. |
| `AG_API_KEY` | `antigravity-secret-key-v2` | API key used only when webhook reporting is enabled. |
| `AG_MAX_WORKERS` | `50` | Max async workers, clamped by CPU. |
| `AG_NO_SANDBOX` | `0` | Disable sandbox when set to `1`. |
| `AG_VERBOSE` | `0` | Verbose server logs. |
| `UAF_RUNTIME_ROOT` | `%LOCALAPPDATA%/KH-UAF` | Runtime state root. |
| `UAF_PROJECT_LOCAL_STATE` | unset | Set to `1` only when `.uaf/` should be written inside the target project. |

## Verification

Use these before claiming a branch is ready:

```bash
python -m json.tool plugin.json
python -m json.tool .codex-plugin/plugin.json
python -m src.skills.uaf_skill_catalog --check
python -m src.skills.uaf_skill_quality
python -m unittest discover -s tests
python -B -c "import pathlib; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in pathlib.Path('.').rglob('*.py')]"
```
