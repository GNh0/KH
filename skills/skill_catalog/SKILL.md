---
name: skill-catalog
description: Use when kh-uaf:always-on-front-door has already run and selected this skill; use it when listing, reading, or adding packaged UAF skills and harnesses in this repository.
---

# UAF Skill Catalog

## KH Entry Contract

- Start every non-trivial turn through `always-on-front-door` unless this skill is that bootstrap step or the current turn was classified as light/direct.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, or a required follow-up gate selects it.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

UAF skills are packaged inside this repository under `skills/<skill-name>/SKILL.md`.
Do not depend on installed external skill folders at runtime.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## Add a skill

1. Create `skills/<skill-name>/`.
2. Add `SKILL.md`.
3. Put `name` and `description` in YAML frontmatter.
4. Keep the body focused on the UAF-native workflow and implementation targets.

Optional support files are allowed:

- `references/` for long examples or external reference notes.
- `scripts/` for deterministic helpers.
- `assets/` for templates or reusable output files.

Support files only affect behavior when `SKILL.md` says when to read or run them.

## CLI

List packaged UAF skills:

```bash
python -m src.skills.uaf_skill_catalog --list
```

Read one packaged skill:

```bash
python -m src.skills.uaf_skill_catalog --read parallel-orchestration-harness
```

Reference-derived examples:

```bash
python -m src.skills.uaf_skill_catalog --read host-agent-orchestration
python -m src.skills.uaf_skill_catalog --read command-output-harness
```

## Execution Levels

The catalog exposes `execution_level` for every skill:

- `python-module`: backed by callable Python contracts or modules.
- `hybrid-harness`: backed by Python contracts plus required workflow procedure.
- `procedure-policy`: host-readable procedure or policy; not a standalone code module.

Do not claim every packaged skill is executed the same way. A run can combine direct module calls, hybrid harness orchestration, and procedure/policy application, but the catalog must make that distinction explicit.

## External Benchmark Recipe

Use this skill as the source of truth for packaged UAF skills:

1. List packaged skills from this repository only.
2. Read a skill by canonical name and return the packaged `SKILL.md` body.
3. Validate frontmatter, support-file wiring, implementation targets, and execution level.
4. Treat local Gemini, Antigravity, Claude, or Codex user folders as references only, not runtime dependencies.
5. Fail packaging when an execution level is missing or a target cannot resolve.

Pressure scenario: if a skill exists in a user's local Antigravity folder but not under this repository's `skills/`, it must not appear as a packaged KH skill.

## Required outputs

- Skill list with name, description, relative path, packaging source, external dependency flag, and execution level.
- Validation summary with total, valid, invalid, and issue details.
- `--read <skill>` output that includes packaged source and the selected SKILL.md body.
- Clear distinction between `python-module`, `hybrid-harness`, and `procedure-policy`.

## Common mistakes

- Do not scan local Gemini, Antigravity, Claude, or Codex user skill folders at runtime.
- Do not claim every skill is directly executable when some are procedure/policy skills.
- Do not accept a skill without trigger-focused frontmatter and implementation targets.
- Do not rely on README-only instructions for support files.

## UAF implementation targets

- `skills/<skill-name>/SKILL.md`
- `src.skills.uaf_skill_catalog`
- `src.skills.catalog`
