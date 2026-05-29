# Superpowers Benchmark Notes

Date: 2026-05-30

## Purpose

This note records how KH UAF should continue benchmarking against external skillbooks without becoming a thin copy of them.

Superpowers is strong at agent behavior activation: short trigger descriptions, mandatory workflow rules, pressure scenarios, and explicit verification gates. Role-stack skillbooks are strong at CEO/advisor, design, review, QA, release, and learning commands. KH UAF is broader: it adds portable skill packaging, Python contracts, role DAGs, evidence gates, memory/goal state, SIDE regression, benchmarks, and host adapter boundaries. The useful direction is to absorb external behavior discipline into KH-native skills and harnesses.

## What To Adopt

| Superpowers strength | KH adoption target |
| --- | --- |
| Strong front-door triggers | Keep KH skill descriptions trigger-focused, especially `brainstorming-harness`, `development-lifecycle-harness`, and `request-complexity-router`. |
| One-question-at-a-time discovery | Use in `brainstorming-harness` before product, SaaS, feature, or unclear design work. |
| Written plans before implementation | Keep `architect-pipeline`, `goal-state-harness`, and `development-lifecycle-harness` as the planning bridge. |
| TDD and verification-before-completion | Preserve in `quality-gates-harness`, `development-lifecycle-harness`, and release gates. |
| Subagent review discipline | Preserve through `subagent-review-pipeline`, `review-gate-harness`, and role DAG reviewers. |
| Compound engineering | Make `workflow-skill-distiller`, `context-state-harness`, `memory-state-harness`, and scenario regression the KH Compound step. |
| Project-local artifacts | Keep KH deliverables in `docs/` and optional state in `.uaf/`; treat `.superpowers/` and `docs/superpowers/` as Superpowers-owned when both systems are installed. |
| Worktree isolation | Use project-local `.worktrees/<task>` or equivalent isolated workspaces for concurrent file-editing workers. |

## Role-Stack Benchmark Coverage

| Role-stack pattern | KH adoption target |
| --- | --- |
| Office-hours style discovery before commitment | `brainstorming-harness` asks one focused question at a time, captures options and decisions, then emits `brainstorm_handoff` for `architect-pipeline`. |
| CEO and advisor plan challenge | `orchestration-role-graph` requires `ceo`, `advisor`, and `product-strategist` roles before architecture and implementation in heavy workflows. |
| Engineering, design, and developer-experience plan reviews | `architect-pipeline`, `domain-orchestration-harness`, `review-gate-harness`, and `subagent-review-pipeline` preserve design, acceptance, implementation, review, and artifact evidence instead of relying on a single prompt. |
| Browser, QA, and release checks | `qa-gate-harness`, `artifact-render-qa-harness`, `browser-qa-boundary`, and `quality-gates-harness` convert checks into GoalState evidence and block release when adapters or evidence are missing. |
| Security officer and safety guardrails | `guard-policy-harness`, `command-hook-policy-harness`, `security-reviewer`, and release gates require command, path, credential, and sandbox risks to be recorded before release. |
| Learn, retro, and project memory | `compound-engineering-harness`, `workflow-skill-distiller`, `memory-state-harness`, and `scenario-evaluation-harness` capture scoped learnings, skill updates, and regression checks after review. |
| Cross-model or second-opinion review | `subagent-review-pipeline`, `review-gate-harness`, and host adapter contracts preserve independent reviewer outputs without assuming one specific LLM provider. |
| Continuous checkpoint and restore | `context-state-harness`, `goal-state-harness`, `snapshot-state-harness`, and `.uaf/state` ledger files provide resume-safe state without requiring external host-specific commits. |

## What Not To Copy

- Do not require `.superpowers/` paths for KH-owned state.
- Do not transition KH workflows into Superpowers-only skill names such as `writing-plans`.
- Do not make every small request enter a heavy harness. KH keeps `request-complexity-router` as the light/medium/heavy boundary.
- Do not replace KH Python contracts with prompt-only rules when deterministic validation is available.
- Do not call same-checkout concurrent file edits safe parallel work unless the write set is proven non-overlapping.

## Priority Improvements

1. Strengthen high-traffic front-door skills first:
   - `brainstorming-harness`
   - `request-complexity-router`
   - `development-lifecycle-harness`
   - `quality-gates-harness`
   - `workflow-skill-distiller`
2. Add SIDE transcript cases that verify KH is selected even when Superpowers is also installed.
3. Add a regression fixture for product/SaaS discovery:
   - user starts with an unclear SaaS idea
   - KH selects `brainstorming-harness`
   - KH asks one focused question at a time
   - KH creates `brainstorm_handoff`
   - KH passes to `architect-pipeline`
4. Keep comparing every packaged skill against this benchmark during external quality audits.

## Current 2.9.4 Changes

- Added `brainstorming-harness` as a KH-native adaptation of Superpowers brainstorming.
- Added `compound-engineering-harness` as a KH-native required learning loop after Plan, Work, and Review.
- Added `BrainstormSession`, `BrainstormOption`, `BrainstormDecision`, validation, and architect handoff contracts.
- Added `CompoundCapture`, `CompoundLearning`, `CompoundMemoryCandidate`, validation, and compound handoff contracts.
- Added demos, smoke checks, SIDE coverage, skill catalog registration, quality registration, and external benchmark rows.
- Updated plugin prompts so new product, SaaS, feature, or unclear design requests prefer KH `brainstorming-harness`.
- Updated plugin prompts so post-review learning routes through KH `compound-engineering-harness`.
- Documented the KH loop as Plan -> Work -> Review -> Compound with scoped memory and regression capture.
- Documented role-stack coverage for discovery, CEO/advisor challenge, engineering/design/DX review, browser/QA/release, security guardrails, learning, cross-model review, and checkpoint/restore.
