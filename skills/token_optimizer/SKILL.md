---
name: token-optimizer
description: Use when terminal logs, command output, or Python code are too large for efficient LLM context handling.
---
# Token Optimizer Skill

This skill provides utilities to prevent token exhaustion during complex debugging or code reading loops.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.

## Instructions
1. If you run a command and it produces an extremely long error log (hundreds of lines) that clutters your context, you can run the python script directly to truncate it:
   `python -c "from src.skills.token_optimizer import truncate_logs; print(truncate_logs('''<PASTE_LOG_HERE>'''))"`
2. Alternatively, if you need to pass a large python file to another agent (or summarize it), minify it first by stripping comments and docstrings via AST:
   `python -c "from src.skills.token_optimizer import minify_code; print(minify_code(open('file.py').read()))"`

## Required outputs

- Compact log or code text that preserves errors, file paths, test names, and exit status context.
- Token-savings estimate or before/after size when used inside a harness result.
- Fallback note when truncation or minification cannot safely preserve actionable context.

## Common mistakes

- Do not remove the only line that identifies the failure.
- Do not minify code that must preserve comments, formatting, or license headers.
- Do not use token optimization as a substitute for reading the relevant source.
- Do not summarize command output in a way that hides a non-zero exit code.

## UAF implementation targets

- `src.skills.token_optimizer`
- `src.skills.catalog`
- `src.skills.uaf_skill_catalog`
- `src.contracts.HarnessResult`
