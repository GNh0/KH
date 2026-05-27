---
name: harness-evaluator
description: A secure code sandbox that executes and tests python code to catch syntax, runtime, and module errors. Use this to verify any code you write before presenting it to the user.
---
# Harness Evaluator Skill

This skill acts as a Tester/Evaluator for your code. It runs the code in an isolated subprocess with AST validation to prevent Remote Code Execution (RCE) and infinite loops.

## Instructions
1. After writing a python script or receiving a python script from the user, save it to a file, for example `./workspace/main.py`.
2. Run the evaluator using the terminal:
   `python -m src.core.runner --mode evaluate --agent_code_path "./workspace/main.py" --test_code_path "./workspace/test.py"`
3. If the evaluation output contains `[Fail]`, read the Stderr logs carefully.
4. Fix the errors in the code based on the Stderr feedback, and re-run the evaluator until it passes `[Success]`.
