# UAF GStack-Derived Skill Quality Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use KH skillbook task-by-task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add UAF-native skill validation, catalog health checks, and gstack-derived quality harness skills.

**Architecture:** Add a dependency-free Python validator module under `src.skills`, expose it through `uaf_skill_catalog`, and add focused tests before implementation. Add new `skills/<name>/SKILL.md` folders that describe UAF-native review, QA, context, guard, and health gate workflows.

**Tech Stack:** Python 3.9+, `unittest`, existing UAF dataclass and skill catalog patterns.

---

### Task 1: Skill Validator Contracts

**Files:**
- Create: `src/skills/uaf_skill_validator.py`
- Test: `tests/test_uaf_skill_validator.py`

- [ ] **Step 1: Write failing tests for built-in skill validation and broken fixtures**

Create tests that call `validate_skill_folders()` against temporary skill folders and the repository's packaged `skills/` directory. Assert that valid skills pass and broken skills return structured errors.

- [ ] **Step 2: Run the validator tests and confirm RED**

Run: `python -m unittest tests.test_uaf_skill_validator -v`

Expected: import failure for `src.skills.uaf_skill_validator`.

- [ ] **Step 3: Implement validator dataclasses and scanning**

Add `SkillValidationIssue`, `SkillValidationResult`, `SkillCatalogValidationReport`, `parse_skill_frontmatter()`, and `validate_skill_folders()`.

- [ ] **Step 4: Run the validator tests and confirm GREEN**

Run: `python -m unittest tests.test_uaf_skill_validator -v`

Expected: all validator tests pass.

### Task 2: Catalog Check CLI

**Files:**
- Modify: `src/skills/uaf_skill_catalog.py`
- Test: `tests/test_uaf_skill_catalog.py`

- [ ] **Step 1: Write failing tests for validation summary and CLI check**

Extend existing catalog tests to assert `collect_packaged_skills()` includes `validation` metadata and that the CLI supports `--check`.

- [ ] **Step 2: Run focused catalog tests and confirm RED**

Run: `python -m unittest tests.test_uaf_skill_catalog -v`

Expected: failure because `validation` metadata and `--check` are not implemented.

- [ ] **Step 3: Wire validator into catalog**

Import `validate_skill_folders()`, attach its `to_dict()` output to collection results, add `check_skills()`, and support CLI `--check`.

- [ ] **Step 4: Run focused catalog tests and confirm GREEN**

Run: `python -m unittest tests.test_uaf_skill_catalog -v`

Expected: all catalog tests pass.

### Task 3: GStack-Derived UAF Harness Skills

**Files:**
- Create: `skills/review_gate_harness/SKILL.md`
- Create: `skills/qa_gate_harness/SKILL.md`
- Create: `skills/context_state_harness/SKILL.md`
- Create: `skills/guard_policy_harness/SKILL.md`
- Create: `skills/health_check_harness/SKILL.md`
- Modify: `tests/test_uaf_skill_catalog.py`

- [ ] **Step 1: Write failing catalog expectations for new harnesses**

Add the five new skill names to the expected core skill set.

- [ ] **Step 2: Run catalog tests and confirm RED**

Run: `python -m unittest tests.test_uaf_skill_catalog -v`

Expected: missing skill failures.

- [ ] **Step 3: Add UAF-native harness docs**

Write concise `SKILL.md` files with frontmatter, workflow, required outputs, and `## UAF implementation targets`.

- [ ] **Step 4: Run catalog and validator tests and confirm GREEN**

Run: `python -m unittest tests.test_uaf_skill_catalog tests.test_uaf_skill_validator -v`

Expected: all focused tests pass.

### Task 4: Full Verification

**Files:**
- No new files unless tests expose a needed fix.

- [ ] **Step 1: Run full unit suite**

Run: `python -m unittest discover -s tests -v`

Expected: all tests pass.

- [ ] **Step 2: Run metadata checks**

Run:

```bash
python -m json.tool plugin.json
python -m src.skills.uaf_skill_catalog --list
python -m src.skills.uaf_skill_catalog --check
python -B -c "import pathlib; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in pathlib.Path('.').rglob('*.py')]"
```

Expected: all commands succeed. `--check` reports `success: true`.
