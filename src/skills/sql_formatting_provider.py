from dataclasses import asdict, dataclass, field
from pathlib import Path
import re
from typing import Any, Dict, List, Sequence, Tuple


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
    re.compile(r"\b(?:query\s+)?(?:behavior|logic|semantics)\s+changes?\s+(?:are|is)\s+(?:allowed|permitted|acceptable)\b"),
    re.compile(r"\b(?:allowed|permitted|acceptable)\s+to\s+(?:change|rewrite|alter)\s+(?:query\s+)?(?:behavior|logic|semantics)\b"),
    re.compile(r"\b(?:query\s+)?(?:behavior|logic|semantics|results?)\s+(?:need|must)\s+not\s+be\s+preserved\b"),
    re.compile(r"\bdo\s+not\s+preserve\s+(?:query\s+)?(?:behavior|logic|semantics)\b"),
    re.compile(r"\bignore\s+(?:the\s+)?(?:style|preservation)\s+contract\b"),
)
BEHAVIOR_PRESERVATION_PATTERNS = (
    re.compile(r"\bpreserv(?:e|es|ed|ing)\b.{0,80}\b(?:query\s+)?(?:behavior|behaviour|logic|semantics|results?)\b", re.DOTALL),
    re.compile(r"\b(?:do|must|shall)\s+not\s+(?:change|alter|rewrite)\b.{0,80}\b(?:query\s+)?(?:behavior|behaviour|logic|semantics|results?)\b", re.DOTALL),
    re.compile(r"\bsemantics?-preserving\b"),
)
PACKAGED_VERIFIER_IDENTITIES = (
    "sql-formatting-style-harness",
    "sql_formatting_style_harness",
    "src.skills.sql_formatting_style.verify_sql_formatting_style",
)
VERIFIER_REQUIREMENT_PATTERN = re.compile(
    r"\b(?:must|shall|required|always|run|invoke|delegate|validate|verify|accept\s+only|reject)\b"
)
GENERIC_PACKAGED_VERIFIER_PATTERN = re.compile(
    r"\bpackaged\s+(?:kh\s+)?(?:sql[- ]formatting\s+)?(?:deterministic\s+)?verifier\b"
)
SCALAR_TO_JOIN_RULE_PATTERNS = (
    re.compile(
        r"\b(?:convert|replace|rewrite|transform|turn)\b.{0,160}"
        r"\b(?:scalar|udf|function)\b.{0,160}\bjoins?\b",
        re.DOTALL,
    ),
    re.compile(
        r"\b(?:scalar|udf|function)\b.{0,120}"
        r"\b(?:must|shall|should|always|become|convert|replace)\b.{0,120}\bjoins?\b",
        re.DOTALL,
    ),
)
SCALAR_CONVERSION_BOUNDARY_PATTERNS = (
    re.compile(
        r"\bonly\s+(?:when|if)\b.{0,180}"
        r"\b(?:implementation|definition|body|contract|metadata|source|equivalence)\b"
        r".{0,120}\b(?:verified|known|proven|available)\b",
        re.DOTALL,
    ),
    re.compile(r"\b(?:verified|proven|known)\b.{0,80}\b(?:lookup\s+)?contract\b", re.DOTALL),
    re.compile(
        r"\b(?:unknown|unverified|unavailable)\b.{0,160}"
        r"\b(?:preserve|keep|leave|stay|do\s+not\s+(?:convert|replace))\b",
        re.DOTALL,
    ),
    re.compile(
        r"\bdo\s+not\s+(?:convert|replace)\b.{0,120}"
        r"\b(?:unless|without)\b.{0,120}"
        r"\b(?:verified|known|proof|body|contract|metadata)\b",
        re.DOTALL,
    ),
)
UNCONDITIONAL_SCALAR_CONVERSION_PATTERNS = (
    re.compile(
        r"\balways\b.{0,80}\b(?:convert|replace|rewrite|transform)\b",
        re.DOTALL,
    ),
    re.compile(
        r"\b(?:convert|replace|rewrite|transform)\b.{0,80}"
        r"\b(?:all|any|every)\b.{0,40}\b(?:scalar|udf|function)\b",
        re.DOTALL,
    ),
    re.compile(
        r"\b(?:all|any|every)\b.{0,40}\b(?:scalar|udf|function)\b"
        r".{0,100}\b(?:must|shall|become|convert|replace)\b.{0,80}\bjoins?\b",
        re.DOTALL,
    ),
)
CONCRETE_MANDATE_PATTERN = re.compile(
    r"\b(?:must|shall|always|required|replace|convert|rewrite|join|use|select|"
    r"resolve|map|standard\s+lookup|verified\s+(?:lookup\s+)?contract|"
    r"when\s+sql\s+contains)\b"
)
SQL_FUNCTION_REFERENCE_PATTERN = re.compile(
    r"(?P<object>(?:\[?[A-Za-z_][A-Za-z0-9_$]*\]?\.){1,2}"
    r"\[?[A-Za-z_][A-Za-z0-9_$]*\]?)\s*\("
)
SQL_TABLE_REFERENCE_PATTERN = re.compile(
    r"\b(?:from|(?:left\s+(?:outer\s+)?)?(?:inner\s+)?join|into|update|"
    r"merge\s+into|delete\s+from)\s+"
    r"(?P<object>`[^`]+`|(?:\[[^\]]+\]\.)*\[[^\]]+\]|"
    r"[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)?)",
    re.IGNORECASE,
)
BACKTICK_IDENTIFIER_PATTERN = re.compile(
    r"`(?P<object>[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)*)`"
)
HEADING_OBJECT_PATTERN = re.compile(r"\b[A-Z]{1,8}\d{2,}[A-Z0-9_$]*\b")
PLACEHOLDER_MARKERS = (
    "example",
    "sample",
    "placeholder",
    "lookup_table",
    "source_table",
    "target_table",
    "table_name",
    "function_name",
)
POLICY_OPTIONAL_PATTERN = re.compile(
    r"\b(?:may|can|could|might|should|optionally)\b|"
    r"\b(?:if\s+desired|when\s+convenient|where\s+practical|as\s+needed)\b"
)
POLICY_REQUIRED_PATTERN = re.compile(
    r"\b(?:must|shall|always|mandatory|required|need(?:s)?\s+to|has\s+to|have\s+to)\b"
)
POLICY_NEGATION_BEFORE_ACTION_PATTERN = re.compile(
    r"\b(?:(?:must|shall|do|does|need|needs|is|are|be|may|can|should)\s+)?"
    r"(?:not|never)(?:\s+\w+){0,2}\s*$|\bwithout\s*$"
)
POLICY_NEGATION_AFTER_ACTION_PATTERN = re.compile(
    r"^.{0,100}\b(?:is|are|be)\s+not\s+(?:required|mandatory)\b"
)
VERIFIER_ACTION_PATTERN = re.compile(
    r"\b(?:run|running|invoke|invoking|delegate|delegating|validate|validating|"
    r"verify|verifying|use|using|apply|applying|execute|executing|call|calling|pass)\b"
)
BEHAVIOR_TARGET_PATTERN = re.compile(
    r"\b(?:query\s+)?(?:behavior|behaviour|logic|semantics|results?)\b"
)
PRESERVATION_ACTION_PATTERN = re.compile(
    r"\b(?:preserv(?:e|es|ed|ing|ation)|retain(?:s|ed|ing)?|remain(?:s|ed|ing)?\s+unchanged)\b"
)
BEHAVIOR_CHANGE_ACTION_PATTERN = re.compile(
    r"\b(?:change|changes|changed|changing|alter|alters|altered|altering|"
    r"rewrite|rewrites|rewritten|rewriting)\b"
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

    policy_sections = _host_policy_sections(content)
    policy_text = "\n".join(
        "\n".join(part for part in section if part).strip()
        for section in policy_sections
    ).lower()
    behavior_states = _behavior_policy_states(policy_sections)
    verifier_states = _packaged_verifier_policy_states(policy_sections)
    issues: List[str] = []
    if "divergent" in behavior_states or any(
        pattern.search(policy_text) for pattern in HOST_DIVERGENCE_PATTERNS
    ):
        issues.append("behavior_change_allowed")
    if "required" not in behavior_states:
        issues.append("missing_behavior_preservation_boundary")
    if "required" in behavior_states and "optional" in behavior_states:
        issues.append("contradictory_behavior_preservation_policy")
    if not _requires_packaged_verifier(policy_sections):
        issues.append("missing_packaged_verifier_requirement")
    if "required" in verifier_states and "optional" in verifier_states:
        issues.append("contradictory_packaged_verifier_policy")
    if any(_has_concrete_schema_object_mandate(section) for section in policy_sections):
        issues.append("concrete_schema_object_mandate")
    if any(_has_unbounded_scalar_to_join_rule(section) for section in policy_sections):
        issues.append("unbounded_scalar_to_join_conversion")
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


def _host_policy_sections(content: str) -> List[Tuple[str, str]]:
    sections: List[Tuple[str, str]] = []
    heading = ""
    lines: List[str] = []
    in_fence = False
    skip_fence = False
    example_section = False
    example_paragraph = False

    def flush() -> None:
        if not example_section and (heading or lines):
            sections.append((heading, "\n".join(lines)))

    for line in content.replace("\r\n", "\n").splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            if in_fence:
                in_fence = False
                skip_fence = False
            else:
                in_fence = True
                skip_fence = example_section or example_paragraph
            continue
        if in_fence:
            if not skip_fence:
                lines.append(line)
            continue
        if stripped.startswith("#"):
            flush()
            heading = stripped.lstrip("#").strip()
            lines = []
            example_section = bool(
                re.search(r"\b(?:examples?|samples?|illustrations?)\b", heading, re.IGNORECASE)
            )
            example_paragraph = False
            continue
        if example_section:
            continue
        if re.search(r"\bexamples?\s*:\s*$", stripped, re.IGNORECASE):
            example_paragraph = True
            continue
        if re.match(r"^(?:for\s+example|e\.g\.)\b", stripped, re.IGNORECASE):
            continue
        if example_paragraph:
            if not stripped:
                example_paragraph = False
            continue
        lines.append(line)
    flush()
    return sections


def _requires_packaged_verifier(
    sections: Sequence[Tuple[str, str]],
) -> bool:
    states = _packaged_verifier_policy_states(sections)
    return "required" in states and not states.intersection({"optional", "negated"})


def _packaged_verifier_policy_states(
    sections: Sequence[Tuple[str, str]],
) -> set[str]:
    states: set[str] = set()
    for section in sections:
        for clause in _policy_clauses(section):
            lowered = clause.lower()
            known_identity = any(
                identity in lowered for identity in PACKAGED_VERIFIER_IDENTITIES
            )
            generic_identity = bool(GENERIC_PACKAGED_VERIFIER_PATTERN.search(lowered))
            if not known_identity and not generic_identity:
                continue
            actions = list(VERIFIER_ACTION_PATTERN.finditer(lowered))
            polarities = [_action_policy_polarity(lowered, action) for action in actions]
            states.update(value for value in polarities if value != "neutral")
            if not actions:
                if re.search(r"\b(?:not\s+required|optional)\b", lowered):
                    states.add("optional")
                elif POLICY_REQUIRED_PATTERN.search(lowered) or re.search(
                    r"\b(?:accept|release)\b.{0,80}\bonly\b|"
                    r"\bonly\b.{0,80}\b(?:accept|release)\b",
                    lowered,
                ):
                    states.add("required")
    return states


def _policy_clauses(section: Tuple[str, str]) -> List[str]:
    clauses: List[str] = []
    for part in section:
        for line in part.splitlines():
            value = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", line).strip()
            if not value:
                continue
            clauses.extend(
                item.strip()
                for item in re.split(r";\s*|(?<=[.!?])\s+(?=[A-Z`])", value)
                if item.strip()
            )
    return clauses


def _action_policy_polarity(text: str, action: re.Match[str]) -> str:
    before = text[max(0, action.start() - 100) : action.start()]
    after = text[action.end() : action.end() + 120]
    if POLICY_NEGATION_BEFORE_ACTION_PATTERN.search(before) or (
        POLICY_NEGATION_AFTER_ACTION_PATTERN.search(after)
    ):
        return "negated"
    if POLICY_OPTIONAL_PATTERN.search(before[-80:]) or POLICY_OPTIONAL_PATTERN.search(
        after[:100]
    ):
        return "optional"
    if POLICY_REQUIRED_PATTERN.search(before[-100:]) or POLICY_REQUIRED_PATTERN.search(
        after[:100]
    ):
        return "required"
    prefix = re.sub(r"^[\s:,-]+", "", text[: action.start()])
    if not prefix or re.search(r"\b(?:accept|release)\b.{0,80}\bonly\b", text):
        return "required"
    return "neutral"


def _behavior_policy_states(
    sections: Sequence[Tuple[str, str]],
) -> set[str]:
    states: set[str] = set()
    for section in sections:
        for clause in _policy_clauses(section):
            lowered = clause.lower()
            if not BEHAVIOR_TARGET_PATTERN.search(lowered):
                continue
            for action in PRESERVATION_ACTION_PATTERN.finditer(lowered):
                polarity = _action_policy_polarity(lowered, action)
                if polarity == "required":
                    states.add("required")
                elif polarity == "optional":
                    states.add("optional")
                elif polarity == "negated":
                    states.add("divergent")
            for action in BEHAVIOR_CHANGE_ACTION_PATTERN.finditer(lowered):
                polarity = _action_policy_polarity(lowered, action)
                if polarity == "negated":
                    states.add("required")
                elif polarity in {"required", "optional"} or re.search(
                    r"\b(?:allowed|permitted|acceptable)\b", lowered
                ):
                    states.add("divergent")
    return states


def _has_concrete_schema_object_mandate(section: Tuple[str, str]) -> bool:
    heading, body = section
    text = "\n".join(part for part in section if part)
    lowered = text.lower()
    if not CONCRETE_MANDATE_PATTERN.search(lowered):
        return False

    candidates = [
        match.group("object")
        for match in SQL_FUNCTION_REFERENCE_PATTERN.finditer(text)
    ]
    candidates.extend(
        match.group("object")
        for match in SQL_TABLE_REFERENCE_PATTERN.finditer(text)
    )
    candidates.extend(
        f"`{match.group('object')}`"
        for match in BACKTICK_IDENTIFIER_PATTERN.finditer(text)
    )
    candidates.extend(HEADING_OBJECT_PATTERN.findall(heading))
    return any(_is_concrete_sql_object(candidate) for candidate in candidates)


def _is_concrete_sql_object(identifier: str) -> bool:
    raw = str(identifier or "").strip()
    normalized = raw.strip("`[]").replace("][", ".")
    lowered = normalized.lower()
    if not normalized or any(marker in lowered for marker in PLACEHOLDER_MARKERS):
        return False
    if (
        lowered in {"select", "from", "join", "where", "case", "null", "sql"}
        or "verify_sql_formatting_style" in lowered
        or lowered.startswith("src.skills.")
    ):
        return False
    if raw.startswith("`") or raw.startswith("["):
        return True
    return bool(
        "." in normalized
        or any(character.isdigit() for character in normalized)
        or normalized.upper() == normalized
    )


def _has_unbounded_scalar_to_join_rule(section: Tuple[str, str]) -> bool:
    text = "\n".join(part for part in section if part).lower()
    if not any(pattern.search(text) for pattern in SCALAR_TO_JOIN_RULE_PATTERNS):
        return False
    if any(
        pattern.search(text) for pattern in UNCONDITIONAL_SCALAR_CONVERSION_PATTERNS
    ):
        return True
    return not any(
        pattern.search(text) for pattern in SCALAR_CONVERSION_BOUNDARY_PATTERNS
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
