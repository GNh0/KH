# Evaluating skills through actual outcomes

Evaluate outcomes using user requests and minimal inputs from tests/scenarios. Include positive requirements and counterexamples in test expectations. Check actual results, scope, and preservation of errors instead of fixed skill counts, wording, or self-ratings.

Ordinary Python unit tests, mocked tool tests, actual agent execution, and rendering in the user's app are different levels of evidence. Mark unexecuted scenarios as unexecuted. For independent skill evaluation, follow the current host's delegation permissions and skill-creator's minimal-input guidance.

Derive expected behavior from current user requirements and approved source before matching implementation findings. Include a valid case, a valid alternative, a violation and insufficient-evidence case where relevant. Put the claimed failure condition into the fixture: an exclusion test must actually introduce the material it claims to exclude. Passing in-repository tests is not independent validation; implementation and tests may share the same false assumption. Where feasible, compare with a separate authoritative evaluator/compiler/runtime and record its actual results and limits.

Evaluate skill selection/application through actual task requests without supplying the skill name or expected implementation as the answer. Inspect the resulting source/diff, relevant reads and execution evidence independently. A checker may support that assessment within its reported scope; it does not establish the agent's overall compliance.

For changes to implementation/audit workflow, inspect the actual host tool trace as well as the final artifacts. Verify that the domain entrypoint and required complete source/reference bodies were available before the first affected write, then locate the saved-body read and review after each affected write. Include a task that crosses artifact responsibilities when that transition is involved. Distinguish tool-call intent, returned content, truncation, failed calls and actual saved files. Statements that an audit happened are not substitutes for this evidence.

Use the native session metadata to identify the evaluated agent and exact JSONL path; do not assume a subagent has no inspectable log. From the KH package root, the explicitly scoped extractor can locate calls and returned records:

```powershell
python -B -m src.maintenance.session_report <absolute-evaluation.jsonl> --excerpt-chars 0 --tool-excerpt-chars 1200
```

Tool previews are bounded and best-effort redacted; retrieve only the relevant complete arguments/results at the reported source locations. Do not print credential configuration, hidden reasoning or unrelated conversations. A recorded read does not establish that its content was correctly applied: compare the proposed/saved implementation and caller behavior separately. Classify missing or materially truncated evidence as unverified rather than passing the workflow. Keep exact log locations and findings in the evaluation handover; do not add per-task receipts or forms to normal development.
