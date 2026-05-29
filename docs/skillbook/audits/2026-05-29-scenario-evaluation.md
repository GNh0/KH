# Scenario Evaluation Harness Report

Date: 2026-05-29

## Purpose

This report records the first deterministic SIDE-style scenario loop for KH UAF request routing, evidence requirements, gate behavior, and resume readiness. The goal was to collect useful improvement signals from common chatbot usage patterns before relying on heavier host or LLM-backed integration runs.

## Scenario Matrix

- SIDE groups: 4 (`human-user`, `domain-expert`, `evidence-gate`, `resume`)
- Domains covered: 7 (`software`, `investment`, `product-design`, `legal`, `medical`, `security`, `general`)
- Final scenarios: 30
- Final meaningful signals: 66
- Signal categories: `classification`, `evidence`, `gate`, `resume`

## First Iteration Findings

The first run produced 13 unexpected failures. These were useful because they came from human-style prompts rather than synthetic keyword checks.

- Ambiguous follow-ups such as "What should I do with this?", "Can you review it?", and "Now make it shorter" were answered too directly without active artifact context.
- Security bypass phrasing with "login screen" was misrouted as product design because `screen` dominated the domain signal.
- Product drawing prompts with dimensions, material, and holes were not recognized as heavy product-design work.
- README generation from a response was under-escalated as a generic medium task instead of a persisted software deliverable.
- PR audit prompts were under-escalated even when production risk was named.
- Resume prompts required `resume_handoff` but did not also require the work design and domain evidence needed to finish safely.
- Summary prompts with current/source-like content did not always require `source_summary`.

## Fixes Codified

- Added `src.orchestration.scenario_evaluator` with deterministic scenario cases, evaluation records, aggregate reports, JSONL trace writing, and CLI summary output.
- Added `scenario-evaluation-harness` as a packaged UAF skill with support files, smoke checks, runnable demo, and external benchmark documentation.
- Improved `request_classifier` for English ambiguous follow-ups, security high-risk precedence, product drawing terms, README/software deliverables, PR audit/review work, investment market/news terms, and resume evidence.
- Preserved regression coverage in `tests.test_scenario_evaluator` and updated skill catalog/quality tests for 29 packaged skills.

## Final Result

Command:

```bash
python -m src.orchestration.scenario_evaluator --summary
```

Result:

```json
{
  "summary": {
    "total": 30,
    "passed": 30,
    "failed": 0,
    "domain_count": 7,
    "side_count": 4,
    "meaningful_signal_count": 66,
    "signal_categories": ["classification", "evidence", "gate", "resume"]
  },
  "unexpected_failures": []
}
```

## Remaining Backlog

- Add artifact-level assertions for deliverable exports, especially product drawings, software functional specs, and investment workbooks.
- Add fixture-level gate simulations for failed command checks, invalid QA skips, security findings, and release blocking.
- Add resume storage integration checks that create actual `current_goal.json`, `goal_events.jsonl`, and `resume_handoff.json` in a temporary runtime root.
- Add a small rotating real-world prompt corpus from future manual sessions, but keep the default matrix compact and deterministic.
