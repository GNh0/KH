<#
.SYNOPSIS
    PowerBuilder PBL -> SRD/SRU/SRW Export Tool
.EXAMPLE
    .\Export-PBL.ps1 -Version 125 -PblPath "C:\project\myapp.pbl" -Action list
    .\Export-PBL.ps1 -Version 105 -PblPath "C:\project\myapp.pbl" -Action exportall
    .\Export-PBL.ps1 -Version 70  -PblPath "C:\project\myapp.pbl" -Action export -ObjectName "d_employee"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$Version,

    [Parameter(Mandatory=$true)]
    [string]$PblPath,

    [Parameter(Mandatory=$true)]
    [ValidateSet("list","export","exportall")]
    [string]$Action,

    [string]$ObjectName,

    [string]$OutputDirectory,

    [string]$OrcaDllPath,

    [string]$RuntimePath,

    [string]$HelperPath,

    [string]$CscPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

function Stop-PblExport {
    param(
        [Parameter(Mandatory=$true)][string]$Message,
        [Parameter(Mandatory=$true)][int]$ExitCode
    )

    [Console]::Error.WriteLine("[ERROR] " + $Message)
    exit $ExitCode
}

function Test-AnsiRoundTrip {
    param([Parameter(Mandatory=$true)][string]$Value)

    try {
        $encoding = [System.Text.Encoding]::GetEncoding(
            [System.Text.Encoding]::Default.CodePage,
            [System.Text.EncoderFallback]::ExceptionFallback,
            [System.Text.DecoderFallback]::ExceptionFallback
        )
        $bytes = $encoding.GetBytes($Value)
        return $encoding.GetString($bytes) -ceq $Value
    }
    catch {
        return $false
    }
}

$versionConfigs = @{
    "70" = @{
        OrcaDll = "C:\Program Files (x86)\Sybase\Shared\PowerBuilder\pborc70.dll"
        RuntimeDirectories = @(
            "C:\Program Files (x86)\Sybase\Shared\PowerBuilder",
            "C:\Program Files\Sybase\Shared\PowerBuilder"
        )
        RuntimeDlls = @("pbvm70.dll")
        ApiMode = "ansi"
    }
    "105" = @{
        OrcaDll = "C:\Program Files\Sybase\Shared\PowerBuilder\PBORC105.DLL"
        RuntimeDirectories = @("C:\Program Files\Sybase\Shared\PowerBuilder")
        RuntimeDlls = @("PBVM105.DLL")
        ApiMode = "unicode"
    }
    "125" = @{
        OrcaDll = "C:\Program Files\Sybase\Shared\PowerBuilder\PBORC125.DLL"
        RuntimeDirectories = @("C:\Program Files\Sybase\Shared\PowerBuilder")
        RuntimeDlls = @("PBVM125.DLL")
        ApiMode = "unicode"
    }
}

$config = $versionConfigs[$Version]
if ($null -eq $config) {
    Stop-PblExport "Select exactly one supported version: 70, 105, or 125." 10
}

$orcaDll = if ([string]::IsNullOrWhiteSpace($OrcaDllPath)) {
    [string]$config.OrcaDll
}
else {
    $OrcaDllPath
}

$runtimeDirectories = if ([string]::IsNullOrWhiteSpace($RuntimePath)) {
    @($config.RuntimeDirectories)
}
else {
    @($RuntimePath.Split([System.IO.Path]::PathSeparator) | Where-Object {
        -not [string]::IsNullOrWhiteSpace($_)
    })
}

if (-not (Test-Path -LiteralPath $orcaDll -PathType Leaf)) {
    Stop-PblExport "ORCA DLL not found: $orcaDll" 11
}

foreach ($runtimeDirectory in $runtimeDirectories) {
    if (-not (Test-Path -LiteralPath $runtimeDirectory -PathType Container)) {
        Stop-PblExport "PowerBuilder runtime directory not found: $runtimeDirectory" 12
    }
}

foreach ($runtimeDll in @($config.RuntimeDlls)) {
    $runtimeDllFound = $false
    foreach ($runtimeDirectory in $runtimeDirectories) {
        if (Test-Path -LiteralPath (Join-Path $runtimeDirectory $runtimeDll) -PathType Leaf) {
            $runtimeDllFound = $true
            break
        }
    }
    if (-not $runtimeDllFound) {
        Stop-PblExport "PowerBuilder runtime DLL not found: $runtimeDll" 13
    }
}

$resolvedPbl = Resolve-Path -LiteralPath $PblPath -ErrorAction SilentlyContinue
if ($null -eq $resolvedPbl) {
    Stop-PblExport "PBL not found: $PblPath" 14
}
$PblPath = $resolvedPbl.Path

if ($Action -notin @("list", "export", "exportall")) {
    Stop-PblExport "Unsupported action: $Action" 15
}

if ($Action -eq "export" -and [string]::IsNullOrWhiteSpace($ObjectName)) {
    Stop-PblExport "-ObjectName is required for export action." 16
}

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    Stop-PblExport "Specify an explicit output directory outside the source project." 17
}
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)

if (-not (Test-Path -LiteralPath $OutputDirectory)) {
    try {
        $null = New-Item -ItemType Directory -Path $OutputDirectory -Force
    }
    catch {
        Stop-PblExport "Output directory cannot be created: $OutputDirectory" 17
    }
}
if (-not (Test-Path -LiteralPath $OutputDirectory -PathType Container)) {
    Stop-PblExport "Output path is not a directory: $OutputDirectory" 18
}

if ($config.ApiMode -eq "ansi") {
    if (-not (Test-AnsiRoundTrip $PblPath)) {
        Stop-PblExport "PB7 cannot represent the PBL path without data loss. Use an ASCII-safe staged path." 19
    }
    if (-not [string]::IsNullOrEmpty($ObjectName) -and -not (Test-AnsiRoundTrip $ObjectName)) {
        Stop-PblExport "PB7 cannot represent ObjectName without data loss." 20
    }
}

# This changes only the current PowerShell process. The helper inherits the same
# selected-version environment; the parent Codex/CMD/global PATH is untouched.
$pathPrefix = [string]::Join([System.IO.Path]::PathSeparator, $runtimeDirectories)
$processPath = [Environment]::GetEnvironmentVariable("PATH", "Process")
$env:PATH = if ([string]::IsNullOrEmpty($processPath)) {
    $pathPrefix
}
else {
    $pathPrefix + [System.IO.Path]::PathSeparator + $processPath
}

# ---- Inline C# (ASCII only) ----
$csSource = @'
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

class PblExporter
{
    [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    static extern IntPtr LoadLibraryW(string path);
    [DllImport("kernel32.dll", CharSet=CharSet.Ansi, ExactSpelling=true, SetLastError=true)]
    static extern IntPtr GetProcAddress(IntPtr hModule, string procName);
    [DllImport("kernel32.dll")]
    static extern bool FreeLibrary(IntPtr hModule);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern bool SetDllDirectoryW(string path);

    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate IntPtr DelOpen();
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate void   DelClose(IntPtr h);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int    DelLibDir(IntPtr h, IntPtr lib, IntPtr cmt, int cLen, IntPtr cb, IntPtr ud);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int    DelExport(IntPtr h, IntPtr lib, IntPtr entry, int type, IntPtr buf, int bufSz);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate void   DelCB(IntPtr p, IntPtr ud);

    static readonly string[] TN = {"Application","DataWindow","Function","Menu","Query","Structure","UserObject","Window","Pipeline","Project","ProxyObject","Binary"};
    static readonly string[] EX = {".sra",".srd",".srf",".srm",".srq",".srs",".sru",".srw",".srp",".srj",".srx",".bin"};

    struct Obj { public string Name; public int Type; }
    static List<Obj> objs = new List<Obj>();
    static bool uni; static int nOff, tOff, cSz;
    static DelCB cbDel;

    static void CB(IntPtr p, IntPtr ud) {
        try {
            IntPtr np = Marshal.ReadIntPtr(IntPtr.Add(p, nOff));
            string nm = uni ? Marshal.PtrToStringUni(np) : Marshal.PtrToStringAnsi(np);
            int tp = Marshal.ReadInt32(IntPtr.Add(p, tOff));
            if (!string.IsNullOrEmpty(nm)) objs.Add(new Obj{Name=nm, Type=tp});
        } catch {}
    }

    static IntPtr AS(string s) { return uni ? Marshal.StringToHGlobalUni(s) : Marshal.StringToHGlobalAnsi(s); }
    static T GF<T>(IntPtr h, string n) where T:class {
        IntPtr a = GetProcAddress(h, n);
        return a == IntPtr.Zero ? null : (T)(object)Marshal.GetDelegateForFunctionPointer(a, typeof(T));
    }

    static string ErrMsg(int c) {
        switch(c) {
            case -3: return "Object not found";
            case -4: return "Bad library";
            case -7: return "Library I/O error";
            case -10: return "Buffer too small";
            default: return "Error code " + c;
        }
    }

    static int Main(string[] args) {
        if (args.Length < 5) {
            Console.Error.WriteLine("Usage: exe <dll> <pbl> <list|export|exportall> <output-dir> <ansi|unicode> [name]");
            return 1;
        }
        string dll = args[0], pbl = Path.GetFullPath(args[1]), act = args[2].ToLower();
        string outD = Path.GetFullPath(args[3]), apiMode = args[4].ToLower();
        string tgt = args.Length > 5 ? args[5] : null;

        if (apiMode == "ansi") { uni = false; cSz = 1; nOff = 264; tOff = 268; }
        else if (apiMode == "unicode") { uni = true; cSz = 2; nOff = 520; tOff = 524; }
        else { Console.Error.WriteLine("[ERROR] Invalid API mode: " + apiMode); return 1; }

        if (act != "list" && act != "export" && act != "exportall") {
            Console.Error.WriteLine("[ERROR] Invalid action: " + act);
            return 1;
        }

        if (!File.Exists(pbl)) { Console.Error.WriteLine("[ERROR] PBL not found: " + pbl); return 1; }

        SetDllDirectoryW(Path.GetDirectoryName(Path.GetFullPath(dll)));
        IntPtr hL = LoadLibraryW(Path.GetFullPath(dll));
        if (hL == IntPtr.Zero) { Console.Error.WriteLine("[ERROR] DLL load failed (err:" + Marshal.GetLastWin32Error() + ")"); return 1; }

        try {
            var fO = GF<DelOpen>(hL, "PBORCA_SessionOpen");
            var fC = GF<DelClose>(hL, "PBORCA_SessionClose");
            var fD = GF<DelLibDir>(hL, "PBORCA_LibraryDirectory");
            var fE = GF<DelExport>(hL, "PBORCA_LibraryEntryExport");
            if (fO == null || fC == null || fD == null) {
                Console.Error.WriteLine("[ERROR] ORCA function not found"); return 1;
            }

            IntPtr hS = fO();
            if (hS == IntPtr.Zero) { Console.Error.WriteLine("[ERROR] Session open failed"); return 1; }

            try {
                cbDel = new DelCB(CB);
                IntPtr cbP = Marshal.GetFunctionPointerForDelegate(cbDel);
                IntPtr pL = AS(pbl);
                IntPtr pC = Marshal.AllocHGlobal(2048 * cSz);
                int rc = fD(hS, pL, pC, 2048, cbP, IntPtr.Zero);
                Marshal.FreeHGlobal(pC);
                Marshal.FreeHGlobal(pL);
                if (rc != 0) { Console.Error.WriteLine("[ERROR] LibraryDirectory failed: " + ErrMsg(rc)); return 1; }

                if (act == "list") {
                    Console.WriteLine();
                    Console.WriteLine("=== Object List ===");
                    Console.WriteLine("File: " + pbl);
                    Console.WriteLine(new string('-', 65));
                    Console.WriteLine(String.Format("  {0,-35} {1,-15} {2}", "Name", "Type", "Ext"));
                    Console.WriteLine(new string('-', 65));
                    foreach (var o in objs) {
                        string tn = o.Type >= 0 && o.Type < TN.Length ? TN[o.Type] : "Unknown";
                        string ex = o.Type >= 0 && o.Type < EX.Length ? EX[o.Type] : ".?";
                        Console.WriteLine(String.Format("  {0,-35} {1,-15} {2}", o.Name, tn, ex));
                    }
                    Console.WriteLine(new string('-', 65));
                    Console.WriteLine("Total: " + objs.Count + " objects");
                }
                else if (act == "export" || act == "exportall") {
                    if (fE == null) { Console.Error.WriteLine("[ERROR] Export function not found"); return 1; }
                    if (!Directory.Exists(outD)) Directory.CreateDirectory(outD);
                    int ok = 0, fail = 0, skip = 0, matched = 0;
                    Console.WriteLine();
                    Console.WriteLine("=== Export Start ===");
                    Console.WriteLine("Output: " + outD);
                    Console.WriteLine();

                    foreach (var o in objs) {
                        if (o.Type == 11) { skip++; continue; }
                        if (act == "export" && tgt != null && !o.Name.Equals(tgt, StringComparison.OrdinalIgnoreCase)) continue;
                        matched++;

                        int bSz = 10 * 1024 * 1024;
                        IntPtr buf = Marshal.AllocHGlobal(bSz * cSz);
                        try {
                            IntPtr pL2 = AS(pbl);
                            IntPtr pE = AS(o.Name);
                            int r2 = fE(hS, pL2, pE, o.Type, buf, bSz);
                            Marshal.FreeHGlobal(pL2);
                            Marshal.FreeHGlobal(pE);

                            if (r2 == 0) {
                                string src = uni ? Marshal.PtrToStringUni(buf) : Marshal.PtrToStringAnsi(buf);
                                string ext = o.Type >= 0 && o.Type < EX.Length ? EX[o.Type] : ".txt";
                                string fp = Path.Combine(outD, o.Name + ext);
                                File.WriteAllText(fp, src, new UTF8Encoding(true));
                                Console.WriteLine("  [OK]   " + o.Name + ext);
                                ok++;
                            } else {
                                Console.Error.WriteLine("  [FAIL] " + o.Name + " -> " + ErrMsg(r2));
                                fail++;
                            }
                        } finally { Marshal.FreeHGlobal(buf); }
                    }
                    Console.WriteLine();
                    Console.WriteLine("Done: OK=" + ok + " / FAIL=" + fail + " / SKIP=" + skip);
                    if (act == "export" && matched == 0) {
                        Console.Error.WriteLine("[ERROR] '" + tgt + "' not found. Use 'list' first.");
                        return 4;
                    }
                    if (fail > 0) return 5;
                }
            } finally { fC(hS); }
        } finally { FreeLibrary(hL); }
        return 0;
    }
}
'@

function Get-PeMachine {
    param([Parameter(Mandatory=$true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }

    $stream = $null
    $reader = $null
    try {
        $stream = [System.IO.File]::OpenRead($Path)
        $reader = New-Object System.IO.BinaryReader($stream)
        if ($reader.ReadUInt16() -ne 0x5A4D) { return $null }
        $stream.Position = 0x3C
        $peOffset = $reader.ReadInt32()
        $stream.Position = $peOffset
        if ($reader.ReadUInt32() -ne 0x00004550) { return $null }
        return $reader.ReadUInt16()
    }
    catch {
        return $null
    }
    finally {
        if ($null -ne $reader) { $reader.Dispose() }
        elseif ($null -ne $stream) { $stream.Dispose() }
    }
}

function Get-PblSha256 {
    param([Parameter(Mandatory=$true)][string]$Path)
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    $stream = $null
    try {
        $stream = [System.IO.File]::OpenRead($Path)
        return [System.BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace("-", "").ToLowerInvariant()
    }
    finally {
        if ($null -ne $stream) { $stream.Dispose() }
        $algorithm.Dispose()
    }
}

# ---- Compile the x86 helper when absent, wrong-architecture, or stale ----
$exePath = if ([string]::IsNullOrWhiteSpace($HelperPath)) {
    Join-Path $PSScriptRoot "PblExporter.exe"
}
else {
    [System.IO.Path]::GetFullPath($HelperPath)
}

$helperExists = Test-Path -LiteralPath $exePath -PathType Leaf
$helperMachine = if ($helperExists) { Get-PeMachine $exePath } else { $null }
$bundlePath = Join-Path $PSScriptRoot "bundle.json"
$bundledExePath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "PblExporter.exe"))
$helperIsStale = $true
$bundleValidationError = ""
if ($helperExists) {
    if ($exePath -eq $bundledExePath -and (Test-Path -LiteralPath $bundlePath -PathType Leaf)) {
        try {
            $bundle = Get-Content -LiteralPath $bundlePath -Raw | ConvertFrom-Json
            $scriptHash = Get-PblSha256 $PSCommandPath
            $helperHash = Get-PblSha256 $exePath
            $helperIsStale = $scriptHash -ne $bundle.sha256.'Export-PBL.ps1' -or $helperHash -ne $bundle.sha256.'PblExporter.exe'
        }
        catch {
            $helperIsStale = $true
            $bundleValidationError = $_.Exception.Message
        }
    }
    else {
        $helperIsStale = (Get-Item -LiteralPath $exePath).LastWriteTimeUtc -lt (Get-Item -LiteralPath $PSCommandPath).LastWriteTimeUtc
    }
}
$needBuild = (-not $helperExists) -or ($helperMachine -ne 0x014C) -or $helperIsStale

if ($needBuild) {
    if ([string]::IsNullOrWhiteSpace($CscPath)) {
        Stop-PblExport "Helper validation failed (exists=$helperExists, machine=$helperMachine, stale=$helperIsStale, detail=$bundleValidationError). Use export_pbl.py --compile-helper only when extraction requires a helper build." 21
    }
    $toolPrefix = [System.IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\') + '\'
    if ($exePath.StartsWith($toolPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        Stop-PblExport "Helper builds must use an explicit temporary HelperPath outside the plugin." 21
    }
    Write-Host "[BUILD] Compiling x86 helper..." -ForegroundColor Cyan
    $selectedCsc = $CscPath
    if ([string]::IsNullOrWhiteSpace($selectedCsc)) {
        $selectedCsc = "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
        if (-not (Test-Path -LiteralPath $selectedCsc -PathType Leaf)) {
            $selectedCsc = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
        }
    }
    if (-not (Test-Path -LiteralPath $selectedCsc -PathType Leaf)) {
        Stop-PblExport "csc.exe not found: $selectedCsc" 21
    }

    $buildToken = [Guid]::NewGuid().ToString("N")
    $csPath = Join-Path ([System.IO.Path]::GetTempPath()) ("kh-pbl-exporter-" + $buildToken + ".cs")
    $compiledPath = Join-Path ([System.IO.Path]::GetTempPath()) ("kh-pbl-exporter-" + $buildToken + ".exe")

    try {
        [System.IO.File]::WriteAllText($csPath, $csSource, [System.Text.UTF8Encoding]::new($false))
        $compilerOutput = & $selectedCsc /nologo /platform:x86 /optimize "/out:$compiledPath" $csPath 2>&1
        $compilerExitCode = $LASTEXITCODE
        if ($compilerOutput) { $compilerOutput | ForEach-Object { Write-Host $_ } }
        if ($compilerExitCode -ne 0 -or -not (Test-Path -LiteralPath $compiledPath -PathType Leaf)) {
            Stop-PblExport "x86 helper compilation failed with exit code $compilerExitCode." 22
        }
        if ((Get-PeMachine $compiledPath) -ne 0x014C) {
            Stop-PblExport "Compiled helper is not x86." 23
        }
        Move-Item -LiteralPath $compiledPath -Destination $exePath -Force
    }
    finally {
        Remove-Item -LiteralPath $csPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $compiledPath -Force -ErrorAction SilentlyContinue
    }
    Write-Host "[BUILD] Done" -ForegroundColor Green
}

if ((Get-PeMachine $exePath) -ne 0x014C) {
    Stop-PblExport "PblExporter helper is not a valid x86 executable." 24
}

# ---- Run exactly once in the selected-version child environment ----
Write-Host "PB $Version | $Action | $PblPath" -ForegroundColor Yellow
$exeArgs = @($orcaDll, $PblPath, $Action, $OutputDirectory, [string]$config.ApiMode)
if (-not [string]::IsNullOrWhiteSpace($ObjectName)) { $exeArgs += $ObjectName }

try {
    & $exePath @exeArgs
    $helperExitCode = $LASTEXITCODE
}
catch {
    [Console]::Error.WriteLine("[ERROR] Helper launch failed: " + $_.Exception.Message)
    exit 25
}

if ($helperExitCode -ne 0) {
    [Console]::Error.WriteLine("[ERROR] PblExporter failed with exit code $helperExitCode.")
}
exit $helperExitCode
