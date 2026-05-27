---
name: kh-uaf
description: Use when Antigravity should apply KH UAF's personal skillbook, packaged skills, goal ledger, memory state, or local orchestration harness in this workspace.
---

# KH UAF

This workspace includes KH UAF, a personal skillbook and Python-first orchestration harness for domain-general agent workflows.

## How to Use

1. Treat the repository root as the UAF runtime root.
2. Read the packaged skills under `skills/` when a task needs a specific workflow.
3. Use `README.md` for install and host integration instructions.
4. Use `SKILL.md` for the root UAF operating guide.
5. Validate the skill pack before relying on it:

```bash
python -m src.skills.uaf_skill_catalog --check
```

## Useful Entry Points

- `skills/`: packaged UAF skill and harness folders.
- `src/`: Python contracts, dispatchers, goal ledger, memory store, and task runners.
- `.uaf/`: project-local runtime state created during workflow runs.
- `docs/skillbook/`: design notes, plans, and handoff decisions.

## UAF Commands

```bash
python -m src.skills.uaf_skill_catalog --list
python -m src.skills.uaf_skill_catalog --read goal-state-harness
python cli.py run --project ./my_app --prompt "Plan and implement the requested work"
```
