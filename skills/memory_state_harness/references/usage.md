# Memory State Harness Usage Reference

This reference expands the portable operating contract for `memory-state-harness`. Read it when the task is real work, when deciding whether this skill applies, or when a review needs evidence beyond the concise `SKILL.md`.

## When to use

Use when a UAF workflow needs scoped persistent memory, memory candidates, project/conversation namespace isolation, or archive/delete cleanup policy.

Context summary: This is the UAF-native persistent memory harness for project/chat-scoped memory. It keeps long-lived project or conversation knowledge separate from short-lived goal state and context compression. It is not system memory and does not write host/global prompt memory by default.

External memory bases adapted by KH:

- OpenClaw: project/chat-scoped durable `MEMORY.md` equivalents, working `memory/YYYY-MM-DD.md` equivalents, action-sensitive memory boundaries, pre-compaction flush, and promotion from working notes to durable scoped memory.
- Hermes: bounded project/chat-scoped `MEMORY.md`/`USER.md` prompt snapshots frozen at session start, separate session search, additive external memory providers, profile/session scoping, and provider status checks.
- RTK/command-output discipline: do not compress or summarize memory evidence in ways that remove source, authority, expiry, or safe-to-act boundaries.

Scope hierarchy:

- `project`: reusable facts for the current workspace.
- `project_chat` or `conversation`: decisions and handoff state for the current thread.
- `project_chat_subagent` or `conversation_chat_subagent`: child or nested child observations, stored under `agents/<lineage>/`.
- sibling subagents are isolated from one another.
- parent-approved sharing is the only default sharing path: `parent_memory_access` for read-only parent context, `parent_memory_candidates` for upward candidate submission.
- host global Codex memory is not the default sink. Treat it as a separate user-approved promotion target for important cross-project behavior rules.

Do not use this skill only because it is available. Use it when the current task needs the behavior named by the trigger, and state whether the skill was actually executed, applied procedurally, or only considered.

## Inputs to collect

- User objective, success criteria, and any explicit completion conditions.
- Target workspace, write boundaries, and whether user-facing deliverables are expected.
- Required role, gate, state, artifact, or command evidence for this harness.
- Existing artifacts or state files that must be preserved rather than overwritten.
- Execution level: `python-module`.
- Implementation targets:
  - `src.contracts.MemoryScope`
  - `src.contracts.MemoryRecord`
  - `src.contracts.MemoryEvent`
  - `src.orchestration.memory_state`
  - `src.orchestration.memory_store`
  - `src.orchestration.runtime_memory`
  - `src.orchestration.session_start_context`
  - `src.orchestration.interruption_state`
  - `src.platforms.codex_thread_registry`
  - `src.tasks.workflows`

## Execution pattern

1. Read `SKILL.md` first and confirm the trigger applies to the current task.
2. Read this reference before performing non-trivial work with `memory-state-harness`.
3. Call or inspect the listed Python implementation targets, then record the exact module/function path and test evidence used.
4. Preserve intermediate decisions in structured evidence rather than relying on terminal logs alone.
5. For cross-project or cross-chat recall, require a user-named source scope and use `src.orchestration.runtime_memory.build_explicit_cross_scope_memory_import(...)`; do not treat keyword similarity as approval to read other scopes.
6. Keep cross-scope results as read-only external context unless `memory_import_approved=true`; applying them to the current scope should default to candidates.
7. For subagent or nested-subagent work, include `agent_lineage` in metadata before memory access. Do not store child observations in the chat or project root unless a parent/controller accepts them.
8. If a child needs parent context, call `build_parent_scope_memory_access(...)`; without `parent_memory_access_approved=true`, return an approval-required result and no records.
9. If a child has reusable observations, call `submit_parent_memory_candidates(...)`; without `parent_memory_candidates_approved=true`, leave only a request event.
10. Treat project/chat prompt memory as frozen-at-session-start context. Writes during a session persist to scoped KH storage but should be surfaced through tool output or the next session-start context pass, not assumed to be inside the active prompt.
11. Keep memory layers separate:
   - project/chat durable compact facts/preferences/standing decisions.
   - working notes and session summaries.
   - nested subagent candidates under `agents/<lineage>/`.
   - on-demand session search for exact past conversation lookup.
   - optional external provider recall with provenance.
12. For action-sensitive memories, record what future behavior changes, when it applies, expiry/unlock condition, what to avoid, and source/owner authority.
13. Run `python scripts/smoke_check.py` when validating this packaged skill in the repository.
14. Report the difference between capability available in the repository and behavior actually executed in the current run.

## Evidence to produce

- Skill name and execution level used for the run.
- Concrete input summary and target workspace or artifact paths.
- Implementation targets touched, imported, called, resolved by smoke check, or explicitly not needed.
- Output files, gate results, state records, or role results created by the skill.
- Cross-scope import evidence when applicable: source scope, target scope, query, approval state, external context count, application status, and promotion mode.
- Parent-scope exchange evidence when applicable: child scope, parent scope, agent lineage, approval state, returned read-only context count, candidate recorded count, and promotion mode.
- Action-sensitive memory boundary when a memory changes future behavior: authority, freshness, expiry/unlock condition, safe-to-act timing, and avoidance rule.
- Prompt snapshot status: scoped frozen snapshot path, scoped live write path, and whether a new session/start-context pass is required before the model can rely on it.
- Verification command or review evidence, including failures and blocked states.

## Failure handling

- If a required implementation target is missing, stop using this skill as executed evidence and report the missing target.
- If the workflow can only be applied procedurally, say so explicitly and record the policy or decision evidence.
- If parallel, role, gate, or state behavior is claimed, prove the actual runtime path instead of citing only repository support.
- If generated artifacts are incomplete, withhold completion until the missing artifact or exception is recorded.

## Quality bar

A valid use of `memory-state-harness` must leave enough evidence for another agent to answer: why this skill applied, what ran or was applied, what changed, and what still needs attention.
