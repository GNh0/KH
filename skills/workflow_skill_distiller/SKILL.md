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

## UAF implementation targets

- `skills/<skill-name>/SKILL.md`
- `src.skills.catalog`
- `src.skills.uaf_skill_catalog`
