# KH Documentation Boundary

This directory contains both current product-surface docs and historical design or audit evidence.

## Current

Use these repo-root paths as the current operating contract for the installed plugin and runtime surface:

- `README.md`
- `README.ko.md`
- `SKILL.md`
- `plugin.json`
- `.codex-plugin/plugin.json`
- `docs/README.md`

Current docs should describe what KH requires, records, or audits. They should not imply that every host or subagent silently complies without the installed plugin prompt, active session context, and session-log evidence.

## Historical

Treat these paths as background evidence, not as the current install or prompt contract:

- `docs/skillbook/**`
- dated files under `docs/kh/qa/**`
- dated files under `docs/kh/reports/**`
- standalone postmortems under `docs/kh/**`

Historical docs are useful for rationale, regression context, and release notes. If they conflict with the current README, root `SKILL.md`, or plugin manifests, update the current product surface first and cite the historical file only as evidence.

## Install Ref Terms

- Marketplace descriptor ref: `main`, used by Codex to read `.agents/plugins/marketplace.json`.
- Plugin source ref: `codex-runtime`, the slim runtime branch installed from the marketplace descriptor.
- Installed cache: `$CODEX_HOME/plugins/cache/.../kh-uaf/<version>`, a generated copy loaded by a Codex session.

A session is stale when the installed cache version, active skill paths, or active plugin prompt still point to an older KH build. The `main` marketplace descriptor ref alone is not stale.
