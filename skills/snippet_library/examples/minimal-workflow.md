# Snippet Library Minimal Workflow Example

## Scenario

A host agent receives a task where this trigger is relevant: Use when the user needs a common code pattern, boilerplate, configuration template, or utility function that can be provided instantly without generation.

The agent must decide whether `snippet-library` applies, run or apply it according to its execution level, and leave auditable evidence.

## Expected steps

1. Load `SKILL.md` and confirm the trigger applies (user wants a known pattern or boilerplate).
2. Read `references/usage.md` before doing the work.
3. Parse the request to identify pattern category and name.
4. Look up the pattern in the known registry.
5. Return the snippet with usage notes, or `blocked` if no match.
6. No orchestration, state, or gate execution.
7. Run `python scripts/smoke_check.py` when validating the packaged skill folder itself.

## Expected evidence

- `skill`: `snippet-library`.
- `execution_level`: `python-module`.
- `support_reference_read`: `references/usage.md`.
- `implementation_targets`:
  - `src.skills.pattern_analyzer`
  - `src.skills.uaf_skill_catalog.collect_packaged_skills`
  - `src.contracts.HarnessResult`
  - `tests.test_skill_catalog`
- `actual_runtime_path`: the concrete module, workflow, policy gate, or procedural step used in this run.
- `verification`: command output, test result, artifact path, or explicit blocked reason.

## Failure cases

- The agent claims a snippet was found but returns custom-generated code instead of a known pattern.
- The agent uses LLM generation when a standard pattern is available in the registry.
- The agent returns a deprecated or insecure pattern without warning.
- The agent uses orchestration overhead for a simple pattern lookup.
- The agent returns an incomplete snippet that cannot be used without additional context.

## Done criteria

- Pattern matched and returned from the known registry (or blocked with alternative suggestion).
- Snippet is syntactically valid and includes usage notes.
- No orchestration state was created.
- Response was generated without LLM token cost (for cached patterns).
