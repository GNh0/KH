# Always On Front Door Usage

## When to use

Plugin instructions request this skill first for every new user task handled by Codex, an Antigravity-style host, Claude Code, or a local worker. They cannot guarantee host auto-selection or plugin injection, so audit compliance from actual runtime receipts or session logs. The user does not need to say KH, UAF, skill, harness, plugin, front door, router, or catalog. Short/simple SQL formatting, translation, rewrite, lookup, arithmetic, and other light/direct requests still enter the runtime when the host follows the request; the runtime then decides whether to exit directly.

Use it before any more specific skill for all requests, including:

- definitions, translation, rewrite, lookup, arithmetic, and other direct answers
- short SQL formatting or alias-only SQL cleanup
- project path or workspace files
- code edits, generated app/site/tool output, or refactoring
- generated documents, images, spreadsheets, diagrams, or deliverables
- command output, logs, review, QA, tests, or verification
- subagents, delegation, persistence, memory, branch finishing, or risky commands

Target-folder checks, parent/sibling folder scans, `Test-Path`, `Get-ChildItem`, `rg`, `Get-Content`, `Select-String`, file reads, MEMORY.md searches, memory quick passes, browser/document/image actions, and plugin-specific work are already work exploration. They must happen after this front-door step. Do not run those checks in the same parallel batch as the front-door command; the front-door command or a blocked runtime result must be the first standalone action.

At bootstrap time, select only `kh-uaf:always-on-front-door`. Other KH skills, browser skills, QA skills, verification skills, and memory handling become eligible only after `kh_front_door` returns. Reading a non-bootstrap KH skill file before front-door is an ordering miss.

When the user provides an explicit target folder, treat that folder as the work boundary. Do not list the parent directory or read sibling folders from earlier tests/runs to seed the new task unless the user explicitly asks for comparison, migration, or reuse.

For short/direct work, use the low-overhead `--micro-summary` packet as the normal machine bootstrap. If it returns `cls.x=direct`, `g.ok=true`, and no `next` list, answer directly without reading any unrelated `SKILL.md`. This is a runtime direct exit, not a host-side bootstrap exception.

A bounded confirmation or status message may reuse only evidence from the current unfinished task when scope is unchanged. Task completion closes that reuse window. A new task or added work must rerun front-door.

Persistent directive: if an earlier message in the same conversation or project says to actively, aggressively, always, by default, or continuously use KH/UAF skills or harnesses, later work-bearing requests should be treated as `kh_active_directive=active` even when the later wording omits KH names. The active directive ends only when the user explicitly opts out.

Execution level: `python-module`.

Implementation targets:

- `src.orchestration.kh_front_door.build_kh_front_door`
- `src.orchestration.request_classifier.classify_request`
- `src.orchestration.plugin_composition.compose_plugin_route`
- `src.skills.uaf_skill_catalog.collect_packaged_skills`
- `skills/always_on_front_door/SKILL.md`
- `skills/automatic_intake_harness/SKILL.md`
- `tests.test_kh_front_door_always_on`

actual_runtime_path: `src.orchestration.kh_front_door.build_kh_front_door`, `python -m src.orchestration.kh_front_door` from the KH repository root, or `scripts/front_door.py` from this skill folder when the host starts elsewhere.

## Inputs to collect

- `prompt`: the user's request as written.
- `project`: the current working directory or explicit target project path.
- `host`: `codex`, `antigravity`, `claude-code`, or `local`.
- `kh_active_directive`: active/inactive, including the earlier user message that established it when available.
- optional `host_skill_paths`: host-provided skill file paths that may need stale-cache checking.

## Execution pattern

Run for every new user request or task. For non-ASCII prompts on Windows, prefer `--prompt-file` so the classifier receives the exact user text instead of a mojibaked shell argument:

```bash
python "<this skill folder>/scripts/front_door.py" --prompt-file "<utf8 prompt file>" --project "<cwd or target project>" --host codex --summary --strict-execution-gate
```

`--prompt "<user request>"` remains available for short ASCII-only prompts. `--prompt-stdin` is also available when the host can provide stdin safely. Keep `--strict-execution-gate` for host runs; exit code 3 means front-door succeeded but task execution is blocked until the reported immediate skill/gate evidence exists.

Use `--micro-summary` as the normal machine bootstrap for short/direct work. The micro packet preserves classification, route, gate, token decision, and ordered next-skill codes. Use `--summary` when human-readable audit details are required. Neither mode authorizes the host to inspect another skill before KH runs.

Then:

1. Use `classification` to choose direct, lightweight skill, or role-DAG depth.
2. Use `plugin_route` to decide whether KH is controller, assistant, or not needed.
3. Use `runtime_applied_skills` only for the skills the command actually executed.
4. Use `selected_not_executed_skills` as a to-do list, not as proof of execution.
5. If another skill is needed next, open only that skill's `SKILL.md` and produce concrete evidence.

## Evidence to produce

Minimum evidence for every request:

- `front_door_status: ok`
- `execution_authorization.must_stop_before_execution` and the allowed/forbidden next actions
- `kh_active_directive` status when carryover from a previous turn is in force
- classification with complexity, domain, confidence, and recommended execution
- plugin route
- `runtime_applied_skills`
- `selected_not_executed_skills`
- skill source path and stale-cache warnings, if any
- implementation_targets traceability for the front-door runtime path
- execution_level and host metadata when the result is used by a session audit
- wrapper path used when the command runs outside the KH repository root
- host-selection compliance status backed by a runtime receipt or session audit

## Failure handling

If front-door command cannot run:

- record `blocked`
- include the exact missing command, import error, stale path, or permission failure
- do not silently continue because the request appears light/direct; the missing runtime remains a bootstrap failure

If a different skill starts first:

- treat the session as a front-door miss
- run `session_skill_audit` after the task
- convert the miss into a regression scenario

## Quality bar

This skill succeeds only when it changes execution order. Reading this file, listing installed plugins, mentioning KH, or saying "I will use always-on-front-door" does not count. For every new user request or task, the next skill/runtime action must be the front-door command or a blocked runtime result. Running MEMORY.md lookup or memory quick pass in the same first parallel batch as this SKILL.md read is a failure because front-door was not first and alone. Reading any other KH skill before front-door is a failure. Reading sibling run folders for a new target is a context leak, not useful project discovery.

The skill should be reviewed against `tests.test_kh_front_door_always_on` in a full source checkout. In a slim runtime branch where `tests/` is intentionally not packaged, that target is a packaged test reference and still documents the expected regression test.
