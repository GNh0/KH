# Snippet Library Usage Reference

This reference expands the portable operating contract for `snippet-library`. Read it when the task is real work, when deciding whether this skill applies, or when a review needs evidence beyond the concise `SKILL.md`.

## When to use

Use when the user needs a common code pattern, boilerplate, configuration template, or utility function that can be provided instantly without generation.

Context summary: This skill is a fast-path lookup for well-known patterns. It requires zero LLM tokens for retrieval of standard patterns and zero orchestration state. It is the fastest possible response path in UAF.

Do not use this skill only because it is available. Use it when the current task needs the behavior named by the trigger, and state whether the skill was actually executed, applied procedurally, or only considered.

Quality rule: snippets must be correct, current, and complete enough to be used directly. Partial or broken snippets are worse than no snippet.

## Inputs to collect

- Pattern request: what code pattern or template the user needs.
- Language/framework: target language and version (e.g., Python 3.11, Node 20).
- Customization: any specific adaptations needed (e.g., async, specific library version).
- Execution level: `python-module`.
- Implementation targets:
  - `src.skills.pattern_analyzer`
  - `src.skills.uaf_skill_catalog.collect_packaged_skills`
  - `src.contracts.HarnessResult`
  - `tests.test_skill_catalog`

## Execution pattern

1. Read `SKILL.md` first and confirm the trigger applies to the current task.
2. Read this reference before performing non-trivial work with `snippet-library`.
3. Parse the user request to identify the pattern category and specific pattern.
4. Look up the pattern in the known pattern registry.
5. If found, return the snippet with usage notes and any version-specific adaptations.
6. If not found, return `status: blocked` with a suggestion to use `single-file-generator`.
7. No state management, no orchestration, no gate execution.

## Evidence to produce

- `skill`: `snippet-library`.
- `execution_level`: `python-module`.
- `pattern_category`: matched category.
- `pattern_name`: specific pattern.
- `language`: output language.
- `snippet_size_bytes`: content size.
- `customized`: boolean indicating if adaptations were applied.
- `lookup_time_ms`: time taken for pattern matching.

## Failure handling

- If no matching pattern is found, return `status: blocked` with the closest available patterns.
- If the requested pattern exists but for a different language/framework version, offer the available version.
- If the pattern requires significant customization beyond simple adaptation, suggest `single-file-generator`.
- Never return a pattern that is known to be deprecated or insecure.

## Quality bar

- All snippets must be syntactically valid in their target language.
- Snippets must follow current best practices (no deprecated APIs, no known vulnerabilities).
- Usage notes must explain any required dependencies or setup.
- Patterns must be self-contained: usable without additional context.
- Response time should be under 100ms for cached patterns.
