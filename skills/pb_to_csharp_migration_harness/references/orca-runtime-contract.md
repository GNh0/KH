# PB ORCA Runtime Contract

## Purpose

This contract prevents the first PowerBuilder conversion in a fresh host session
from launching ORCA before the selected PowerBuilder runtime is available in the
child process environment.

It governs process startup only. It does not prove that a PBL is behaviorally
equivalent to exported source, that a license is valid, or that generated C# is
correct.

## Normative requirements

The words `must`, `must not`, and `require` in this file are release gates, not
recommendations. A direct PBL capability, list, or export claim is blocked unless
all five conditions below are evidenced:

1. The capability probe starts zero child processes and reports
   `executed_process_count=0`.
2. The request selects exactly one explicit PowerBuilder runtime version. No
   implicit default, version range, or try-next-version behavior is allowed.
3. A failed probe returns the standalone fallback decision without starting a
   helper or conversion process.
4. A conversion prepends the selected runtime only in the spawned child
   environment. Parent, user, machine, and later session `PATH` values remain
   unchanged.
5. Every launched list/export operation records the selected provider and
   version, argument array, child environment receipt, exact exit code,
   stdout/stderr receipt, and produced artifact paths plus SHA-256 values.

A zero exit code without the expected artifact receipts is not successful
conversion evidence. A nonzero exit code blocks conversion, parity, and
completion claims.

## Execution boundary

The runtime has two separate operations:

1. `probe` performs file, configuration, architecture, output-path, and argument
   checks. It launches zero ORCA, helper, compiler, or PowerShell processes.
2. `convert` consumes a successful probe, builds one child environment, and
   launches one selected-version conversion command.

Do not combine probe and conversion by trying each installed ORCA version until
one happens to work.

## Supported version data

Version data belongs in the runtime's configured `OrcaVersionConfig` records.
The host selects exactly one configured record and passes its API, DLLs, helper,
and runtime directories to the child operation. This document intentionally
does not name a default or enumerate machine-specific versions. Probing must
use the selected record and must not scan, infer, or retry other records.

## Capability probe

The probe validates only bounded, configured paths and values:

- the configured tool root and `Export-PBL.ps1`;
- exactly one selected version;
- the selected ORCA DLL;
- the selected version's runtime directories and required runtime DLLs;
- an existing x86 `PblExporter.exe`, or a compiler capable of producing it;
- the requested PBL and action;
- the output directory or its nearest existing writable parent;
- If the selected API declares legacy ANSI input, round-trip safety for the PBL
  path and object name.

The probe must not:

- execute PowerShell, ORCA, `PblExporter.exe`, `csc.exe`, or a license check;
- recursively search drives, projects, registry trees, or historical folders;
- mutate `PATH`, create output, copy a PBL, or persist a capability cache;
- infer or silently default the PowerBuilder version.

A successful probe reports `executed_process_count=0`.

## Fresh-session conversion flow

1. Require one configured version.
2. Run the zero-process probe.
3. Copy the current environment into a child-only dictionary.
4. Prepend only the selected version's runtime directories to the child
   `PATH`.
5. Build a command argument array beginning with:

   ```text
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File Export-PBL.ps1
   ```

6. Pass `Version`, `PblPath`, `Action`, `OutputDirectory`, `OrcaDllPath`,
   `RuntimePath`, `HelperPath`, and optional `ObjectName` as distinct arguments.
7. Start one PowerShell child with that environment. `Export-PBL.ps1` sets the
   same selected runtime prefix in its process scope before starting the helper.
8. Preserve the helper's exact exit code and capture the operation receipt
   required by the normative requirements.

Neither Python nor PowerShell may change the parent or machine/user `PATH`.

## Conditional legacy ANSI staging

Only a selected runtime whose configured API declares ANSI input uses this
staging rule.

- If both values round-trip through the active Windows ANSI code page, keep the
  original arguments, including spaces and Korean text.
- If only the PBL path cannot round-trip, copy it to a temporary ASCII-safe
  directory for this invocation and keep the requested output directory.
- Delete the temporary staged copy after the child returns.
- If the object name cannot round-trip, do not replace characters and do not
  start conversion. Return a structured fallback decision.

Staging is conditional. Unicode APIs and representable paths must not be copied
merely because they contain non-ASCII characters.

## Standalone fallback

Unknown version, moved/missing tool, missing DLL, unavailable x86 helper,
unwritable output, or unsafe arguments return:

- `status=fallback`;
- a stable `reason_code`;
- `executed=false`;
- no ORCA startup error text;
- fallback order `exported_source`, `pasted_source`, `described_behavior`.

Fallback is not conversion success and must not be reported as source parity.
The host must not continue with another installed runtime version after fallback.

## Exit-code contract

`Export-PBL.ps1` returns nonzero for:

- unsupported or missing version;
- missing ORCA/runtime DLL, PBL, output path, helper, or compiler;
- non-representable arguments for the selected ANSI API;
- helper compile or launch failure;
- ORCA session, library-directory, object lookup, or export failure.

`PblExporter.exe` returns nonzero when any selected export fails or a requested
object is absent. `Export-PBL.ps1` propagates that value. `PblExport.bat` checks
`ERRORLEVEL`, prints success only for zero, and exits with the original failure
code.

The host records one immutable operation receipt containing:

- `provider`, `selected_version`, `action`, and the exact argument array;
- `executed`, `child_started`, and `executed_process_count`;
- a child-environment fingerprint proving the selected runtime prefix without
  exposing or changing the parent `PATH`;
- the exact process exit code and bounded stdout/stderr artifact references;
- every object-list/export output path and SHA-256.

The receipt is evidence only for the command that produced it. Probe success is
not list/export success, process success is not artifact success, and artifact
presence is not PBL behavioral parity.

## Host API

Use the module without shell string interpolation:

```powershell
python -m src.skills.pb_orca_runtime probe `
  --tool-root "<absolute-tool-root>" `
  --version <selected-version> `
  --pbl "<absolute-pbl-path>" `
  --action list

python -m src.skills.pb_orca_runtime convert `
  --tool-root "<absolute-tool-root>" `
  --version <selected-version> `
  --pbl "<absolute-pbl-path>" `
  --action export `
  --object-name "<exact-object-name>"
```

The probe JSON is a capability decision, not an ORCA execution receipt. The
conversion JSON records whether a child started and preserves its exit code.

## Verification

Automated tests use temporary fake DLLs, a minimal x86 PE header, and an injected
process runner. They verify:

- zero process launches during probe;
- one first-call launch for each supported version;
- no execution for unknown version or missing tool/runtime;
- exact failure-code propagation;
- array-safe spaces and Korean arguments;
- selected runtime `PATH` and conversion in the same child call;
- no mutation of global `PATH`;
- conditional legacy-ANSI ASCII staging without lossy conversion.

Real ORCA licensing, session opening, PBL compatibility, exported-source
correctness, and DevExpress/C# migration behavior remain manual or environment
integration checks.
