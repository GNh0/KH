import re
import shlex
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from src.skills.base import agent_skill


CREDENTIAL_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,127}$")
SECRET_MARKER_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\.env\b",
        r"\$env:[A-Z_][A-Z0-9_]*\b",
        r"\bEnv:[A-Z_][A-Z0-9_]*\b",
        r"\$[A-Z_][A-Z0-9_]*\b",
        r"\$\{[A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|CONNECTION[_-]?STRING)[A-Z0-9_]*\}",
        r"%[A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|CONNECTION[_-]?STRING)[A-Z0-9_]*%",
        r"\bos\.environ\b",
        r"\bprocess\.env\b",
        r"\bgetenv\s*\(",
        r"\bAPI[_-]?KEY\b",
        r"\bTOKEN\b",
        r"\bSECRET\b",
        r"\bPASSWORD\b",
        r"\bCONNECTION[_-]?STRING\b",
    ]
)
UNSAFE_SECRET_READ_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bcat\s+.*\.env\b",
        r"\btype\s+.*\.env\b",
        r"\bGet-Content\s+.*\.env\b",
        r"\bWrite-(Host|Output)\s+\$env:[A-Z_][A-Z0-9_]*\b",
        r"\bWrite-(Host|Output)\s+\$[A-Z_][A-Z0-9_]*\b",
        r"\becho\s+\$[A-Z_][A-Z0-9_]*\b",
        r"\becho\s+\$env:[A-Z_][A-Z0-9_]*\b",
        r"\becho\s+\$\{[A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|CONNECTION[_-]?STRING)[A-Z0-9_]*\}",
        r"\becho\s+%[A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|CONNECTION[_-]?STRING)[A-Z0-9_]*%",
        r"\bcmd(?:\.exe)?\b.*\becho\s+%[A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|CONNECTION[_-]?STRING)[A-Z0-9_]*%",
        r"\bcmd(?:\.exe)?\b.*\bset\s+[A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|CONNECTION[_-]?STRING)[A-Z0-9_]*\b",
        r"\bset\s+[A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|CONNECTION[_-]?STRING)[A-Z0-9_]*\b",
        r"\bprintenv\b",
        r"\bpython\b.*\bos\.environ\b.*\b(print|write)\b",
        r"\bnode\b.*\bprocess\.env\b",
        r"\bset\s*\|\s*findstr\b",
    ]
)
SAFE_PRESENCE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bgrep\s+-[A-Za-z]*q[A-Za-z]*\s+",
        r"\bSelect-String\b.*(?:^|\s)-Quiet(?:\s|$)",
        r"\bTest-Path\b",
    ]
)
SAFE_PROMPT_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE | re.DOTALL)
    for pattern in [
        r"\bRead-Host\b.*-AsSecureString\b.*\bAdd-Content\b",
        r"\bread\s+-s\b.*>>",
    ]
)


@dataclass(frozen=True)
class CredentialSafetyPlan:
    credential_name: str
    env_file: str
    platform: str
    check_command: str
    prompt_command: str
    forbidden_commands: List[str]
    evidence: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CredentialSafetyPlan":
        return cls(
            credential_name=str(payload.get("credential_name", "")),
            env_file=str(payload.get("env_file", "")),
            platform=str(payload.get("platform", "")),
            check_command=str(payload.get("check_command", "")),
            prompt_command=str(payload.get("prompt_command", "")),
            forbidden_commands=list(payload.get("forbidden_commands", []) or []),
            evidence=list(payload.get("evidence", []) or []),
        )


@agent_skill(
    name="build_credential_safety_plan",
    description="Build safe credential presence and prompt commands without reading or printing secret values.",
)
def build_credential_safety_plan(
    credential_name: str,
    env_file: str = "~/.env",
    platform: str = "powershell",
) -> CredentialSafetyPlan:
    name = normalize_credential_name(credential_name)
    env_path = _normalize_env_file(env_file)
    ps_env_path = _quote_powershell_single(env_path)
    bash_env_path = shlex.quote(env_path)
    platform_key = (platform or "powershell").strip().lower()
    if platform_key in {"windows", "pwsh", "powershell"}:
        check_command = (
            f"$envFile = {ps_env_path}; "
            f"if (Test-Path -LiteralPath $envFile) "
            f"{{ Select-String -LiteralPath $envFile -Pattern '^{name}=' -Quiet }} "
            f"else {{ exit 1 }}"
        )
        prompt_command = (
            f"$envFile = {ps_env_path}; "
            f"$secret = Read-Host 'Enter {name} (typing hidden)' -AsSecureString; "
            "$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret); "
            "try { "
            "$plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr); "
            "New-Item -ItemType File -Force -Path $envFile | Out-Null; "
            f"Add-Content -LiteralPath $envFile -Value ('{name}=' + $plain); "
            "'Saved.' "
            "} finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }"
        )
        platform_key = "powershell"
    elif platform_key in {"bash", "sh", "posix"}:
        check_command = f"env_file={bash_env_path}; grep -sq '^{name}=' \"$env_file\""
        prompt_command = (
            f"env_file={bash_env_path}; "
            f"printf 'Enter {name} (typing hidden): ' && "
            f"read -s val && echo && mkdir -p \"$(dirname \"$env_file\")\" && "
            f"printf '%s\\n' '{name}='\"$val\" >> \"$env_file\" && echo 'Saved.'"
        )
        platform_key = "bash"
    else:
        raise ValueError(f"unsupported credential safety platform: {platform}")

    return CredentialSafetyPlan(
        credential_name=name,
        env_file=env_path,
        platform=platform_key,
        check_command=check_command,
        prompt_command=prompt_command,
        forbidden_commands=[
            "cat ~/.env",
            "type %USERPROFILE%\\.env",
            "Get-Content $HOME\\.env",
            f"echo ${name}",
            f"echo $env:{name}",
            f"printenv {name}",
        ],
        evidence=[
            "presence check uses quiet/no-value matching",
            "prompt command asks outside chat with hidden input",
            "secret value is never printed as terminal output",
        ],
    )


@agent_skill(
    name="classify_credential_command",
    description="Classify credential-related commands as safe presence checks, unsafe secret exposure, or neutral.",
)
def classify_credential_command(command: str) -> Dict[str, Any]:
    text = command or ""
    unsafe_matches = [pattern.pattern for pattern in UNSAFE_SECRET_READ_PATTERNS if pattern.search(text)]
    safe_matches = [pattern.pattern for pattern in SAFE_PRESENCE_PATTERNS if pattern.search(text)]
    prompt_matches = [pattern.pattern for pattern in SAFE_PROMPT_PATTERNS if pattern.search(text)]
    marker_matches = [pattern.pattern for pattern in SECRET_MARKER_PATTERNS if pattern.search(text)]
    if unsafe_matches:
        verdict = "unsafe_secret_exposure"
        allowed = False
        reason = "command may print or load credential values into the agent context"
    elif safe_matches:
        verdict = "safe_presence_check"
        allowed = True
        reason = "command checks presence without emitting secret values"
    elif prompt_matches:
        verdict = "safe_hidden_prompt"
        allowed = True
        reason = "command prompts outside chat using hidden input and writes without printing the secret"
    elif marker_matches:
        verdict = "unsafe_secret_exposure"
        allowed = False
        reason = "credential-related command is not a recognized safe presence check or hidden prompt"
    else:
        verdict = "neutral"
        allowed = True
        reason = "no credential exposure pattern detected"
    return {
        "verdict": verdict,
        "allowed": allowed,
        "reason": reason,
        "matched_patterns": unsafe_matches or safe_matches or prompt_matches or marker_matches,
    }


@agent_skill(
    name="validate_credential_safety_plan",
    description="Validate that a credential safety plan checks presence without leaking secret values.",
)
def validate_credential_safety_plan(plan: CredentialSafetyPlan | Dict[str, Any]) -> Dict[str, Any]:
    candidate = plan if isinstance(plan, CredentialSafetyPlan) else CredentialSafetyPlan.from_dict(plan)
    issues: List[str] = []
    if not CREDENTIAL_NAME_RE.match(candidate.credential_name):
        issues.append("invalid_credential_name")
    check_verdict = classify_credential_command(candidate.check_command)
    prompt_verdict = classify_credential_command(candidate.prompt_command)
    if not check_verdict["allowed"] or check_verdict["verdict"] != "safe_presence_check":
        issues.append("check_command_not_safe_presence_only")
    if not prompt_verdict["allowed"] or prompt_verdict["verdict"] != "safe_hidden_prompt":
        issues.append("prompt_command_may_expose_secret")
    for forbidden in candidate.forbidden_commands:
        verdict = classify_credential_command(forbidden)
        if verdict["allowed"]:
            issues.append(f"forbidden_command_not_detected:{forbidden}")
    return {
        "valid": not issues,
        "issues": issues,
        "check_command_verdict": check_verdict,
        "prompt_command_verdict": prompt_verdict,
        "credential_name": candidate.credential_name,
        "env_file": candidate.env_file,
        "platform": candidate.platform,
    }


def normalize_credential_name(value: str) -> str:
    name = (value or "").strip().upper()
    if not CREDENTIAL_NAME_RE.match(name):
        raise ValueError("credential name must be uppercase letters, digits, and underscores only")
    return name


def _normalize_env_file(value: str) -> str:
    text = (value or "~/.env").strip()
    if not text:
        text = "~/.env"
    if "\n" in text or "\r" in text:
        raise ValueError("env_file must be a single path")
    if any(char in text for char in [";", "|", "&", "`", "$", "\"", "'", "<", ">", "*", "?", "[", "]", "(", ")"]):
        raise ValueError("env_file must not contain shell control, expansion, quote, or glob characters")
    return str(Path(text).expanduser()) if text.startswith("~") else text


def _quote_powershell_single(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
