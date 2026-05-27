---
name: android-cli-harness
description: Use when building UAF support for Android SDK checks, device diagnostics, project creation, emulator workflows, or app run/deploy command planning.
---

# Android CLI Harness

This skill captures Android CLI patterns as a UAF-native harness. Do not depend on the Gemini Android plugin at runtime; keep command planning and diagnostics inside UAF.

## Workflow

1. Check whether the Android CLI and SDK tools are available.
2. Report installed SDK packages and connected device state.
3. Produce dry-run command plans before creating, running, or deploying projects.
4. Return command output through `HarnessResult`.

## UAF implementation targets

- `src.skills.android_cli`
- `src.harness.command_runner`
- `src.contracts.HarnessResult`
