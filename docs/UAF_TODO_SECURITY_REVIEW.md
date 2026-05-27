# UAF TODO And Security Review

Date: 2026-05-28

## Scope

This review covers the current lightweight host skill/harness direction. It intentionally excludes real-time dashboards, distributed servers, Hermes/OpenClaw providers, and concrete Browser/QA sidecars because those are not required for the current personal-use target.

## Checks Run During This Pass

- Focused resume handoff tests.
- Static scan for TODO/FIXME, credential-like strings, subprocess usage, shell execution, and unsafe execution markers.
- Documentation pass over README, root SKILL, goal/context harnesses, and the active work ledger.

## Completed In This Pass

- Added `HandoffSnapshot`.
- Added `ResumeHandoff`.
- Added `.uaf/state/resume_handoff.json`.
- Added `.uaf/state/resume_handoff.md`.
- Integrated resume handoff generation into workflow completion when goal metadata exists.
- Added tests for contract round-trip, missing state handling, handoff generation from goal/artifact state, and workflow metadata integration.

## Priority TODO

### P1: Remove Default Webhook API Key Fallback

Current state:

- `src/api/server.py` and `src/tasks/workflows.py` still default to `antigravity-secret-key-v2`.
- This is acceptable only for local development, but it is a weak default if the optional webhook server is exposed.

Recommended next action:

- Make webhook server startup fail closed when `AG_API_KEY` is missing, or generate a clearly local-only random dev token.
- Update `plugin.json` and README so no reusable default secret is presented as a production value.

### P1: Add Public Export Redaction For Handoff Files

Current state:

- Runtime handoff files are project-local and may include absolute local paths.
- This is useful for local continuation but should not be shared outside the workspace without redaction.

Recommended next action:

- Add a `redacted=True` export path that removes `project_dir`, local artifact paths, and local state paths.
- Keep full local handoff unchanged for private workspace use.

### P2: Add Git State To Resume Handoff

Current state:

- `resume_handoff` captures goal, evidence, artifacts, and memory context.
- It does not yet capture git branch, head sha, or dirty-file summary.

Recommended next action:

- Add optional git state metadata so a future host session can detect stale or conflicting handoffs before continuing.

### P2: Add JSON Schema Validation For Host Contracts

Current state:

- Contracts are dataclass-based and tested, but host/sidecar JSON boundaries do not publish schemas.

Recommended next action:

- Generate or maintain JSON schema files for `AdapterRequest`, `WorkflowTaskResult`, `WorkflowDispatchResult`, `HandoffSnapshot`, and `ArtifactManifest`.

### P2: Add Host Plugin Smoke Checklist

Current state:

- UAF is designed as a Codex/Antigravity skill/harness package, but manual host smoke steps are not yet documented as a checklist.

Recommended next action:

- Add a short checklist proving a host session can read `SKILL.md`, inspect `.uaf/state/resume_handoff.md`, and continue from missing evidence without previous chat context.

### P3: Add Domain-Specific Artifact Validators Only When Needed

Current state:

- Domain orchestration is intentionally generic.

Recommended next action:

- Add validators only for domains that are actually used repeatedly. Do not prebuild investment, equipment, software, or legal-specific validation until there is a real recurring workflow.

## Explicit Non-Goals For Now

- Real-time dashboard.
- Distributed server control plane.
- Hermes/OpenClaw provider implementation.
- Bundled Playwright Browser/QA sidecar.
- Native Antigravity SDK adapter without a stable host API.
