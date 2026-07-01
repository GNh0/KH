from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class WindowsDevServerLaunchPlan:
    project_dir: str
    command: str
    port: int
    url: str
    stdout_path: str
    stderr_path: str
    health_check_command: str
    evidence: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_streamlit_launch_plan(
    project_dir: str | Path,
    app_path: str | Path | None = None,
    *,
    port: int = 8501,
    python_exe: str = "python",
    env: Dict[str, str] | None = None,
    visible: bool = False,
    log_dir: str = "logs",
) -> WindowsDevServerLaunchPlan:
    if app_path is None or not str(app_path).strip():
        raise ValueError("app_path must be explicit; KH must not assume a dashboard or web app layout.")

    root = Path(project_dir)
    stdout_path = root / log_dir / "streamlit.out"
    stderr_path = root / log_dir / "streamlit.err"
    window_style = "Normal" if visible else "Hidden"
    env_assignments = [
        "[Environment]::SetEnvironmentVariable('PATH', $null, 'Process')",
        "$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')",
    ]
    for key, value in sorted((env or {}).items()):
        env_assignments.append(f"$env:{_ps_identifier(key)} = '{_ps_quote(value)}'")

    app_arg = str(app_path)
    args = (
        f"-m streamlit run \"{_ps_quote(app_arg)}\" "
        f"--server.address 0.0.0.0 --server.port {int(port)} --server.headless true"
    )
    command_lines = [
        f"New-Item -ItemType Directory -Path '{_ps_quote(log_dir)}' -Force | Out-Null",
        *env_assignments,
        (
            f"$p = Start-Process -FilePath '{_ps_quote(python_exe)}' "
            f"-ArgumentList @('{_ps_quote(args)}') "
            "-WorkingDirectory (Get-Location) "
            f"-WindowStyle {window_style} "
            f"-RedirectStandardOutput '{_ps_quote(str(stdout_path))}' "
            f"-RedirectStandardError '{_ps_quote(str(stderr_path))}' "
            "-PassThru"
        ),
        "$p | Select-Object Id,ProcessName",
    ]
    url = f"http://127.0.0.1:{int(port)}"
    health = (
        f"try {{ (Invoke-WebRequest -UseBasicParsing -Uri {url} -TimeoutSec 10).StatusCode }} "
        "catch { $_.Exception.Message }"
    )
    return WindowsDevServerLaunchPlan(
        project_dir=str(root),
        command="\n".join(command_lines),
        port=int(port),
        url=url,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        health_check_command=health,
        evidence=[
            "windows_dev_server_launch_plan",
            "normalized_path_environment",
            "redirected_logs",
            "http_health_check",
        ],
        notes=[
            "Avoid Start-Process -UseNewEnvironment when Path/PATH duplicate keys can break Windows launches.",
            "Use a visible window only when the host needs an interactive long-running server.",
        ],
    )


def _ps_quote(value: str) -> str:
    return str(value).replace("'", "''")


def _ps_identifier(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(value))
    return cleaned or "KH_ENV"


__all__ = ["WindowsDevServerLaunchPlan", "build_streamlit_launch_plan"]
