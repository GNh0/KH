---
name: code-review
description: Review actual code changes for correctness, project-contract regressions and appropriate verification.
---

# Code review

Read the latest diff and actual callers against the intended outcome. Use current target files and relevant approved project examples. Consult the [selected personal style](../../references/personal-style.md) for a style review of the relevant language only.

Distinguish style choices, data/compatibility defects and unverified areas. Test behaviors that could regress; do not infer working UI/DB behavior from a build or static checker. Explain actionable findings with the file, location, impact and reproduction conditions. Follow [workspace files](../work-execution/references/workspace-files.md) for review scratch and cleanup.
