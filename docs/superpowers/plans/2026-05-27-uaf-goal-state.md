# UAF Goal State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `GoalState` contract and propagate it through UAF adapter and workflow metadata.

**Architecture:** Keep goal state in Python core contracts and serialize it through existing `metadata` dictionaries. Add a packaged `goal-state-harness` skill so future review, QA, and release gates can use a stable workflow goal vocabulary.

**Tech Stack:** Python 3.9+, dataclasses, unittest, existing UAF catalog and workflow modules.

---

### Task 1: Goal Contract

**Files:**
- Modify: `src/contracts.py`
- Modify: `tests/test_contracts.py`

- [ ] **Step 1: Write the failing contract round-trip test**

Add a test that constructs `GoalState(objective="build api", success_criteria=["design approved"], evidence_required=["tests"])`, round-trips through `to_dict()` and `from_dict()`, and asserts equality.

- [ ] **Step 2: Run contract tests to confirm RED**

Run: `python -m unittest tests.test_contracts -v`

Expected: import failure because `GoalState` does not exist.

- [ ] **Step 3: Implement `GoalState`**

Add the frozen dataclass with fields from the spec and `to_dict()` / `from_dict()` methods.

- [ ] **Step 4: Run contract tests to confirm GREEN**

Run: `python -m unittest tests.test_contracts -v`

Expected: all contract tests pass.

### Task 2: Goal Metadata Propagation

**Files:**
- Modify: `src/orchestration/agent_loop.py`
- Modify: `src/tasks/workflows.py`
- Modify: `src/platforms/dispatcher_factory.py`
- Modify: `tests/test_agent_loop.py`
- Modify: `tests/test_workflows.py`
- Modify: `tests/test_dispatcher.py`

- [ ] **Step 1: Write failing tests for goal metadata**

Add tests that `AgentLoop.build_goal_metadata("build api")` returns `metadata["goal"]["status"] == "active"`, workflow dispatch preserves `metadata["goal"]`, and Antigravity pending adapter results include `metadata["goal"]`.

- [ ] **Step 2: Run focused tests to confirm RED**

Run: `python -m unittest tests.test_agent_loop tests.test_workflows tests.test_dispatcher -v`

Expected: failures because goal metadata is not wired.

- [ ] **Step 3: Implement goal metadata wiring**

Add `AgentLoop.build_goal_metadata()`, merge goal metadata into dispatch requests, preserve `goal` in workflow result metadata, and include `goal` in adapter result metadata.

- [ ] **Step 4: Run focused tests to confirm GREEN**

Run: `python -m unittest tests.test_agent_loop tests.test_workflows tests.test_dispatcher -v`

Expected: all focused tests pass.

### Task 3: Packaged Goal Harness

**Files:**
- Create: `skills/goal_state_harness/SKILL.md`
- Modify: `tests/test_uaf_skill_catalog.py`
- Modify: `plugin.json`
- Modify: `README.md`
- Modify: `SKILL.md`

- [ ] **Step 1: Write failing catalog expectation**

Add `goal-state-harness` to the expected packaged skill set and gstack-derived/UAF-native source checks.

- [ ] **Step 2: Run catalog tests to confirm RED**

Run: `python -m unittest tests.test_uaf_skill_catalog -v`

Expected: missing skill failure.

- [ ] **Step 3: Add skill and docs**

Add the `goal-state-harness` skill and update plugin/README/SKILL references.

- [ ] **Step 4: Run catalog tests to confirm GREEN**

Run: `python -m unittest tests.test_uaf_skill_catalog -v`

Expected: all catalog tests pass.

### Task 4: Full Verification

- [ ] **Step 1: Run full unit suite**

Run: `python -m unittest discover -s tests -v`

Expected: all tests pass.

- [ ] **Step 2: Run metadata and compile checks**

Run:

```bash
python -m json.tool plugin.json
python -m src.skills.uaf_skill_catalog --check
python -B -c "import pathlib; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in pathlib.Path('.').rglob('*.py')]"
```

Expected: all commands succeed.
