from dataclasses import asdict, dataclass, field
from pathlib import Path
import re
from typing import Any, Dict, List


PACKAGED_PROVIDER_ID = "sql-formatting"
PACKAGED_PROVIDER_SKILL_DIR = "sql_formatting"
PACKAGED_PROVIDER_SKILL_NAME = "sql-formatting"
CANONICAL_CONTRACT_RELATIVE_PATH = (
    "sql_formatting_style_harness/references/style-contract.md"
)
REQUIRED_SUPPORT_FILES = (
    "SKILL.md",
    "references/usage.md",
    "examples/minimal-workflow.md",
    "scripts/smoke_check.py",
    "scripts/demo.py",
)
REQUIRED_SKILL_MARKERS = (
    "Execution actor: host LLM",
    "sql_formatting_style_harness/references/style-contract.md",
    "does not implement a headless Python formatter",
    "src.skills.sql_formatting_style.verify_sql_formatting_style",
)
HOST_DIVERGENCE_PATTERNS = (
    re.compile(r"\b(?:may|can|should|must|will)\s+(?:change|rewrite)\s+(?:query\s+)?(?:behavior|logic|semantics)\b"),
    re.compile(r"\bdo\s+not\s+preserve\s+(?:query\s+)?(?:behavior|logic|semantics)\b"),
    re.compile(r"\bignore\s+(?:the\s+)?(?:style|preservation)\s+contract\b"),
)


@dataclass(frozen=True)
class SqlFormattingProviderInspection:
    provider_id: str
    status: str
    compatible: bool
    provider_root: str
    skill_path: str
    contract_path: str
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HostSqlFormattingProviderInspection:
    status: str
    availability: str
    compatibility: str
    compatible: bool
    skill_path: str
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def inspect_host_sql_formatting_provider(
    skill_path: str | Path,
) -> HostSqlFormattingProviderInspection:
    path = Path(skill_path).expanduser().resolve()
    if not path.is_file():
        return HostSqlFormattingProviderInspection(
            status="missing",
            availability="missing",
            compatibility="unknown",
            compatible=False,
            skill_path=str(path),
            issues=["missing_host_sql_formatting_skill"],
        )

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            content = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            return _unreadable_host_provider(path, exc)
    except (OSError, UnicodeError) as exc:
        return _unreadable_host_provider(path, exc)

    lowered = content.lower()
    issues = [
        "behavior_change_allowed"
        for pattern in HOST_DIVERGENCE_PATTERNS
        if pattern.search(lowered)
    ]
    issues = list(dict.fromkeys(issues))
    compatibility = "divergent" if issues else "compatible"
    return HostSqlFormattingProviderInspection(
        status="available",
        availability="available",
        compatibility=compatibility,
        compatible=not issues,
        skill_path=str(path),
        issues=issues,
    )


def inspect_packaged_sql_formatting_provider(
    skills_root: str | Path | None = None,
) -> SqlFormattingProviderInspection:
    root = Path(skills_root) if skills_root is not None else _default_skills_root()
    root = root.expanduser().resolve()
    provider_root = root / PACKAGED_PROVIDER_SKILL_DIR
    skill_path = provider_root / "SKILL.md"
    contract_path = root / CANONICAL_CONTRACT_RELATIVE_PATH

    if not provider_root.is_dir() or not skill_path.is_file():
        return SqlFormattingProviderInspection(
            provider_id=PACKAGED_PROVIDER_ID,
            status="missing",
            compatible=False,
            provider_root=str(provider_root),
            skill_path=str(skill_path),
            contract_path=str(contract_path),
            issues=["missing_packaged_sql_formatting_skill"],
        )

    issues: List[str] = []
    for relative_path in REQUIRED_SUPPORT_FILES:
        if not (provider_root / relative_path).is_file():
            issues.append(f"missing_support_file:{relative_path}")

    try:
        skill_content = skill_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        issues.append(f"unreadable_skill:{type(exc).__name__}")
        skill_content = ""

    if _frontmatter_name(skill_content) != PACKAGED_PROVIDER_SKILL_NAME:
        issues.append("invalid_frontmatter_name")
    for marker in REQUIRED_SKILL_MARKERS:
        if marker not in skill_content:
            issues.append(f"missing_skill_marker:{marker}")

    if not contract_path.is_file():
        issues.append("missing_canonical_style_contract")
    if (provider_root / "references" / "style-contract.md").exists():
        issues.append("forked_style_contract")

    status = "available" if not issues else "corrupt"
    return SqlFormattingProviderInspection(
        provider_id=PACKAGED_PROVIDER_ID,
        status=status,
        compatible=not issues,
        provider_root=str(provider_root),
        skill_path=str(skill_path),
        contract_path=str(contract_path),
        issues=issues,
    )


def packaged_sql_formatting_provider(
    skills_root: str | Path | None = None,
    *,
    host: str = "codex",
) -> Dict[str, Any]:
    inspection = inspect_packaged_sql_formatting_provider(skills_root)
    return {
        "provider_id": PACKAGED_PROVIDER_ID,
        "display_name": "KH Packaged SQL Formatting",
        "aliases": [
            "sql-formatting",
            "sql formatting",
            "sql-formatting skill",
            "sql formatting skill",
            "t-sql formatting",
            "tsql formatting",
        ],
        "capabilities": ["sql_formatting"],
        "status": inspection.status,
        "metadata": {
            "host": host,
            "source": "packaged-kh-skill",
            "path": inspection.skill_path,
            "contract_path": inspection.contract_path,
            "availability": inspection.status,
            "compatibility": "compatible" if inspection.compatible else inspection.status,
            "compatibility_issues": list(inspection.issues),
            "provider_precedence": 20,
            "execution_actor": "host-llm",
            "headless_python_formatter": False,
            "verification_provider": "sql-formatting-style-harness",
        },
    }


def _default_skills_root() -> Path:
    return Path(__file__).resolve().parents[2] / "skills"


def _unreadable_host_provider(
    path: Path,
    exc: BaseException,
) -> HostSqlFormattingProviderInspection:
    return HostSqlFormattingProviderInspection(
        status="unavailable",
        availability="unavailable",
        compatibility="unknown",
        compatible=False,
        skill_path=str(path),
        issues=[f"unreadable_host_skill:{type(exc).__name__}"],
    )


def _frontmatter_name(content: str) -> str:
    if not content.startswith("---\n"):
        return ""
    end = content.find("\n---", 4)
    if end == -1:
        return ""
    for line in content[4:end].splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() == "name":
            return value.strip().strip("\"'")
    return ""
