---
name: skill-catalog
description: Use when listing, reading, or adding packaged UAF skills and harnesses in this repository.
---

# UAF Skill Catalog

UAF skills are packaged inside this repository under `skills/<skill-name>/SKILL.md`.
Do not depend on installed Gemini, Antigravity, RTK, or Superpower skill folders at runtime.

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

## UAF implementation targets

- `skills/<skill-name>/SKILL.md`
- `src.skills.uaf_skill_catalog`
- `src.skills.catalog`
