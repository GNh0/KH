# systematic-debugging-harness Usage Reference

## When to use

Use when a UAF workflow encounters a bug, failing test, unexpected behavior, flaky result, or broken environment and must diagnose before patching.

This harness applies to code failures, test failures, local server issues, browser verification failures, command errors, data migration problems, adapter errors, and host permission failures. It should not make simple questions heavy; use it when there is an observed failure or a concrete bug report.

## Inputs to collect

- Exact user report or failing command.
- Expected behavior, actual behavior, error text, exit code, and affected files or artifacts.
- Environment facts: OS, shell, sandbox/permission state, service availability, credentials, ports, package manager, and dependency status.
- Prior related changes and the smallest code path likely involved.
- Existing tests, smoke checks, or manual steps that can reproduce the problem.

## Execution pattern

1. Capture the symptom in a short structured record before editing.
2. Reproduce the failure with the narrowest command or manual step. If reproduction is blocked, record the blocker and stop broad patching.
3. Classify failure type so the next action is appropriate: product bug, test bug, environment issue, missing dependency, permission issue, flaky result, or unclear.
4. Form one hypothesis and choose the smallest check that can prove or disprove it.
5. Read only the relevant code and data needed for that hypothesis.
6. Patch the smallest root cause.
7. Add a regression check when practical, or record why no stable check exists.
8. Run the original failing check, targeted verification, and broader verification as needed.
9. Route repeatable lessons to Compound, memory candidates, or scenario regressions.

## Evidence to produce

- Symptom record with command/input, expected/actual behavior, and failure text.
- Reproduction evidence or blocker reason.
- Hypothesis, observation, root cause, patch scope, and regression evidence.
- Verification commands with exit code and result.
- Review finding or QA check when a gate needs normalized evidence.
- Compound candidate when this bug class is likely to recur.

## Failure handling

- If reproduction is impossible, block or ask for the missing input instead of guessing.
- If the failure is environmental, report the environment fix and avoid product code changes unless needed.
- If a hypothesis fails, record it and choose a new one rather than stacking speculative patches.
- If verification remains red after a patch, continue debugging instead of claiming partial completion as fixed.

## Quality bar

A valid debugging run should let another agent see the original symptom, the root cause, the smallest patch, the regression evidence, and exactly why the final verification passed or remains blocked.
