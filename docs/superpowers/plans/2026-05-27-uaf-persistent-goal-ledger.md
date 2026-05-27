# UAF Persistent Goal Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist UAF goal status and event history under each project so workflow intent survives context compaction and process restarts.

**Architecture:** Add a focused `GoalLedger` storage helper under `src/orchestration/`, then wire local workflow dispatch to write initial and evaluated goal states. Keep the state format JSON/JSONL and keep `.uaf/` ignored by git.

**Tech Stack:** Python 3.9+, stdlib `json`, `pathlib`, `datetime`, `unittest`, existing UAF `GoalState` metadata.

---

### Task 1: Ledger Storage

**Files:**
- Create: `src/orchestration/goal_ledger.py`
- Create: `tests/test_goal_ledger.py`

- [ ] **Step 1: Write failing tests**

Create tests for save/load current state, appending ordered JSONL events, and rejecting traversal outside the project root.

- [ ] **Step 2: Run focused tests to confirm RED**

Run: `python -m unittest tests.test_goal_ledger -v`

Expected: import failure because `src.orchestration.goal_ledger` does not exist.

- [ ] **Step 3: Implement minimal `GoalLedger`**

Implement `save_current_goal()`, `load_current_goal()`, `append_event()`, `read_events()`, `resolve_project_path()`, and `describe_paths()`.

- [ ] **Step 4: Run focused tests to confirm GREEN**

Run: `python -m unittest tests.test_goal_ledger -v`

Expected: all ledger tests pass.

### Task 2: Workflow Wiring

**Files:**
- Modify: `src/tasks/workflows.py`
- Modify: `tests/test_workflows.py`
- Modify: `tests/test_dispatcher.py`

- [ ] **Step 1: Write failing workflow tests**

Add tests that workflow dispatch writes `.uaf/state/current_goal.json`, appends events, and exposes ledger paths in workflow and local dispatcher metadata.

- [ ] **Step 2: Run focused tests to confirm RED**

Run: `python -m unittest tests.test_workflows tests.test_dispatcher -v`

Expected: failures because workflow dispatch does not write a ledger.

- [ ] **Step 3: Wire `GoalLedger` into workflow dispatch**

Write initial state before workers, write evaluated state after evidence evaluation, append terminal status event, and return `goal_ledger` metadata.

- [ ] **Step 4: Run focused tests to confirm GREEN**

Run: `python -m unittest tests.test_workflows tests.test_dispatcher -v`

Expected: all focused tests pass.

### Task 3: Documentation

**Files:**
- Modify: `.gitignore`
- Modify: `README.md`
- Modify: `SKILL.md`
- Modify: `skills/goal_state_harness/SKILL.md`
- Modify: `docs/CODEX_ACTIVE_WORK.md`

- [ ] **Step 1: Update docs**

Document `.uaf/state/current_goal.json`, `.uaf/state/goal_events.jsonl`, and resume-safe goal ledger behavior.

- [ ] **Step 2: Run full verification**

Run:

```bash
python -m json.tool plugin.json
python -m src.skills.uaf_skill_catalog --check
python -m unittest discover -s tests -v
python -B -c "import pathlib; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in pathlib.Path('.').rglob('*.py')]"
```

Expected: all commands succeed.
