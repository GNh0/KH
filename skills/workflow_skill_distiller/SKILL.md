---
name: workflow-skill-distiller
description: Use when turning a repeated user workflow, completed interaction, or project-specific process into a reusable UAF skill folder.
---

# Workflow Skill Distiller

This skill defines how UAF captures workflows as portable skills. A new skill should be added as `skills/<skill-name>/SKILL.md`; optional support files are used only when that `SKILL.md` says when to read or run them.

## Workflow

1. Extract the trigger condition from the repeated workflow.
2. Keep `SKILL.md` concise and procedural.
3. Put heavy examples in `references/` and deterministic helpers in `scripts/`.
4. Add tests or smoke checks when the skill is surfaced through Python or MCP.

## Required outputs

- New or updated `skills/<skill-name>/SKILL.md` with trigger-focused frontmatter.
- Explicit workflow, required outputs, common mistakes, and implementation targets.
- Support-file guidance inside SKILL.md when `references/`, `scripts/`, or `assets/` are used.
- Catalog validation and targeted tests for any Python-backed behavior.

## Common mistakes

- Do not turn a one-off session story into a reusable skill.
- Do not hide support-file behavior in README-only text.
- Do not create extra README, changelog, or guide files inside a skill folder.
- Do not publish a skill whose trigger description summarizes the workflow instead of when to use it.

## UAF implementation targets

- `skills/<skill-name>/SKILL.md`
- `src.skills.catalog`
- `src.skills.uaf_skill_catalog`
