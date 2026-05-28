---
name: kh-uaf
description: Use when Antigravity should apply KH UAF's personal skillbook, packaged skills, goal ledger, memory state, or local orchestration harness in this workspace.
---

# KH UAF

This workspace includes KH UAF, a personal skillbook and Python-first orchestration harness for domain-general agent workflows.

## How to Use

1. Treat the repository root as the packaged UAF source, not as the target project's runtime state folder.
2. Read the packaged skills under `skills/` when a task needs a specific workflow.
3. Use `README.md` for install and host integration instructions.
4. Use `SKILL.md` for the root UAF operating guide.
5. Validate the skill pack before relying on it:

```bash
python -m src.skills.uaf_skill_catalog --check
```

## Useful Entry Points

- `skills/`: packaged UAF skill and harness folders.
- `src/`: Python contracts, dispatchers, DAG role orchestrator, role artifacts, evidence gates, retention helpers, goal ledger, memory store, and task runners.
- `%LOCALAPPDATA%/KH-UAF/`: default runtime state for `.uaf` and snapshot data.
- `docs/`: target-project user-facing deliverables routed by task type, such as standard-template software 기능정의서/개발설계서/API/data/test artifacts, documentation-grade general orchestration DOCX/XLSX files, conditional revision-managed 사용 매뉴얼, investment analysis workbooks, and product-design SVG/DXF handoff artifacts.
- `docs/skillbook/`: design notes, plans, and handoff decisions.

## UAF Commands

```bash
python -m src.skills.uaf_skill_catalog --list
python -m src.skills.uaf_skill_catalog --read goal-state-harness
python cli.py run --project ./my_app --prompt "Plan and implement the requested work"
```
