---
name: brainstorming-harness
description: Use when kh-uaf:always-on-front-door has already run and selected this skill; use it when a user is starting a feature, product, project, SaaS, or design idea and the direction is not approved yet.
---

# Brainstorming Harness

## KH Entry Contract

- Start every non-trivial turn through `always-on-front-door` unless this skill is that bootstrap step or the current turn was classified as light/direct.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, or a required follow-up gate selects it.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

This harness adapts the Superpowers brainstorming pattern into KH UAF. It is the lightweight front door before `architect-pipeline`, `domain-orchestration-harness`, or `development-lifecycle-harness`: clarify the user's intent, explore alternatives, capture decisions, and hand off only after the design direction is approved.

Source label: Superpowers brainstorming adapted for KH UAF.

## Support files

- Read `references/usage.md` before applying this skill to real project discovery; it expands trigger boundaries, evidence, and handoff rules.
- Use `examples/minimal-workflow.md` as a compact acceptance scenario for KH-style brainstorming.
- Run `python scripts/smoke_check.py` from this skill folder to verify support files and implementation targets.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo.

## When To Use

Use this harness when:

- The user wants to start a new product, SaaS, app, workflow, analysis, design, or major feature.
- The request is creative or underspecified enough that immediate implementation would hide assumptions.
- The user needs options, tradeoffs, naming, MVP scope, target users, workflow shape, or architecture direction before planning.
- A visual companion or mockup may help choose among directions, but the final decision still needs text evidence.

Do not use it for quick factual questions, small edits with clear acceptance criteria, or already-approved implementation plans.

## Core Flow

1. After front-door routing, inspect only the explicit target project/folder when it exists. If the target folder does not exist yet, create or plan inside that exact target; do not list the parent directory or read sibling folders from earlier tests/runs.
   - Fresh/empty target fast path: if the exact target folder exists and has no files, do not read `MEMORY.md`, memory summaries, parent folders, sibling folders, previous test outputs, or older project artifacts unless the user explicitly asks for reuse, comparison, migration, or prior context.
   - For this fast path, return a compact direction proposal with 2-3 options, one recommendation, and an approval question. Do not escalate to GoalState, role DAG, document exports, QA, or review gates before approval.
2. If the next choices are visual, offer a visual companion in its own message.
3. Ask one question at a time. Prefer 2-3 clear choices with a recommendation.
4. Capture decisions as structured records: `objective`, `target_user`, `problem`, `options`, `recommendation`, `constraints`, `decisions`, and `open_questions`.
5. Present 2-3 approaches with tradeoffs and a recommended direction.
6. Present the chosen design direction and ask for approval before implementation or scaffolding.
7. Build a `BrainstormSession`, validate it, and create a `brainstorm_handoff`.
8. Write KH project artifacts when useful: `.kh/brainstorm/<run-id>/content/*.md` for local working notes, `.kh/brainstorm/<run-id>/state/*.json` for run-local state, and `docs/kh/handoffs/*.md` for shareable summaries.
9. Pass the handoff to the next KH skill:
   - `architect-pipeline` for product/system design.
   - `domain-orchestration-harness` for cross-domain role/gate design.
   - `goal-state-harness` when completion criteria and evidence are central.
   - `development-lifecycle-harness` only after the design direction is approved.

## Minimum Discovery Checkpoints

Do not collapse brainstorming into a single option picker unless the user has already supplied enough detail for every checkpoint below. For early product, project, app, SaaS, workflow, analysis, research, policy, process, design, document, manufacturing/specification, investment, operations, or other domain work, progress through these checkpoints and preserve evidence:

1. `intent_frame`: objective, target user/operator/audience, and success criteria.
2. `problem_frame`: current pain, workflow boundary, constraints, and non-goals.
3. `option_frame`: 2-3 approaches with tradeoffs and one recommendation.
4. `approval_frame`: explicit user approval, rejection, or blocked/waiting state.
5. `handoff_frame`: `BrainstormSession`, `validate_brainstorm_session`, `decision_log`, `brainstorm_handoff`, and next KH skill.

If the user only says "handle this topic/project/work" and then chooses one proposed option, that approval is permission to continue the KH flow, not permission to skip the handoff. Build and validate the handoff before architecture, domain orchestration, analysis, deliverable generation, or implementation. If time, host tools, or missing context prevents this, record `brainstorming_status=blocked` with the missing checkpoint instead of claiming the skill ran.

## User-Facing Reporting

- The final answer should read like a normal brainstorming or direction-setting response in the user's language.
- Do not expose internal validation text such as `KH brainstorming validation`, `valid=true`, `missing=[]`, `BrainstormSession`, or raw handoff keys unless the user asks for a skill/harness audit.
- If the direction is not approved yet, end with the approval decision or next question, not with internal framework status.
- Keep `BrainstormSession` validation, handoff payloads, and artifact paths as internal evidence or audit material.
- For fresh/empty target fast path, avoid mentioning KH, UAF, skill names, validation status, or internal routing unless the user explicitly asks how the tool was used.

## Evidence Contract

A valid brainstorming run leaves:

- `brainstorm_handoff`
- `decision_log`
- `recommended_option`
- `constraints` when constraints are known
- `open_questions` when unresolved questions remain
- next skill selection, usually `architect-pipeline`
- project artifact paths when written under `.kh/brainstorm/.../content/`, `.kh/brainstorm/.../state/`, and `docs/kh/handoffs/`

The agent must not claim KH-backed brainstorming if it only had an informal conversation and did not preserve a handoff or decision evidence.

## External Benchmark Recipe

Use this harness as the KH equivalent of Superpowers brainstorming:

1. Start with user intent and context, not code.
2. Keep question count low and ask one at a time.
3. Present alternatives and your recommendation before locking scope.
4. Stop before implementation until the user approves the direction.
5. Convert approval into a `BrainstormSession` and `build_architect_handoff`.
6. Hand off to KH architecture or domain orchestration rather than Superpowers `writing-plans`.

Pressure scenario: a user says "I want to build a SaaS." The agent should not scaffold immediately. It should clarify target customer, MVP center, product/repo naming, constraints, and preferred stack, then produce a handoff for `architect-pipeline`.

## UAF implementation targets

- `src.orchestration.brainstorming.BrainstormOption`
- `src.orchestration.brainstorming.BrainstormDecision`
- `src.orchestration.brainstorming.BrainstormSession`
- `src.orchestration.brainstorming.validate_brainstorm_session`
- `src.orchestration.brainstorming.build_architect_handoff`
- `src.orchestration.brainstorming.write_brainstorm_markdown_artifacts`
- `src.orchestration.project_markdown.KHProjectMarkdownStore`
- `tests.test_brainstorming_harness`
- `tests.test_project_markdown_artifacts`
- `skills/brainstorming_harness/SKILL.md`

## Boundaries

- Do not copy Superpowers paths such as `.superpowers/brainstorm` or force `docs/superpowers/specs`.
- Do not transition to Superpowers `writing-plans` from KH. KH handoff targets are UAF skills.
- Do not ask a batch of broad questions at once. One question at a time keeps the user in control.
- Do not use this harness to delay obvious small tasks.
- Do not store private or sensitive business assumptions outside the selected project/conversation scope.
- Do not read previous scenario folders, sibling workspaces, or older brainstorm outputs to seed a new brainstorming target unless the user explicitly asks for reuse, comparison, or migration.

## Required outputs

- A short statement of the selected objective and target user.
- Options considered with tradeoffs and a recommended option.
- Decision log and constraints.
- Open questions, if any.
- `BrainstormSession` validation result.
- Handoff payload for the next KH skill.
- Markdown handoff and state paths when visible project artifacts are created.

## Common mistakes

- Treating brainstorming as implementation permission.
- Creating visual files without linking them to a decision.
- Asking five questions at once.
- Presenting only one approach before recommending it.
- Losing product names, repo decisions, or MVP scope during context compression.
- Letting sibling test outputs or earlier run folders influence a new brainstorm without explicit user permission.
