# systematic-debugging-harness Minimal Workflow Example

## Scenario

A verification check fails after a feature change. The output says the generated artifact is missing a required record, but the user expected the saved result to satisfy the contract.

## Expected steps

1. Record the failing command, expected record, actual missing record, and affected artifact or module.
2. Reproduce the failure with the narrowest relevant check.
3. Hypothesize that the producer skipped a required field, record, or mapping.
4. Inspect only the producer, mapper, or verification setup that can affect the missing record.
5. Patch the producer or test to match the intended contract.
6. Add or update the regression test.
7. Re-run the original failing command and broader relevant tests.
8. Record whether a reusable route-registration lesson should become a scenario regression.

## Expected evidence

- `actual_runtime_path`: `skills/systematic_debugging_harness/SKILL.md`
- `execution_level`: `hybrid-harness`
- `debug_status`: `fixed`
- `root_cause`: required record not emitted
- `regression_evidence`: targeted artifact or module check
- `verification`: original failing check now passes

## Failure cases

- The agent patches unrelated files without reproducing the missing-record failure.
- The final answer says fixed while the original command still fails.
- The failure was a missing database service, but product code was changed anyway.
- No regression evidence is added for a real product bug.

## Done criteria

- Root cause and patch scope are explicit.
- Regression evidence exists or a no-regression rationale is recorded.
- Original failure and broader relevant checks are accounted for.
- Catalog validation and the skill smoke check pass.

## Runtime binding

- execution_level: hybrid-harness
- implementation_targets:
  - `src.harness.evaluator.Evaluator`
  - `src.orchestration.gate_evaluators.build_review_finding`
  - `src.orchestration.gate_evaluators.build_qa_check`
- actual_runtime_path: `src.harness.evaluator.Evaluator`
- verification evidence: run `scripts/smoke_check.py`, `scripts/demo.py --output-dir <tmp>`, and the failing/passing regression command captured in the debug record.
