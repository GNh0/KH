# Auxiliary files and project cleanliness

Keep task scratch outside the user's project and source tree. Use a task-specific directory under the system temporary location for probe scripts, SQL checks, PB exports used for analysis, snapshots, logs, and intermediate build or render output. Pass that directory explicitly when a tool accepts an output path; do not rely on a default that writes beside an input file. Use stdout or an in-memory result when no file is needed.

Write actual source changes and requested final deliverables to their intended locations. If a tool can only write beside its input, first check whether a disposable input copy in the temporary directory preserves the behavior being tested. Do not move the user's original source merely to run a tool.

Own the lifecycle of scratch you create. Prefer `TemporaryDirectory` or `try/finally` cleanup for scoped scripts. Reading or verifying an analysis export does not make it a final deliverable: remove it once the required information has been used. A tool that accepts an output directory may deliberately retain successful output; the caller remains responsible for analysis-only output.

Before final handover, verify the requested final files, remove disposable task-owned exports, snapshots, probe scripts, logs and intermediate build/render output, and check that removal succeeded. Preserve source changes, requested deliverables, pre-existing files and evidence needed for review or continuation. Do not delete a user-selected output folder as a whole; remove only known task-owned disposable items. An untracked file or temporary-looking name alone does not establish ownership.

On failure or interruption, clean scratch that is no longer needed. Keep only necessary recovery/continuation evidence outside the project and record its path and purpose in the existing response or handoff; clean it after use on resumption. If cleanup fails because a file is locked or inaccessible, give the remaining path and reason instead of claiming it was removed. No auxiliary files means no cleanup scan or extra cleanup report is needed.
