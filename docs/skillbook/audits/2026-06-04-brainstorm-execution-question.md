# Brainstorm Execution-Question Regression

Date: 2026-06-04

## Trigger

Blind subagent session `019e90e4-d307-7453-9528-0aa3bef01ca9` handled an inventory inbound/outbound dashboard request without explicit KH skill names. The first response improved over earlier runs by avoiding file writes and by presenting objective, scope, options, required data, and a recommendation.

## Failure

The response still ended with an execution-style approval question:

- "추천 방향인 단순 수불장형 대시보드로 바로 구현해도 될까요?"
- "승인해주시면 ... 화면 파일을 생성해서 개발하겠습니다."

That is not enough for Superpowers-style brainstorming. The first brainstorm question must ask the user to choose or approve the domain direction, not to approve immediate implementation.

## Fix

- Strengthened `brainstorming-harness` so the first approval question must be a direction question, not an execution question.
- Updated the plugin default prompt to forbid generated-file, QA/browser, deliverable, implementation-start, and stack-bound approval promises before domain direction approval.
- Extended `session_skill_audit` to flag approval-plus-execution wording as `premature_execution_approval_question`.
- Added a regression test with the exact inventory-dashboard failure wording.

## Verification

Required verification before release:

- `python -B -m unittest tests.test_session_skill_audit tests.test_brainstorming_harness tests.test_superpowers_benchmark_alignment`
- `python -B -m src.orchestration.session_skill_audit <blind-session-log> --summary`
- Full repository tests and skill catalog/quality checks before publishing the marketplace wrapper.

## Expected Behavior

For a blind request such as "재고 입출고 관리 대시보드 개발해줘", the first response should stop at a question like:

> 단순 수불장형, 위치 재고형, LOT/시리얼형 중 어떤 운영 모델이 맞나요? 제 추천은 단순 수불장형입니다.

It should not mention target-folder file creation or implementation start until the user has separately approved the domain direction and the current-run brainstorm handoff exists.
