---
name: always-on-front-door
description: Use when starting any conversation or receiving any new user request or task in Codex, an Antigravity-style host, Claude Code, or a local agent; perform KH semantic intake before any response, including clarifying questions, without requiring the user to name KH, UAF, a skill, or a harness.
---

# Always On Front Door

## Immediate Action

At the start of every conversation and for every new user request or task, invoke this skill and perform the semantic gate below before responding. This includes clarifying questions and requests that do not mention KH, UAF, a skill, a harness, a plugin, or routing. Do not read another skill, inspect a target, search memory, or call a tool before this gate.

### Host-Native Semantic Fast Path

The host may answer without launching Python or crossing any tool boundary only when it can determine with high confidence from the request text and already-visible conversation context that every condition below is true:

- The turn is direct or meta and can be answered entirely from the host model's current context.
- It needs no specialist capability and is not stateful.
- It needs no source, file, memory, browser, connector, command, current-data lookup, or other read-only tool access.
- It requests no mutation, persistence, credential handling, high-risk judgment, artifact or deliverable, verification, or governed workflow.

For this path, do not open another `SKILL.md`. Record the decision as `intake_mode=host_native_semantic_fast_path`, `route=direct`, and `governed_runtime_executed=false`. Record Token Optimizer as `considered_not_needed` for a short answer or `passthrough` when preserving the visible input is safer. `runtime_applied_skills` must be empty because no Python runtime ran. The semantic decision is KH always-on intake, but it is not a governed runtime receipt.

Fail closed. Any ambiguity, read-only source or tool need, specialist capability, mutation, persistence, credentials, high-risk domain or action, artifact or deliverable, verification, or governed work must invoke the Python front-door runtime as the next standalone tool call. A clarifying question caused by ambiguity also requires the runtime. If unsure whether the fast path applies, it does not apply.

For runtime-required turns, target bootstrap latency is under 10 seconds from this decision to starting the command. If the command path is missing or stale, resolve the latest installed `kh-uaf` cache path or repo skill folder once, then run the command. If it still cannot run, report blocked with the missing path.

### Windows UTF-8 Template

Use this exact shape for Korean, Japanese, Chinese, or any non-ASCII prompt:

```powershell
$promptPath = Join-Path $env:TEMP "kh-front-door-prompt.txt"
$contextPath = Join-Path $env:TEMP "kh-front-door-context.json"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$prompt = @'
<exact user request>
'@
$contextJson = @{
    request_intent = @{ user_resume_requested = $false }
    requires_resume = $false
} | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText($promptPath, $prompt, $utf8NoBom)
[System.IO.File]::WriteAllText($contextPath, $contextJson, $utf8NoBom)
python "<this skill folder>\scripts\front_door.py" --prompt-file $promptPath --context-file $contextPath --project "<cwd or target project>" --host codex --summary --strict-execution-gate
```

For short ASCII-only prompts, `--prompt "<user request>"` is accepted. If running from the KH repository root, `python -m src.orchestration.kh_front_door ...` is also valid. Keep `--strict-execution-gate` on normal host runs so a blocked execution gate returns a non-zero code instead of looking like successful task authorization.

Use `--micro-summary` as the normal machine bootstrap when a runtime-required turn is expected to stay small. It executes the governed runtime classification and gate. A returned direct route exits without opening another `SKILL.md`, while a returned `next` list is executed in order. Use `--summary` when human-readable audit keys such as `front_door_status`, `execution_gate`, `execution_authorization`, `immediate_next_skills`, `required_next_action_codes`, and `token_optimizer` are required.

Only after the command returns should selected follow-up skills be read or applied. The host-native fast path never reads follow-up skills.

This universal trigger is declared by the skill itself and does not depend on plugin manifest prompts or explicit KH naming. Skill metadata can improve host discovery but cannot guarantee host auto-selection or plugin injection. Audit governed execution from actual runtime receipts or session logs. Metadata, manifest text, or a `SKILL.md` read alone is never evidence that the governed runtime executed.

### Audit compliance

Audit compliance requires correlated host, runtime, or tool provenance. Assistant-authored prose or JSON is an unverified claim and cannot prove front-door execution, skill application, or execution authorization.

A bounded confirmation or status message may reuse current evidence only while the same task is unfinished and its scope is unchanged. Rerun front-door after task completion, for a new task, or when a message adds new work.

## KH Entry Contract

- Perform semantic intake for every new user task. Use the host-native fast path only when every eligibility condition is satisfied; otherwise verify that the governed runtime ran.
- If an earlier message in the same conversation or project asked to actively/default-use KH/UAF skills or harnesses, keep `kh_active_directive=active` for later turns until explicit opt-out. The directive is additional context, not a prerequisite for bootstrap.
- A host-native direct decision may record semantic intake, but it must set `governed_runtime_executed=false` and cannot claim any runtime-applied skill.
- Count governed runtime application only when the front-door command ran or a concrete blocked result was recorded because the runtime was unavailable.
- A `SKILL.md` read, plugin listing, marketplace metadata, or `selected_not_executed_skills` entry is not governed execution evidence.
- `immediate_next_skills` must produce same-turn applied/skipped/blocked evidence before source exploration, implementation, verification, or final claims; session audit treats SKILL.md-only handling as `immediate_next_skill_not_applied`.

## Workflow

1. Evaluate the host-native eligibility list from the request and already-visible context without tools.
2. If every condition passes, answer directly, record the host-native decision and Token Optimizer disposition, and stop without Python or more skill reads.
3. Otherwise run the front-door runtime. The runtime decides direct/light, specialist-routed, ambiguous, or work-bearing handling for all escalated turns.
4. Treat `runtime_applied_skills` as executed and `selected_not_executed_skills` as selected follow-up only.
5. Execute `immediate_next_skills` first, in order. Do not treat the full `recommended_skills` or `selected_not_executed_skills` list as the next execution plan.
6. If `execution_gate.can_execute=false`, stop before global memory lookup, source reads, file writes, scaffolding, deliverable generation, browser QA, verification, or subagent dispatch. First apply, skip with rationale, or block `immediate_next_skills`.
7. If the gate is `blocked_until_large_work_preflight`, do only the allowed setup evidence: GoalState, orchestration bundle, workspace/domain boundary, token decision, host/subagent strategy, parallel strategy, role-audit decision, command-output plan, deliverable/render quality plan, guard/rollback policy, and verification plan.
8. After runtime intake, route specialist providers by capability. KH intake must not hide host-local skills such as `sql-formatting` when they match the request.
9. Before any Git executable, inspect the exact target ancestry through `src.orchestration.git_workspace_gate`. If no valid Git metadata exists, skip Git and GitHub branch-finishing actions for the task and do not retry Git merely to reconfirm absence.

## Required outputs

- Host-native direct: `intake_mode`, `route`, `governed_runtime_executed=false`, empty `runtime_applied_skills`, and Token Optimizer disposition.
- Runtime-required: `front_door_status`, request classification, plugin route, `execution_gate`, and `execution_authorization`.
- `runtime_applied_skills`, `selected_not_executed_skills`, `immediate_next_skills`, and `skill_status_summary`.
- `kh_active_directive` when persistent KH use was requested.
- Blocked rationale when a required runtime command cannot run. A host-side direct rationale is valid only when every fast-path eligibility condition is affirmatively satisfied.

## User-Facing Reporting

- Keep raw KH routing evidence in tool output, runtime metadata, handoff files, or audit reports.
- Do not append raw KH status lines to ordinary final answers unless the user asks how KH was used.
- If a progress update is needed, keep it short and then return to the user's task.

## Common mistakes

- Do not read MEMORY.md, source files, target folders, parent/sibling folders, other SKILL.md files, or support references before the front-door command.
- Do not use the fast path merely because a request is short. SQL work, current lookup, tool use, and ambiguous translation or rewrite context require runtime intake.
- Do not parallelize the front-door command with pre-intake reads.
- Do not use `--prompt "<non-ASCII text>"` on Windows; use `--prompt-file`.
- Do not ignore stale cache path failures; resolve the latest cache or repo skills path before claiming KH use.
- Do not run broad uncapped searches after intake. Narrow `rg`/file reads and use command-output filtering before hundreds of raw lines enter context.
- Do not treat a user saying "develop/make/create" as implementation approval when front-door selected brainstorming.
- Do not treat selected follow-up skills as exclusive; specialist plugins may still be routed after intake.
- Do not skip `immediate_next_skills` and jump directly to source exploration, implementation, verification, or final claims.
- Do not treat this or a support-file read as governed runtime application, even when the file contains runtime marker names.
- Do not treat exit code 3 from `--strict-execution-gate` as a front-door crash. It means KH intake succeeded and the next action is limited to the reported gate/setup evidence.
- Do not launch `git.exe` to discover whether the target is a repository. Use the filesystem-only Git workspace gate first and reuse that decision for the task.

## UAF implementation targets

- `src.orchestration.kh_front_door.build_kh_front_door`
- `src.orchestration.request_classifier.classify_request`
- `src.orchestration.plugin_composition.compose_plugin_route`
- `src.skills.uaf_skill_catalog.collect_packaged_skills`
- `skills/always_on_front_door/SKILL.md`
- `skills/automatic_intake_harness/SKILL.md`
- `src.orchestration.session_skill_audit.analyze_session_skills`
- `tests.test_kh_front_door_always_on`
- `tests.test_session_skill_audit`

## Support files

- Use `scripts/front_door.py` as the skill-local front-door wrapper when the host starts outside the KH repository root.
- Read `references/usage.md` only before changing host trigger wording.
- Use `examples/minimal-workflow.md` for blind-request acceptance scenarios.
- Run `python scripts/smoke_check.py` from this skill folder for support-file and target checks.
- Run `python scripts/demo.py --output-dir <tmp>` to verify the front-door demo path.
