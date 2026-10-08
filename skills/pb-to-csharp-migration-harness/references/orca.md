# PB extraction / ORCA

Verify the exact PBL, selected ORCA DLL, bitness, dependent DLLs, child-process PATH, and license. Omit the version normally: the bundled launcher finds installed PB 7.0/10.5/12.5 runtimes and attempts extraction in descending version order. Only successful native execution with recognizable fresh PB source confirms the selected runtime. A PBL header of 0600 alone does not establish PB 6. This selects a runtime that can read the library, not proof of its original authoring version.

PblScripter's export script and x86 helper are bundled under `scripts/pbl-exporter`; no `C:\PblScripter` installation is needed. PowerBuilder's vendor DLLs remain part of the local licensed installation. Standard Sybase paths and PATH directories are checked for matching ORCA/runtime DLLs. `convert` requires an explicit export output directory; use a task-specific system temporary directory for analysis exports unless the user specifies a final destination. Automatic selection uses a temporary PBL copy and isolated output per candidate; failed/partial outputs are discarded. `probe` only inspects capability, not actual library compatibility.

Even with exit code 0, Session open failed, Bad library, SySAM/license errors, or empty output mean failure. One issue fixed by changing PATH does not explain every later error. Inspect actual output and target exports. If extraction fails, continue with supplied exports/pasted source and identify missing evidence.
# Local tool usage

Call the launcher by absolute path from any working directory (Python 3.11+, Windows PowerShell):

```powershell
python -B <skill-root>/scripts/export_pbl.py probe --pbl <absolute-pbl>
python -B <skill-root>/scripts/export_pbl.py convert --pbl <absolute-pbl> --output-directory <absolute-temp-output>
python -B <skill-root>/scripts/export_pbl.py convert --pbl <absolute-pbl> --action export --object-name <object> --output-directory <absolute-temp-output>
```

Normally omit `--version` and `--tool-root`. If necessary, `--version 70|105|125` pins one runtime, `--orca-dll` and repeated `--runtime-directory` override a custom installation, and `--tool-root` selects an external exporter. Unsupported/missing runtimes are reported; do not silently install PB or migrate a library. Inspect `version_attempts` for failures when automatic selection cannot extract the requested source.

The shipped helper is checked against the source/binary hashes in `bundle.json`; archive/checkout timestamps do not trigger a build. If it is absent or mismatched, select `--compile-helper` only when other supplied exports cannot support the task and rebuilding is necessary. Helper builds use a disposable system temporary directory and leave the plugin and source project untouched. This execution option does not require separate approval paperwork. Releasing an edited exporter requires rebuilding the paired helper and refreshing the two hashes.

Check exit codes, error diagnostics, and newly created/changed nonempty PB exports together. Exit 0 with error text is failure; exit 0 without new output is unverified. This check does not establish full application behavior either. Before calling an actual external Export-PBL.ps1, read its target paths and version options.
