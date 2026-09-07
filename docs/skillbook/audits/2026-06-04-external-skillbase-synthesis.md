# External Skillbase Synthesis Audit

Date: 2026-06-04

## Trigger

Blind subagent session `019e90fa-abb8-7fa0-8ab3-6fe45b832103` passed the first brainstorm response, but after the user replied `1번 단순 재고 원장형으로 진행해줘`, it treated the option choice as implementation approval and generated files in a relative substitute folder.

## External Bases Read

- Superpowers `brainstorming`: brainstorm before code, ask one question at a time, propose 2-3 approaches, present design sections, write and self-review a spec, ask the user to review the spec, then transition only to planning.
- Compound Engineering: strategy/context -> brainstorm requirements -> plan -> work -> review -> compound learning, with planning/review carrying most of the quality load.
- RTK: optimize command output through command-aware filtering, raw/failure recovery, and agent-specific degradation instead of lossy generic summaries.

## Failure

KH was treating a direction choice as if it were execution approval. That skipped the Superpowers-style design/spec review loop and violated the target path guard by writing a same-name relative folder.

## Fix

- `request_classifier` now treats option choice without explicit implementation wording as `brainstorm_direction_choice_needs_design_review`.
- Front-door keeps `execution_gate.can_execute=false` for `1번 ... 진행해줘` style responses.
- `brainstorming-harness` now states that option choice continues design/spec review and another focused question.
- `session_skill_audit` flags `option_choice_treated_as_execution_approval` as P0 when implementation tools follow an option choice.
- Plugin prompt now describes the Superpowers/Compound/RTK synthesis explicitly.

## Expected Behavior

After a user chooses option 1, KH should ask the next scoped question, for example:

> 1번 단순 재고 원장형으로 잡겠습니다. 다음은 범위 확정입니다. 1차 버전에 안전재고 알림, 입출고 등록, 최근 이력, 품목 검색 중 무엇을 포함할까요?

It should not write files, scaffold, run QA, or generate deliverables until a reviewed KH handoff/spec exists and the user separately asks to implement or create files.
