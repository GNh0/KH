# Scenario Evaluation Harness Report

Date: 2026-05-29

## Purpose

This report records the deterministic SIDE-style scenario loop for KH UAF request routing, evidence requirements, gate behavior, and resume readiness. The harness is intentionally local and repeatable: it turns human-like chatbot conversations into regression data before heavier host or LLM-backed integration runs.

## Baseline Matrix

- SIDE groups: 4 (`human-user`, `domain-expert`, `evidence-gate`, `resume`)
- Domains covered: 7 (`software`, `investment`, `product-design`, `legal`, `medical`, `security`, `general`)
- Final scenarios: 30
- Final meaningful signals: 66
- Signal categories: `classification`, `evidence`, `gate`, `resume`

## Stress Expansion

The stress corpus now combines the original 90 deterministic scenarios with repeated SIDE probes from varied one-shot and multi-turn conversations. The added waves covered data/file workflows, creative and marketing work, travel/local/current lookups, Korean life-admin, education/language/document work, health/fitness/cooking/lifestyle, career/workplace, civic/government forms, DevOps/cloud/security, and everyday safety/social prompts.

Latest stress run:

- Scenarios: 193
- Passed: 193
- Unexpected failures: 0
- Domains covered: 31
- SIDE groups: 8
- Meaningful signals: 385
- Signal categories: `classification`, `evidence`, `gate`, `resume`

## Interactive SIDE Assistant Correction

The first broad stress loops were useful as deterministic routing pressure, but they were not enough to prove that SIDE agents were actually applying KH skills and harnesses during a conversation. The corrected loop now has two layers:

- `scenario_evaluator`: deterministic user-pattern corpus for routing, evidence, gates, and resume behavior.
- `interactive_side_evaluator`: multi-turn SIDE assistant transcript checks that require exact packaged KH skill names, route decisions, evidence keys, and response-policy signals.

The all-skill SIDE transcript smoke covers every packaged KH skill/harness:

- Packaged skills/harnesses covered: 31
- Conversations: 8
- Multi-turn conversations: 8
- Signal categories: `catalog`, `evidence`, `assistant_policy`, `token_usage`
- Failure mode now caught: a SIDE response that sounds plausible but uses an invented skill name instead of an exact KH packaged skill.

Live SIDE assistant runs confirmed the same risk. Without exact catalog context, agents produced useful answers but emitted non-KH names such as `equipment_design_planning`, `command_hook_safety_policy`, or generic `high_risk`. After injecting exact packaged skill names, the same SIDE agents selected concrete KH skills such as `command-output-harness`, `parallel-orchestration-harness`, `subagent-review-pipeline`, `traceability-matrix-harness`, and `domain-orchestration-harness`. This means real host runs must either provide the packaged skill catalog up front or route through `skill-catalog` before claiming a SIDE used KH skills.

The live run also exposed an overlap case: when a destructive command appears inside a command-hook conversation, a SIDE may select `command-hook-policy-harness` but miss `guard-policy-harness`. The evaluator already accepts multi-skill traces through `selected_skills`; the recommended host behavior is to include both skills when hook policy and destructive/write-boundary safety are both active.

## Token Usage Evidence

`token-optimizer` now reports before/after token estimates, so a run can show the cost difference between using the optimizer and passing raw content through unchanged.

Recorded fields:

- `without_token_optimizer`
- `with_token_optimizer`
- `estimated_tokens_saved`
- `token_savings_ratio`
- `by_strategy`

The interactive SIDE report aggregates these token-usage records at workflow level, so token optimization is measured as evidence rather than asserted in prose.

Latest all-skill SIDE smoke summary:

```json
{
  "total": 31,
  "passed": 31,
  "failed": 0,
  "skill_count": 31,
  "catalog_skill_count": 31,
  "conversation_count": 8,
  "multi_turn_conversation_count": 8,
  "meaningful_signal_count": 94,
  "token_usage": {
    "without_token_optimizer": 830,
    "with_token_optimizer": 53,
    "estimated_tokens_saved": 777,
    "token_savings_ratio": 0.9361
  }
}
```

Latest live-style SIDE stress summary:

```json
{
  "total": 76,
  "passed": 76,
  "failed": 0,
  "skill_count": 31,
  "conversation_count": 14,
  "multi_turn_conversation_count": 14,
  "min_turns_per_conversation": 3,
  "max_turns_per_conversation": 11,
  "multi_skill_turn_count": 3,
  "route_counts": {
    "skill_call": 51,
    "workflow_harness": 23,
    "procedure_policy": 2
  },
  "execution_level_counts": {
    "python-module": 51,
    "hybrid-harness": 23,
    "procedure-policy": 2
  },
  "meaningful_signal_count": 233,
  "token_usage": {
    "case_count": 5,
    "without_token_optimizer": 5783,
    "with_token_optimizer": 172,
    "estimated_tokens_saved": 5611,
    "token_savings_ratio": 0.9703
  }
}
```

This is still not statistically representative user telemetry. It is a deterministic regression/stress fixture that is strong enough to catch catalog, routing, evidence, multi-skill, and token-stat regressions before real host usage.

## Findings Codified

- Simple conceptual questions stay light, but domain is preserved for education, language, fitness, DevOps, civic, and other downstream policies.
- Active artifacts now prevent short follow-ups from collapsing to direct answers when the user is editing, exporting, converting, charting, filing, or resuming work.
- High-risk routing now covers investment, medical, legal, security, privacy, booking, marketing, employment-law, immigration, government submission, production operations, leaked secrets, SSNs, self-harm, domestic violence, minor privacy, and impersonation/harassment boundaries.
- Current-data and external-evidence requests require `source_summary` for local services, weather, booking, food safety, education deadlines, salary/job-market data, and government deadlines.
- Resume scenarios require `resume_handoff`; medium resume work can remain skill-level when it is continuation/analysis rather than implementation.
- Bounded everyday drafts and rewrites stay light, while external send/report/post/submit actions clarify unless explicit permission or a high-risk transaction context is present.

## Commands

Baseline:

```bash
python -m src.orchestration.scenario_evaluator --summary
```

Stress:

```bash
python -m src.orchestration.scenario_evaluator --summary --stress
```

Latest stress result:

```json
{
  "summary": {
    "total": 193,
    "passed": 193,
    "failed": 0,
    "domain_count": 31,
    "side_count": 8,
    "meaningful_signal_count": 385,
    "signal_categories": ["classification", "evidence", "gate", "resume"]
  },
  "unexpected_failures": []
}
```

## Remaining Backlog

- Keep adding rotating SIDE waves from real usage, but only preserve representative failures as deterministic regression cases.
- Add live SIDE transcript fixtures that persist exact `KH_TRACE` lines from multi-agent runs, including invented-skill-name failures.
- Add artifact-level assertions for deliverable exports, especially spreadsheet/document conversions and generated charts.
- Add fixture-level gate simulations for failed command checks, invalid QA skips, security findings, and release blocking.
- Add resume storage integration checks that create actual `current_goal.json`, `goal_events.jsonl`, and `resume_handoff.json` in a temporary runtime root.
