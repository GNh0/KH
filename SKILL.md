# KH skill index

This repository is a Codex plugin, not a mandatory intake workflow. Load the relevant `skills/*/SKILL.md` entrypoint for the current request. See [사용법](README.ko.md) and [current documentation](docs/README.md). Historical sessions and the old UAF runtime are reference material only.

This file is an index, not an automatically executed router. The host exposes each installed skill's name/description/path, selects a matching entrypoint, then reads its instructions. Keep selection metadata in the individual skills. For the current artifact, follow that entrypoint's required reference/source path before implementation; reassess it when scope changes. Reading a skill or passing a partial checker does not establish that the final work follows it.

Before handing over skill-guided work, use the shared [rule audit](skills/rule-audit/SKILL.md) to compare applicable rules with actual results and repair confirmed violations within scope.
