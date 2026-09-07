# KH UAF Full Skill/Harness Recheck - 2026-07-01

## Scope

This audit covered the KH UAF `codex-runtime` branch after the routing,
token-telemetry, deliverable, SQL-style, role-artifact, and usability fixes.
The target source version is `2.9.99`.

## Work Completed

- Re-ran KH front-door intake for a full repository skill/harness recheck.
- Preserved the distinction between skills that were actually applied and
  skills that were only selected for later execution.
- Cleaned user-facing and runtime skill text so packaged skill files no longer
  depend on Korean-only wording, while final answers remain user-language
  adaptive.
- Reworked type-aware deliverable exports for general, software, product, and
  investment workflows.
- Added software-profile role deliverable mapping so role artifacts align with
  exported software deliverables.
- Hardened brainstorming routing so a stack mention such as HTML/CSS/JS does
  not by itself approve implementation.
- Split Token Optimizer provider selection from actual optimization status and
  preserved not-used rationale and before/after payload telemetry.
- Updated SQL style checks to preserve localized business text and host-local
  formatter boundaries.
- Removed stale mojibake text from core runtime modules touched by this pass.

## Independent Review Evidence

- Veteran skill/harness review found a role-deliverable profile mismatch. The
  software profile now maps architect and QA roles to software deliverables such
  as `development_design.docx`, `screen_api_definition.docx`,
  `data_definition.xlsx`, and `test_verification_plan.xlsx`.
- LLM power-user review rated the candidate usable for practical plugin testing
  but blocked live release confidence until the installed marketplace cache
  updates from `2.9.98` to `2.9.99`.

## Verification Evidence

- Full unittest discovery: `785` tests passed.
- Skill catalog check: `41/41` packaged skills valid.
- Skill quality summary: `41/41` valid, lowest score `9.3`.
- Practical quality gate: KH-Bench `8/8` passed, practical confidence `10.0`.
- Practical release gate remained false only because the installed Codex
  marketplace cache was still `2.9.98` while source manifests were `2.9.99`.
- Packaged `skills/` text scan found no Hangul or replacement-character hits.

## Release Notes

The source branch must be committed and pushed to `origin/codex-runtime` before
Codex marketplace upgrade can install `2.9.99`. Until the user upgrades after
that push, any fresh Codex session may still load the older `2.9.98` cache.
