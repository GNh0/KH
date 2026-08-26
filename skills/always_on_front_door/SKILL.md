---
name: always-on-front-door
description: Use when starting any new user request to select the smallest matching skill or direct path from visible context. Do not run Python merely to classify a clear request.
---

# Always On Front Door

## Workflow

1. Read the request and already-visible conversation context. Do not inspect files, memory, or tools merely to decide what the request means.
2. Scan the available skill descriptions. If one clearly matches, read only that skill and follow it. When both process and domain skills apply, use the process skill first.
3. If the request is self-contained and no specialist skill or tool is needed, answer directly without loading another skill or launching a routing script.
4. If several providers genuinely conflict, the target is unclear, or the work is high-risk or large enough to require reproducible routing evidence, use the governed front-door runtime described in `references/usage.md`.
5. Apply only the workflow depth the task needs. A small edit does not need GoalState, a role DAG, or a full audit; substantial implementation may need them.

## Selection Rules

- Prefer semantic judgment over keyword matching. Examples in a request are evidence, not universal routing rules.
- Do not require the user to name KH, UAF, a skill, or a harness.
- Do not let KH hide a better matching host or plugin skill such as SQL formatting, browser QA, documents, spreadsheets, or image generation.
- Do not read every skill. Skill descriptions are the index; `SKILL.md` is progressive disclosure after selection.
- Treat a selected skill as used only when its instructions affected the work or its executable target ran. A name in a list is not execution evidence.
- Respond in the user's current language unless the user requests another language.

## KH Entry Contract

- Routing evidence is the chosen direct, specialist, or governed path.
- Selection evidence is an observed specialist `SKILL.md` read or a governed runtime receipt; direct answers need neither.
- Execution evidence is the behavior, tool output, artifact, or verification produced after selection. Reading a skill alone is not execution.

## Safety And State

- Keep destructive actions, credential access, live database writes, external publishing, and other high-impact mutations behind their specific authorization and safety gates.
- Before any Git executable, use `src.orchestration.git_workspace_gate` on the exact target. Do not launch `git.exe` until the filesystem-only gate confirms Git metadata. If Git metadata is absent, skip Git and GitHub actions without retrying Git.
- Consider Token Optimizer on every KH-routed turn, but execute it only when reducible command, log, or subagent output exists. Preserve SQL, source, rules, and other contract-sensitive text.
- Use scoped memory, GoalState, orchestration, review, and Compound only when their triggers are actually present.

## Runtime Audit Mode

The Python front door is an optional deterministic audit and orchestration entrypoint, not a prerequisite for ordinary work. Use it when the user requests routing evidence, when provider selection remains ambiguous after semantic inspection, or when a governed high-risk/large-work packet is required. Read `references/usage.md` before running it.

Keep raw routing JSON in tool output or audit artifacts. Do not append it to ordinary user-facing answers unless requested.

## Required outputs

- Use the smallest matching path and preserve the user's requested language and scope.
- For governed runtime mode, retain the route, authorization state, selected-versus-applied status, and source path as internal evidence.

## Common mistakes

- Running Python, scanning the catalog, or reading every skill for a clear request.
- Treating a selected skill name as proof that its workflow executed.
- Forcing KH when another visible host or plugin skill is a better match.

## Support files

- `references/usage.md`: governed runtime and Windows UTF-8 invocation details.
- `examples/minimal-workflow.md`: direct, specialist, and governed examples.
- `scripts/front_door.py`: optional deterministic routing and audit wrapper.
- `scripts/demo.py`: runnable direct, specialist, and governed routing examples.
- `scripts/smoke_check.py`: package and target validation.

## UAF implementation targets

- `src.orchestration.kh_front_door.build_kh_front_door`
- `src.orchestration.request_classifier.classify_request`
- `src.orchestration.session_skill_audit.analyze_session_skills`
- `src.orchestration.git_workspace_gate`
- `tests.test_kh_front_door_always_on`
