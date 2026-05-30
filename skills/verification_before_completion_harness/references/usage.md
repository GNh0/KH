# verification-before-completion-harness Usage Reference

## When to use

Use when a UAF workflow is about to claim completion, commit, push, ship, or hand off work and must prove fresh verification evidence first.

This harness should be selected before a final answer, branch finish, push, PR, release decision, or "done" status whenever the work changed files, created artifacts, ran subagents, handled risky commands, or promised a verification path. It is intentionally lighter than a full release process for tiny non-behavioral edits, but it still requires an explicit no-test rationale when no command can usefully run.

## Inputs to collect

- Active objective, success criteria, required evidence, and missing evidence from GoalState.
- Changed files, generated artifacts, dependency changes, and any manually verified behavior.
- Task progress fields: active task, RED/GREEN evidence, review status, fix/re-review status, commit SHA, and next task.
- Review and QA gate output, including unresolved findings, waived findings, and failed verification paths.
- Commands already run, their recency, exit codes, and whether they were targeted or broad checks.
- Sandbox, permission, network, browser, local server, or dependency constraints that affect verification.

## Execution pattern

1. State the intended completion claim in concrete terms: local only, committed, pushed, PR-ready, released, partial, or blocked.
2. Map the claim to evidence. A local implementation needs targeted tests or smoke checks; a pushed branch needs clean git state and push evidence; a UI claim needs browser/render/manual QA evidence or an explicit residual risk note.
3. Reject stale evidence if code changed after the verification command ran.
4. Run the narrowest relevant check first, then broader checks proportionate to blast radius.
5. Preserve output with `command-output-harness` when long logs appear. Use `token-optimizer` only when compression preserves exit code, test names, error paths, and reviewer severity.
6. Normalize failures into `verification_status=failed` or `blocked`; do not bury them inside a general summary.
7. Update GoalState and progress state before the final user report.
8. Finish with an integration state and next action.

## Evidence to produce

- `verification_status` plus command evidence with exit code and final result.
- Requirement-to-evidence mapping, including manual QA where appropriate.
- `completion_claim` and `integration_state`.
- Freshness note showing verification happened after the final code change or why that was impossible.
- `residual_risk` for skipped, failed, unavailable, or substituted verification.
- Final report fields that another agent can resume from without reading the full chat.

## Failure handling

- If a command fails for a real product bug, block completion and route to systematic debugging or quality gates.
- If a command fails because of sandbox, missing service, missing credential, or unavailable browser, report the failed route and the weaker evidence that was available.
- If the user explicitly asks for commit or push despite incomplete verification, preserve the risk in branch-finishing evidence.
- If output is huge, optimize only after preserving failure identity and exit status.

## Quality bar

A valid use must let another agent answer these questions: what completion was claimed, what changed, what fresh evidence proves it, what failed or could not be checked, what risk remains, and what integration action happened.
