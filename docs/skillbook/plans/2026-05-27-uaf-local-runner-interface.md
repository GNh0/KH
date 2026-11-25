# UAF Local Runner Interface Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use KH skillbook task-by-task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make local workflow workers consume a real runner interface and treat runner `WorkflowTaskResult` values as the source of truth.

**Architecture:** Add `src/tasks/runners.py` with task input and local runner classes. Update `src/tasks/workflows.py` so workers call the runner, then report the result to webhook as a side effect. Merge runner evidence into goal evidence evaluation.

**Tech Stack:** Python 3.9+, dataclasses, asyncio, httpx, unittest, existing UAF contracts.

---

### Task 1: Runner Contract

**Files:**
- Create: `src/tasks/runners.py`
- Create: `tests/test_task_runners.py`

- [ ] **Step 1: Write failing tests**

Add tests for a successful safe task and a failed traversal task.

- [ ] **Step 2: Run focused tests to confirm RED**

Run: `python -m unittest tests.test_task_runners -v`

Expected: import failure because `src.tasks.runners` does not exist.

- [ ] **Step 3: Implement `WorkflowTaskInput` and `LocalTaskRunner`**

Implement safe path resolution, `WorkflowTaskResult` creation, runner metadata, and runner evidence.

- [ ] **Step 4: Run focused tests to confirm GREEN**

Run: `python -m unittest tests.test_task_runners -v`

Expected: runner tests pass.

### Task 2: Workflow Worker Wiring

**Files:**
- Modify: `src/tasks/workflows.py`
- Modify: `tests/test_workflows.py`
- Modify: `tests/test_dispatcher.py`

- [ ] **Step 1: Write failing workflow tests**

Update webhook failure expectations so a runner success stays successful while webhook failure is stored in metadata. Add a runner path failure test.

- [ ] **Step 2: Run focused tests to confirm RED**

Run: `python -m unittest tests.test_workflows tests.test_dispatcher -v`

Expected: failures because current worker still treats webhook failure as task failure and does not expose runner metadata.

- [ ] **Step 3: Wire runner into worker**

Create one `WorkflowTaskInput` per queued file, call `LocalTaskRunner.run()`, append the runner result, then POST webhook and merge report metadata.

- [ ] **Step 4: Run focused tests to confirm GREEN**

Run: `python -m unittest tests.test_task_runners tests.test_workflows tests.test_dispatcher -v`

Expected: all focused tests pass.

### Task 3: Documentation and Verification

**Files:**
- Modify: `README.md`
- Modify: `SKILL.md`
- Modify: `docs/CODEX_ACTIVE_WORK.md`

- [ ] **Step 1: Update docs**

Document that local worker source of truth is now runner output and webhook is reporting only.

- [ ] **Step 2: Run full verification**

Run:

```bash
python -m json.tool plugin.json
python -m src.skills.uaf_skill_catalog --check
python -m unittest discover -s tests -v
python -B -c "import pathlib; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in pathlib.Path('.').rglob('*.py')]"
```

Expected: all commands succeed.
