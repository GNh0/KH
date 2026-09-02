---
name: always-on-front-door
description: Use when the user explicitly requests KH routing evidence or audit, provider selection remains unresolved, or a governed high-risk or large workflow requires reproducible routing. Do not invoke for ordinary clear work.
---

# Front Door Audit

This is explicit routing-audit and governed-runtime documentation. It is not a bootstrap specialist, a prerequisite, or a file that ordinary requests should load. The plugin-level contract is sufficient for direct and single-domain-skill routing.

## Workflow

1. Confirm that an explicit audit, unresolved provider conflict, or governed high-risk/large-work trigger exists. If not, stop without reading support files or producing routing output.
2. Read only the visible request and current conversation context needed for the audit. Do not search global memory, project files, or tools merely to classify it.
3. Distinguish the expected direct, single-domain-skill, or governed path. Ordinary clear work should be direct or load only its matching domain skill; this skill itself is not part of that path.
4. Run the governed front-door runtime described in `references/usage.md` only when reproducible routing or authorization evidence is required.
5. Keep routing receipts internal unless the user requested them or a blocked safety decision must be explained.

## Selection Rules

- Prefer semantic judgment over keyword matching. Examples in a request are evidence, not universal routing rules.
- Do not select this skill because KH is installed, because a new turn started, or because another skill might apply.
- Do not let KH hide a better matching host or plugin skill such as SQL formatting, browser QA, documents, spreadsheets, or image generation.
- Ordinary DB, SQL, C#, file, and tool work must not load this skill as a preflight step.
- Treat a selected skill as used only when its instructions affected the work or its executable target ran. A name in a list is not execution evidence.
- Respond in the user's current language unless the user requests another language.

## KH Entry Contract

- Routing evidence is required only in explicit audit or governed mode.
- Selection evidence is a governed runtime receipt or an observed domain-skill read being audited; direct answers need neither.
- Execution evidence is the behavior, tool output, artifact, or verification produced after selection. Reading a skill alone is not execution.

## Safety And State

- Keep destructive actions, credential access, live database writes, external publishing, and other high-impact mutations behind their specific authorization and safety gates.
- Before any Git executable, use `src.orchestration.git_workspace_gate` on the exact target. Do not launch `git.exe` until the filesystem-only gate confirms Git metadata. If Git metadata is absent, skip Git and GitHub actions without retrying Git.
- Select Token Optimizer only when a large reducible command, log, test, or subagent payload exists, or when the user explicitly requests optimization or telemetry. Do not read it merely to record a no-op decision.
- Select Credential Safety only when actual credential material, secret configuration, or a credential-bearing command is involved. An already-configured MCP or database call is not a trigger.
- Use scoped memory, GoalState, orchestration, review, and Compound only when their triggers are actually present.

## Runtime Audit Mode

The Python front door is an optional deterministic audit and orchestration entrypoint, not a prerequisite for ordinary work. Use it only when the user requests routing evidence, provider selection remains ambiguous after semantic inspection, or a governed high-risk/large-work packet is required. Read `references/usage.md` before running it.

Keep raw routing JSON in tool output or audit artifacts. Do not append it to ordinary user-facing answers unless requested.

## Required outputs

- For explicit audit, report the smallest matching path and preserve the user's requested language and scope.
- For governed runtime mode, retain the route, authorization state, selected-versus-applied status, and source path as internal evidence.
- Do not narrate routing, token, credential, memory, Goal, or orchestration decisions during ordinary work.

## Common mistakes

- Loading this skill for a clear SQL, DB, C#, file, or tool request.
- Running Python, scanning the catalog, searching global memory, or reading every skill for a clear request.
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
