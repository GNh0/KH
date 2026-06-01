---
name: scenario-evaluation-harness
description: Use when kh-uaf:always-on-front-door has already run and selected this skill; use it when validating KH UAF against repeated SIDE-style human usage scenarios for request routing, evidence collection, gate decisions, and resume handoff behavior.
---
# Scenario Evaluation Harness

## KH Entry Contract

- Start every non-trivial turn through `always-on-front-door` unless this skill is that bootstrap step or the current turn was classified as light/direct.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, or a required follow-up gate selects it.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

This skill runs a deterministic scenario matrix that behaves like small SIDE groups: human-style users, domain experts, evidence/gate reviewers, resume reviewers, repeated multi-turn user probes, and KH-assistant SIDE transcript checks. It converts chatbot usage patterns into traceable regression data instead of relying on one-off manual impressions.

Source label: Scenario evaluation harness.

## Support files

- Read `references/usage.md` before adding scenario categories, changing signal thresholds, or interpreting report output.
- Use `examples/minimal-workflow.md` as the compact acceptance scenario for classification, evidence, gate, and resume signals.
- Run `python scripts/smoke_check.py` from this skill folder to verify support files and implementation targets.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable scenario evaluation mini-demo.
- Run `python -m src.orchestration.interactive_side_evaluator --summary --skills` to verify all packaged skills/harnesses through the KH-assistant SIDE transcript smoke checks.
- Run `python -m src.orchestration.interactive_side_evaluator --summary --skills --stress` for broader live-style SIDE transcript stress coverage with conversation length, route, execution-level, multi-skill, and token-usage statistics.

## Instructions

1. Start with `src.orchestration.scenario_evaluator.default_scenarios()` so every run covers the same baseline matrix.
2. Use `src.orchestration.scenario_evaluator.stress_scenarios()` or CLI `--stress` when the goal is broad regression pressure rather than a quick baseline check.
3. Treat `scenario_evaluator` scenarios as simulated SIDE observations, not as external LLM conversations.
4. Classify the prompt with `classify_request`, compare expected complexity, domain, execution depth, evidence, and required harnesses.
5. For scenarios with gate expectations, feed required evidence through `evaluate_goal_evidence` and record complete or blocked status.
6. For resume scenarios, require `resume_handoff` evidence when context says the next session must continue without prior chat.
7. Write `scenario_trace.jsonl` when investigating a regression so each scenario has a durable record.
8. Use `src.orchestration.interactive_side_evaluator.default_skill_side_turns()` when validating that KH-assistant SIDE transcripts select exact packaged skill names, route decisions, evidence keys, and response-policy signals across every KH skill/harness.
9. Use `src.orchestration.interactive_side_evaluator.stress_skill_side_turns()` before calling the transcript data meaningful; it adds varied multi-turn conversations, multi-skill overlap cases, and token usage comparisons. Treat this as deterministic stress data, not statistical user telemetry.
10. Reject SIDE transcripts that only sound plausible but omit exact `selected_skill` catalog names or evidence traces.
11. Convert unexpected failures into tests before changing classifier, evidence, gate, resume, or SIDE transcript code.
12. Keep the matrix broad and fast enough to run before heavier integration checks. Prefer representative failures from many varied conversations over large near-duplicate keyword sweeps.

## External Benchmark Recipe

Use this skill as a Superpowers-style repeated evaluation loop:

1. Run the baseline matrix with `python -m src.orchestration.scenario_evaluator --summary`.
2. Run the stress matrix with `python -m src.orchestration.scenario_evaluator --summary --stress`.
3. Confirm the baseline summary has at least four SIDE groups, seven domains, and classification/evidence/gate/resume signal categories.
4. Confirm the stress summary has at least 190 scenarios, 25 domains, and 360 meaningful signals.
5. If `unexpected_failures` is non-empty, inspect the trace before modifying routing or gate code.
6. Add one regression scenario for each real user pattern that produced a useful failure.
7. Keep expected blocked cases as passing data when the system blocks for the correct evidence reason.

Pressure scenario: a user asks a context-dependent follow-up such as "Do the same thing for the other file" after context compression. The harness must classify it as ambiguous without active artifact context, and a resume scenario must require `resume_handoff` evidence before claiming continuity is safe.

## Required outputs

- A summary containing total scenarios, pass/fail counts, SIDE count, domain count, and signal categories.
- JSONL trace records with `scenario_id`, expected values, actual classification, findings, and signals.
- Stable failure categories for classification, evidence, gate, and resume issues.
- Regression tests for any unexpected failure that is fixed.

## Common mistakes

- Do not treat expected blocked evidence scenarios as failed tests.
- Do not inflate the matrix with hundreds of near-duplicate keywords.
- Do not let a passing classifier hide missing gate or resume evidence.
- Do not claim real LLM quality from `scenario_evaluator` alone; it validates deterministic UAF contracts and routing boundaries.
- Do not count an interactive SIDE assistant run as KH-backed unless its trace uses exact packaged skill names from `skill-catalog`.
- Do not report token optimization as useful without before/after token usage statistics.

## UAF implementation targets

- `src.orchestration.scenario_evaluator.default_scenarios`
- `src.orchestration.scenario_evaluator.stress_scenarios`
- `src.orchestration.scenario_evaluator.evaluate_scenarios`
- `src.orchestration.scenario_evaluator.build_scenario_report`
- `src.orchestration.interactive_side_evaluator.default_skill_side_turns`
- `src.orchestration.interactive_side_evaluator.stress_skill_side_turns`
- `src.orchestration.interactive_side_evaluator.evaluate_skill_side_turns`
- `src.orchestration.interactive_side_evaluator.build_skill_side_report`
- `src.skills.demo_scenarios.run_skill_demo`
- `tests.test_scenario_evaluator`
- `tests.test_interactive_side_evaluator`
- `tests.test_uaf_skill_catalog`
