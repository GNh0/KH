---
name: harness-evaluator
description: Use when Python code needs isolated syntax, runtime, or module verification before presenting results.
---
# Harness Evaluator Skill

## KH Entry Contract

- Select this skill directly when its semantic trigger matches the current request; no separate routing preflight is required.
- An active KH directive does not select this skill by itself; the current request must still match this skill's trigger or require it as a workflow gate.
- Use this skill when its frontmatter trigger directly matches the current request or an already-selected workflow requires it.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

This skill acts as a Tester/Evaluator for Python code. It uses AST validation, subprocess isolation, and timeout limits to reduce accidental side effects and runaway execution. These controls mitigate risk but do not make untrusted code safe outside the configured sandbox.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## Instructions
1. After writing a python script or receiving a python script from the user, save it to a file, for example `./workspace/main.py`.
2. For direct UAF contracts, call `Evaluator.evaluate_code_result(...)` and attach the returned `HarnessResult` to gate evidence.
3. Run the evaluator using the terminal when file-based evaluation is preferred:
   `python -m src.core.runner --mode evaluate --agent_code_path "./workspace/main.py" --test_code_path "./workspace/test.py"`
4. If the evaluation output contains `[Fail]`, read the Stderr logs carefully.
5. Fix the errors in the code based on the Stderr feedback, and re-run the evaluator until it passes `[Success]`.

## External Benchmark Recipe

Use this harness for small, isolated runtime proof:

1. Keep the evaluated code minimal and dependency-free unless the dependency is part of the harness contract.
2. Put assertions in the test code, not in the final explanation.
3. Prefer `Evaluator.evaluate_code_result` so callers get `HarnessResult(success, stdout, stderr, exit_code, metadata)`.
4. Treat syntax errors, import errors, runtime errors, and missing cleanup as separate failure classes.
5. Include the failing snippet or command in evidence when the evaluator blocks completion.

Pressure scenario: if generated Python compiles but fails at import time, the evaluator result is failed with stderr and exit code; do not report "syntax OK" as runtime success.

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
