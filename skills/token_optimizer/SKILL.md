---
name: token-optimizer
description: Compresses very long terminal logs or minifies python code to save LLM context window tokens. Use this when you are dealing with huge files or massive error outputs.
---
# Token Optimizer Skill

This skill provides utilities to prevent token exhaustion during complex debugging or code reading loops.

## Instructions
1. If you run a command and it produces an extremely long error log (hundreds of lines) that clutters your context, you can run the python script directly to truncate it:
   `python -c "from src.skills.token_optimizer import truncate_logs; print(truncate_logs('''<PASTE_LOG_HERE>'''))"`
2. Alternatively, if you need to pass a large python file to another agent (or summarize it), minify it first by stripping comments and docstrings via AST:
   `python -c "from src.skills.token_optimizer import minify_code; print(minify_code(open('file.py').read()))"`

## UAF implementation targets

- `src.skills.token_optimizer`
- `src.skills.catalog`
- `src.skills.uaf_skill_catalog`
- `src.contracts.HarnessResult`
