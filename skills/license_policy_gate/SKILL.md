---
name: license-policy-gate
description: Use when a task needs license checks, terms-of-use notification, API key preflight, dataset restrictions, or secret-handling policy before execution.
---

# License Policy Gate

This skill makes external-access policy checks explicit and reusable. It is inspired by domain skills that require license notices and API key handling, but it is implemented as a UAF-native gate.

## Workflow

1. Identify the external service, dataset, or tool.
2. Check terms, license, and required user notification.
3. Verify required environment variables without printing secrets.
4. Record the preflight result before allowing the task to continue.

## UAF implementation targets

- `src.skills.license_checker`
- `src.contracts.HarnessResult`
