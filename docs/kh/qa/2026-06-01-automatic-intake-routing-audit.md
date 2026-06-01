# KH automatic intake routing audit

Date: 2026-06-01
Branch: `codex-runtime`
Scope: Codex plugin skill routing, blind subagent usability tests, and session skill audit behavior.

## Problem

The user found a serious usability failure: if a user did not explicitly name KH, UAF, skill, harness, front-door, or router, the session could start source exploration or implementation without first applying the KH skill catalog and routing logic.

That makes the skill pack behave like a manual checklist instead of an automatically useful plugin.

## Key finding

Blind subagent tests in the same Codex session do not automatically prove newly edited plugin behavior.

The current Codex session and subagents inherit the already installed plugin cache. During this audit, the installed cache was:

- `C:\Users\KONEIT\.codex\plugins\cache\kh-uaf-marketplace\kh-uaf\2.9.26`

The local repository was being edited as `2.9.27`. The installed `2.9.26` cache did not contain the new `automatic_intake_harness` skill folder, so subagents launched before a marketplace upgrade could not be treated as proof that the new automatic intake contract was active.

## Fix applied

Added `automatic-intake-harness` as a first-class packaged skill and front-door runtime marker.

The front door now treats non-trivial ordinary user requests as KH-capable even when the request does not mention KH internals. Examples:

- "작은 HTML 할 일 도구를 만들고 검증해줘"
- "긴 pytest 로그에서 실패 원인만 요약해줘"
- "요구정의 문서와 검증 체크리스트를 만들어줘"

The expected split is:

- `runtime_applied_skills`: only the intake pieces that actually ran.
- `selected_not_executed_skills`: workflow skills selected for later execution but not yet run.
- `skill_status_summary`: per-skill status, application mode, evidence note, and blocked reason if applicable.

This prevents "I read a skill name, therefore I used the skill" overclaiming.

## Changed areas

- `skills/automatic_intake_harness/`
- `src/orchestration/kh_front_door.py`
- `src/orchestration/request_classifier.py`
- `src/orchestration/session_skill_audit.py`
- `src/skills/uaf_skill_catalog.py`
- `README.md`
- `README.ko.md`
- `SKILL.md`
- `plugin.json`
- `.codex-plugin/plugin.json`
- `.agents/plugins/kh-uaf/skills/kh-uaf/SKILL.md`

## Verification already run

These checks validate the repository working tree, not the already installed Codex plugin cache:

```powershell
python -B -m src.skills.uaf_skill_catalog --check
```

Result:

- `success: true`
- `total_skills: 39`
- `valid_skills: 39`
- `invalid_skills: 0`

```powershell
python -B -m src.benchmarks.kh_bench_verified --summary
```

Result:

- 8/8 tasks passed
- unresolved task list was empty

```powershell
python -B -m src.benchmarks.practical_quality_gate --summary
```

Result on `codex-runtime`:

- KH-Bench passed 8/8
- `release_ready: false`
- blocking finding: `static skill structure gate failed`

Interpretation: `codex-runtime` is the slim Codex install target and does not contain the development `tests/` tree. Full static quality/release validation must be run on `main` after the same changes are applied there. The runtime branch still needs catalog, smoke/demo, front-door, stale-cache, and import checks before publishing.

```powershell
python -B skills\automatic_intake_harness\scripts\smoke_check.py
```

Result:

- support files resolved
- implementation targets resolved

```powershell
python -B skills\automatic_intake_harness\scripts\demo.py --output-dir C:\Users\KONEIT\Documents\Codex\kh-automatic-intake-demo
```

Result:

- ordinary prompts routed through front-door intake
- runtime-applied skills included `automatic-intake-harness`, `plugin-composition-policy`, `request-complexity-router`, and `skill-catalog`

```powershell
python -B -m src.orchestration.kh_front_door --prompt "Build a small HTML todo tool and verify it" --project C:\Users\KONEIT\Desktop\Jang\SKillsTest --host codex --summary
```

Result:

- classified as heavy/software/role_dag
- KH selected as controller
- runtime-applied skills were limited to the four front-door runtime skills
- implementation, review, QA, role audit, and branch finishing skills were selected but not falsely reported as executed

```powershell
python -B -m src.orchestration.kh_front_door --prompt "Summarize this long pytest log and preserve the failing test name, file line, assertion values, and exit code" --project C:\Users\KONEIT\Desktop\Jang\SKillsTest --host codex --summary
```

Result:

- classified as medium/skill_read
- selected `command-output-harness` and `token-optimizer`
- runtime-applied skills remained limited to front-door intake

During this audit, the pytest-log prompt initially fell through to ambiguous/clarify before `command-output-harness` selection. The classifier was fixed so command-output requests are detected before context-free ambiguity handling.

```powershell
python -B -m src.orchestration.kh_front_door --prompt "Summarize this long pytest log and preserve the failing test name, file line, assertion values, and exit code" --project C:\Users\KONEIT\Desktop\Jang\SKillsTest --host codex --summary --host-skill-path C:\Users\KONEIT\.codex\plugins\cache\kh-uaf-marketplace\kh-uaf\2.9.25\skills\parallel_orchestration_harness\SKILL.md
```

Result:

- `front_door_status: blocked`
- stale cache path reported as `stale_kh_cache_path`
- warning told the host to resolve repo-local skills or the latest `kh-uaf` cache before continuing

```powershell
python -B -m src.orchestration.session_skill_audit --summary C:\Users\KONEIT\.codex\sessions\2026\06\01\rollout-2026-06-01T08-57-07-019e8078-4bde-7813-a1db-5025a3881511.jsonl
```

Result:

- historical session remained flagged
- `automatic-intake-harness` was marked missing for non-trivial KH-capable work
- stale KH cache paths were still detected
- incomplete subagent/review evidence was still detected

This is the intended behavior: the audit should not forgive the bad historical session just because the code has now been fixed.

## Blind subagent test interpretation

Earlier blind subagent tests showed that agents could complete simple tasks such as:

- static app generation
- long log summarization
- requirements/checklist document generation

However, because those subagents were launched from the already loaded session/plugin cache, those tests only prove ordinary task completion quality. They do not prove the new `2.9.27` automatic intake behavior until the plugin is upgraded and a fresh session/subagent context is created.

## Required post-upgrade validation

After publishing and upgrading the marketplace plugin, open a fresh Codex session and run blind tests that do not mention KH, UAF, skill, harness, plugin, front-door, router, or catalog.

Required scenarios:

1. Simple direct question
   - Expected: no heavy KH workflow.
   - Evidence: classified as light/direct or considered-not-needed.

2. Small project file generation
   - Expected: automatic intake runs before file exploration or edits.
   - Evidence: `runtime_applied_skills` includes the four front-door runtime skills.

3. Long pytest/build log summarization
   - Expected: command-output and token optimizer selected, with preserved failure facts.
   - Evidence: selected skills are separated from actually executed compression/summarization.

4. Document/deliverable generation
   - Expected: routed as document/domain work, with user-facing deliverables separated from internal harness evidence.

5. Dangerous/destructive request
   - Expected: high-risk classification and guard/review route before action.

## Release risk

Current source-level risk is reduced, but installed-plugin risk remains until the user upgrades the KH UAF marketplace entry and starts a fresh session. Any subagent spawned before that upgrade can still behave like the old cache.
