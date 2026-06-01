# KH Front-Door Routing Audit - 2026-06-01

## Scope

This audit records a usability failure found in Codex session `019e8078-4bde-7813-a1db-5025a3881511`.

The user explicitly asked the assistant to use the KH plugin for work under `C:\Users\KONEIT\Desktop\Source\TY\C_KONE110_codex`, but the session began source/work commands before KH front-door routing evidence appeared.

## Finding

Requiring the user to name every individual KH skill or harness defeats the purpose of a packaged skillbook.

Expected behavior:

1. A request such as "use KH", "use KH plugin", "KH skills", "KH harness", or `/kh:*` is enough to trigger KH.
2. KH first inspects the root guide or skill catalog.
3. KH applies `plugin-composition-policy` and `request-complexity-router`.
4. KH selects the minimal skill bundle automatically.
5. KH records selected, considered, skipped, or blocked skills with evidence.
6. Only after that front-door step should source reads, edits, role DAG work, or deliverable generation begin.

Observed failure:

- The session started source exploration before front-door evidence.
- Existing `session-skill-audit` could show many skills as observed later in the session, but it did not originally flag the initial routing miss.

## Remediation

Added `session-skill-audit` detection for explicit KH requests followed by source/work commands before front-door evidence.

The audit now emits a P1 issue:

```json
{
  "skill": "plugin-composition-policy",
  "status": "missing_front_door",
  "severity": "P1"
}
```

The fix also updates the root `SKILL.md`, the Antigravity/Codex wrapper skill, README files, and plugin default prompt so the contract is visible to hosts.

## Verification Evidence

Target session audit after the fix:

```powershell
python -B -m src.orchestration.session_skill_audit --summary "C:\Users\KONEIT\.codex\sessions\2026\06\01\rollout-2026-06-01T08-57-07-019e8078-4bde-7813-a1db-5025a3881511.jsonl"
```

Result summary:

- `plugin-composition-policy`: `missing_front_door`, P1.
- Trigger sample: user assigned the copied `C_KONE110_codex` folder and said KH plugin would be used.
- First work sample: source listing began with `Get-ChildItem` before KH front-door evidence.

Regression coverage added:

- English KH plugin request starts work first -> P1 `missing_front_door`.
- Korean KH plugin request starts work first -> P1 `missing_front_door`.
- KH plugin request runs skill catalog and routing evidence first -> no `missing_front_door`.

Validation run:

- `python -B -m unittest tests.test_session_skill_audit tests.test_plugin_packaging tests.test_plugin_composition_policy tests.test_superpowers_replacement_layer` -> 39 tests passed.
- `python -B -m unittest tests.test_docs_branding tests.test_session_skill_audit tests.test_plugin_packaging tests.test_plugin_composition_policy tests.test_superpowers_replacement_layer` -> 42 tests passed after removing a mojibake compatibility marker.
- `python -B -m unittest discover -s tests` -> 469 tests passed.
- `python -B -m src.skills.uaf_skill_catalog --check` -> 38 valid / 0 invalid.
- `python -B -m src.skills.uaf_skill_quality --summary` -> success, lowest quality score 9.3, no low-quality skills.
- `python -B -m src.benchmarks.practical_quality_gate --summary` -> release ready, 8/8 KH-Bench tasks passed, practical confidence score 10.0.
- `python -m json.tool plugin.json`, `.codex-plugin/plugin.json`, and `.agents/plugins/marketplace.json` -> valid JSON.
- `git diff --check` -> no whitespace errors.

## Branch Structure

`main` keeps tests, docs, audits, and development evidence.

`codex-runtime` is the slim branch used by the Codex marketplace install path from `.agents/plugins/marketplace.json`. Runtime behavior changes must be pushed to `codex-runtime`; tests and this audit remain on `main`.
