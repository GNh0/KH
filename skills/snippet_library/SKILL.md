---
name: snippet-library
description: "Use when the user needs a common code pattern, boilerplate, configuration template, or utility function that can be provided instantly without generation."
---

# Snippet Library Skill

This skill provides instant access to common code patterns, boilerplates, and configuration templates. It requires no orchestration, no LLM generation, and no state management. Patterns are looked up and returned directly.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## When to use

- "Give me a FastAPI app boilerplate"
- "Show me a Python logging setup"
- "Provide a Dockerfile template for a Python app"
- "What's the pattern for a retry decorator?"
- Any request for a well-known code pattern that does not need custom logic

## Supported pattern categories

- **Web frameworks**: FastAPI, Flask, Express basic setups
- **Configuration**: Dockerfile, docker-compose, .env, pyproject.toml, tsconfig.json
- **Utilities**: retry decorator, singleton, observer, factory patterns
- **Testing**: pytest fixtures, unittest setup, mock patterns
- **CI/CD**: GitHub Actions workflow, pre-commit config
- **Data**: SQLAlchemy model, Pydantic schema, dataclass patterns

## Workflow

1. Receive request for a code pattern or template.
2. Match the request to a known pattern category and specific snippet.
3. If a match is found, return the snippet with usage notes.
4. If no match is found, return `status: blocked` suggesting `single-file-generator` for custom generation.
5. Optionally adapt the snippet to the user's specified language or framework version.

## Required outputs

- `status`: `passed` or `blocked`.
- `pattern_category`: the matched category (e.g., "web-framework", "configuration").
- `pattern_name`: specific pattern identifier.
- `snippet`: the code content.
- `usage_notes`: brief explanation of how to use or customize the snippet.
- `language`: programming language of the snippet.

## Common mistakes

- Do not generate custom logic when a standard pattern suffices.
- Do not return outdated patterns (e.g., Python 2 syntax, deprecated APIs).
- Do not provide patterns without usage notes or context.
- Do not claim a pattern exists when the request requires custom generation.
- Do not use orchestration overhead for a simple pattern lookup.

## UAF implementation targets

- `src.skills.pattern_analyzer`
- `src.skills.uaf_skill_catalog.collect_packaged_skills`
- `src.contracts.HarnessResult`
- `tests.test_skill_catalog`
