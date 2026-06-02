# 2026-06-02 Vague Dashboard Blind Retest

## Scenario

- Installed cache observed before retest: `2.9.45`.
- Blind subagent prompt did not mention KH, UAF, skills, or harnesses:
  `C:\Users\KONEIT\Desktop\Jang\SKillsTest\RetestAutoRoute_20260602_J 폴더에서 재고 입출고 관리 대시보드 개발해줘.`
- Expected behavior: front-door should route the vague new dashboard/app request through `brainstorming-harness` and stop before implementation until the direction is approved.

## Observed Failure

- The subagent created `index.html`, `styles.css`, and `app.js` immediately.
- It wrote the files under the sandbox cwd instead of the requested Desktop target path after target-path escalation was rejected.
- It used memory-derived static dashboard guidance after front-door instead of respecting the new target boundary and brainstorming handoff requirement.

Session audit result:

- `issue_count=11`
- Missing or insufficient evidence included `brainstorming-harness`, `command-output-harness`, `harness-evaluator`, `plan-execution-harness`, `qa-gate-harness`, `quality-gates-harness`, and `verification-before-completion-harness`.
- Additional P1: cross-scope context leak from parent folder/memory-derived pattern use.

## Root Cause

The request classifier treated `대시보드` / `dashboard` as a specificity marker and excluded the prompt from early discovery routing. Because the request was short, it later fell to `light/direct_answer`, so the host continued with ordinary static-dashboard implementation behavior.

## Fix

- `dashboard` / `대시보드` are now accepted as vague discovery objects when no stronger implementation specifics are present.
- The exact failed Korean inventory-dashboard prompt now routes to:
  - `complexity=medium`
  - `domain=operations`
  - `recommended_execution=skill_read`
  - selected follow-up: `brainstorming-harness`
- The marketplace default prompt and `always-on-front-door` skill now forbid creating substitute folders when the exact requested target path is unavailable or needs approval.

## Verification

- `python -B -m unittest tests.test_request_classifier tests.test_kh_front_door -v`
  - `58 tests OK`
- Exact failed prompt front-door rerun:
  - `brainstorming-harness` selected
  - required next action says not to implement or create deliverables before approved direction and handoff.

## Follow-up

Version bumped to `2.9.46` so Codex marketplace upgrade creates a new plugin cache instead of reusing `2.9.45`.
