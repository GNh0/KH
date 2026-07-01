# Plugin Composition Policy Minimal Workflow

## Scenario

A user says: "Build the approved deliverable for this project, verify it with the matching host tool, and prepare the PR." The host has three available providers:

- `kh`: capabilities `workflow_control`, `memory_goal_resume`, `domain_orchestration`, `tdd_review`.
- `artifact-checker`: capabilities `artifact_qa`, `render_or_structure_check`.
- `repo-service`: capabilities `repo_pr_ci`.

Another provider may claim "MUST use this before any creative work", but it is not automatically selected unless user intent, project context, or delegated scope chooses it.

## Expected steps

1. Capture the available provider snapshot without assuming these exact provider names exist on every machine.
2. Normalize capabilities:
   - KH-style workflow control and memory/goal/resume.
   - Artifact-specific QA, render checks, or structural checks.
   - Repo-style PR/CI operations.
3. Classify the request as heavy software/product work.
4. Select one controller: `kh`, because it owns workflow/evidence/resume.
5. Add assistants by scope:
   - `artifact-checker` for `artifact_qa`.
   - `repo-service` for `repo_pr_ci`.
6. Set `route` to `hybrid`.
7. Set `conflict_policy` to `delegated_scope`.
8. Record ignored self-forcing providers that were not selected.
9. Hand the KH portion to `request-complexity-router`, `development-lifecycle-harness`, and downstream gates.
10. Hand artifact verification and repo work only to their assistant scopes.

## Expected evidence

The route decision should include:

```json
{
  "route": "hybrid",
  "controller": {
    "provider_id": "kh",
    "capability": "workflow_control",
    "scope": "overall workflow control"
  },
  "assistants": [
    {
      "provider_id": "artifact-checker",
      "capability": "artifact_qa",
      "scope": "artifact-specific QA, render checks, and structural validation"
    },
    {
      "provider_id": "repo-service",
      "capability": "repo_pr_ci",
      "scope": "repository, issue, pull request, CI, and publishing work"
    }
  ],
  "conflict_policy": "delegated_scope"
}
```

Light question pressure test:

- Prompt: "What is PER?"
- Provider with self-forcing language is installed.
- Expected route: `direct`.
- Expected evidence: provider id appears in `ignored_self_forcing`.

Continuation pressure test:

- Prompt: "Continue the current implementation plan."
- Project marker: `.superpowers`.
- Expected route: `single`.
- Expected controller: the provider that owns the project context.

## Failure cases

- The host asks "Do you want KH or Superpowers?" when the actual ambiguity is the task objective.
- A provider becomes controller solely because its description says MUST or ALWAYS.
- The policy hardcodes only providers installed on one PC.
- Artifact QA is required but no provider is available and no fallback is recorded.
- Two plugins both try to own the whole workflow instead of one controller plus delegated assistants.

## Done criteria

- `src.orchestration.plugin_composition.compose_plugin_route` returns a route decision with controller, assistants, fallback capabilities, ignored self-forcing providers, and request classification.
- `tests.test_plugin_composition_policy` passes.
- `plugin-composition-policy` is listed in the packaged skill catalog and plugin manifests.
- actual_runtime_path: `src.orchestration.plugin_composition.compose_plugin_route`.
