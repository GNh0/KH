---
name: modern-web-quality-harness
description: Use when adding responsive layout, accessibility, performance, asset rendering, or visual verification checks for web applications.
---

# Modern Web Quality Harness

This skill turns modern web guidance into repeatable UAF quality gates. The checks should be implemented locally through UAF harness modules.

## Workflow

1. Define the viewport matrix.
2. Verify layout stability and absence of obvious overlap.
3. Capture screenshots or browser diagnostics when available.
4. Report accessibility, performance, and rendering issues as structured results.

## UAF implementation targets

- `src.skills.web_quality`
- `src.harness.evaluator`
- `src.contracts.HarnessResult`
