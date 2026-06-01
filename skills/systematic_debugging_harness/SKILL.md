---
name: systematic-debugging-harness
description: Use when kh-uaf:always-on-front-door has already run and selected this skill; use it when a UAF workflow encounters a bug, failing test, unexpected behavior, flaky result, or broken environment and must diagnose before patching.
---

# Systematic Debugging Harness

## KH Entry Contract

- Start every non-trivial turn through `always-on-front-door` unless this skill is that bootstrap step or the current turn was classified as light/direct.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, or a required follow-up gate selects it.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

This is the KH-native debugging workflow. It requires the controller to capture symptoms, form a testable hypothesis, verify root cause, patch the smallest cause, and preserve regression evidence.

It replaces ad hoc "try a fix" loops with an auditable debug chain that can feed quality gates, review gates, GoalState evidence, and Compound learning.

## Support files

- Read `references/usage.md` before applying this skill to real debugging work.
- Use `examples/minimal-workflow.md` as a compact scenario for bug triage and regression evidence.
- Run `python scripts/smoke_check.py` from this skill folder to verify support files and implementation targets.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the packaged KH skill demo path.

## Workflow

1. Capture the exact symptom, command, input, expected behavior, actual behavior, and environment boundary.
2. Reproduce the issue or record why reproduction is blocked.
3. Classify the failure as product bug, test bug, environment issue, missing dependency, permission issue, flaky behavior, or unclear.
4. Form one root-cause hypothesis at a time and choose the smallest observation or command that can disprove it.
5. Inspect relevant code paths only after the symptom and hypothesis are known.
6. Patch the smallest cause and avoid unrelated refactors.
7. Add or update a regression test, smoke check, or manual evidence that would have caught the bug.
8. Run targeted verification, broader relevant verification, and review/security checks when blast radius requires them.
9. Capture a Compound lesson or scenario regression when the bug class is likely to recur.

## Required outputs

- `debug_status`: `reproduced`, `blocked`, `fixed`, `not_a_bug`, or `needs_context`.
- Symptom record with command/input, expected behavior, actual behavior, and failure text.
- Root-cause hypothesis and disconfirming/confirming evidence.
- Minimal patch scope and files changed.
- Regression evidence or explicit no-regression rationale.
- Verification evidence and remaining risk.
- Optional Compound candidate when the bug pattern should be remembered.

## Common mistakes

- Do not patch before reproducing or recording why reproduction is blocked.
- Do not chase multiple hypotheses at once without evidence.
- Do not classify an environment failure as a product bug without proof.
- Do not fix the symptom while leaving the root cause untested.
- Do not skip regression evidence for a real bug when a practical check exists.

## UAF implementation targets

- `src.harness.evaluator.Evaluator`
- `src.orchestration.gate_evaluators.build_review_finding`
- `src.orchestration.gate_evaluators.build_qa_check`
- `skills/systematic_debugging_harness/SKILL.md`
