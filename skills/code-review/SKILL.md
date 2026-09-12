---
name: code-review
description: Review actual changes for correctness, source-contract regressions, and appropriate verification before reporting completion.
---

# Code review

Read the latest diff and actual callers; review against the user's intended outcome. Do not substitute another project or an old copy for evidence of current behavior. Distinguish style preferences, data/compatibility defects, and unverified areas.

For changes that could regress behavior, run tests of that behavior. Avoid tests that merely match implementation wording, fixed reviewer/score requirements, and repeated full test runs. Apply the narrow necessity criteria in [preferences and exceptions](../work-execution/references/preferences.md) to LINQ, intermediate tables, and builds.

Explain findings with the file, location, actual impact, and reproduction conditions. A passing build is not evidence of screen layout, database persistence, or actual agent execution. If completion includes applying the result, distinguish file creation from application and finish the authorized application. Clearly identify anything unverified.
