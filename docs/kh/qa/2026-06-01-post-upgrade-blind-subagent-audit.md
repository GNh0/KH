# KH UAF Post-Upgrade Blind Subagent Audit

Date: 2026-06-01
Plugin cache tested: `C:\Users\KONEIT\.codex\plugins\cache\kh-uaf-marketplace\kh-uaf\2.9.27`
Source branch: `codex-runtime`

## Scope

This audit checked whether ordinary non-trivial requests trigger KH UAF intake after a Codex marketplace upgrade, without naming KH, UAF, skill, harness, plugin, front door, or router in the delegated user prompt.

## Installed Cache Checks

Passed:

- `python -B -m src.skills.uaf_skill_catalog --check`
  - Result: `39 valid / 0 invalid`
- `python -B skills\automatic_intake_harness\scripts\smoke_check.py`
  - Result: support files and implementation targets resolved.
- `python -B skills\automatic_intake_harness\scripts\demo.py --output-dir C:\Users\KONEIT\Documents\Codex\kh-installed-automatic-intake-demo`
  - Result: success case and stale-cache blocked case produced valid JSON artifacts.
- `python -B -m src.orchestration.kh_front_door --prompt "Build a small HTML todo tool and verify it." --project "C:\Users\KONEIT\Desktop\Jang\SKillsTest" --host codex --summary`
  - Result: `heavy`, `software`, `role_dag`
  - Runtime applied: `automatic-intake-harness`, `plugin-composition-policy`, `request-complexity-router`, `skill-catalog`
  - Selected but not executed: role/lifecycle/review/QA/token/memory/subagent/verification harnesses.
- `python -B -m src.orchestration.kh_front_door --prompt "Summarize this long pytest log and preserve the failing test name, file line, assertion values, and exit code." --project "C:\Users\KONEIT\Desktop\Jang\SKillsTest" --host codex --summary`
  - Result: `medium`, `general`, `skill_read`
  - Selected but not executed: `command-output-harness`, `token-optimizer`, `workflow-usability-harness`, `context-state-harness`.
- `python -B -m src.orchestration.kh_front_door --prompt "Explain what a plugin marketplace is." --project "C:\Users\KONEIT\Desktop\Jang\SKillsTest" --host codex --summary`
  - Result: `light`, `general`, `direct_answer`
  - This proves simple concept questions stay cheap.

Failed or blocked:

- `python -B -m src.benchmarks.practical_quality_gate --summary` from the installed cache failed.
  - Cause: installed runtime does not include repository `tests/test_*.py`.
  - Fix direction: fail closed with an explicit source-test availability finding instead of crashing or claiming release quality from an installed runtime cache.

## Blind Subagent Scenarios

Subagents received ordinary user prompts that did not mention KH, UAF, skill, harness, plugin, front door, or router.

### Static Todo App

Prompt: create a static HTML todo app with add, toggle, delete, localStorage, and mobile responsiveness.

Outcome:

- Work artifact created: `C:\Users\KONEIT\Desktop\Jang\SKillsTest\post-upgrade-blind-app\index.html`
- Functional verification passed by the subagent.
- Session audit result: `automatic-intake-harness` was required but absent.
- Issue count: 24
- Runtime applied KH skills: 0

### Long Pytest Log Summary

Prompt: summarize a long pytest failure log while preserving failing test name, file/line, assertion values, and exit code.

Outcome:

- Output preserved the required failure facts.
- Session audit result: KH runtime evidence absent; this was a small enough task that no automatic-intake issue was raised, but plugin-composition evidence was still missing.
- Issue count: 2
- Runtime applied KH skills: 0

### Inventory Requirements Documents

Prompt: create user-facing requirements and screen/data/checklist documents for an inventory tool.

Outcome:

- Work artifacts created:
  - `C:\Users\KONEIT\Desktop\Jang\SKillsTest\post-upgrade-inventory-spec\01_요구정의서.md`
  - `C:\Users\KONEIT\Desktop\Jang\SKillsTest\post-upgrade-inventory-spec\02_화면_데이터_검증_체크리스트.md`
- Session audit result: `automatic-intake-harness` was inspected but not runtime-applied; related lifecycle/design/state skills were missing.
- Issue count: 18
- Runtime applied KH skills: 0

## Finding

The installed `2.9.27` cache contains the automatic intake skill and the executable front-door works when called directly. However, blind subagents did not reliably run KH intake from ordinary task wording even though the KH skill list was visible in the session system context. This means the current plugin is not yet sufficient to guarantee automatic KH use inside delegated agents.

The correct claim is:

- Direct front-door CLI and installed cache routing: working.
- Honest separation of `runtime_applied_skills` and `selected_not_executed_skills`: working in CLI output.
- Blind subagent automatic adoption without controller-provided intake evidence: not reliable.

## Changes Made After Audit

- Shortened `.codex-plugin/plugin.json` default prompt for version `2.9.28` so the first instruction is the automatic-intake rule instead of a long feature list.
- Added explicit root-skill guidance that a controller should run front-door intake before delegating non-trivial subagent work, then audit returned work.
- Updated `practical_quality_gate` so installed runtimes without source tests fail closed with an explicit `source test evidence availability` finding instead of crashing.
- Updated skill audit target handling so missing packaged test modules are represented as packaged/source test references instead of uncaught import failures.

## Residual Risk

This is still a host-compliance limitation. A Codex skill/plugin can strongly instruct the model, provide a short default prompt, and expose an executable front-door, but it cannot forcibly intercept every future subagent task unless the host runtime itself runs front-door intake before delegation. For reliable delegated workflows, the controller must call `kh_front_door` before `spawn_agent` and include only the bounded selected task packet.
