---
name: domain-orchestration-harness
description: Use when a UAF workflow must handle a non-code or cross-domain objective, require a design stage, persist design artifacts, or route work through review, QA/QC, risk, policy, and final decision gates.
---

# Domain Orchestration Harness

This harness makes UAF domain orchestration portable beyond software development. Every objective should be classified into a `DomainProfile`, converted into a mandatory `WorkDesign`, backed by internal design artifacts, and exported as user-facing deliverables that match the task type before execution or final release decisions.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.

## When To Use

Use this harness when:

- The user objective is not clearly a coding-only task.
- The task needs subject-matter decomposition, role assignment, or expert review.
- The workflow needs design outputs such as a requirements brief, orchestration design, equipment plan, analysis model, process map, checklist, or any other domain-specific artifact.
- Review, QA/QC, risk, policy, compliance, or final decision roles must inspect evidence before completion.

## Core Flow

1. Understand the objective and available context.
2. Build a `DomainProfile` with domain name, subdomains, required roles, required design artifact types, review gates, risk/policy gates, and evidence requirements.
3. Create a `WorkDesign` before execution. The design must name scope, assumptions, constraints, deliverables, roles, required artifacts, review gates, and risk/policy checks.
4. Persist the `WorkDesign` and all supplied design artifacts through `ArtifactStore` in the UAF runtime store.
5. Export user-facing deliverables to the target project's `docs/` folder through the type-aware deliverable router.
   - Use the general orchestration profile for broad planning/process work.
   - Use product/mechanical design artifacts for drawing-oriented work, including design notes, dimension/BOM tables, SVG concept drawings, and DXF CAD handoff files when the input supports them.
   - Use analysis/reporting artifacts for investment or research work, including analysis reports, scenario workbooks, and risk/policy workbooks.
   - Export `사용_매뉴얼.docx` only when the workflow needs user/operations instructions, `export_manual` is true, or manual revision metadata is supplied.
   - Do not export a manual by default for analysis/reporting-only topics such as investment, valuation, portfolio review, research, or generic analysis.
   - When a manual is exported, put `리비전 버전 관리` first and include `manual_revision` / `manual_revision_note` metadata when available.
   - Record the selected profile, artifact type, format, path, and evidence in `deliverable_exports["plan"]`.
6. Attach the resulting `ArtifactManifest` and `deliverable_exports` metadata to workflow metadata and `GoalState.metadata`.
7. Dispatch bounded role tasks.
8. Run review, analysis, QA/QC, risk, security, policy, and release gates against the manifest and export evidence.
9. Iterate or block when required evidence is missing.

## Required Evidence

The default design-stage evidence keys are:

- `work design saved`
- `artifact manifest saved`
- `required design artifacts saved`
- `risk policy checked`
- `requirements brief exported`
- `orchestration design exported`
- `deliverable definition exported`
- `process flow exported`
- `role task breakdown exported`
- `evidence plan exported`
- `risk policy checklist exported`
- `manual exported` only when the manual file is actually written

These keys should participate in `GoalState.evidence_required` whenever the workflow is intended to be evidence-complete.

## External Benchmark Recipe

Use this harness like an Antigravity science skill adapted to arbitrary domains:

1. Classify the objective first: software, product/mechanical, analysis/reporting, operations, education, or generic.
2. Build `DomainProfile` and `WorkDesign` before producing user-facing files.
3. Select artifact types by objective, not by a fixed DOCX/XLSX/PDF/DXF/SVG checklist.
4. Export only useful user deliverables to `docs/`; keep internal UAF state, traceability, and harness evidence in runtime metadata.
5. Run role, review, QA, policy, traceability, template, and render gates before claiming the workflow is complete.

Pressure scenario: if the user asks for a product drawing from dimensions, the router should produce drawing/design artifacts such as SVG/DXF/BOM when supported, not generic software feature documents. If the input is insufficient for a drawing, block with missing dimensions instead of fabricating geometry.

## Domain Examples

The artifact names are examples, not a fixed taxonomy. The router should choose artifacts by objective and evidence needs, not by a mandatory extension list. The default general exports are domain-neutral (`요구정의서.docx`, `오케스트레이션_설계서.docx`, `산출물_정의서.docx`, `처리흐름도.docx`, `역할별_작업분해표.xlsx`, `증거계획서.xlsx`, `위험_정책_체크리스트.xlsx`) and should be filled from the current domain context. `사용_매뉴얼.docx` is a conditional operational/user-instruction artifact, not a universal artifact.

- Software development: feature definition, architecture, DB design, API design, test strategy, security model.
- Equipment/product design: product design document, dimension/BOM workbook, SVG concept drawing, DXF CAD handoff, control logic, safety review, manufacturing constraints.
- Investment analysis: investment analysis report, data sources, valuation method, risk model, scenario matrix workbook, compliance checklist.
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
- `src.orchestration.deliverable_exports.export_office_deliverables`
- `src.tasks.workflows.async_project_workflow`
- `skills/domain_orchestration_harness/SKILL.md`

## Boundaries

- Do not hardcode one industry taxonomy into the core framework.
- Do not make the default export software-development-specific. Domain-specific files can be added, but the base package must work for arbitrary orchestration topics.
- Do not force every workflow to create DOCX, XLSX, PDF, DXF, SVG, or PNG. Pick the artifact types that fit the objective and record that routing decision.
- Do not treat generated answer text as completion evidence unless it is attached to a persisted artifact or normalized evidence record.
- Do not skip the design stage because the domain is unfamiliar. Use a generic profile and record assumptions instead.
- Do not store secrets, credentials, or unsupported durable claims inside design artifacts.

## Required outputs

- `DomainProfile` with domain, subdomains, roles, artifact types, review gates, risk/policy gates, and evidence requirements.
- `WorkDesign` persisted to the UAF runtime store before execution.
- `ArtifactManifest` and `deliverable_exports` metadata with selected profile, artifact type, format, path, and evidence.
- User-facing deliverables that match the task type, not a fixed file-extension checklist.
- Gate results that block completion when required design, QA, policy, or export evidence is missing.

## Common mistakes

- Do not equate domain orchestration with software architecture; choose artifacts by objective.
- Do not force DOCX/XLSX/PDF/DXF/SVG/PNG output when the domain does not need those files.
- Do not place internal UAF state or harness-only reports in the user's `docs/` folder.
- Do not mark generic assumptions as verified facts; route them to review or risk gates.
