# UAF Resume Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add resume-safe handoff snapshots and a final audit/TODO artifact so future host sessions can continue UAF work from repo-local state.

**Architecture:** Add a small dataclass contract in `src/contracts.py`, a focused builder in `src/orchestration/handoff.py`, and a workflow integration point after the goal ledger is saved. Keep outputs under `.uaf/state/` and keep public documentation under `docs/`.

**Tech Stack:** Python dataclasses, JSON/Markdown file output, existing `GoalLedger`, existing `ArtifactStore`, unittest.

---

### Task 1: Handoff Contract Tests

**Files:**
- Modify: `tests/test_contracts.py`
- Create: `tests/test_handoff.py`

- [ ] Write a failing round-trip test for `HandoffSnapshot`.
- [ ] Write failing tests proving a handoff can be built from existing goal ledger and artifact manifest state.
- [ ] Run the focused tests and confirm they fail because the contract/module does not exist.

### Task 2: Handoff Implementation

**Files:**
- Modify: `src/contracts.py`
- Create: `src/orchestration/handoff.py`

- [ ] Add `HandoffSnapshot` with `to_dict` and `from_dict`.
- [ ] Add `ResumeHandoff.build_snapshot()` to read goal, missing evidence, artifact manifest, memory context, and next action.
- [ ] Add `ResumeHandoff.save()` to write `.uaf/state/resume_handoff.json` and `.uaf/state/resume_handoff.md`.
- [ ] Run focused tests and confirm they pass.

### Task 3: Workflow Integration

**Files:**
- Modify: `src/tasks/workflows.py`
- Modify: `tests/test_workflows.py`

- [ ] Write a failing workflow test proving dispatch writes resume handoff metadata.
- [ ] Persist the handoff after the final goal ledger save.
- [ ] Attach handoff paths and snapshot metadata to `WorkflowDispatchResult.metadata["resume_handoff"]`.
- [ ] Run focused workflow tests and confirm they pass.

### Task 4: Skills, Docs, and Final TODO

**Files:**
- Modify: `README.md`
- Modify: `SKILL.md`
- Modify: `skills/context_state_harness/SKILL.md`
- Modify: `skills/goal_state_harness/SKILL.md`
- Modify: `docs/CODEX_ACTIVE_WORK.md`
- Create: `docs/UAF_TODO_SECURITY_REVIEW.md`

- [ ] Document the resume handoff contract and where host tools should read it.
- [ ] Add final audit/security TODOs discovered during this pass.
- [ ] Run skill catalog validation.

### Task 5: Verification and Push

**Files:**
- No code files.

- [ ] Run `python -m json.tool plugin.json`.
- [ ] Run `python -m src.skills.uaf_skill_catalog --check`.
- [ ] Run Python compile check.
- [ ] Run `python -m unittest discover -s tests -v`.
- [ ] Commit and push to `origin/main`.
