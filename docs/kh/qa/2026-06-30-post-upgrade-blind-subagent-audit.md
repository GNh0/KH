# 2026-06-30 Post-Upgrade Blind Subagent Audit

## Context

After the user upgraded the KH UAF Codex marketplace cache to 2.9.89, two fresh subagents were started without mentioning KH, UAF, skills, or harnesses in the task prompts.

- Dashboard brainstorm agent: `019f16a2-ff17-7461-b5f8-485a93ff93b2`
- SQL formatting agent: `019f16a3-32b5-7761-a53d-38dca44024c3`
- Independent audit reviewer: `019f16a4-bcb5-7c82-a929-b1b186bec3c0`

## Findings

The dashboard brainstorm agent correctly ran the KH front door, stopped before target folder inspection or file creation, and returned an operating-model brainstorm instead of implementing immediately. The previous audit still failed because:

- `session_skill_audit` treated front-door bootstrap command text as implementation evidence.
- SQL requirement detection used broad session text, so front-door JSON terms such as `execute`, `Get-Content`, `source_reads`, and `create` could trigger `sql-formatting-style-harness` in a non-SQL brainstorm session.
- Immediate-next evidence did not accept a visible brainstorming response as runtime application.

The SQL formatting agent used the host-local `sql-formatting` skill, but did not run the KH `sql-formatting-style-harness` verifier. That remains a real behavior gap for old cache versions. The skill frontmatter now makes the KH verifier a companion trigger for direct SQL formatting, cleaning, standardizing, refactoring, or generation requests.

## Changes

- Scoped SQL required-skill detection to real user SQL requests and user-facing SQL answers instead of whole-session text.
- Accepted visible first-response brainstorming as immediate-next application only when it stops execution and meets the full first-visible-response contract.
- Excluded front-door prompt bootstrap commands from brainstorming execution-bypass samples.
- Avoided treating a first-turn option question as missing handoff unless the agent claims brainstorming completion or moves to planning/implementation.
- Moved the brainstorming first-visible-response contract near the top of `brainstorming-harness`.
- Broadened `sql-formatting-style-harness` frontmatter so Codex can select it alongside the host-local `sql-formatting` skill.

## Evidence

Commands run after the patch:

```text
python -B -m unittest discover -s tests -p test_session_skill_audit.py
Result: 113 tests OK

python -B -m src.orchestration.session_skill_audit --summary <dashboard-session> <sql-session>
Result: dashboard session passed; SQL session still failed in old 2.9.89 logs because verifier was not selected before this patch.

python -B -m src.skills.uaf_skill_catalog --check
Result: 41 valid / 0 invalid
```

## Follow-up Review

Independent reviewer `019f16bd-a39d-7ae3-987b-55aaba9a1c7e` found that the 2.9.90 patch reduced the SQL false positive but could weaken brainstorming evidence: a thin option-picker response could avoid the immediate-next failure while also avoiding the shallow-brainstorming issue.

2.9.91 tightens that gap:

- A visible brainstorming response is runtime-applied only when the first response contract has no missing marker group.
- Thin option-picker responses are detected as brainstorming attempts even when they do not include recommendation wording.
- Missing brainstorm marker groups now always report `shallow_visible_brainstorming` instead of only reporting selected critical combinations.
- Regression coverage now asserts that a thin response with options still raises `shallow_visible_brainstorming` and does not satisfy `immediate_next_skills`.

## Remaining Verification

After publishing 2.9.91 and upgrading the marketplace cache, run another blind SQL formatting subagent. Expected behavior: both the host-local `sql-formatting` skill and KH `sql-formatting-style-harness` should be selected, and the session audit should no longer report `missing_sql_formatting_style_verifier`.
