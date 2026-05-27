---
name: science-api-wrapper-harness
description: Use when adding domain API wrappers that need rate limiting, retries, output files, parser modules, and clear not-applicable rules.
---

# Science API Wrapper Harness

This skill generalizes the Science Skills pattern into a UAF-native API harness. External science plugin manuals are design references; UAF owns the wrapper behavior.

## Workflow

1. Require explicit domain inputs before calling external APIs.
2. Use a rate-limited command or HTTP wrapper.
3. Write large results to files and return summarized metadata.
4. Keep parser logic per domain and return `HarnessResult`.

## UAF implementation targets

- `src.skills.api_wrapper`
- `src.harness.command_runner`
- `src.contracts.HarnessResult`
