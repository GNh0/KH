# UAF Skill Quality Design

## Goal

Improve the Universal Agent Framework by adding Python-first skill catalog validation, health reporting, and reusable quality-gate harness definitions.

## Context

UAF currently has a working contract layer, role graph, sandbox, snapshot manager, webhook receiver, and packaged skill catalog. The weak point is not the list/read catalog itself; it is that `skills/*/SKILL.md` files are trusted without validation, and the workflow gates are mostly represented as metadata rather than executable checks.

Mature agent workflow systems solve similar problems with generated `SKILL.md` files, host-specific skill outputs, static validation, health checks, safety skills, review/QA workflows, and rich tests. UAF should not vendor or depend on external skill runtimes. It should adopt the portable design patterns that match this repository.

## Scope

This phase adds:

- A Python `uaf_skill_validator` module for packaged skill validation.
- A `--check` command in `src.skills.uaf_skill_catalog`.
- JSON health output that callers can use in CLI, CI, or future app integrations.
- UAF-native harness skills for review, QA, context, guard, and health workflow patterns:
  - `review-gate-harness`
  - `qa-gate-harness`
  - `context-state-harness`
  - `guard-policy-harness`
  - `health-check-harness`
- Tests proving that built-in skills pass validation and intentionally broken skills fail clearly.

This phase does not implement browser automation, iOS QA, gbrain memory sync, or real subagent code generation. Those are larger adapter/runtime projects and should build on top of the validation and gate contracts added here.

## Architecture

`src.skills.uaf_skill_validator` becomes the validation source of truth. It scans `skills/<folder>/SKILL.md`, parses YAML-style frontmatter without adding dependencies, detects duplicate names, checks required fields, flags unresolved template placeholders, and reports missing body sections that UAF wants every harness to carry.

`src.skills.uaf_skill_catalog` continues to list and read skills. It gains a health/check surface:

- `validate_packaged_skills(...)` returns structured validation results.
- `collect_packaged_skills(...)` includes validation summary metadata.
- CLI `--check` prints JSON and exits non-zero when validation fails.

The validator reports data through dataclasses with `to_dict()` methods so it matches the style already used in `src.contracts`.

## Validation Rules

Every packaged skill should have:

- A `SKILL.md` file under a direct child folder of `skills/`.
- Frontmatter delimited by `---`.
- Non-empty `name` and `description`.
- A normalized unique name.
- A markdown body with an H1 heading.
- A `## UAF implementation targets` section.
- No unresolved `{{PLACEHOLDER}}` strings.

The `## UAF implementation targets` requirement reflects the existing UAF pattern. It keeps skill documents tied to concrete modules instead of becoming generic prompt prose.

## Tests

New tests should cover:

- Built-in packaged skills all validate successfully.
- Missing frontmatter fails.
- Duplicate skill names fail.
- Missing implementation targets fails.
- Unresolved placeholders fail.
- `collect_packaged_skills()` exposes a validation summary.
- `python -m src.skills.uaf_skill_catalog --check` returns success for the current repository.

Existing tests must keep passing:

- `python -m unittest discover -s tests -v`
- `python -m json.tool plugin.json`
- `python -m src.skills.uaf_skill_catalog --list`

## Follow-Up

After this phase, a separate implementation phase should replace placeholder workflow execution with concrete adapter runners. That work should use the validation and gate metadata added here to decide which review, QA, security, and release checks are required before a workflow can report success.
