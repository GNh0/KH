# Brainstorming Harness Usage Reference

This reference expands the portable operating contract for `brainstorming-harness`. Read it when KH UAF needs to turn an early idea into a structured design handoff before architecture, domain orchestration, or implementation.

## When to use

Use when a user is starting a feature, product, project, or design idea and the agent must clarify intent, compare approaches, and produce an approved handoff before implementation.

Context summary: this is the KH UAF version of Superpowers brainstorming. It keeps the useful interaction pattern but changes the storage, handoff, and next-step contracts to KH. The output is not a Superpowers spec. It is a KH `BrainstormSession` plus handoff evidence for the next UAF skill.

Do not use this skill only because it is available. Use it when the current task needs discovery before design or implementation, and state whether the skill was actually executed, applied procedurally, or only considered.

## Inputs to collect

- User objective and what success should look like.
- Target user, buyer, operator, or audience.
- Problem being solved and current pain.
- 2-3 possible approaches with tradeoffs.
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
6. Confirm the direction before creating architecture, scaffolding, or code.
7. Build a `BrainstormSession` and run `validate_brainstorm_session`.
8. If valid, call `build_architect_handoff` and pass the payload to the selected KH skill.
9. When the user benefits from visible project notes, call `write_brainstorm_markdown_artifacts` so KH creates `.kh/brainstorm/.../content/*.md`, `.kh/brainstorm/.../state/`, and `docs/kh/handoffs/*.md`.
10. Preserve intermediate decisions in structured evidence rather than relying on chat memory alone.
11. Run `python scripts/smoke_check.py` when validating this packaged skill in the repository.

## Evidence to produce

- Skill name and execution level used for the run.
- User objective, target user, problem, constraints, and success criteria.
- Options considered and tradeoffs.
- Recommendation and approved decisions.
- `BrainstormSession` validation result.
- Handoff target, usually `architect-pipeline`.
- Markdown handoff paths if project-local KH notes were written.
- Verification command or review evidence when validating the packaged skill itself.

Keep this evidence available for audits, but do not print raw validation fields
in ordinary final answers. User-facing responses should show the options,
recommendation, tradeoffs, open questions, and approval request. Raw fields such
as `valid=true`, `missing=[]`, `BrainstormSession`, and `brainstorm_handoff`
belong in internal evidence unless the user asks for KH usage details.

## Failure handling

- If no target user or problem is known, keep asking clarifying questions instead of claiming a handoff is complete.
- If no option is recommended, block handoff and record `recommended_option` as missing.
- If the user rejects the proposed direction, update decisions and rerun validation.
- If the task is too broad for one design, decompose it and brainstorm only the first project slice.
- If visual artifacts are created, record what decision they supported and avoid leaving orphan mockups.
- If a sibling or previous run folder was read accidentally, discard that run as contaminated, record the leak, and restart from the requested target boundary.

## Quality bar

A valid use of `brainstorming-harness` must leave enough evidence for another agent to answer: what idea was explored, what alternatives were considered, what the user approved, what constraints apply, what is unresolved, and which KH skill should receive the handoff next.

It must also preserve scope independence. Prior run folders are not context unless the user asks to compare or reuse them.
