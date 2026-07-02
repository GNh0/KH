# PBL Export Process

This reference captures the portable PowerBuilder export procedure used by the migration harness. It is written as a fallback guide; local tools may not exist.

## Preferred route

Use a PBL export tool such as `Export-PBL.ps1` or an equivalent ORCA/PblScripter wrapper when it is available. The useful operations are:

- list objects in a PBL before export;
- export the named screen/user object first;
- export linked DataWindows after the SRU/SRW points to them;
- export into a separate output directory, never into the source PBL tree;
- preserve original encoding when reading exported text.

Known local example commands from prior sessions used `-Version 70`, `-Action list`, `-Action export`, `-ObjectName <object>`, and a target output folder beside or outside the source tree. These are examples only; the harness must not require that path to exist.

## Runtime prerequisites

PowerBuilder 7 libraries may require PB shared runtime paths before ORCA can open older PBLs. If export fails with messages like `Session open failed` or `Bad library`, check runtime DLL path and PB version before concluding that the PBL is corrupt.

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
