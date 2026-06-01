---
name: kh-uaf
description: Use when Antigravity should apply KH UAF's personal skillbook, packaged skills, goal ledger, memory state, or local orchestration harness in this workspace.
---

# KH UAF

This workspace includes KH UAF, a personal skillbook and Python-first orchestration harness for domain-general agent workflows.

## How to Use

1. Treat the repository root as the packaged UAF source, not as the target project's runtime state folder.
2. When a user says to use KH, KH UAF, the KH plugin, KH skills/harnesses, or `/kh:*`, run KH front-door auto routing before source exploration or edits.
3. Read `SKILL.md`, `plugin-composition-policy`, `request-complexity-router`, or the packaged skill catalog to classify the request and select the minimal skill bundle automatically. Users should not need to name every harness.
4. Record selected, considered, skipped, and blocked skills with evidence; then start source reads, edits, role DAG execution, or deliverable generation.
5. Use `README.md` for install and host integration instructions.
6. Validate the skill pack before relying on it:

```bash
python -m src.skills.uaf_skill_catalog --check
```

For large project, SaaS, app, multi-file implementation, role-DAG, or long-running work, create `large_work_orchestration_bundle` evidence before implementation. Its `skill_statuses` must account for routing, host orchestration, GoalState, lifecycle, token optimization, memory, parallel strategy, subagent review, role execution audit, Compound, and workflow distillation as `applied`, `considered_not_needed`, `skipped_with_rationale`, or `blocked`, with `application_mode` set to `runtime`, `procedural`, `considered`, or `blocked`.

If a session explicitly requests KH but starts source/work commands before this front-door evidence exists, treat it as a P1 `missing_front_door` failure in `session-skill-audit`.

## Useful Entry Points

- `skills/`: packaged UAF skill and harness folders.
- `src/`: Python contracts, dispatchers, DAG role orchestrator, role artifacts, evidence gates, retention helpers, goal ledger, memory store, and task runners.
- `%LOCALAPPDATA%/KH-UAF/`: default runtime state for `.uaf` and snapshot data.
- `docs/`: target-project user-facing deliverables routed by task type, such as standard-template software functional specification, development design, API/data/test artifacts, documentation-grade general orchestration DOCX/XLSX files, conditional revision-managed manuals, investment analysis workbooks, and product-design SVG/DXF handoff artifacts.
- `deliverable_exports.quality` and `role_execution_audit`: metadata-only harness outputs for template quality, render QA, traceability rows, and role DAG execution audit. Do not write these harness-only reports into `docs/` unless the user explicitly asks for them as deliverables.
- `docs/skillbook/`: design notes, plans, and handoff decisions.

## UAF Commands

```bash
python -m src.skills.uaf_skill_catalog --list
python -m src.skills.uaf_skill_catalog --read goal-state-harness
python cli.py run --project ./my_app --prompt "Plan and implement the requested work"
```
