# UAF Goal Evidence Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect `GoalState.evidence_required` to review, QA, and release gate outcomes.

**Architecture:** Add a focused goal evidence evaluator under orchestration, then call it from workflow dispatch before building role gate results. Keep existing role gate behavior unchanged when no goal metadata is supplied.

**Tech Stack:** Python 3.9+, dataclasses, unittest, existing UAF workflow and role graph modules.

---

### Task 1: Goal Evidence Evaluator

**Files:**
- Create: `src/orchestration/goal_evidence.py`
- Modify: `tests/test_goal_evidence.py`

- [ ] **Step 1: Write failing tests**

Add tests for `evaluate_goal_evidence()` showing complete and blocked outcomes.

- [ ] **Step 2: Run focused tests to confirm RED**

Run: `python -m unittest tests.test_goal_evidence -v`

Expected: import failure because `src.orchestration.goal_evidence` does not exist.

- [ ] **Step 3: Implement evaluator**

Implement exact normalized matching for required and collected evidence, returning an updated serialized goal dict.

- [ ] **Step 4: Run focused tests to confirm GREEN**

Run: `python -m unittest tests.test_goal_evidence -v`

Expected: all goal evidence tests pass.

### Task 2: Role Gate Evidence Blocking

**Files:**
- Modify: `src/orchestration/roles.py`
- Modify: `tests/test_orchestration_roles.py`

- [ ] **Step 1: Write failing gate test**

Add a test where implementer tasks succeed but the evaluated goal is blocked for missing evidence. Assert `qa-verifier` and `release-manager` are blocked with missing evidence metadata.

- [ ] **Step 2: Run focused tests to confirm RED**

Run: `python -m unittest tests.test_orchestration_roles -v`

Expected: failure because `build_role_gate_results()` ignores goal evidence.

- [ ] **Step 3: Implement gate handling**

Extend `build_role_gate_results(task_results, goal=None)` so missing goal evidence blocks QA and release after spec/code review pass.

- [ ] **Step 4: Run focused tests to confirm GREEN**

Run: `python -m unittest tests.test_orchestration_roles -v`

Expected: all role graph tests pass.

### Task 3: Workflow and Dispatcher Wiring

**Files:**
- Modify: `src/tasks/workflows.py`
- Modify: `src/platforms/dispatcher_factory.py`
- Modify: `tests/test_workflows.py`
- Modify: `tests/test_dispatcher.py`

- [ ] **Step 1: Write failing workflow and dispatcher tests**

Add tests that local workflow metadata contains evaluated goal status and evidence, and local dispatcher metadata exposes the same evaluated goal.

- [ ] **Step 2: Run focused tests to confirm RED**

Run: `python -m unittest tests.test_workflows tests.test_dispatcher -v`

Expected: failures because workflow metadata still returns the original active goal.

- [ ] **Step 3: Wire evaluator into workflow dispatch**

Collect deterministic workflow evidence, evaluate goal completion, pass the evaluated goal to role gates, and return it in workflow and adapter metadata.

- [ ] **Step 4: Run focused tests to confirm GREEN**

Run: `python -m unittest tests.test_workflows tests.test_dispatcher -v`

Expected: all focused tests pass.

### Task 4: Documentation and Verification

**Files:**
- Modify: `README.md`
- Modify: `skills/goal_state_harness/SKILL.md`

- [ ] **Step 1: Update docs**

Document that GoalState now participates in QA/release gate blocking.

- [ ] **Step 2: Run full verification**

Run:

```bash
python -m json.tool plugin.json
python -m src.skills.uaf_skill_catalog --check
python -m unittest discover -s tests -v
python -B -c "import pathlib; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in pathlib.Path('.').rglob('*.py')]"
```

Expected: all commands succeed.
