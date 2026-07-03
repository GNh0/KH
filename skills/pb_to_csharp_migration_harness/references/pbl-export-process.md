# PBL Export Process

This reference captures the portable PowerBuilder export procedure used by the migration harness. It is written as a fallback guide; local tools may not exist.

## Provider order

Use a PBL export provider in this order:

1. PblScripter or an equivalent `Export-PBL.ps1` wrapper.
2. Direct ORCA, when the wrapper is missing but the matching PB runtime/ORCA libraries are installed.
3. Already exported `.sru`, `.srw`, `.srd`, or `.srm` source files.
4. Pasted PB source text.
5. User-described PB behavior.
6. Bundled reference baseline only.

The useful operations are the same for PblScripter and direct ORCA:

- list objects in a PBL before export;
- export the named screen/user object first;
- export linked DataWindows after the SRU/SRW points to them;
- export into a separate output directory, never into the source PBL tree;
- preserve original encoding when reading exported text.

Known local example commands from prior sessions used `-Version 70`, `-Action list`, `-Action export`, `-ObjectName <object>`, and a target output folder beside or outside the source tree. These are examples only; the harness must not require that path to exist. When using direct ORCA instead of the wrapper, preserve the same sequence: open session, open library, list entries, export selected object, close library/session.

## Version matching

Match the ORCA/runtime major version to the PBL lineage before opening or exporting:

- PB 7.0 PBL: use PB 7.0 ORCA/runtime.
- PB 12.5 PBL: use PB 12.5 ORCA/runtime.
- Unknown version: probe/list only, record the suspected version, and do not claim full source parity until the version/runtime is confirmed.

Do not treat a failed export as proof that the PBL is corrupt until the PB version, runtime DLL path, and ORCA/license state are checked.

## Runtime prerequisites

PowerBuilder libraries may require PB shared runtime paths before ORCA can open older PBLs. If export fails with messages like `Session open failed` or `Bad library`, check runtime DLL path and PB version before concluding that the PBL is corrupt.

If licensing/SySAM blocks ORCA export, stop claiming full source evidence. Use pasted source, previously exported files, screenshots, report designer, or binary strings only as lower-confidence evidence.

## Evidence strength

Strong evidence:

- exported `.sru`, `.srw`, and `.srd` files from the active PBL;
- event flow confirmed in SRU/SRW;
- linked DataWindow retrieve/update metadata confirmed in SRD;
- PB behavior compared against C#/SP target logic.

Weak evidence:

- binary string extraction from `.pbl` or `.pbd`;
- object names only;
- screenshots without source;
- stale rollout notes without current file verification.

## Safe export policy

Do not write under the source tree when exporting for analysis. Use an external output directory controlled by the current run. Keep generated fragments, probes, and verifier output under that output directory.

If the source root is a production or legacy working directory, treat it as read-only. If the sandbox prevents direct export, request permission or ask the user for exported files instead of creating substitute outputs.

## Error interpretation

- Tool missing: continue with standalone or pasted-source mode.
- PBL missing: ask for the correct artifact or proceed with references only.
- Runtime path missing: try the documented runtime path fix if permission and tool access allow it.
- ORCA/license failure: mark blocked for full source inspection and proceed with weak evidence only.
- Encoding damage: re-read with the correct encoding before quoting identifiers or Korean text.
