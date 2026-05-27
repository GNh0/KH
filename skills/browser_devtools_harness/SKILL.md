---
name: browser-devtools-harness
description: Use when adding browser debugging, console capture, network inspection, screenshot verification, Lighthouse-style checks, or frontend runtime diagnostics to UAF.
---

# Browser DevTools Harness

This skill converts Chrome DevTools and modern web guidance patterns into UAF-native browser diagnostics. The packaged skill is the source of truth; external browser plugins are reference material only.

## Workflow

1. Start or connect to a browser session through a UAF adapter.
2. Capture console, network, and page errors.
3. Run viewport and screenshot checks for visual regressions.
4. Return structured diagnostics through `AdapterResult` or `HarnessResult`.

## UAF implementation targets

- `src.skills.browser_devtools`
- `src.platforms.dispatcher_factory`
- `src.contracts.AdapterResult`
