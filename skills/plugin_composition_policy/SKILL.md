---
name: plugin-composition-policy
description: Use when kh-uaf:always-on-front-door has already run and selected this skill; use it when multiple plugins, tools, skills, connectors, or future capability providers may apply and the host must choose direct, single-provider, hybrid, or clarification routing without letting any provider self-force selection.
---

# Plugin Composition Policy

## KH Entry Contract

- Start every non-trivial turn through `always-on-front-door` unless this skill is that bootstrap step or the current turn was classified as light/direct.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, or a required follow-up gate selects it.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

This is the KH top-level capability broker. It chooses the lightest fitting route across dynamic providers instead of hardcoding the plugins installed on one machine.

## Support files

- Read `references/usage.md` when adding provider capabilities, resolving a plugin conflict, or deciding whether a route should be direct, single-provider, hybrid, or clarify.
- Use `examples/minimal-workflow.md` as the compact acceptance scenario for dynamic provider discovery, ignored self-forcing rules, controller/assistant composition, and fallbacks.
- Run `python scripts/smoke_check.py` from this skill folder to verify support files and implementation targets.
- Run `python scripts/demo.py --output-dir <tmp>` to execute a deterministic mini-demo through the packaged skill demo runner.

## When To Use

Use this policy before plugin-specific MUST/ALWAYS rules when:

- More than one plugin, tool, skill, connector, or host capability could apply.
- A provider claims it must always run, but user intent and project context have not selected it yet.
- A task may need hybrid routing such as KH for goal/evidence plus Browser for visual QA or GitHub for PR/CI.
- Installed providers may change across machines, sessions, marketplaces, or host apps.
- The user asks whether KH, Superpowers, Browser, GitHub, Notion, or another provider should be selected.

Do not use this policy to make simple requests heavy. Clear light questions should remain direct answers.

## Instructions

1. Discover the current provider snapshot from host tools, plugin manifests, skill descriptions, project markers, and user request text.
2. Normalize provider names into capabilities such as `workflow_control`, `planning_methodology`, `tdd_review`, `repo_pr_ci`, `browser_qa`, `knowledge_docs`, `memory_goal_resume`, `image_generation`, `host_automation`, and `domain_orchestration`.
3. Apply selection order: explicit user request, project context, request complexity and risk, then lightest sufficient capability route.
4. Treat provider MUST/ALWAYS wording as internal procedure only after the provider is selected as controller or assistant for a delegated scope.
5. Prefer direct answers for light conceptual requests.
6. Prefer a single controller when one provider owns the workflow.
7. Use hybrid composition when one controller plus specialist assistants is more natural than forcing a single plugin.
8. Ask a short clarification about the objective or artifact when the task is ambiguous; do not ask the user to pick plugins unless they requested a comparison.

## Required outputs

The route decision should include:

- `route`: `direct`, `single`, `hybrid`, or `clarify`.
- `controller`: provider id, primary capability, scope, and reason.
- `assistants`: provider id, delegated capability, scope, and reason.
- `conflict_policy`: normally `delegated_scope`.
- `ignored_self_forcing`: providers whose mandatory wording was not allowed to self-select.
- `unavailable_capabilities`: requested specialist capabilities with fallback behavior.
- `explicit_user_request`: whether the user named the selected provider.
- `classification`: request complexity/domain route from `request-complexity-router`.
- `available_providers_snapshot`: normalized dynamic provider snapshot.
- `reasons`: short routing evidence.

## Common Mistakes

- Do not hardcode only the plugins on the current PC.
- Do not let a provider select itself solely because its description says MUST or ALWAYS.
- Do not force KH when an existing non-KH project context is clearly being resumed.
- Do not force one plugin when a controller plus assistant providers gives a cleaner route.
- Do not ask the user to choose between plugin names when a normal task clarification would solve the ambiguity.
- Do not apply assistant plugin rules outside their delegated scope.

## UAF implementation targets

- `src.orchestration.plugin_composition`
- `src.orchestration.plugin_composition.compose_plugin_route`
- `src.orchestration.plugin_composition.PluginCompositionDecision`
- `src.orchestration.request_classifier.classify_request`
- `tests.test_plugin_composition_policy`
