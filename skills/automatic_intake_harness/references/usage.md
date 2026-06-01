# Automatic Intake Harness Usage Reference

Use this reference when a host, plugin manifest, or root guide must decide whether KH should run before ordinary work. The core rule is simple: non-trivial work should get intake even when the user does not know KH vocabulary.

## When to use

Apply this skill before acting on requests that involve:

- reading or editing project files
- creating code, documents, spreadsheets, diagrams, or other deliverables
- summarizing long command output, build logs, test logs, or stack traces
- reviewing code, specs, QA evidence, or release readiness
- running tests, verification, subagents, role workers, or branch finishing
- preserving goal state, memory, snapshots, handoffs, or progress state
- destructive, security, legal, financial, medical, privacy, or other high-risk decisions

Do not apply heavy workflow machinery for simple direct questions, short explanations, translations, or tiny one-off text transforms. The intake step may still classify these as direct answers.

Execution level: `python-module`.

Implementation targets:

- `src.orchestration.kh_front_door.build_kh_front_door`
- `src.orchestration.request_classifier.classify_request`
- `src.orchestration.plugin_composition.compose_plugin_route`
- `src.skills.uaf_skill_catalog.collect_packaged_skills`
- `skills/automatic_intake_harness/SKILL.md`

## Inputs to collect

- Raw user request text.
- Target project path or current working directory.
- Host label such as `codex`, `antigravity`, `claude-code`, or `local`.
- Optional host-provided skill paths, especially installed plugin cache paths.
- Optional provider snapshot when other plugins or connectors may assist.

## Execution pattern

Run:

```bash
python -m src.orchestration.kh_front_door --prompt "<user request>" --project "<target project>" --host codex --summary
```

Then use the JSON result:

- `classification` decides whether the request is light, medium, heavy, high risk, or ambiguous.
- `plugin_route` decides direct, single-provider, hybrid, or clarify.
- `recommended_skills` is the selected bundle.
- `runtime_applied_skills` is the list of components actually executed by intake.
- `selected_not_executed_skills` is the follow-up list that still requires real evidence before it can be reported as applied.

## Evidence to produce

A valid use records:

- the exact front-door command or function path used
- skill source resolution from repo-local `skills/` or installed cache
- selected skills and status summary
- stale cache path checks when host paths were supplied
- follow-up commands, gates, artifacts, or explicit skipped rationale for selected skills

## Failure handling

- If no packaged skill source exists, block KH usage and report the missing path.
- If a host path points to a stale cache version, block stale-path usage and resolve the current source before proceeding.
- If intake classified a command-output task as heavy role work, treat that as a routing bug and prefer command-output/token optimization evidence.
- If the agent already started work without intake, record a postmortem issue instead of pretending intake happened.

## Quality bar

Another agent should be able to audit a finished session and answer:

- Did the user need to know internal KH names? The answer should be no for non-trivial work.
- What actually ran before source exploration?
- Which skills were only selected, and which produced runtime evidence?
- Were logs, tests, documents, and high-risk actions routed to the appropriate follow-up checks?

The actual_runtime_path is `src.orchestration.kh_front_door.build_kh_front_door` or the CLI wrapper `python -m src.orchestration.kh_front_door`.
