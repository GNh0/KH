# Explicit Cross-Scope Memory Import

## Decision

KH memory recall stays current-scope by default. Similar keywords must not make
the host search or apply another project/chat memory automatically.

When the user explicitly names another project or chat as context, the host may
call `src.orchestration.runtime_memory.build_explicit_cross_scope_memory_import(...)`.
That result is read-only `external_context` until the caller records
`memory_import_approved=true`.

## Policy

- Source scope must be explicit: `source_scope`, `memory_import_source_project_dir`,
  or `memory_import_source_thread_id`.
- Read-only recall does not change current memory.
- Approved application defaults to current-scope memory candidates.
- Durable promotion requires a separate `memory_import_promote=true` decision.
- Imported records keep source scope, source record id, source kind, query, and
  source score metadata.
- Deleted source scopes block import.

## Verification

- `tests.test_runtime_memory` verifies current-scope isolation, approval-required
  read-only import, and approved candidate import.
- `tests.test_workflow_usability_layer` verifies session-start context can carry
  explicitly requested imports without applying them.
