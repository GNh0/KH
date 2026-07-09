---
name: workflow-skill-distiller
description: Use when kh-uaf:always-on-front-door has already run and selected this skill; use it when turning a repeated user workflow, completed interaction, or project-specific process into a reusable UAF skill folder.
---

# Workflow Skill Distiller

## KH Entry Contract

- Start every non-trivial turn through `always-on-front-door` unless this skill is that bootstrap step or the current turn was classified as light/direct.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, or a required follow-up gate selects it.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

This is the downstream distillation step for Compound-captured learning. `compound-engineering-harness` owns the learning capture, no-learning rationale, memory/scenario handoff, and regression plan; this skill runs only when that capture identifies a repeatable workflow that should become a portable skill. A new skill should be added as `skills/<skill-name>/SKILL.md`; optional support files are used only when that `SKILL.md` says when to read or run them.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## Workflow

1. Call `src.skills.workflow_distiller.should_distill_workflow` to reject one-off workflows before writing a skill.
2. Run a short design pass before writing files: purpose, inputs, outputs, strict steps, flexible steps, failure handling, existing skill dependencies, required external tools/runtimes, and whether code is needed.
3. Extract the trigger condition from the repeated workflow and keep it in `Use when...` form.
4. Call `src.skills.workflow_distiller.build_skill_scaffold` when creating a new skill folder skeleton, passing the intended execution level when known.
5. If the workflow needs code, API calls, file I/O, data processing, or computation, require file-output-first helpers with explicit `--output`, selectors or `--limit`, short stdout, and retry/rate-limit behavior when external services are involved.
6. If the workflow needs an external tool, runtime, package manager, browser, MCP server, or API client, require an availability check before use; when missing, record setup approval or fallback and verify PATH/connection state after setup.
7. If the workflow is instruction-only, state why no helper code is needed.
8. Keep `SKILL.md` concise and procedural.
9. Put heavy examples in `references/` and deterministic helpers in `scripts/`.
10. Add tests or smoke checks when the skill is surfaced through Python or MCP.
11. For generated skills, run the generated `scripts/smoke_check.py` from the generated skill folder and pass `UAF_REPO_ROOT` when the skill is outside the repository tree.

## Large Work Bundle Reporting

When this skill is part of `large_work_orchestration_bundle`, record `skill_statuses["workflow-skill-distiller"]` as `applied`, `considered_not_needed`, `skipped_with_rationale`, or `blocked`. Do not publish a skill only because work was large; require a repeated workflow, clear trigger, and verification path.

## External Benchmark Recipe

Use this skill like Superpowers `writing-skills` adapted for UAF:

1. Write the pressure scenario first: what mistake should the future agent stop making?
2. Call `should_distill_workflow` and reject the candidate if reuse, trigger, or evidence is weak.
3. Check dependencies first; reference existing skills instead of reimplementing their behavior.
4. Generate the scaffold with `build_skill_scaffold`.
5. Replace generic wording with one runnable example, expected evidence, and failure handling.
6. For helper scripts, enforce output files and explicit limits before any large result enters context.
7. Run the generated smoke check from inside the generated skill folder and from the repository root.

Pressure scenario: if the proposed skill only describes one completed conversation, the distiller must return candidate/blocked rather than publish it as reusable.

## Required outputs

- New or updated `skills/<skill-name>/SKILL.md` with trigger-focused frontmatter.
- Explicit workflow, required outputs, common mistakes, and implementation targets.
- Design evidence covering purpose, inputs, outputs, dependencies, tool/runtime preflight, code-vs-instruction decision, failure handling, and output/limit/rate-limit choices.
- Support-file guidance inside SKILL.md when `references/`, `scripts/`, or `assets/` are used.
- Catalog validation, robust smoke target resolution, and targeted tests for any Python-backed behavior.

## Common mistakes

- Do not turn a one-off session story into a reusable skill.
- Do not skip design approval or dependency review for an underspecified workflow.
- Do not assume required tools, package managers, browsers, MCP servers, APIs, or PATH entries are already available.
- Do not emit large helper-script output to stdout when a file output and field/limit selector is safer.
- Do not hide support-file behavior in README-only text.
- Do not create extra README, changelog, or guide files inside a skill folder.
- Do not publish a skill whose trigger description summarizes the workflow instead of when to use it.

## UAF implementation targets

- `src.skills.workflow_distiller.should_distill_workflow`
- `src.skills.workflow_distiller.build_skill_scaffold`
- `skills/<skill-name>/SKILL.md`
- `src.skills.catalog`
- `src.skills.uaf_skill_catalog`
- `tests.test_workflow_distiller_runtime`
