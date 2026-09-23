# Auxiliary files and project cleanliness

Keep task scratch outside the user's project and source tree. Use a task-specific directory under the system temporary location for probe scripts, SQL checks, PB exports used for analysis, snapshots, logs, and intermediate build or render output. Pass that directory explicitly when a tool accepts an output path; do not rely on a default that writes beside an input file. Use stdout or an in-memory result when no file is needed.

Write actual source changes and requested final deliverables to their intended locations. If a tool can only write beside its input, first check whether a disposable input copy in the temporary directory preserves the behavior being tested. Do not move the user's original source merely to run a tool.

At completion, inspect files created by the task and remove disposable scratch after its result has been verified. Preserve pre-existing files and any evidence still needed for review; keep retained analysis outside the project and give its location. An explicit user-selected output directory takes precedence over the temporary default.
