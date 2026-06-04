# Brainstorming Harness Usage Reference

This reference expands the portable operating contract for `brainstorming-harness`. Read it when KH UAF needs to turn an early idea into a structured design handoff before architecture, domain orchestration, or implementation.

This harness intentionally adapts proven external patterns rather than inventing a shorter flow:

- Superpowers: brainstorm before code, ask one question at a time, propose 2-3 approaches, present design sections, write and review a spec, then hand off to planning.
- Compound Engineering: brainstorm requirements, plan, work, review, compound learnings, and use strategy/context anchors where available.
- RTK-style output discipline: compress only noisy command output where essential facts are preserved; keep passthrough or raw/failure recovery when compression would damage quality.

## When to use

Use when a user is starting a feature, product, project, analysis, research, policy, process, document, manufacturing/specification, operation, investment, or design idea and the agent must clarify intent, compare approaches, and produce an approved handoff before execution.

Context summary: this is the KH UAF version of Superpowers brainstorming. It keeps the useful interaction pattern but changes the storage, handoff, and next-step contracts to KH. The output is not a Superpowers spec. It is a KH `BrainstormSession` plus handoff evidence for the next UAF skill.

Do not use this skill only because it is available. Use it when the current task needs discovery before design or implementation, and state whether the skill was actually executed, applied procedurally, or only considered.

## Inputs to collect

- User objective and what success should look like.
- Target user, buyer, operator, or audience.
- Problem being solved and current pain.
- 2-3 possible approaches with tradeoffs.
- Domain/workflow options before technology choices. For operations, manufacturing, investment, drawing/design, analysis, or business process work, options should describe operating models, process boundaries, data records, controls, and tradeoffs first.
- Recommended approach and why.
- Constraints such as budget, stack, timeline, privacy, repo, deployment, or compliance.
- Decisions already approved by the user.
- Open questions that should remain visible for the architect or domain workflow.
- Project artifact destination when visible KH notes are wanted: `.kh/brainstorm/<run-id>/content/*.md`, `.kh/brainstorm/<run-id>/state/*.json`, and `docs/kh/handoffs/*.md`.
- Execution level: `hybrid-harness`.
- Implementation targets:
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

## Execution pattern

1. Read `SKILL.md` first and confirm the trigger applies.
2. Inspect only the explicit target project/folder if it exists. If the target folder is new, do not scan its parent or read sibling folders from earlier tests/runs.
   - If the exact target folder exists and is empty, do not read `MEMORY.md`, memory summaries, parent directories, sibling folders, previous test outputs, or older brainstorm folders unless the user explicitly asks for reuse, comparison, migration, or prior context.
   - For this empty-target fast path, do not export files, create GoalState, run role DAG, or start QA/review gates before approval.
3. Ask one question at a time. Prefer multiple-choice options when that reduces friction.
4. Offer visual companion only when seeing a layout, diagram, or comparison is better than reading text.
5. Present 2-3 approaches with tradeoffs and a recommendation.
   - For domain workflows, the approaches must be domain choices first. Example for inventory inbound/outbound: simple ledger, location-controlled stock, lot/serial/expiry-controlled stock, or approval/ERP-linked stock flow.
   - Include the minimum required records, such as item, location, quantity, transaction type, owner, timestamp, reason, memo, safety stock, and optional lot, serial, expiry, supplier/customer, or work order.
   - Keep technology stack choices secondary unless the user already supplied the workflow model and asked for implementation technology.
6. Confirm the direction before creating architecture, scaffolding, or code. For vague product, app, service, SaaS, or project requests, do not implement or scaffold in the same turn.
7. Treat "1번으로 진행", "go with option 1", or a similar option choice as direction approval only. It does not authorize implementation or file creation.
8. Continue the design/spec loop after option selection: confirm success criteria, scope, data shape, screens/artifacts, non-goals, risks, and acceptance criteria one question or section at a time.
9. Build a `BrainstormSession` and run `validate_brainstorm_session`.
10. If valid, call `build_architect_handoff` and pass the payload to the selected KH planning skill, not implementation.
11. When the user benefits from visible project notes, call `write_brainstorm_markdown_artifacts` so KH creates `.kh/brainstorm/.../content/*.md`, `.kh/brainstorm/.../state/`, and `docs/kh/handoffs/*.md`.
12. Self-review the written handoff/spec for placeholders, contradictions, ambiguity, and scope.
13. Ask the user to review or approve the written handoff/spec before planning or implementation.
14. Preserve intermediate decisions in structured evidence rather than relying on chat memory alone.
15. Run `python scripts/smoke_check.py` when validating this packaged skill in the repository.

## Checkpoint contract

Superpowers-style brainstorming is a sequence of small checkpoints, not a single yes/no question. KH uses the same interaction discipline but stores KH-native evidence for any domain, not only software development. A valid run should preserve:

- `intent_frame`: objective, target user/operator/audience, success criteria.
- `problem_frame`: pain, current workflow, constraints, non-goals.
- `option_frame`: 2-3 options, tradeoffs, recommended option.
- `approval_frame`: explicit user decision, rejection, or waiting/blocked state.
- `handoff_frame`: `BrainstormSession`, `validate_brainstorm_session`, `decision_log`, `brainstorm_handoff`, and next KH skill.

If a broad domain request receives only one direction question and then jumps into file creation, analysis, deliverable generation, or implementation, mark it as `brainstorming_status=blocked` or `missing_brainstorm_handoff`. If the user supplied all checkpoint content upfront, the agent may keep the conversation short, but it still must create and validate the structured handoff before execution.

For "simple" product or workflow requests, do not skip brainstorming. Use a compact domain-first form: objective/operator, workflow boundary, 2-3 operating models, required records, recommendation, and one approval question.

The first visible response must not be only an option picker. For a vague or new app, dashboard, product, operations, manufacturing, document, drawing/design, analysis, investment, or workflow request, include these user-visible sections, translated to the user's apparent language when helpful: objective/operator, workflow boundary, success criteria/constraints/non-goals, operating model options and tradeoffs, required records/data/artifact shape, open questions, recommendation, and approval question. If the exact target folder is missing or empty, state that briefly, but still provide the full domain-first brainstorm and stop before implementation.

Keep recommendation language advisory. The agent should not decide the user's operating model or stack on its own. Avoid final-decision phrases such as "2번으로 가겠습니다", "기준으로 만들겠습니다", "I will go with option 2", or "we will use React" before approval. If implementation technology is not the user's decision target, keep it secondary and do not include it in the approval question.

Keep the approval question about direction only. Do not combine the first decision question with immediate implementation wording such as "바로 구현해도 될까요", "승인해주시면 파일을 생성하겠습니다", "바로 개발하겠습니다", or "I can implement now." Do not mention target-path file generation in the first approval question. Ask which operating model the user wants, state the recommendation as advice, then wait for approval before implementation or stack selection.

The first brainstorm should end with a direction question, not an execution question. Do not say that approval will immediately create files, start development, run QA, or produce deliverables. A valid first question asks the user to choose the operating model or answer one missing domain constraint, then stops.

Approval continuation is a separate gate. When the user approves the recommendation in a later message, create or record `approval_frame`, `BrainstormSession`, `validate_brainstorm_session`, `decision_log`, and `brainstorm_handoff` before any write, QA, browser, verification, or broad memory call. Do not use global Codex memory, memory skill notes, sibling folders, or previous run folders as implementation shortcuts during this continuation unless the user explicitly requested reuse. If the handoff cannot be produced, stop with `brainstorming_status=blocked`.

Direction choice is not execution approval. If the user only chooses an option, keep the request inside `brainstorming-harness` and ask the next focused design question. Execution approval requires a reviewed handoff/spec plus a separate instruction to implement, create files, generate deliverables, or start work.

The compact form is still a multi-checkpoint discovery pass, not a one-question option picker. Before asking for approval, the visible response should cover:

- Objective and target operator/audience.
- Unknowns about current workflow, success criteria, constraints, and non-goals.
- 2-3 operating-model options with tradeoffs.
- Required records/data or artifact/output shape.
- Open questions that could change scope.
- One recommendation and one next approval or clarification question.

If these are not present, keep brainstorming or record `brainstorming_status=blocked`; do not proceed to code, analysis, deliverables, QA, or verification.

## Evidence to produce

- Skill name and execution level used for the run.
- User objective, target user, problem, constraints, and success criteria.
- Options considered and tradeoffs.
- Recommendation and approved decisions.
- Explicit user approval before implementation/scaffolding, or a clear blocked/waiting-for-approval state.
- `BrainstormSession` validation result.
- Handoff target, usually `architect-pipeline`.
- Markdown handoff paths if project-local KH notes were written.
- Checkpoint evidence for intent, problem, options, approval, and handoff.
- Verification command or review evidence when validating the packaged skill itself.

Keep this evidence available for audits, but do not print raw validation fields
in ordinary final answers. User-facing responses should show the options,
recommendation, tradeoffs, open questions, and approval request. Raw fields such
as `valid=true`, `missing=[]`, `BrainstormSession`, and `brainstorm_handoff`
belong in internal evidence unless the user asks for KH usage details.

## Failure handling

- If no target user or problem is known, keep asking clarifying questions instead of claiming a handoff is complete.
- If no option is recommended, block handoff and record `recommended_option` as missing.
- If a domain workflow only received technology-stack options, mark the brainstorm as shallow and redo the option frame around operating models and required records.
- If the user rejects the proposed direction, update decisions and rerun validation.
- If the task is too broad for one design, decompose it and brainstorm only the first project slice.
- If visual artifacts are created, record what decision they supported and avoid leaving orphan mockups.
- If a sibling or previous run folder was read accidentally, discard that run as contaminated, record the leak, and restart from the requested target boundary.
- If the agent created product code, analysis output, user deliverables, or domain artifacts before approval, mark the run as a brainstorming bypass and redo discovery from the target boundary.
- If the agent created product code, analysis output, user deliverables, or domain artifacts after approval but before `BrainstormSession` validation and `brainstorm_handoff`, mark the run as missing handoff evidence and route back to `brainstorming-harness` before architecture, domain orchestration, analysis, deliverable, or implementation claims.

## Quality bar

A valid use of `brainstorming-harness` must leave enough evidence for another agent to answer: what idea was explored, what alternatives were considered, what the user approved, what constraints apply, what is unresolved, and which KH skill should receive the handoff next.

It must also preserve scope independence and approval order. Prior run folders are not context unless the user asks to compare or reuse them. A vague product request is not implementation approval; the brainstorm should stop at the approval request unless approval already exists.

For domain work, the quality bar includes domain fit. A response that asks only "HTML, React, or WinForms?" for an inventory process has not satisfied the option frame because it has not decided how stock is managed, what records exist, or which workflow controls matter.
