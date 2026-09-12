# Preferences and necessary exceptions

This user defaults to the existing project's approach. Avoid LINQ, intermediate tables, and builds by default. Use them only when implementation would be difficult without them or the performance difference from an alternative would be extreme. Shorter code, authoring convenience, habit, and vague performance expectations do not justify an exception.

Check alternatives and actual constraints, then briefly explain the necessity. Do not invent performance multipliers or a separate approval step. The user's current explicit choice overrides older general preferences. Do not extend a task-specific requirement to separate row ownership with Clone/ImportRow into the default for other uploads.

Do not merely assert correctness or API compatibility as a justification: establish the specific reason implementation would be difficult without the approach. Choose builds when needed for implementation or resolving an error, not as a default completion ritual.
