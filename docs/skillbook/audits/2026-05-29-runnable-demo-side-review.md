# Runnable Demo SIDE Review

## Scope

This audit records the 2026-05-29 SIDE review round for KH UAF runnable skill demos.

## Implemented

- Added `scripts/demo.py` to all 27 packaged skills.
- Added `src.skills.demo_scenarios` as the shared deterministic demo runner.
- Added `tests/test_skill_demos.py` to run every demo from both repository root and skill-folder cwd.
- Extended `src.skills.uaf_skill_quality` so demo execution is a release gate beside smoke checks and target audits.
- Added generated-file manifest enforcement so every file created under the demo output directory is declared in the JSON `artifacts` list.
- Moved default demo output outside the repository root.

## SIDE Findings Addressed

- Artifact validation is fail-closed: validation evidence containing failures marks the artifact invalid.
- Quality gate now validates the emitted demo schema, not only top-level keys.
- `verification.artifacts_validated` is explicit.
- Default no-argument demo output uses temp KH-UAF demo storage rather than `.demo-output` in the repo.
- Runtime support files are auto-declared through `demo_file_manifest.json`.
- Blocked/failure cases now include remediation guidance and preserve `failed` when the underlying contract reports failure.

## Verification

- `python -m unittest tests.test_skill_demos`
- `python -m src.skills.uaf_skill_catalog --check`
- `python -m src.skills.uaf_skill_quality --summary`
- `python -m unittest discover -s tests`

All checks passed after the SIDE fixes.
