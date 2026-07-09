# verification-before-completion-harness Minimal Workflow Example

## Scenario

A KH implementation run has edited three files and is about to report that the task is complete and pushed. The active GoalState requires tests, review, and push evidence. The last test command was run before the final fix.

## Expected steps

1. Read the active goal, progress state, changed files, and review status.
2. Detect that the prior test output is stale because code changed after it ran.
3. Run the targeted regression test and the broader relevant suite.
4. Preserve command, exit code, and final pass/fail status.
5. Update progress state with `verification_status=passed` and current integration state.
6. If the push succeeds, report committed/pushed; if it fails, report blocked with the exact reason.

## Expected evidence

- `actual_runtime_path`: `skills/verification_before_completion_harness/SKILL.md`
- `execution_level`: `hybrid-harness`
- `verification_status`: `passed`
- `fresh_verification`: command ran after the last code change
- `completion_claim`: `pushed`
- `commit_sha`: present
- `residual_risk`: empty or explicitly explained

## Failure cases

- The agent says tests passed but only cites a previous run.
- Browser QA was promised, failed to launch, and was replaced by an HTTP 200 check without disclosure.
- A failing command is hidden in a success summary.
- The goal remains active but final completion is claimed.

## Done criteria

- Completion is supported by fresh evidence or explicitly blocked.
- Verification failures are visible in final status.
- GoalState and progress state contain enough evidence for resume.
- Catalog validation and the skill smoke check pass.

## Runtime binding

- execution_level: hybrid-harness
- implementation_targets:
  - `src.orchestration.session_postmortem.analyze_codex_session_jsonl`
  - `src.orchestration.gate_evaluators.evaluate_release_gate`
  - `src.orchestration.development_progress.derive_review_status`
- actual_runtime_path: `src.orchestration.gate_evaluators.evaluate_release_gate`
- verification evidence: run `scripts/smoke_check.py`, `scripts/demo.py --output-dir <tmp>`, and the exact fresh test/build/check command that supports the completion claim.
