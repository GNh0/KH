---
name: workflow-skill-distiller
description: Use when turning a repeated user workflow, completed interaction, or project-specific process into a reusable UAF skill folder.
---

# Workflow Skill Distiller

This skill defines how UAF captures workflows as portable skills. A new skill should be added as `skills/<skill-name>/SKILL.md`; optional support files are used only when that `SKILL.md` says when to read or run them.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.

## Workflow

1. Call `src.skills.workflow_distiller.should_distill_workflow` to reject one-off workflows before writing a skill.
2. Extract the trigger condition from the repeated workflow and keep it in `Use when...` form.
3. Call `src.skills.workflow_distiller.build_skill_scaffold` when creating a new skill folder skeleton, passing the intended execution level when known.
4. Keep `SKILL.md` concise and procedural.
5. Put heavy examples in `references/` and deterministic helpers in `scripts/`.
6. Add tests or smoke checks when the skill is surfaced through Python or MCP.
7. For generated skills, run the generated `scripts/smoke_check.py` from the generated skill folder and pass `UAF_REPO_ROOT` when the skill is outside the repository tree.

## Required outputs

- New or updated `skills/<skill-name>/SKILL.md` with trigger-focused frontmatter.
- Explicit workflow, required outputs, common mistakes, and implementation targets.
- Support-file guidance inside SKILL.md when `references/`, `scripts/`, or `assets/` are used.
- Catalog validation, robust smoke target resolution, and targeted tests for any Python-backed behavior.

## Common mistakes

- Do not turn a one-off session story into a reusable skill.
- Do not hide support-file behavior in README-only text.
- Do not create extra README, changelog, or guide files inside a skill folder.
- Do not publish a skill whose trigger description summarizes the workflow instead of when to use it.

## UAF implementation targets

- `src.skills.workflow_distiller.should_distill_workflow`
- `src.skills.workflow_distiller.build_skill_scaffold`
- `skills/<skill-name>/SKILL.md`
- `src.skills.catalog`
- `src.skills.uaf_skill_catalog`
- `tests.test_workflow_distiller_runtime`
