---
name: quality-gates-harness
description: Use when a UAF workflow needs failing-test-first implementation, systematic debugging, review gates, or evidence-based completion checks.
---

# Quality Gates Harness

This is a personal UAF quality harness for testing, debugging, and verification workflows. It complements the sandbox evaluator by defining when evidence is required.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.

## Reference basis

- Personal quality workflow: test-driven development, systematic debugging, requesting code review, receiving code review, and verification before completion.

## Workflow

1. For new behavior or bug fixes, write the narrow test or smoke check first.
2. Run the check and confirm it fails for the expected reason.
3. Change production code only after the failing check is observed.
4. Re-run the targeted check, then the broader relevant suite.
5. For unexpected failures, capture the exact error, form a root-cause hypothesis, test it, then patch.
6. Use `build_review_finding`, `build_qa_check`, and gate evaluators when evidence must be normalized into a UAF gate record.
7. Before completion, map each user requirement to evidence from tests, build output, command output, or manual inspection.

## Review gates

- `spec`: every requested behavior is covered and no unrelated behavior was added.
- `runtime`: tests, build, or evaluator output prove the code can run.
- `regression`: the original bug or requested behavior has a direct check when practical.
- `security`: new command execution, file writes, network calls, and secrets handling are reviewed.

## Required outputs

- Failing-first evidence for behavior changes when practical.
- Targeted verification output followed by broader relevant checks.
- Structured review gate result with spec, runtime, regression, and security status.
- Missing-evidence or blocker notes when a check cannot be executed.

## Common mistakes

- Do not write tests after implementation and call it TDD.
- Do not accept task success when required evidence is missing.
- Do not skip root-cause tracing for unexpected failures.
- Do not collapse all review gates into one pass/fail string.

## UAF implementation targets

- `src.harness.evaluator`
- `src.harness.sandbox`
- `src.core.runner`
- `src.orchestration.gate_evaluators.build_review_finding`
- `src.orchestration.gate_evaluators.build_qa_check`
- `src.orchestration.gate_evaluators.evaluate_qa_checks`
- `tests`
- `src.skills.uaf_skill_catalog`
