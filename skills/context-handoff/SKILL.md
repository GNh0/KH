---
name: context-handoff
description: Capture or restore a compact checkpoint for an ongoing task when the user requests handoff or long work needs reliable continuation.
---

# Context handoff

Briefly record the current objective, authorized scope, latest corrections, changed files, validation results, and next steps. Link the relevant actual files and error locations instead of copying long tool outputs.

On resumption, check current files/processes and the paused state. Do not repeat completed steps; incorporate new feedback into the existing objective. Honor the user's stop request and scheduled resumption time.

Check skill names and versioned cache paths in the handoff against the current session's skill list. Use the current paths when supplied. Do not add searches for removed harnesses or skill-use tables to the handoff procedure.

This is a handoff for the current task. Do not create automatic persistent memory, an all-session search, a separate Goal ledger, or a snapshot/rollback system. Memory updates and creation of other tasks require the current user's explicit request and must follow the host tool contracts.
