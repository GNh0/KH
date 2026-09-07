# 2026-06-04 Blind Subagent Routing Audit

## Purpose

Verify that a fresh subagent can route an ordinary user request through the installed KH UAF front-door without the user naming KH, UAF, skills, harnesses, brainstorming, or plugin internals.

## Blind Prompt

```text
C:\Users\KONEIT\Desktop\Jang\SKillsTest\RetestAutoRoute_20260604_A 폴더에서 재고 입출고 관리 대시보드 개발해줘.
```

This prompt intentionally did not mention KH, UAF, front-door, skills, harnesses, plugin, audit, memory, or brainstorming.

## Evidence

- Subagent id: `019e8fea-06ea-7510-802f-48427f9a1f36`
- Session log: `C:\Users\KONEIT\.codex\sessions\2026\06\04\rollout-2026-06-04T08-55-39-019e8fea-06ea-7510-802f-48427f9a1f36.jsonl`
- Installed cache at test time: `2.9.48`
- Package version after this patch: `2.9.49`

## Observed Behavior

The subagent did not implement or scaffold files. It checked only the exact target folder, reported that the folder did not exist, proposed three implementation directions, recommended static HTML/CSS/JS, and asked for approval before creating the folder and files.

Target folder check after completion:

```text
TARGET_FOLDER_MISSING
```

No `index.html`, `styles.css`, `app.js`, `.kh`, `.uaf`, or generated artifacts were created in the requested target.

## Session Skill Audit Result

Command:

```powershell
python -B -m src.orchestration.session_skill_audit --summary "C:\Users\KONEIT\.codex\sessions\2026\06\04\rollout-2026-06-04T08-55-39-019e8fea-06ea-7510-802f-48427f9a1f36.jsonl"
```

Result:

```json
{
  "issue_count": 0,
  "runtime_applied_skill_names": [
    "always-on-front-door",
    "automatic-intake-harness",
    "plugin-composition-policy",
    "request-complexity-router",
    "skill-catalog"
  ],
  "required_missing_skill_names": [],
  "required_unaccepted_skill_names": []
}
```

This confirms the earlier failures were not reproduced:

- `missing_front_door`: not present
- `brainstorming_execution_gate_bypassed`: not present
- `cross_chat_memory_leak`: not present
- implementation-before-approval: not observed

## Fix Applied During Audit

`session_skill_audit` previously counted the front-door runtime output `blocked_actions.browser_qa` as if browser QA had already occurred. That was wrong: in this case it meant browser QA was blocked until the brainstorming gate was satisfied.

The audit now scans browser/local-app QA requirements by active text chunk and excludes front-door runtime output from that specific QA trigger. It also distinguishes browser storage direction text, such as `browser localStorage`, from real browser QA evidence such as Playwright, screenshot, localhost, or opened/verified browser checks.

Regression tests added:

- `test_browser_storage_direction_does_not_require_qa_gate`
- `test_browser_verification_still_requires_qa_gate`

## Verification

```powershell
python -B -m unittest tests.test_session_skill_audit.SessionSkillAuditTests.test_browser_storage_direction_does_not_require_qa_gate tests.test_session_skill_audit.SessionSkillAuditTests.test_browser_verification_still_requires_qa_gate
python -B -m unittest discover -s tests
python -B -m src.skills.uaf_skill_catalog --check
python -B -m src.skills.uaf_skill_quality --summary
python -B -m src.orchestration.session_skill_audit --summary "C:\Users\KONEIT\.codex\sessions\2026\06\04\rollout-2026-06-04T08-55-39-019e8fea-06ea-7510-802f-48427f9a1f36.jsonl"
```

Observed results:

- Targeted regression tests: `2 tests OK`
- Full unit suite: `517 tests OK`
- Catalog check: `40 valid / 0 invalid`
- Skill quality: `success=true`, `lowest_quality_score=9.3`, `low_quality_skills=[]`
- Blind subagent session audit: `issue_count=0`

## Remaining Note

The tested installed cache was `2.9.48`. This patch bumps package metadata to `2.9.49`; the Codex marketplace cache must be upgraded after the commit is pushed for newly spawned agents to use the patched audit code from the plugin cache.
