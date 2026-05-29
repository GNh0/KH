---
name: brainstorming-harness
description: Use when a user is starting a feature, product, project, SaaS, or design idea and the direction is not approved yet.
---

# Brainstorming Harness

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

1. Inspect current project context first when a repository exists.
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
