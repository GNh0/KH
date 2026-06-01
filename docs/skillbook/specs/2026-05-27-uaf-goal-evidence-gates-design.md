# UAF Goal Evidence Gates Design

## Goal

Make UAF review and release gates use `GoalState` evidence before reporting a workflow as complete.

## Scope

This phase connects the existing `GoalState` contract to workflow gate decisions:

- Workflow metadata should update `metadata["goal"]` from `active` to `complete` or `blocked`.
- QA and release gates should block when required goal evidence is missing.
- Gate results should expose required evidence, collected evidence, and missing evidence.
- Existing task failures should still fail/block the role graph before evidence-based completion can pass.

This phase does not implement natural-language evidence matching, browser execution, or real subagent code generation. Evidence matching is exact after simple normalization.

## Evidence Model

`GoalState.evidence_required` is the list of evidence keys needed before completion. `GoalState.evidence` is the list already collected by adapters, workers, or workflow helpers.

Workflow dispatch can add deterministic evidence:

- `design_doc` when the design document is non-empty.
- `target_files` when the workflow has at least one target file.
- `workflow dispatch completed` after worker fan-out/fan-in completes.

The evaluator compares normalized evidence keys case-insensitively and ignores surrounding whitespace.

## Completion Rules

1. If implementer tasks fail, the goal becomes `blocked` with a workflow failure reason.
2. If tasks succeed but required evidence is missing, the goal becomes `blocked` with the missing evidence listed.
3. If tasks succeed and all required evidence is present, the goal becomes `complete`.
4. If no goal is supplied, existing gate behavior remains unchanged.

## Gate Rules

When task results pass but goal evidence is missing:

- `spec-reviewer` remains `passed`.
- `code-quality-reviewer` remains `passed`.
- `qa-verifier` becomes `blocked`.
- `security-reviewer` remains `passed` unless upstream quality failed.
- `release-manager` becomes `blocked`.

This keeps implementation and code review separate from completion evidence, while preventing release from claiming completion without proof.

## Tests

Tests should prove:

- Goal evidence evaluation marks a goal `complete` when all required evidence is present.
- Goal evidence evaluation marks a goal `blocked` when required evidence is missing.
- Role gate results block QA and release when the evaluated goal is blocked by missing evidence.
- Local workflow results return updated `metadata["goal"]`, including collected evidence.
- Local dispatcher exposes the evaluated goal in adapter metadata.
