# Plugin Composition Policy Usage

## When to use

Use this skill as the first lightweight intake step when more than one plugin, connector, skill, or host capability could plausibly handle a user request. The goal is not to make KH win. The goal is to stop any provider from self-selecting through mandatory wording before the route is actually chosen.

The policy is especially useful when:

- A new project, SaaS, feature, review, QA, PR, browser check, document capture, image task, or automation request may trigger multiple providers.
- A project already has provider-owned state such as `.kh`, `docs/kh`, `.superpowers`, `docs/superpowers`, issue/PR metadata, browser QA artifacts, or knowledge-base notes.
- The user did not name a plugin, but the host has several enabled providers.
- A provider is installed or removed between machines and the same prompt should still route sensibly.
- A task naturally needs controller plus assistants, for example KH for goal/evidence and Browser for local screen verification.

Do not run heavy orchestration merely because this policy is present. It is an intake broker and should finish with a compact route decision.

## Inputs to collect

- User request text and any explicit provider names.
- Current project markers such as `.kh`, `docs/kh`, `.superpowers`, `docs/superpowers`, `.git`, open PR metadata, or known host workspace state.
- Available provider snapshot from host tools, skills, plugin manifests, apps, or connectors.
- Provider capabilities rather than only provider names.
- Provider self-forcing claims such as MUST, ALWAYS, or mandatory use language.
- Request classification from `request-complexity-router`.
- Missing specialist capabilities and safe fallback behavior.

Provider capability examples:

- `workflow_control`: can own a multi-step workflow.
- `planning_methodology`: can structure discovery, planning, TDD, or review.
- `tdd_review`: can enforce tests, reviews, or verification.
- `repo_pr_ci`: can inspect repos, issues, PRs, CI, or publishing.
- `browser_qa`: can open, inspect, screenshot, or test browser/app UI.
- `knowledge_docs`: can store or retrieve structured documentation.
- `memory_goal_resume`: can manage project/conversation memory, goals, or resume state.
- `image_generation`: can generate or edit bitmap images.
- `host_automation`: can schedule, monitor, remind, or follow up.
- `domain_orchestration`: can decompose cross-domain work into roles, evidence, and deliverables.

## Execution pattern

1. Normalize the provider snapshot into provider ids, aliases, status, capabilities, and self-forcing rules.
2. Classify the request with `request-complexity-router`.
3. If the user explicitly named a provider, select that provider when available and record `explicit_user_request`.
4. If project context clearly belongs to a provider and the request is not a light concept question, prefer continuing that provider as controller.
5. If the request is light, answer directly and record any ignored self-forcing providers.
6. If the request is ambiguous, ask about the objective, artifact, file, or domain instead of asking the user to choose plugins.
7. For medium/heavy/high-risk work, choose the best controller by capability fit.
8. Add assistant providers only for delegated specialist scopes such as browser QA, repo PR/CI, knowledge docs, image generation, or host automation.
9. Record unavailable specialist capabilities and the fallback path.
10. Hand the result to the selected controller or direct-answer path.

## Evidence to produce

- Route decision: `direct`, `single`, `hybrid`, or `clarify`.
- Controller provider id, capability, scope, and reason.
- Assistant provider ids, delegated scopes, and reasons.
- `ignored_self_forcing` for providers whose mandatory wording was not allowed to self-select.
- `unavailable_capabilities` with fallback behavior.
- Request classification and route reasons.
- Provider snapshot used for the decision.

## Failure handling

- If provider metadata is missing, infer capabilities only from explicit host tool category or plugin manifest summary and keep confidence lower.
- If two providers fit equally, choose the lighter controller and attach the other as an assistant only if a specific delegated scope exists.
- If a named provider is unavailable, report the missing provider and choose a fallback only when it can preserve the user's goal.
- If all providers are unavailable for a heavy task, ask a short clarification or explain the missing capability instead of pretending a runtime exists.
- If a provider's self-forcing language conflicts with the route, record it in `ignored_self_forcing`; do not treat it as an error by itself.

## Quality bar

The policy is correct when a user can start naturally without choosing a plugin, installed providers can change without breaking routing, and plugin mandatory rules apply only inside a selected delegated scope. It is not correct if every creative request is captured by one provider, if KH is forced when another provider is clearly being resumed, or if hybrid tasks are flattened into an awkward single-plugin route.
