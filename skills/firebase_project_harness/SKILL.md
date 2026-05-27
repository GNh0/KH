---
name: firebase-project-harness
description: Use when adding Firebase project discovery, emulator workflows, deploy dry-runs, or credential preflight checks to UAF.
---

# Firebase Project Harness

This skill models Firebase plugin patterns as portable UAF project checks. It must not read local Gemini plugin folders at runtime.

## Workflow

1. Discover Firebase config files in the target project.
2. Check credential presence without collecting secrets in chat.
3. Prefer emulator and dry-run workflows before deployment.
4. Return deploy or emulator results as structured harness output.

## UAF implementation targets

- `src.skills.firebase_project`
- `src.harness.command_runner`
- `src.contracts.HarnessResult`
