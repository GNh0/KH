# PB extraction / ORCA

Verify the exact PBL, user-selected PB version, ORCA DLL, bitness, dependent DLLs, child-process PATH, and license. A PBL header of 0600 alone does not establish PB 6. Successful preparation is not completed execution.

`src.pb.orca` provides execution of the existing PblScripter. Supply actual tool paths for the selected version. Use an explicit export output directory without changing user originals. If the environment needs a helper build, assess implementation necessity and the user's current build instructions.

Even with exit code 0, Session open failed, Bad library, SySAM/license errors, or empty output mean failure. One issue fixed by changing PATH does not explain every later error. Inspect actual output and target exports. If extraction fails, continue with supplied exports/pasted source and identify missing evidence.
# Local tool usage

`python -m src.pb.orca probe --pbl <absolute-pbl> --version <selected-version>` only reads the execution environment. Use `convert` when extraction is needed. Do not compile by default when a working x86 helper is absent. Select `--compile-helper` only when other supplied exports cannot support the task and an extraction helper is necessary. This is an execution option, not a procedure requiring separate approval paperwork.

Check exit codes, error diagnostics, and newly created/changed nonempty PB exports together. Exit 0 with error text is failure; exit 0 without new output is unverified. This check does not establish full application behavior either. Before calling an actual external Export-PBL.ps1, read its target paths and version options.
