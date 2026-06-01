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

## Follow-Up Audit: Marketplace Ref and Mixed Blind Results

Time: 2026-06-01 12:30-12:45 KST

Trigger: A new ordinary Codex session, `019e813d-c26b-7d82-82df-d6f052c83dc7`, was started with the plain request "make a simple web dashboard". The user reported that KH UAF was still not being picked up automatically.

### Local Marketplace Configuration Finding

- Config file: `C:\Users\KONEIT\.codex\config.toml`
- Marketplace block: `[marketplaces.kh-uaf-marketplace]`
- Expected local marketplace ref: `main`
- Local marketplace revision observed: `078adea27a0f0e2db15fb511b97e69341a785dd6`
- Installed cache present during the audit: `C:\Users\KONEIT\.codex\plugins\cache\kh-uaf-marketplace\kh-uaf\2.9.27`
- Marketplace descriptor checked: `.agents/plugins/marketplace.json`
- Plugin source ref in marketplace descriptor: `codex-runtime`
- Active source revision at the time of the audit: `c42892c6824d2aa4aa143665f7d40e49ec6d28f0`
- Active source plugin version at that audit point: `2.9.28`

Correction: the local Codex marketplace `ref = "main"` is expected for this setup. It fetches the marketplace descriptor from `main`; the descriptor itself already points the `kh-uaf` plugin source at `codex-runtime`. Therefore `ref = "main"` is not evidence that the plugin should reinstall from `main`.

Temporary local action and correction:

- The marketplace ref was briefly changed from `main` to `codex-runtime` during the audit because the marketplace-ref layer was misread as the plugin-source layer.
- This was incorrect for the user's intended marketplace setup.
- The config was restored to `ref = "main"`.
- A backup remains at `C:\Users\KONEIT\.codex\config.toml.kh-uaf-ref-backup`.

The remaining live issue is not that the marketplace ref was `main`. The remaining issue is that the active Codex session and installed cache still exposed plugin `2.9.27` during the test. A fresh marketplace upgrade/reload must be verified by checking the installed cache path and the active session skill list for `2.9.28`.

### Session `019e813d-c26b-7d82-82df-d6f052c83dc7`

Plain prompt category: simple web dashboard build.

Audit command:

```bash
python -B -m src.orchestration.session_skill_audit --summary "C:\Users\KONEIT\.codex\sessions\2026\06\01\rollout-2026-06-01T12-32-48-019e813d-c26b-7d82-82df-d6f052c83dc7.jsonl"
```

Result:

- `runtime_applied_skills`: 0
- `observed_skills`: 0
- Required skills: 20
- Required applied: 0
- Required missing evidence: 20
- Issue count: 22
- `automatic-intake-harness`: absent
- `plugin-composition-policy`: absent
- `request-complexity-router`: absent
- `skill-catalog`: absent

Manual log parsing showed that the session used the Browser skill and proceeded with static dashboard implementation and browser checks, but no KH front-door runtime evidence appeared. This is a real blind automatic-intake failure.

### Blind Subagent `019e813b-1ab8-7af2-93b9-78f2c7b6c50c`

Plain prompt category: static calculator app, no KH/UAF/skill/harness wording.

Result:

- Created: `C:\Users\KONEIT\Desktop\Jang\SKillsTest\post-upgrade-blind-calc\index.html`
- `runtime_applied_skills`: 4
- Runtime applied: `automatic-intake-harness`, `plugin-composition-policy`, `request-complexity-router`, `skill-catalog`
- Required skills: 25
- Required applied: 4
- Required missing evidence: 21
- Issue count: 22

This run proves that a blind subagent can sometimes pick up automatic intake from the installed KH skill. However, it still missed many downstream lifecycle, QA, deliverable, token, and verification harnesses. It also had failed verification attempts that were later reported as blocked/fallback rather than fully hidden.

### Blind Subagent `019e813b-36e2-7223-8b6e-257c9d63d97f`

Plain prompt category: user-facing customer inquiry requirements/checklist documents, no KH/UAF/skill/harness wording.

Result:

- Created two user-facing Markdown documents under `C:\Users\KONEIT\Desktop\Jang\SKillsTest\post-upgrade-blind-docs`.
- `runtime_applied_skills`: 0
- Required skills: 14
- Required applied: 0
- Required missing evidence: 14
- Issue count: 17
- `automatic-intake-harness`: absent

This is another blind automatic-intake failure.

### Controlled Subagent `019e813b-743c-7d23-a70f-9719b7002282`

This was not a blind test. The controller explicitly instructed the agent to run `kh_front_door` before summarizing a pytest log.

Result:

- Runtime applied: `automatic-intake-harness`, `plugin-composition-policy`
- Selected but not executed / inspected: command output and token-related follow-ups
- Output preserved failing test name, file/line, assertion values, and exit code.

This only proves that explicit controller-mediated intake works. It does not prove automatic blind adoption.

## Updated Conclusion

The post-upgrade state is mixed:

- Direct `kh_front_door` routing works.
- Controller-mediated routing works.
- One blind subagent picked up KH intake.
- Another blind subagent and the user's separate plain dashboard session did not pick up KH intake.
- The installed cache and active session skill list still exposed `2.9.27` during the audit even though the marketplace descriptor points the plugin source at `codex-runtime`, where `2.9.28` was available.

Therefore KH UAF should not claim that blind automatic adoption is solved. The honest claim is that automatic-intake instructions and audit tooling exist, but host/subagent compliance is still not deterministic unless the controller runs front-door intake before delegation or the Codex host provides a hard preflight hook.

## Follow-Up Fix: Install Layer Audit Command

Added after the marketplace-ref correction:

```bash
python -m src.orchestration.plugin_install_audit --summary
```

Purpose:

- Distinguish the Codex marketplace descriptor ref from the plugin source ref.
- Report that `ref = "main"` in `C:\Users\KONEIT\.codex\config.toml` is expected for this repository when `.agents/plugins/marketplace.json` points `kh-uaf` at `codex-runtime`.
- Compare the source manifest version with installed cache versions.
- Produce an `attention_required` status when the installed cache is behind source, without blaming the marketplace descriptor ref.

Current verification output after adding the command:

- Marketplace ref: `main`
- Plugin source ref: `codex-runtime`
- Source plugin version: `2.9.29`
- Installed cache version: `2.9.27`
- Status: `attention_required`

This keeps the failure cause separated:

- Install/cache freshness problem: active cache is behind source.
- Host/session reload problem: active session skill list can still point at an older cache until a fresh thread or reload.
- Blind auto-adoption problem: even with the skill present, subagent compliance is mixed unless the controller runs front-door intake or the host provides a hard preflight.
