# Brainstorming Harness Minimal Workflow Example

## Scenario

A user says they want to build a SaaS project with KH UAF. The request is too early for implementation because target user, MVP center, repo naming, and stack direction are not fully approved.

The agent must use `brainstorming-harness`, keep the conversation lightweight, and produce a KH handoff for `architect-pipeline`.

## Expected steps

1. Load `SKILL.md` and confirm the trigger applies.
2. Read `references/usage.md` before doing the work.
3. Inspect the project context if a repository exists.
4. Ask one focused question at a time.
5. Present 2-3 approaches with tradeoffs and a recommendation.
6. Capture approved decisions in a `BrainstormSession`.
7. Validate the session with `validate_brainstorm_session`.
8. Build the handoff with `build_architect_handoff`.
9. Pass the handoff to `architect-pipeline` only after the user approves the direction.
10. Run `python scripts/smoke_check.py` when validating the packaged skill folder itself.

## Expected evidence

- `skill`: `brainstorming-harness`.
- `execution_level`: `hybrid-harness`.
- `support_reference_read`: `references/usage.md`.
- `implementation_targets`:
  - `src.orchestration.brainstorming.BrainstormOption`
  - `src.orchestration.brainstorming.BrainstormDecision`
  - `src.orchestration.brainstorming.BrainstormSession`
  - `src.orchestration.brainstorming.validate_brainstorm_session`
  - `src.orchestration.brainstorming.build_architect_handoff`
  - `tests.test_brainstorming_harness`
  - `skills/brainstorming_harness/SKILL.md`
- `actual_runtime_path`: `src.orchestration.brainstorming`.
- `verification`: validation result, demo result, or explicit blocked reason.

## Failure cases

- The agent scaffolds code before the user approves the design direction.
- The agent asks a batch of unrelated questions in one message.
- The agent writes Superpowers artifacts such as `.superpowers/brainstorm/...` instead of KH handoff evidence.
- The agent claims brainstorming is complete without a target user, problem, recommended option, or decision log.
- The agent hands off to Superpowers `writing-plans` instead of a KH skill.

## Done criteria

- The trigger match is explicit.
- Required inputs and boundaries are recorded.
- The execution level is stated accurately.
- `BrainstormSession` validates or reports missing fields.
- The next KH skill is named.
- Missing or blocked work is represented as structured evidence, not hidden in prose.
