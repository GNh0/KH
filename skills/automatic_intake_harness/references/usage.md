# Automatic Intake Harness Usage Reference

Use this reference when a host, plugin manifest, or root guide must request KH intake before a new user request. The host cannot guarantee plugin auto-selection. Governed execution requires a runtime receipt or session audit; a strict host-native direct decision is semantic intake but not a runtime receipt. The user never needs to know KH vocabulary.

## When to use

Apply this skill before acting on requests that involve:

- reading or editing project files
- creating code, documents, spreadsheets, diagrams, or other deliverables
- summarizing long command output, build logs, test logs, or stack traces
- reviewing code, specs, QA evidence, or release readiness
- running tests, verification, subagents, role workers, or branch finishing
- preserving goal state, memory, snapshots, handoffs, or progress state
- destructive, security, legal, financial, medical, privacy, or other high-risk decisions

Do not apply heavy workflow machinery for simple direct/meta questions, short explanations, unambiguous translations, or tiny one-off text transforms. When these are non-specialist, non-stateful, and need no source/tool read, mutation, persistence, credentials, risk handling, artifact, verification, or governed workflow, the host may decide the direct exit without Python. Fail closed to runtime on any ambiguity or failed condition.

Persistent directive: if the user previously asked the assistant to actively, always, by default, or continuously use KH/UAF skills or harnesses in this conversation or project, carry `kh_active_directive=active` into later work-bearing turns. The later request does not need to repeat KH, UAF, skill, or harness names.

Execution level: `host-native-semantic` for an eligible direct exit; `python-module` otherwise.

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
- `kh_active_directive` status and source message when a previous user instruction made KH active by default.
- Optional host-provided skill paths, especially installed plugin cache paths.
- Optional provider snapshot when other plugins or connectors may assist.

## Execution pattern

For an eligible host-native direct exit, do not run a command or read another skill. Record:

- `intake_mode=host_native_semantic_fast_path`
- `route=direct`
- `governed_runtime_executed=false`
- `runtime_applied_skills=[]`
- Token Optimizer `considered_not_needed` or `passthrough`

For every other request, run:

```bash
python "<always_on_front_door skill folder>/scripts/front_door.py" --prompt "<user request>" --project "<target project>" --host codex --summary
```

Then use the JSON result:

- `classification` decides whether the request is light, medium, heavy, high risk, or ambiguous.
- `plugin_route` decides direct, single-provider, hybrid, or clarify.
- `recommended_skills` is the selected bundle.
- `runtime_applied_skills` is the list of components actually executed by intake.
- `selected_not_executed_skills` is the follow-up list that still requires real evidence before it can be reported as applied.

## Evidence to produce

A valid host-native direct use records the eligibility rationale and explicitly states that no governed runtime or runtime-applied skill was claimed. A valid governed use records:

- the exact front-door command or function path used
- `kh_active_directive` status when a previous user instruction is being carried into the current turn
- skill source resolution from repo-local `skills/` or installed cache
- selected skills and status summary
- stale cache path checks when host paths were supplied
- follow-up commands, gates, artifacts, or explicit skipped rationale for selected skills

## Failure handling

- If no packaged skill source exists, block KH usage and report the missing path.
- If a host path points to a stale cache version, block stale-path usage and resolve the current source before proceeding.
- If the host-native gate sees a command-output task, source/tool need, specialist need, mutation, persistence, credentials, high risk, artifact, verification, or ambiguity, invoke runtime rather than reasoning past the boundary.
- If intake classified a command-output task as heavy role work, treat that as a routing bug and prefer command-output/token optimization evidence.
- If the agent already started work without intake, record a postmortem issue instead of pretending intake happened.

## Quality bar

Another agent should be able to audit a finished session and answer:

- Did the user need to know internal KH names? The answer should be no for every routed request.
- Was this a host-native semantic decision or governed runtime execution?
- What actually ran before source exploration?
- Which skills were only selected, and which produced runtime evidence?
- Were logs, tests, documents, and high-risk actions routed to the appropriate follow-up checks?

The actual_runtime_path is `src.orchestration.kh_front_door.build_kh_front_door`, the repo-root CLI `python -m src.orchestration.kh_front_door`, or the skill-local wrapper `always_on_front_door/scripts/front_door.py`.

## Runtime binding

- Execution level: python-module
- Implementation targets:
  - `src.orchestration.kh_front_door.build_kh_front_door`
  - `src.orchestration.request_classifier.classify_request`
  - `src.orchestration.plugin_composition.compose_plugin_route`
  - `src.skills.uaf_skill_catalog.collect_packaged_skills`
- Application path: host-native only for the strict no-tool direct contract; otherwise run the front-door Python module before project reads, memory lookup, subagent dispatch, or target-folder inspection.
- Completion rule: never infer governed execution from reading this file. Report runtime application only when the front-door result records classification, plugin route, skill source, token decision, and applied/skipped/blocked evidence.
