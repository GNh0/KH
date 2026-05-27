---
name: domain-orchestration-harness
description: Use when a UAF workflow must handle a non-code or cross-domain objective, require a design stage, persist design artifacts, or route work through review, QA/QC, risk, policy, and final decision gates.
---

# Domain Orchestration Harness

This harness makes UAF domain orchestration portable beyond software development. Every objective should be classified into a `DomainProfile`, converted into a mandatory `WorkDesign`, and backed by persisted design artifacts before execution or final release decisions.

## When To Use

Use this harness when:

- The user objective is not clearly a coding-only task.
- The task needs subject-matter decomposition, role assignment, or expert review.
- The workflow needs design outputs such as a requirements brief, equipment plan, analysis model, process map, checklist, or any other domain-specific artifact.
- Review, QA/QC, risk, policy, compliance, or final decision roles must inspect evidence before completion.

## Core Flow

1. Understand the objective and available context.
2. Build a `DomainProfile` with domain name, subdomains, required roles, required design artifact types, review gates, risk/policy gates, and evidence requirements.
3. Create a `WorkDesign` before execution. The design must name scope, assumptions, constraints, deliverables, roles, required artifacts, review gates, and risk/policy checks.
4. Persist the `WorkDesign` and all supplied design artifacts through `ArtifactStore`.
5. Attach the resulting `ArtifactManifest` to workflow metadata and `GoalState.metadata`.
6. Dispatch bounded role tasks.
7. Run review, analysis, QA/QC, risk, security, policy, and release gates against the manifest evidence.
8. Iterate or block when required evidence is missing.

## Required Evidence

The default design-stage evidence keys are:

- `work design saved`
- `artifact manifest saved`
- `required design artifacts saved`
- `risk policy checked`

These keys should participate in `GoalState.evidence_required` whenever the workflow is intended to be evidence-complete.

## Domain Examples

The artifact names are examples, not a fixed taxonomy:

- Software development: feature definition, architecture, DB design, API design, test strategy, security model.
- Equipment design: equipment design document, drawings, parts list, control logic, safety review, manufacturing constraints.
- Investment analysis: analysis plan, data sources, valuation method, risk model, scenario matrix, compliance checklist.
- Operations: process map, handoff model, metrics plan, exception handling, risk checklist.
- Education: curriculum structure, assessment plan, learning objectives, evaluation rubric.

## UAF implementation targets

- `src.contracts.DomainProfile`
- `src.contracts.DomainRole`
- `src.contracts.WorkDesign`
- `src.contracts.DesignArtifact`
- `src.contracts.ArtifactManifest`
- `src.orchestration.domain_profiles.DomainProfileBuilder`
- `src.orchestration.artifacts.ArtifactStore`
- `src.tasks.workflows.async_project_workflow`
- `skills/domain_orchestration_harness/SKILL.md`

## Boundaries

- Do not hardcode one industry taxonomy into the core framework.
- Do not treat generated answer text as completion evidence unless it is attached to a persisted artifact or normalized evidence record.
- Do not skip the design stage because the domain is unfamiliar. Use a generic profile and record assumptions instead.
- Do not store secrets, credentials, or unsupported durable claims inside design artifacts.
