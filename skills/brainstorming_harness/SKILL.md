---
name: brainstorming-harness
description: Use when kh-uaf:always-on-front-door has already run and selected this skill; use it when a user is starting an underspecified product, project, workflow, analysis, research, policy, process, document, specification, investment, operations, manufacturing, drawing, or design direction and the direction is not approved yet.
---

# Brainstorming Harness

## KH Entry Contract

- Start every non-trivial turn through `always-on-front-door` unless this skill is that bootstrap step or the current turn was classified as light/direct.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, or a required follow-up gate selects it.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

This harness adapts the Superpowers brainstorming pattern into KH UAF. It is the lightweight front door before `architect-pipeline`, `domain-orchestration-harness`, or `development-lifecycle-harness`: clarify the user's intent, explore alternatives, capture decisions, and hand off only after the product, process, analysis, document, specification, operations, manufacturing, investment, drawing, or design direction is approved.

Source label: Superpowers brainstorming adapted for KH UAF.

KH should not invent a shorter replacement for this flow. It should adapt the upstream pattern:

1. Explore current project context within the requested boundary.
2. Ask clarifying questions one at a time.
3. Propose 2-3 approaches with tradeoffs and a recommendation.
4. Present design sections and get user approval section by section when needed.
5. Write or preserve a right-sized KH design/spec handoff.
6. Self-review the spec for placeholders, contradictions, ambiguity, and scope.
7. Ask the user to review the written spec or handoff before planning.
8. Only after that, route to KH planning or implementation.

Compound Engineering adds the loop around this: strategy or context anchor -> brainstorm requirements -> plan -> work -> review -> compound learning. RTK adds command-output discipline: optimize noisy logs only when facts are preserved, and keep raw/failure recovery when compression could hide evidence.

The invariant is approval before implementation: design/spec review approval must exist before planning, and implementation approval must be separate from an option choice.

## Support files

- Read `references/usage.md` before applying this skill to real project discovery; it expands trigger boundaries, evidence, and handoff rules.
- Use `examples/minimal-workflow.md` as a compact acceptance scenario for KH-style brainstorming.
- Run `python scripts/smoke_check.py` from this skill folder to verify support files and implementation targets.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo.

## When To Use

Use this harness when:

- The user wants to start a new product, SaaS, app, workflow, analysis, research, policy, process, document, specification, investment, operations, manufacturing, drawing, design, or major feature.
- The request is creative or underspecified enough that immediate implementation would hide assumptions.
- The user needs options, tradeoffs, naming, MVP scope, target users, workflow shape, or architecture direction before planning.
- A visual companion or mockup may help choose among directions, but the final decision still needs text evidence.

Do not use it for quick factual questions, small edits with clear acceptance criteria, or already-approved implementation plans.

## Core Flow

0. If front-door returned `execution_gate.can_execute=false` with `status=blocked_until_brainstorming_handoff`, treat that as a hard stop for execution. Do not consult global Codex `MEMORY.md`, `.codex/memories/skills/...`, previous chat/subagent memories, previous dashboard/page patterns, sibling run folders, scaffold source, create user deliverables, run verification, or browser-test until this harness produces approval and handoff evidence.
1. Before the first visible brainstorm, do not inspect even the explicit target project/folder. Do not run `Test-Path`, `Get-ChildItem`, `rg`, `Get-Content`, target-folder existence checks, target write preflight, parent scans, sibling scans, or source reads. Treat the named target path as user context only.
   - Fresh/empty/new target fast path: do not read `MEMORY.md`, memory summaries, parent folders, sibling folders, previous test outputs, older project artifacts, or the exact target folder unless the user explicitly asks for reuse, comparison, migration, prior context, or implementation preflight.
   - For this fast path, return a compact direction proposal with 2-3 options, one recommendation, and an approval question. The options must be domain/workflow choices first, not only implementation technology choices. Do not escalate to GoalState, role DAG, document exports, QA, review gates, target write preflight, or source/file inspection before approval.
2. If the next choices are visual, offer a visual companion in its own message.
3. Ask one question at a time. Prefer 2-3 clear choices with a recommendation.
4. Capture decisions as structured records: `objective`, `target_user`, `problem`, `options`, `recommendation`, `constraints`, `decisions`, and `open_questions`.
5. Present 2-3 approaches with tradeoffs and a recommended direction.
6. Present the chosen direction and ask for approval before design/spec handoff writing. For vague product, app, service, SaaS, project, analysis, design, process, document, specification, operations, investment, or other domain-work requests, stop here unless the user approves the direction in a later message.
7. Treat a user choice such as "go with option 1" as approval of that direction only. It is not approval to implement, scaffold, create files, verify, or produce user deliverables.
8. After a direction choice, continue the design/spec loop: confirm success criteria, scope, data shape, screens/artifacts, non-goals, risks, and acceptance criteria one question or section at a time.
9. Build a `BrainstormSession`, validate it, and create a `brainstorm_handoff`.
10. Write KH project artifacts when useful: `.kh/brainstorm/<run-id>/content/*.md` for local working notes, `.kh/brainstorm/<run-id>/state/*.json` for run-local state, and `docs/kh/handoffs/*.md` for shareable summaries.
11. Self-review the handoff/spec for placeholders, contradictions, ambiguity, and scope before planning.
12. Ask the user to review or approve the written handoff/spec before planning or implementation.
13. Pass the handoff to the next KH skill:
   - `architect-pipeline` for product/system design.
   - `domain-orchestration-harness` for cross-domain role/gate design.
   - `goal-state-harness` when completion criteria and evidence are central.
   - `plan-execution-harness` or `development-lifecycle-harness` only after the design/spec review gate is approved.

## Minimum Discovery Checkpoints

Do not collapse brainstorming into a single option picker unless the user has already supplied enough detail for every checkpoint below. For early product, project, app, SaaS, workflow, analysis, research, policy, process, design, document, manufacturing/specification, investment, operations, or other domain work, progress through these checkpoints and preserve evidence:

1. `intent_frame`: objective, target user/operator/audience, and success criteria.
2. `problem_frame`: current pain, workflow boundary, constraints, and non-goals.
3. `option_frame`: 2-3 approaches with tradeoffs and one recommendation.
4. `approval_frame`: explicit user approval, rejection, or blocked/waiting state.
5. `handoff_frame`: `BrainstormSession`, `validate_brainstorm_session`, `decision_log`, `brainstorm_handoff`, and next KH skill.

If the user only says "handle this topic/project/work" and then chooses one proposed option, that approval is permission to continue the KH flow, not permission to skip the handoff. Build and validate the handoff before architecture, domain orchestration, analysis, deliverable generation, or implementation. If time, host tools, or missing context prevents this, record `brainstorming_status=blocked` with the missing checkpoint instead of claiming the skill ran.

If the user says "option 1", "go with option 2", or similar, continue brainstorming/design review. Ask the next scoped question, such as which fields, screens, constraints, non-goals, acceptance criteria, or output format should be included. Do not create files from an option choice alone.

## Superpowers-Level Discovery Ladder

For underspecified work, the visible brainstorming response must not be only "here are three options, approve one." Use a compact but complete ladder:

1. Intent: restate the objective and target operator/audience.
2. Reality check: state what is unknown about the current workflow, data source, constraints, success criteria, and non-goals.
3. Model choices: present 2-3 operating models with tradeoffs, not only technology stacks.
4. Data and artifact shape: list the records, fields, documents, files, drawings, or outputs that the chosen model will need.
5. Recommendation: choose one direction and explain why it fits the likely goal.
6. Decision point: ask one next approval or clarification question.

If any ladder item is missing, keep brainstorming or mark `brainstorming_status=blocked`. Do not create product files, analysis output, user deliverables, or verification artifacts from an option picker alone.

## Domain-First Compact Brainstorm

For operations, business process, manufacturing, investment, drawing/design, document, analysis, or other cross-domain requests, the first user-facing brainstorming response must start from the domain problem instead of the technology stack.

## Visible First Response Gate

For a vague or new app, dashboard, product, operations, manufacturing, document, drawing/design, analysis, investment, or workflow request, the first visible response must include every section below. Translate the section headings to the user's apparent language when helpful, but keep the content complete:

1. Objective/operator: what is being built or decided, and who will operate or use it.
2. Workflow boundary: which process slice is in scope and what is not yet known.
3. Success criteria/constraints/non-goals: how a useful first version will be judged, plus obvious limits.
4. Operating model options and tradeoffs: 2-3 domain models with pros/cons, not just technology stacks.
5. Required records/data/artifact shape: fields, documents, drawings, files, or outputs the chosen model needs.
6. Open questions: the few assumptions that still need confirmation.
7. Recommendation: one direction and why it fits the likely goal.
8. Approval question: one clear next decision before implementation, deliverable generation, or verification.

Missing target folders, empty folders, or "simple" wording do not remove this gate. A response that only says the folder is missing and lists 2-3 options is failed brainstorming. Continue discovery until all eight sections are visible, then stop for approval.

## Recommendation Discipline

A recommendation is advisory, not an agent-owned final decision. Before the user approves:

- Do say: "My recommendation is option 2 because..." and ask the user to choose or approve.
- Do not say or imply: "I will go with option 2", "we will use this as the basis", "I will create it this way", or similar final-decision wording.
- Do not ask for approval of an implementation stack such as HTML/CSS/JavaScript, React, WinForms, or database storage unless the user asked for stack selection or already approved the domain operating model.
- Keep open questions visible when they could change the scope.
- The first approval question should ask the user to choose or approve the operating model, not to approve immediate implementation. Prefer "Which operating model should we use? My recommendation is option 1." Do not ask "Can I implement this now?", "If you approve, I will create files", or "I can implement now" until the domain direction is approved.
- Do not promise target-path file creation, implementation, development, or deliverable generation in the first brainstorm approval question.
- The first brainstorm should end with a direction question, not an execution question. Good: "Which operating model should we choose: simple stock ledger, location-controlled stock, or lot/serial stock? My recommendation is the simple ledger unless location tracking is required." Bad: "If you approve, I will create the files in the target folder."
- Do not mention implementation start, generated files, browser verification, QA, or deliverable creation in the same question that asks the user to choose the domain direction.
- A later option choice is still not implementation approval. It advances to design/spec review and another focused question, not file generation.

If the agent has already written final-decision wording before user approval, mark the run as `unilateral_brainstorm_decision` and redo the decision question.

## Option Choice Continuation Gate

When the user replies with only a direction choice such as "option 1" or "go with the recommendation", do not lock the implementation scope.

Do not respond with a block such as "implementation scope", "I will set the implementation scope as follows", KPI/form/table/storage lists, target-folder creation approval, or "I will create the files". That turns a direction choice into execution approval and fails the brainstorm.

Instead:

1. Record the selected direction as direction evidence only.
2. State that implementation scope is not final yet.
3. Ask the next focused design/spec question that could change the output, such as stock calculation rule, required fields, screens/artifacts, non-goals, risks, acceptance criteria, approvals, locations, lots/serials, or export/output shape.
4. Keep asking one focused question or presenting one review section at a time until the `BrainstormSession`, decision log, self-reviewed handoff/spec, and separate implementation approval exist.

Example continuation after an inventory option choice:

"Option 1, the simple stock-ledger direction, is recorded. Implementation scope is not final yet. Next, how should current stock be calculated: A) transaction-derived only, B) editable current quantity with audit log, or C) hybrid with adjustment reasons?"

## Handoff Transition Gate

Do not keep asking option questions indefinitely. After 3-4 focused user decisions, or once the remaining unknowns are low-risk defaults, stop the option ladder and produce a concise design/spec review handoff instead of continuing to brainstorm.

The handoff transition response should:

1. Summarize recorded decisions.
2. List unresolved assumptions as defaults or explicit open questions.
3. State that no files have been created yet.
4. Ask for separate execution approval in a way that makes the next action explicit.

Do not start implementation in the same response unless the user already gave explicit execution approval after reviewing the handoff/spec. If the host cannot produce a handoff quickly, stop with `brainstorming_status=blocked` rather than stalling or continuing the option ladder.

## Approved Continuation Gate

When the user later approves a recommended option, that approval opens the next KH stage only after current-run handoff evidence exists. Before implementation, file writes, deliverable generation, QA, browser verification, or broad memory lookup:

1. Preserve `approval_frame` from the later user message.
2. Build or record a `BrainstormSession` for the current request.
3. Validate the session or record `brainstorming_status=blocked`.
4. Preserve `decision_log` and `brainstorm_handoff`.
5. Route to the next KH skill.

Do not read global Codex `%CODEX_HOME%/memories/MEMORY.md`, `%CODEX_HOME%/memories/skills/...`, sibling folders, old static-page preferences, or prior subagent outputs during this continuation unless the user explicitly asked to reuse or compare previous context. If the handoff cannot be produced, stop with the blocked reason instead of scaffolding from memory.

For an inventory inbound/outbound request, a valid compact brainstorm should include:

1. Assumed objective and target operator, such as warehouse staff, purchasing, production, or management.
2. Current workflow boundary, such as inbound receiving, outbound issue/shipment, transfer, adjustment, returns, stocktake, and shortage monitoring.
3. 2-3 operating model choices with tradeoffs, such as simple ledger, location-controlled stock, lot/serial/expiry-controlled stock, or approval/ERP-linked stock flow.
4. Required data records, such as item code/name, location, quantity, transaction type, date/time, owner, reason, memo, safety stock, and optional lot, serial, expiry, supplier, customer, or work order.
5. Open questions, such as whether locations, approvals, ERP import/export, lots/serials, barcode scans, or stocktaking are required.
6. One recommended domain direction and one approval question before any implementation or artifact generation.

Technical choices such as static HTML, React, WinForms, database, or deployment can appear only after the domain choices are framed, unless the user already supplied enough workflow, data, and approval detail. A "simple" request still needs this compact domain-first pass; simplicity changes the length, not the ordering.

## User-Facing Reporting

- The final answer should read like a normal brainstorming or direction-setting response in the user's language.
- For domain work, make the visible options about workflow/operating model first; keep technology options secondary unless the user asked specifically for a stack decision.
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

Pressure scenario: a user says "I want to build a SaaS" or "plan an operations analysis workflow." The agent should not scaffold or generate the final artifact immediately. It should clarify target audience/operator, objective, success criteria, constraints, options, and recommended direction, then produce a handoff for `architect-pipeline` or `domain-orchestration-harness`.

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
- User approval evidence before any implementation, scaffolding, source writes, or deliverable generation beyond brainstorm notes.
- Checkpoint evidence for `intent_frame`, `problem_frame`, `option_frame`, `approval_frame`, and `handoff_frame`.

## Common mistakes

- Treating brainstorming as implementation permission.
- Treating the user's initial "develop/create/make" wording as approval to skip a front-door brainstorming gate.
- Reading global Codex `MEMORY.md` or `.codex/memories/skills/...` after a fresh/empty target fast path and using old implementation preferences to bypass the current brainstorm gate.
- Asking one direction question, receiving a choice, and implementing without `BrainstormSession` plus `brainstorm_handoff`.
- Implementing or scaffolding immediately after a vague product idea without a separate user approval of the recommended direction.
- Creating visual files without linking them to a decision.
- Asking five questions at once.
- Presenting only one approach before recommending it.
- Presenting only implementation technology choices for a domain workflow, such as HTML versus React, without first framing operating models, required records, and workflow boundaries.
- Losing product names, repo decisions, or MVP scope during context compression.
- Letting sibling test outputs or earlier run folders influence a new brainstorm without explicit user permission.
