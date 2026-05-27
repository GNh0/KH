---
name: antigravity-bridge
description: Use when listing, reading, or extending the packaged UAF skill and harness folders that were designed from Antigravity, Gemini, RTK, and Superpower-style references.
---

# UAF Skill Folder Catalog

This is not a runtime bridge into an installed Antigravity or Gemini plugin directory. UAF skills are packaged inside this repository under `skills/<skill-name>/SKILL.md`.

## Add a skill

1. Create a folder under `skills/`.
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
python -m src.skills.antigravity_bridge --list
```

Read one packaged skill:

```bash
python -m src.skills.antigravity_bridge --read parallel-orchestration-harness
```

## UAF implementation targets

- `skills/<skill-name>/SKILL.md`
- `src.skills.antigravity_bridge`
- `src.skills.catalog`
