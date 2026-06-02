# Post-Upgrade E2E Subagent Audit - 2026-06-02

## Scope

This audit records the live post-upgrade check for KH UAF `2.9.43` before the follow-up fix released as `2.9.44`.

The test target was:

```text
C:\Users\KONEIT\Desktop\Jang\SKillsTest\AutoRouteClean_20260602_I
```

The blind first prompt sent to a fresh subagent did not mention KH, UAF, skills, harnesses, audit, or plugin internals:

```text
C:\Users\KONEIT\Desktop\Jang\SKillsTest\AutoRouteClean_20260602_I 폴더에서 창고 재고 입출고 업무 프로세스 방향 잡아줘
```

The follow-up approval prompt also did not mention KH:

```text
A안으로 확정. 이제 그 방향으로 폴더 안에 업무정의서랑 처리흐름도 수준까지 만들어줘. 구현 코드는 아직 만들지마.
```

## Live Results

- Installed cache used by the subagent: `C:\Users\KONEIT\.codex\plugins\cache\kh-uaf-marketplace\kh-uaf\2.9.43`.
- First turn classification: medium operations direction-setting.
- Front-door ran from the installed plugin cache before target folder inspection.
- The exact target folder was checked and found empty.
- No sibling folders, older scenario folders, or `MEMORY.md` were used to seed the answer.
- First final answer stopped at direction approval and did not expose raw KH fields such as `front_door_status`, `runtime_applied_skills`, `brainstorming_status`, `valid=true`, or `missing=[]`.
- After approval, the subagent created two user-facing Markdown deliverables and no code files:
  - `01_업무정의서_창고재고입출고.md`
  - `02_처리흐름도_창고재고입출고.md`

## Verification Evidence

Commands run from `C:\Users\KONEIT\Desktop\Jang\KH`:

```text
python -B -m src.orchestration.session_skill_audit --summary "C:\Users\KONEIT\.codex\sessions\2026\06\02\rollout-2026-06-02T14-48-31-019e86e0-5bc6-70f1-9b22-30912c865dec.jsonl"
Result after fix: issue_count=0, required_missing_evidence=0, required_unaccepted=0

python -B -m unittest tests.test_session_skill_audit -v
Result: 33 tests OK
```

Generated test-folder file check:

```text
Get-ChildItem C:\Users\KONEIT\Desktop\Jang\SKillsTest\AutoRouteClean_20260602_I -Recurse
Result: 2 Markdown files, 0 code files
```

Final-answer leakage check:

```text
HasKhRawStatus=False
MentionsMemory=False
MentionsSiblingReuse=False
HasApprovalStop=True
```

## Fix From This Audit

The first post-approval session audit produced a false positive for `snapshot-state-harness`.

Root cause: `session_skill_audit` treated the selected skill name `worktree-isolation-harness` inside front-door output as evidence of a real git/worktree workflow because it matched the substring `worktree`. That incorrectly caused `snapshot-state-harness` to become required for a run that only created new Markdown files in an empty folder.

Fix:

- `session_skill_audit` now requires actual worktree workflow evidence such as `.worktrees`, `git worktree`, `git commit`, or `git push`.
- The skill name `worktree-isolation-harness` no longer triggers git/worktree requirements by itself.
- Negated phrases such as `no git or worktree command` do not trigger worktree requirements.
- Regression tests now cover both the false-positive case and the real git/worktree case.

## Release Note

The fix is included in plugin version `2.9.44`.
