from __future__ import annotations

import argparse
import json
import locale
import os
import shutil
import struct
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence


FALLBACK_ORDER = ("exported_source", "pasted_source", "described_behavior")
SUPPORTED_ACTIONS = frozenset({"list", "export", "exportall"})
X86_PE_MACHINE = 0x014C


@dataclass(frozen=True)
class OrcaVersionConfig:
    version: str
    orca_dll: Path
    runtime_directories: tuple[Path, ...]
    runtime_dll_names: tuple[str, ...]
    api_mode: str

    def __post_init__(self) -> None:
        if self.api_mode not in {"ansi", "unicode"}:
            raise ValueError("api_mode must be 'ansi' or 'unicode'")
        if not self.runtime_directories:
            raise ValueError("at least one runtime directory is required")


@dataclass(frozen=True)
class OrcaRequest:
    tool_root: Path
    version: str | None
    pbl_path: Path
    action: str
    object_name: str | None = None
    output_directory: Path | None = None
    ascii_stage_root: Path | None = None


@dataclass(frozen=True)
class OrcaCapabilityDecision:
    status: str
    reason_code: str
    message: str
    selected_version: str | None
    tool_script: Path
    orca_dll: Path | None
    runtime_directories: tuple[Path, ...]
    runtime_dlls: tuple[Path, ...]
    helper_path: Path
    helper_mode: str | None
    csc_path: Path | None
    output_directory: Path
    api_mode: str | None
    ascii_staging_required: bool
    ascii_stage_root: Path | None
    executed_process_count: int = 0
    fallback_order: tuple[str, ...] = FALLBACK_ORDER

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "reason_code": self.reason_code,
            "message": self.message,
            "selected_version": self.selected_version,
            "tool_script": str(self.tool_script),
            "orca_dll": str(self.orca_dll) if self.orca_dll else None,
            "runtime_directories": [str(path) for path in self.runtime_directories],
            "runtime_dlls": [str(path) for path in self.runtime_dlls],
            "helper_path": str(self.helper_path),
            "helper_mode": self.helper_mode,
            "csc_path": str(self.csc_path) if self.csc_path else None,
            "output_directory": str(self.output_directory),
            "api_mode": self.api_mode,
            "ascii_staging_required": self.ascii_staging_required,
            "ascii_stage_root": (
                str(self.ascii_stage_root) if self.ascii_stage_root else None
            ),
            "executed_process_count": self.executed_process_count,
            "fallback_order": list(self.fallback_order),
        }


@dataclass(frozen=True)
class OrcaConversionResult:
    status: str
    reason_code: str
    message: str
    executed: bool
    exit_code: int | None
    stdout: str
    stderr: str
    command: tuple[str, ...]
    path_prefix: tuple[str, ...]
    staged_input: bool
    probe: OrcaCapabilityDecision

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "reason_code": self.reason_code,
            "message": self.message,
            "executed": self.executed,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "command": list(self.command),
            "path_prefix": list(self.path_prefix),
            "staged_input": self.staged_input,
            "probe": self.probe.to_dict(),
        }


def default_version_configs() -> dict[str, OrcaVersionConfig]:
    return {
        "70": OrcaVersionConfig(
            version="70",
            orca_dll=Path(
                r"C:\Program Files (x86)\Sybase\Shared\PowerBuilder\pborc70.dll"
            ),
            runtime_directories=(
                Path(r"C:\Program Files (x86)\Sybase\Shared\PowerBuilder"),
                Path(r"C:\Program Files\Sybase\Shared\PowerBuilder"),
            ),
            runtime_dll_names=("pbvm70.dll",),
            api_mode="ansi",
        ),
        "105": OrcaVersionConfig(
            version="105",
            orca_dll=Path(
                r"C:\Program Files\Sybase\Shared\PowerBuilder\PBORC105.DLL"
            ),
            runtime_directories=(
                Path(r"C:\Program Files\Sybase\Shared\PowerBuilder"),
            ),
            runtime_dll_names=("PBVM105.DLL",),
            api_mode="unicode",
        ),
        "125": OrcaVersionConfig(
            version="125",
            orca_dll=Path(
                r"C:\Program Files\Sybase\Shared\PowerBuilder\PBORC125.DLL"
            ),
            runtime_directories=(
                Path(r"C:\Program Files\Sybase\Shared\PowerBuilder"),
            ),
            runtime_dll_names=("PBVM125.DLL",),
            api_mode="unicode",
        ),
    }


def read_pe_machine(path: Path) -> int | None:
    try:
        with path.open("rb") as stream:
            if stream.read(2) != b"MZ":
                return None
            stream.seek(0x3C)
            offset_bytes = stream.read(4)
            if len(offset_bytes) != 4:
                return None
            pe_offset = struct.unpack("<I", offset_bytes)[0]
            stream.seek(pe_offset)
            if stream.read(4) != b"PE\x00\x00":
                return None
            machine_bytes = stream.read(2)
            if len(machine_bytes) != 2:
                return None
            return struct.unpack("<H", machine_bytes)[0]
    except (OSError, ValueError):
        return None


def _default_ansi_encoding() -> str:
    try:
        "".encode("mbcs")
        return "mbcs"
    except LookupError:
        return locale.getpreferredencoding(False) or "cp1252"


def _round_trips(value: str, encoding: str) -> bool:
    try:
        return value.encode(encoding, errors="strict").decode(
            encoding, errors="strict"
        ) == value
    except (LookupError, UnicodeError):
        return False


def _is_ascii_path(path: Path) -> bool:
    return str(path).isascii()


def _nearest_existing_parent(path: Path) -> Path | None:
    candidate = path
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate:
            return None
        candidate = parent
    return candidate if candidate.is_dir() else candidate.parent


class PbOrcaRuntime:
    def __init__(
        self,
        *,
        version_configs: Mapping[str, OrcaVersionConfig] | None = None,
        process_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        base_environment: Mapping[str, str] | None = None,
        powershell_executable: str = "powershell.exe",
        ansi_encoding: str | None = None,
        csc_candidates: Sequence[Path] | None = None,
    ) -> None:
        self._version_configs = dict(version_configs or default_version_configs())
        self._process_runner = process_runner
        self._base_environment = base_environment
        self._powershell_executable = powershell_executable
        self._ansi_encoding = ansi_encoding or _default_ansi_encoding()
        self._csc_candidates = tuple(
            csc_candidates
            if csc_candidates is not None
            else (
                Path(r"C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"),
                Path(
                    r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
                ),
            )
        )

    def _fallback(
        self,
        request: OrcaRequest,
        *,
        reason_code: str,
        message: str,
        config: OrcaVersionConfig | None = None,
        runtime_dlls: tuple[Path, ...] = (),
        helper_mode: str | None = None,
        csc_path: Path | None = None,
        ascii_staging_required: bool = False,
        ascii_stage_root: Path | None = None,
    ) -> OrcaCapabilityDecision:
        output_directory = request.output_directory or (
            request.pbl_path.parent / request.pbl_path.stem
        )
        return OrcaCapabilityDecision(
            status="fallback",
            reason_code=reason_code,
            message=message,
            selected_version=request.version,
            tool_script=request.tool_root / "Export-PBL.ps1",
            orca_dll=config.orca_dll if config else None,
            runtime_directories=config.runtime_directories if config else (),
            runtime_dlls=runtime_dlls,
            helper_path=request.tool_root / "PblExporter.exe",
            helper_mode=helper_mode,
            csc_path=csc_path,
            output_directory=output_directory,
            api_mode=config.api_mode if config else None,
            ascii_staging_required=ascii_staging_required,
            ascii_stage_root=ascii_stage_root,
        )

    def probe(self, request: OrcaRequest) -> OrcaCapabilityDecision:
        version = (request.version or "").strip()
        config = self._version_configs.get(version)
        if config is None:
            return self._fallback(
                request,
                reason_code="version_not_selected_or_unsupported",
                message="Select exactly one configured ORCA version before conversion.",
            )

        tool_script = request.tool_root / "Export-PBL.ps1"
        if not tool_script.is_file():
            return self._fallback(
                request,
                reason_code="tool_not_found",
                message="The configured PBL export tool is missing or moved.",
                config=config,
            )

        if request.action not in SUPPORTED_ACTIONS:
            return self._fallback(
                request,
                reason_code="unsupported_action",
                message="The requested PBL export action is not supported.",
                config=config,
            )

        if request.action == "export" and not (request.object_name or "").strip():
            return self._fallback(
                request,
                reason_code="object_name_required",
                message="ObjectName is required for the export action.",
                config=config,
            )

        if not request.pbl_path.is_file():
            return self._fallback(
                request,
                reason_code="pbl_not_found",
                message="The configured PBL input is missing or moved.",
                config=config,
            )

        if not config.orca_dll.is_file():
            return self._fallback(
                request,
                reason_code="orca_dll_not_found",
                message="The selected version's ORCA DLL is not available.",
                config=config,
            )

        missing_runtime_directories = [
            path for path in config.runtime_directories if not path.is_dir()
        ]
        if missing_runtime_directories:
            return self._fallback(
                request,
                reason_code="runtime_directory_not_found",
                message="A selected-version PowerBuilder runtime directory is missing.",
                config=config,
            )

        runtime_dlls: list[Path] = []
        for dll_name in config.runtime_dll_names:
            match = next(
                (
                    directory / dll_name
                    for directory in config.runtime_directories
                    if (directory / dll_name).is_file()
                ),
                None,
            )
            if match is None:
                return self._fallback(
                    request,
                    reason_code="runtime_dll_not_found",
                    message=(
                        "The selected version's required PowerBuilder runtime DLL "
                        f"is missing: {dll_name}"
                    ),
                    config=config,
                    runtime_dlls=tuple(runtime_dlls),
                )
            runtime_dlls.append(match)

        helper_path = request.tool_root / "PblExporter.exe"
        helper_mode: str | None = None
        csc_path = next((path for path in self._csc_candidates if path.is_file()), None)
        helper_is_current_x86 = (
            helper_path.is_file()
            and read_pe_machine(helper_path) == X86_PE_MACHINE
            and helper_path.stat().st_mtime_ns >= tool_script.stat().st_mtime_ns
        )
        if helper_is_current_x86:
            helper_mode = "existing_x86"
        elif csc_path is not None:
            helper_mode = "compile_x86"
        else:
            return self._fallback(
                request,
                reason_code="x86_helper_unavailable",
                message="No valid x86 helper or x86-targeting C# compiler is available.",
                config=config,
                runtime_dlls=tuple(runtime_dlls),
            )

        output_directory = request.output_directory or (
            request.pbl_path.parent / request.pbl_path.stem
        )
        output_parent = _nearest_existing_parent(output_directory)
        if output_parent is None or not os.access(output_parent, os.W_OK):
            return self._fallback(
                request,
                reason_code="output_path_unavailable",
                message="The output path has no existing writable parent.",
                config=config,
                runtime_dlls=tuple(runtime_dlls),
                helper_mode=helper_mode,
                csc_path=csc_path,
            )

        ascii_staging_required = False
        ascii_stage_root: Path | None = None
        if config.api_mode == "ansi":
            if not _round_trips(str(request.pbl_path), self._ansi_encoding):
                candidate = request.ascii_stage_root or Path(tempfile.gettempdir())
                if (
                    not candidate.is_dir()
                    or not _is_ascii_path(candidate)
                    or not os.access(candidate, os.W_OK)
                ):
                    return self._fallback(
                        request,
                        reason_code="ascii_stage_path_unavailable",
                        message=(
                            "PB7 cannot represent the PBL path and no writable "
                            "ASCII-safe staging root is available."
                        ),
                        config=config,
                        runtime_dlls=tuple(runtime_dlls),
                        helper_mode=helper_mode,
                        csc_path=csc_path,
                        ascii_staging_required=True,
                        ascii_stage_root=candidate,
                    )
                ascii_staging_required = True
                ascii_stage_root = candidate

            if request.object_name and not _round_trips(
                request.object_name, self._ansi_encoding
            ):
                return self._fallback(
                    request,
                    reason_code="object_name_not_ansi_representable",
                    message=(
                        "PB7 cannot represent ObjectName without data loss; "
                        "conversion was not started."
                    ),
                    config=config,
                    runtime_dlls=tuple(runtime_dlls),
                    helper_mode=helper_mode,
                    csc_path=csc_path,
                    ascii_staging_required=ascii_staging_required,
                    ascii_stage_root=ascii_stage_root,
                )

        return OrcaCapabilityDecision(
            status="ready",
            reason_code="capability_ready",
            message="Capability probe passed without launching ORCA or its helper.",
            selected_version=version,
            tool_script=tool_script,
            orca_dll=config.orca_dll,
            runtime_directories=config.runtime_directories,
            runtime_dlls=tuple(runtime_dlls),
            helper_path=helper_path,
            helper_mode=helper_mode,
            csc_path=csc_path,
            output_directory=output_directory,
            api_mode=config.api_mode,
            ascii_staging_required=ascii_staging_required,
            ascii_stage_root=ascii_stage_root,
        )

    def _build_command(
        self,
        request: OrcaRequest,
        decision: OrcaCapabilityDecision,
        pbl_path: Path,
    ) -> list[str]:
        runtime_path = ";".join(str(path) for path in decision.runtime_directories)
        command = [
            self._powershell_executable,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(decision.tool_script),
            "-Version",
            str(decision.selected_version),
            "-PblPath",
            str(pbl_path),
            "-Action",
            request.action,
            "-OutputDirectory",
            str(decision.output_directory),
            "-OrcaDllPath",
            str(decision.orca_dll),
            "-RuntimePath",
            runtime_path,
            "-HelperPath",
            str(decision.helper_path),
        ]
        if decision.csc_path is not None:
            command.extend(("-CscPath", str(decision.csc_path)))
        if request.object_name:
            command.extend(("-ObjectName", request.object_name))
        return command

    def _execute(
        self,
        request: OrcaRequest,
        decision: OrcaCapabilityDecision,
        pbl_path: Path,
        *,
        staged_input: bool,
    ) -> OrcaConversionResult:
        base_environment = dict(
            self._base_environment
            if self._base_environment is not None
            else os.environ
        )
        path_prefix = tuple(str(path) for path in decision.runtime_directories)
        current_path = base_environment.get("PATH", "")
        base_environment["PATH"] = os.pathsep.join(
            [*path_prefix, *([current_path] if current_path else [])]
        )
        command = self._build_command(request, decision, pbl_path)

        try:
            completed = self._process_runner(
                command,
                cwd=str(request.tool_root),
                env=base_environment,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            return OrcaConversionResult(
                status="failed",
                reason_code="powershell_launch_failed",
                message="The PowerShell child process could not be started.",
                executed=False,
                exit_code=None,
                stdout="",
                stderr=str(exc),
                command=tuple(command),
                path_prefix=path_prefix,
                staged_input=staged_input,
                probe=decision,
            )

        exit_code = int(completed.returncode)
        return OrcaConversionResult(
            status="completed" if exit_code == 0 else "failed",
            reason_code=(
                "conversion_completed" if exit_code == 0 else "conversion_process_failed"
            ),
            message=(
                "PBL conversion completed."
                if exit_code == 0
                else "PBL conversion failed; the child exit code was preserved."
            ),
            executed=True,
            exit_code=exit_code,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            command=tuple(command),
            path_prefix=path_prefix,
            staged_input=staged_input,
            probe=decision,
        )

    def convert(self, request: OrcaRequest) -> OrcaConversionResult:
        decision = self.probe(request)
        if not decision.ready:
            return OrcaConversionResult(
                status="fallback",
                reason_code=decision.reason_code,
                message=decision.message,
                executed=False,
                exit_code=None,
                stdout="",
                stderr="",
                command=(),
                path_prefix=(),
                staged_input=False,
                probe=decision,
            )

        if not decision.ascii_staging_required:
            return self._execute(
                request,
                decision,
                request.pbl_path,
                staged_input=False,
            )

        assert decision.ascii_stage_root is not None
        with tempfile.TemporaryDirectory(
            prefix="kh-pb-orca-", dir=str(decision.ascii_stage_root)
        ) as temporary_directory:
            staged_path = Path(temporary_directory) / "input.pbl"
            shutil.copy2(request.pbl_path, staged_path)
            return self._execute(
                request,
                decision,
                staged_path,
                staged_input=True,
            )


def _build_request(arguments: argparse.Namespace) -> OrcaRequest:
    return OrcaRequest(
        tool_root=Path(arguments.tool_root),
        version=arguments.version,
        pbl_path=Path(arguments.pbl),
        action=arguments.action,
        object_name=arguments.object_name,
        output_directory=(
            Path(arguments.output_directory) if arguments.output_directory else None
        ),
        ascii_stage_root=(
            Path(arguments.ascii_stage_root) if arguments.ascii_stage_root else None
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PB ORCA runtime preflight and runner")
    parser.add_argument("operation", choices=("probe", "convert"))
    parser.add_argument("--tool-root", default=r"C:\PblScripter")
    parser.add_argument("--version")
    parser.add_argument("--pbl", required=True)
    parser.add_argument("--action", default="exportall")
    parser.add_argument("--object-name")
    parser.add_argument("--output-directory")
    parser.add_argument("--ascii-stage-root")
    arguments = parser.parse_args(argv)

    runtime = PbOrcaRuntime()
    request = _build_request(arguments)
    if arguments.operation == "probe":
        print(json.dumps(runtime.probe(request).to_dict(), ensure_ascii=False, indent=2))
        return 0

    result = runtime.convert(request)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    if result.status == "completed":
        return 0
    if result.exit_code is not None:
        return result.exit_code
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
