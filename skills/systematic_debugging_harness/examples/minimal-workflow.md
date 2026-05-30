# systematic-debugging-harness Minimal Workflow Example

## Scenario

A test fails after a feature change. The output says an API route returns 404, but the user expected the dashboard to load real data.

## Expected steps

1. Record the failing command, expected response, actual 404 response, and affected route.
2. Reproduce the failure with the narrowest API test.
3. Hypothesize that the route was registered under a different prefix.
4. Inspect only the route registration and test client setup.
5. Patch the route or test to match the intended contract.
6. Add or update the regression test.
7. Re-run the original failing command and broader relevant tests.
8. Record whether a reusable route-registration lesson should become a scenario regression.

## Expected evidence

- `actual_runtime_path`: `skills/systematic_debugging_harness/SKILL.md`
- `execution_level`: `hybrid-harness`
- `debug_status`: `fixed`
- `root_cause`: route prefix mismatch
- `regression_evidence`: targeted API test
- `verification`: original failing check now passes

## Failure cases

- The agent patches unrelated UI code without reproducing the 404.
- The final answer says fixed while the original command still fails.
- The failure was a missing database service, but product code was changed anyway.
- No regression evidence is added for a real product bug.

## Done criteria

- Root cause and patch scope are explicit.
- Regression evidence exists or a no-regression rationale is recorded.
- Original failure and broader relevant checks are accounted for.
- Catalog validation and the skill smoke check pass.
