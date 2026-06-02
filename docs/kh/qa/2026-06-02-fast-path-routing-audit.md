# Fast Path Routing Audit - 2026-06-02

## Scope

This audit records the fix for KH UAF sessions that were too slow or too heavy for medium/light direction-setting requests.

The target behavior is:

- run `always-on-front-door` automatically for non-trivial ordinary requests, even when the user does not name KH, UAF, skills, or harnesses;
- for direction-setting or brainstorming requests in an explicit empty/new folder, select a lightweight path and stop before implementation;
- avoid `MEMORY.md`, parent folder scans, sibling folder scans, GoalState, role DAG, QA/review gates, and document export before the user approves execution;
- do not append internal KH status lines to ordinary final answers;
- keep read-only commands from being counted as runtime skill evidence, while still flagging them as front-door order violations when they run before intake.

## Findings

The prior audit logic mixed two separate concepts:

- passive evidence filtering: `Get-Content`, `Select-String`, `Get-ChildItem`, and similar reads should not count as runtime application of a KH skill;
- front-door ordering: those same reads are still work-bearing when they happen before `always-on-front-door` on a non-trivial request.

That made one always-on regression test fail: a session could run `Get-ChildItem` before front-door and no longer show `always-on-front-door` as required missing.

Subagent blind testing also showed the old installed cache still printed an internal `KH 상태` line in an ordinary brainstorming final answer. The repository changes suppress that in the plugin prompt and brainstorming skill instructions.

## Changes

- Added a plugin fast path for medium/light direction-setting, brainstorming, process direction, and scope-choice requests in explicit empty/new folders.
- Updated `always_on_front_door` and `brainstorming_harness` instructions to keep internal KH routing evidence out of ordinary final answers.
- Narrowed token optimizer postmortem gating so cumulative total tokens alone do not force compression when active-context pressure is low.
- Narrowed session audit requirements so generic read-only output and subagent mentions do not over-trigger unrelated harnesses.
- Restored always-on required coverage for ordinary work requests such as build/create/modify/dashboard/verify.
- Removed unreachable audit code left behind after renderable artifact routing was narrowed.

## Evidence

Commands run from `C:\Users\KONEIT\Desktop\Jang\KH`:

```text
python -B -m unittest tests.test_kh_front_door_always_on tests.test_session_skill_audit -v
Result: 34 tests OK

python -B -m unittest discover -s tests -f -v
Result: 508 tests OK

python -B -m src.skills.uaf_skill_catalog --check
Result: success=true, valid_skills=40, invalid_skills=0

python -B -m src.skills.uaf_skill_quality
Result: quality_success=true, lowest_quality_score=9.3, low_quality_skills=[]

python -B -m src.orchestration.kh_front_door --prompt "<empty-folder inventory process direction request>" --project "<empty target folder>" --host codex --summary
Result: classification=medium/operations, recommended_execution=skill_read, selected_not_executed_skills includes brainstorming-harness, token-optimizer, workflow-usability-harness

python -B -m src.orchestration.session_skill_audit --summary "C:\Users\KONEIT\.codex\sessions\2026\06\02\rollout-2026-06-02T13-45-47-019e86a6-ef57-7592-94f6-ba236fbece94.jsonl"
Result: issue_count=0, runtime_applied_skills=5, token_optimizer_status=considered_not_needed
```

## Remaining Live Validation

The repository version is ready for plugin upgrade testing. A new Codex subagent or new chat should verify the installed cache version after upgrade and re-run a blind prompt without KH terms:

```text
C:\Users\KONEIT\Desktop\Jang\SKillsTest\<new-empty-folder> 폴더에서 창고 재고 입출고 업무 프로세스 방향 잡아줘
```

Expected live behavior:

- front-door runs automatically;
- brainstorming is selected;
- no sibling project artifacts are read;
- no files are created before approval;
- final answer does not include raw KH status fields.
