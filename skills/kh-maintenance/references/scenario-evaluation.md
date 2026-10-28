# Evaluating skills through actual outcomes

Evaluate outcomes using user requests and minimal inputs from tests/scenarios. Include positive requirements and counterexamples in test expectations. Check actual results, scope, and preservation of errors instead of fixed skill counts, wording, or self-ratings.

Ordinary Python unit tests, mocked tool tests, actual agent execution, and rendering in the user's app are different levels of evidence. Mark unexecuted scenarios as unexecuted. For independent skill evaluation, follow the current host's delegation permissions and skill-creator's minimal-input guidance.

Derive expected behavior from current user requirements and approved source before matching implementation findings. Include a valid case, a valid alternative, a violation and insufficient-evidence case where relevant. Put the claimed failure condition into the fixture: an exclusion test must actually introduce the material it claims to exclude. Passing in-repository tests is not independent validation; implementation and tests may share the same false assumption. Where feasible, compare with a separate authoritative evaluator/compiler/runtime and record its actual results and limits.

Evaluate skill selection/application through actual task requests without supplying the skill name or expected implementation as the answer. Inspect the resulting source/diff, relevant reads and execution evidence independently. A checker may support that assessment within its reported scope; it does not establish the agent's overall compliance.
