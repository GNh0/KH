---
name: systematic-debugging
description: Diagnose an unclear failure by tracing the actual execution path, reproducing its conditions, and testing a focused causal hypothesis.
---

# Systematic debugging

First identify the current files, procedures, connection target, and exact failure stage. Distinguish observations, hypotheses, and user reports. If an exception occurs at Connect, do not attribute it to authentication or relay issues without checking.

Narrow the reproduction input and execution path, then test the hypothesis with minimal comparisons. Measure SQL execution, data transfer, C# binding, and BestFit costs separately using the same parameters and row counts. A short tool success message or exit code alone does not establish that the actual output is correct.

Once the cause is clear, fix only the affected scope and recheck the failure conditions. Do not treat a user-resolved issue or inability to reproduce as confirmation of a cause. Do not repeat unchanged checks or the same failed hypothesis.
