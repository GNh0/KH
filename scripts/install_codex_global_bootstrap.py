"""Install a thin Codex global KH UAF front-door bootstrap skill.

Codex Desktop can load personal skills from ``$CODEX_HOME/skills`` even in
subagent sessions where personal marketplace plugin skills are not present in
the generated skill list.  This installer writes a small bridge skill that
locates the latest installed KH UAF plugin cache and runs its front-door
wrapper before any target-project exploration.
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from typing import Iterable, Optional


SKILL_NAME = "kh-uaf-front-door"


def default_codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    if configured:
        return Path(configured)
    return Path.home() / ".codex"


def _version_key(path: Path) -> tuple[int, ...]:
    parts = []
    for part in path.name.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(-1)
    return tuple(parts)


def iter_cache_roots(codex_home: Path) -> Iterable[Path]:
    cache_root = codex_home / "plugins" / "cache" / "kh-uaf-marketplace" / "kh-uaf"
    if not cache_root.is_dir():
        return []
    return sorted((p for p in cache_root.iterdir() if p.is_dir()), key=_version_key, reverse=True)


def find_latest_cache(codex_home: Path) -> Optional[Path]:
    for root in iter_cache_roots(codex_home):
        wrapper = root / "skills" / "always_on_front_door" / "scripts" / "front_door.py"
        if wrapper.is_file():
            return root
    return None


def render_skill() -> str:
    return """---
name: kh-uaf-front-door
description: Use when any non-trivial Codex request involves project paths, code changes, generated docs/assets, long logs, reviews, QA, verification, subagents, persistence, branch work, or risky actions; read this skill alone, then run KH front_door.py as the next standalone tool call before MEMORY.md lookup, target-folder checks, sibling scans, source reads, or implementation, even when the user does not name KH, UAF, a skill, or a harness.
---

# KH UAF Front Door

This is a thin global Codex bootstrap skill. It exists because some Codex
subagent contexts can receive personal `$CODEX_HOME/skills` entries while not
receiving personal marketplace plugin skills. It does not replace KH UAF. It
locates the latest installed `kh-uaf@kh-uaf-marketplace` cache and delegates to
the packaged `always_on_front_door` wrapper.

## Immediate Action

For a work-bearing request, this skill must run before target-folder checks,
parent/sibling folder scans, project file reads, `MEMORY.md` lookup, browser or
document actions, generated code, verification, or subagent dispatch.

Do not parallelize this SKILL.md read with `MEMORY.md` lookup, `Get-ChildItem`,
`Test-Path`, source reads, browser work, document work, or any target-project
inspection. After this SKILL.md has been read, the next standalone tool call
must be the KH front-door wrapper or an explicit blocked result naming the
missing wrapper path.

The only allowed pre-intake lookup is resolving the installed KH UAF plugin
cache itself:

```powershell
$khRoot = Get-ChildItem -LiteralPath "$env:USERPROFILE\\.codex\\plugins\\cache\\kh-uaf-marketplace\\kh-uaf" -Directory |
  Sort-Object Name -Descending |
  Select-Object -First 1
python "$($khRoot.FullName)\\skills\\always_on_front_door\\scripts\\front_door.py" --prompt "<user request>" --project "<cwd or target project>" --host codex --summary
```

If `CODEX_HOME` is set, use `$env:CODEX_HOME` instead of
`$env:USERPROFILE\\.codex`.

## Workflow

1. Decide whether the request is direct/light or work-bearing.
2. If work-bearing, run the front-door wrapper above as the first standalone
   work-bearing command.
3. Treat only `runtime_applied_skills` as executed.
4. Treat `selected_not_executed_skills` as selected follow-up work until a
   concrete module, gate, artifact, command-output handler, or blocked
   rationale produces evidence.
5. If `brainstorming-harness` is selected for a vague product, app, service,
   SaaS, platform, or design request, read the installed cache's
   `skills/brainstorming_harness/SKILL.md`, present options or one scoped
   question, and stop for user approval before scaffolding or product code.
6. If the installed KH UAF cache or wrapper is missing, report blocked with the
   missing path instead of continuing as if KH ran.

## Required Outputs

- `front_door_status`, request classification, and plugin route.
- `runtime_applied_skills` and `selected_not_executed_skills`.
- A blocked rationale if the KH UAF cache or wrapper cannot be resolved.
- For vague product/project discovery, a visible approval checkpoint before any
  implementation or scaffold.

## Common Mistakes

- Do not read `MEMORY.md` before front-door.
- Do not inspect the target folder or sibling folders before front-door.
- Do not count this SKILL.md read as KH runtime execution.
- Do not implement a vague product request in the same turn before the user
  approves the brainstorming direction.
"""


def install(codex_home: Path, *, force: bool = False) -> Path:
    latest_cache = find_latest_cache(codex_home)
    if latest_cache is None:
        raise FileNotFoundError(
            f"KH UAF plugin cache with front_door.py was not found under {codex_home}"
        )
    target_dir = codex_home / "skills" / SKILL_NAME
    target_file = target_dir / "SKILL.md"
    if target_file.exists() and not force:
        existing = target_file.read_text(encoding="utf-8")
        if "KH UAF Front Door" in existing and "front_door.py" in existing:
            return target_file
        raise FileExistsError(f"Refusing to overwrite non-KH skill: {target_file}")
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file.write_text(render_skill(), encoding="utf-8", newline="\n")
    return target_file


def remove(codex_home: Path) -> bool:
    target_dir = codex_home / "skills" / SKILL_NAME
    target_file = target_dir / "SKILL.md"
    if not target_file.exists():
        return False
    content = target_file.read_text(encoding="utf-8")
    if "KH UAF Front Door" not in content:
        raise FileExistsError(f"Refusing to remove non-KH skill: {target_file}")
    shutil.rmtree(target_dir)
    return True


def check(codex_home: Path) -> dict[str, object]:
    latest_cache = find_latest_cache(codex_home)
    target_file = codex_home / "skills" / SKILL_NAME / "SKILL.md"
    content = target_file.read_text(encoding="utf-8") if target_file.is_file() else ""
    return {
        "codex_home": str(codex_home),
        "latest_cache": str(latest_cache) if latest_cache else "",
        "installed": target_file.is_file(),
        "target": str(target_file),
        "has_front_door_text": "front_door.py" in content,
        "has_brainstorming_stop": "stop for user approval" in content,
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", type=Path, default=default_codex_home())
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--remove", action="store_true")
    args = parser.parse_args(argv)

    codex_home = args.codex_home.expanduser().resolve()
    if args.remove:
        removed = remove(codex_home)
        print({"removed": removed, "codex_home": str(codex_home)})
        return 0
    if args.check:
        print(check(codex_home))
        return 0
    target = install(codex_home, force=args.force)
    print({"installed": True, "target": str(target), "codex_home": str(codex_home)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
