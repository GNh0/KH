---
name: harness-evaluator
description: Use when Python code needs isolated syntax, runtime, or module verification before presenting results.
---
# Harness Evaluator Skill

This skill acts as a Tester/Evaluator for your code. It runs the code in an isolated subprocess with AST validation to prevent Remote Code Execution (RCE) and infinite loops.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.

## Instructions
1. After writing a python script or receiving a python script from the user, save it to a file, for example `./workspace/main.py`.
2. Run the evaluator using the terminal:
   `python -m src.core.runner --mode evaluate --agent_code_path "./workspace/main.py" --test_code_path "./workspace/test.py"`
3. If the evaluation output contains `[Fail]`, read the Stderr logs carefully.
4. Fix the errors in the code based on the Stderr feedback, and re-run the evaluator until it passes `[Success]`.

## Required outputs

- `HarnessResult` with status, stdout, stderr, execution time, and failure reason.
- Syntax or runtime evidence that can be attached to workflow gates.
- Clear distinction between sandbox rejection, test failure, timeout, and successful execution.

## Common mistakes

- Do not run untrusted Python outside the sandbox just because it is small.
- Do not treat syntax compile success as runtime correctness.
- Do not hide stderr when returning a failed result.
- Do not retry indefinitely after a timeout; report the timeout as a blocker or failure.

## UAF implementation targets

- `src.harness.evaluator.Evaluator`
- `src.harness.sandbox.CodeSandbox`
- `src.core.runner`
- `src.contracts.HarnessResult`
