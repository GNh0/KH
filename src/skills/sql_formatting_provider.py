from collections.abc import Mapping
import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Sequence, Tuple

from src.orchestration.goal_evidence import RuntimeProducerBoundary
from src.orchestration.runtime_paths import runtime_root
from src.skills.sql_formatting_style import verify_sql_formatting_style


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
    "src.skills.sql_formatting_provider.guard_and_bind_verified_sql_final_response",
    "python -m src.skills.sql_formatting_provider",
    "correlated front-door provider selection",
    "`cli_inputs`",
    "Paste-ready full SQL first.",
    "Every user correction invalidates the previous verification.",
    "Complete alias plans for every multi-source formatted scope",
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
MARKDOWN_FENCE_LINE_PATTERN = re.compile(
    r"^ {0,3}(?P<marker>`{3,}|~{3,})[ \t]*(?P<info>[^\r\n]*)[ \t]*$"
)
SQL_FENCE_LANGUAGES = {"sql", "tsql", "t-sql"}
SQL_PROVIDER_RECEIPT_PRODUCER = "sql-formatting-provider-cli-v1"
SQL_PROVIDER_RECEIPT_CLAIM_KIND = "sql_final_response_release"
SQL_PROVIDER_RECEIPT_SCHEMA_VERSION = 1
SQL_PROVIDER_SELECTION_RECEIPT_PRODUCER = "kh-front-door-sql-provider-selection-v1"
SQL_PROVIDER_SELECTION_RECEIPT_CLAIM_KIND = "sql_provider_selection"
SQL_PROVIDER_SELECTION_RECEIPT_SCHEMA_VERSION = 1
SQL_PROVIDER_SELECTION_SCHEMA_VERSION = 1
SQL_PROVIDER_SELECTION_SOURCES = {"host-local-skill", "packaged-kh-skill"}
SQL_PROVIDER_SELECTION_GATE_STATUSES = {
    "execution_allowed_after_selected_skill_setup",
    "execution_allowed_localized_patch_with_scope_lock",
    "execution_allowed_readonly_analysis",
}
SQL_PROVIDER_NONCE_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{16,128}$")
SQL_CLI_PATH_ARGUMENTS = (
    "original_file",
    "candidate_file",
    "response_file",
    "provider_selection_file",
    "provider_path",
    "selected_active_provider_path",
)
SQL_CLI_SCOPE_ARGUMENTS = ("session_id", "invocation_nonce")
SQL_CLI_REQUIRED_HASHES = (
    "original_text_sha256",
    "candidate_text_sha256",
    "response_text_sha256",
    "provider_selection_sha256",
    "original_file_sha256",
    "candidate_file_sha256",
    "response_file_sha256",
    "provider_selection_file_sha256",
)
SQL_CLI_INPUT_FIELDS = {
    "module",
    "exit_status",
    "arguments",
    "resolved_paths",
    "hashes",
}
SQL_CLI_ARGUMENT_FIELDS = {*SQL_CLI_PATH_ARGUMENTS, *SQL_CLI_SCOPE_ARGUMENTS}
SQL_CLI_RESOLVED_PATH_FIELDS = set(SQL_CLI_PATH_ARGUMENTS)
SQL_CLI_HASH_FIELDS = set(SQL_CLI_REQUIRED_HASHES)
SQL_FINAL_RELEASE_FIELDS = {
    "status",
    "provider_path_guard",
    "binding",
    "verification",
    "cli_inputs",
}
SQL_FINAL_BINDING_FIELDS = {
    "status",
    "original_sha256",
    "formatted_sha256",
    "final_response_sha256",
    "verification_id",
    "sql_fence_count",
}
SQL_FINAL_PROVIDER_GUARD_FIELDS = {
    "status",
    "authority",
    "provider_path",
    "selected_active_provider_path",
    "current_packaged_fallback_path",
    "provider_id",
    "provider_source",
    "provider_selection_sha256",
}
SQL_FINAL_VERIFICATION_FIELDS = {
    "success",
    "stdout",
    "stderr",
    "exit_code",
    "execution_time",
    "metadata",
}


class SqlFinalResponseBindingError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class SqlFormattingProviderPathError(ValueError):
    def __init__(self, code: str, message: str, provider_path: str) -> None:
        self.code = code
        self.provider_path = provider_path
        super().__init__(f"{code}: {message}: {provider_path}")


class SqlFormattingCliArtifactError(ValueError):
    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}: {message}: {path}")


@dataclass(frozen=True)
class SqlFormattingRepairDecision:
    status: str
    attempts_used: int
    max_attempts: int
    repair_allowed: bool
    sql_delivery_allowed: bool
    blocked_reason: str
    issue_codes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_sql_formatting_repair_gate(
    verifier_results: Sequence[Mapping[str, Any]],
    *,
    repair_issue_codes: Sequence[str] = (),
) -> SqlFormattingRepairDecision:
    """Allow one initial verification plus one evidence-directed repair."""
    attempts = list(verifier_results)
    max_attempts = 2
    issue_codes = {
        str(code).strip()
        for code in repair_issue_codes
        if str(code).strip()
    }
    def collect_issue_codes(value: Any) -> None:
        if isinstance(value, Mapping):
            code = value.get("code")
            if isinstance(code, str) and code.strip():
                issue_codes.add(code.strip())
            for nested in value.values():
                collect_issue_codes(nested)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for nested in value:
                collect_issue_codes(nested)

    for result in attempts:
        if not isinstance(result, Mapping):
            continue
        collect_issue_codes(result.get("issues", []))
        collect_issue_codes(result.get("metadata", {}))

    def is_ready(result: Any) -> bool:
        if not isinstance(result, Mapping):
            return False
        metadata = result.get("metadata", {})
        readiness = (
            metadata.get("release_readiness", {})
            if isinstance(metadata, Mapping)
            else {}
        )
        return (
            result.get("success") is True
            and type(result.get("exit_code")) is int
            and result.get("exit_code") == 0
            and isinstance(readiness, Mapping)
            and readiness.get("status") == "ready"
        )

    def decision(
        status: str,
        *,
        repair_allowed: bool = False,
        sql_delivery_allowed: bool = False,
        blocked_reason: str = "",
    ) -> SqlFormattingRepairDecision:
        return SqlFormattingRepairDecision(
            status=status,
            attempts_used=len(attempts),
            max_attempts=max_attempts,
            repair_allowed=repair_allowed,
            sql_delivery_allowed=sql_delivery_allowed,
            blocked_reason=blocked_reason,
            issue_codes=sorted(issue_codes),
        )

    if not attempts:
        return decision(
            "initial_verification_required",
            blocked_reason="sql_formatting_initial_verification_required",
        )
    if len(attempts) > max_attempts:
        return decision(
            "blocked",
            blocked_reason="sql_formatting_repair_limit_exhausted",
        )
    if len(attempts) == 1 and is_ready(attempts[0]):
        return decision("ready", sql_delivery_allowed=True)
    if len(attempts) == 1:
        if issue_codes:
            return decision("repair_allowed", repair_allowed=True)
        return decision(
            "blocked",
            blocked_reason="sql_formatting_repair_evidence_required",
        )
    if not issue_codes:
        return decision(
            "blocked",
            blocked_reason="sql_formatting_repair_evidence_required",
        )
    if is_ready(attempts[1]):
        return decision("ready", sql_delivery_allowed=True)
    return decision(
        "blocked",
        blocked_reason="sql_formatting_repair_limit_exhausted",
    )


class DuplicateJsonKeyError(ValueError):
    pass


def load_json_without_duplicate_keys(value: str) -> Any:
    def reject_duplicates(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise DuplicateJsonKeyError(f"duplicate JSON key: {key}")
            result[key] = item
        return result

    return json.loads(value, object_pairs_hook=reject_duplicates)


@dataclass(frozen=True)
class SqlFinalResponseBinding:
    status: str
    final_response: str
    formatted_sql: str
    original_sha256: str
    formatted_sha256: str
    final_response_sha256: str
    verification_id: str
    sql_fence_count: int
    verification: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AuthoritativeSqlFormattingProviderPath:
    status: str
    authority: str
    provider_path: str
    selected_active_provider_path: str
    current_packaged_fallback_path: str
    provider_id: str
    provider_source: str
    provider_selection_sha256: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SqlFinalResponseRelease:
    status: str
    provider_path_guard: AuthoritativeSqlFormattingProviderPath
    binding: SqlFinalResponseBinding

    def to_receipt_dict(self) -> Dict[str, Any]:
        binding = self.binding.to_dict()
        binding.pop("final_response", None)
        binding.pop("formatted_sql", None)
        verification = binding.pop("verification", {})
        return {
            "status": self.status,
            "provider_path_guard": self.provider_path_guard.to_dict(),
            "binding": binding,
            "verification": verification,
        }


@dataclass(frozen=True)
class SqlFormattingCliArtifacts:
    original_bytes: bytes
    candidate_text: str
    response_text: str
    provider_selection: Mapping[str, Any]
    raw_bytes: Dict[str, bytes]
    resolved_paths: Dict[str, str]
    hashes: Dict[str, str]


@dataclass(frozen=True)
class _MarkdownFencedBlock:
    marker: str
    info: str
    body: str
    start: int
    end: int


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


def sql_provider_selection_sha256(provider_selection: Mapping[str, Any]) -> str:
    if not isinstance(provider_selection, Mapping) or not provider_selection:
        raise SqlFormattingProviderPathError(
            "provider_selection_missing",
            "Correlated front-door provider selection evidence is required",
            "",
        )
    payload = json.dumps(
        _unsigned_sql_provider_selection(provider_selection),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def attach_sql_provider_selection_runtime_receipt(
    provider_selection: Mapping[str, Any],
) -> Dict[str, Any]:
    unsigned = _unsigned_sql_provider_selection(provider_selection)
    schema_errors = _sql_provider_selection_schema_errors(unsigned)
    if schema_errors:
        raise SqlFormattingProviderPathError(
            schema_errors[0],
            ",".join(schema_errors),
            "",
        )
    selected = _selected_sql_provider_claim(unsigned)
    receipt_payload = {
        "schema_version": SQL_PROVIDER_SELECTION_RECEIPT_SCHEMA_VERSION,
        "receipt_type": "kh_front_door_sql_provider_selection",
        "producer_module": "src.orchestration.kh_front_door",
        "provider_selection_sha256": sql_provider_selection_sha256(unsigned),
        "provider_id": selected["provider_id"],
        "provider_source": selected["provider_source"],
        "provider_path": selected["provider_path"],
        "selected_active_provider_path": selected["selected_active_provider_path"],
        "compatibility": selected["compatibility"],
        "selection_status": selected["selection_status"],
        "host": unsigned["host"],
        "project": unsigned["project"],
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    result = dict(unsigned)
    result["provider_selection_receipt"] = (
        _sql_provider_selection_runtime_boundary().issue_claim(
            receipt_payload,
            claim_kind=SQL_PROVIDER_SELECTION_RECEIPT_CLAIM_KIND,
            claim_id_field="provider_selection_receipt_id",
            claim_id_prefix="selection",
        )
    )
    return result


def validate_sql_provider_selection_runtime_receipt(
    provider_selection: Mapping[str, Any],
    *,
    require_external_host_authenticity: bool = False,
    external_host_authenticator: Any = None,
) -> List[str]:
    if not isinstance(provider_selection, Mapping) or not provider_selection:
        return ["provider_selection_missing"]
    receipt = provider_selection.get("provider_selection_receipt")
    if not isinstance(receipt, Mapping):
        return ["provider_selection_runtime_receipt_missing"]
    errors = _sql_provider_selection_schema_errors(provider_selection)
    errors.extend(
        _runtime_receipt_identity_errors(
            receipt,
            error_prefix="provider_selection_runtime_receipt",
            schema_version=SQL_PROVIDER_SELECTION_RECEIPT_SCHEMA_VERSION,
            receipt_id_field="provider_selection_receipt_id",
            receipt_id_pattern=re.compile(r"^selection-[0-9a-f]{32}$"),
            boundary=_sql_provider_selection_runtime_boundary(),
            producer_name=SQL_PROVIDER_SELECTION_RECEIPT_PRODUCER,
            claim_kind=SQL_PROVIDER_SELECTION_RECEIPT_CLAIM_KIND,
        )
    )
    errors.extend(
        _sql_provider_selection_runtime_boundary().validate_claim(
            receipt,
            claim_kind=SQL_PROVIDER_SELECTION_RECEIPT_CLAIM_KIND,
            claim_id_field="provider_selection_receipt_id",
            consume=False,
        )
    )
    selected = _explicit_sql_provider_selection_claim(provider_selection)
    expected = {
        "schema_version": SQL_PROVIDER_SELECTION_RECEIPT_SCHEMA_VERSION,
        "receipt_type": "kh_front_door_sql_provider_selection",
        "producer_module": "src.orchestration.kh_front_door",
        "provider_selection_sha256": sql_provider_selection_sha256(provider_selection),
        "provider_id": selected.get("provider_id"),
        "provider_source": selected.get("provider_source"),
        "provider_path": selected.get("provider_path"),
        "selected_active_provider_path": selected.get(
            "selected_active_provider_path"
        ),
        "compatibility": selected.get("compatibility"),
        "selection_status": selected.get("selection_status"),
        "host": provider_selection.get("host"),
        "project": provider_selection.get("project"),
    }
    for key, expected_value in expected.items():
        actual = receipt.get(key)
        if type(actual) is not type(expected_value) or actual != expected_value:
            errors.append(f"provider_selection_runtime_receipt_{key}_mismatch")
    issued_value = receipt.get("issued_at")
    issued_at = issued_value if type(issued_value) is str else ""
    if type(issued_value) is not str:
        errors.append("provider_selection_runtime_receipt_issued_at_not_string")
    try:
        parsed = datetime.fromisoformat(issued_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timezone required")
    except ValueError:
        errors.append("provider_selection_runtime_receipt_issued_at_invalid")
    if require_external_host_authenticity:
        authenticated = False
        if callable(external_host_authenticator):
            try:
                authenticated = external_host_authenticator(dict(receipt)) is True
            except Exception:
                authenticated = False
        if not authenticated:
            errors.append("provider_selection_external_host_authenticity_unverified")
    return list(dict.fromkeys(errors))


def _unsigned_sql_provider_selection(
    provider_selection: Mapping[str, Any],
) -> Dict[str, Any]:
    unsigned = dict(provider_selection)
    unsigned.pop("provider_selection_receipt", None)
    return unsigned


def _explicit_sql_provider_selection_claim(
    provider_selection: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "provider_id": provider_selection.get("provider_id"),
        "provider_source": provider_selection.get("provider_source"),
        "provider_path": provider_selection.get("provider_path"),
        "selected_active_provider_path": provider_selection.get(
            "selected_active_provider_path"
        ),
        "compatibility": provider_selection.get("compatibility"),
        "selection_status": provider_selection.get("selection_status"),
    }


def _sql_provider_selection_schema_errors(provider_selection: Any) -> List[str]:
    if not isinstance(provider_selection, Mapping):
        return ["provider_selection_missing"]
    errors: List[str] = []
    schema_version = provider_selection.get("schema_version")
    if type(schema_version) is not int:
        errors.append("provider_selection_schema_version_not_integer")
    elif schema_version != SQL_PROVIDER_SELECTION_SCHEMA_VERSION:
        errors.append("provider_selection_schema_version_mismatch")

    string_fields = [
        "host",
        "project",
        "provider_id",
        "provider_path",
        "selected_active_provider_path",
        "provider_source",
        "compatibility",
        "selection_status",
        "front_door_status",
    ]
    for key in string_fields:
        value = provider_selection.get(key)
        if type(value) is not str:
            errors.append(f"provider_selection_{key}_not_string")
        elif not value.strip():
            errors.append(f"provider_selection_{key}_missing")

    if type(provider_selection.get("front_door_status")) is str and provider_selection[
        "front_door_status"
    ] != "ok":
        errors.append("provider_selection_not_authorized")
    if type(provider_selection.get("provider_id")) is str and provider_selection[
        "provider_id"
    ] != PACKAGED_PROVIDER_ID:
        errors.append("provider_selection_provider_id_mismatch")
    if type(provider_selection.get("provider_source")) is str and provider_selection[
        "provider_source"
    ] not in SQL_PROVIDER_SELECTION_SOURCES:
        errors.append("provider_selection_provider_source_not_allowed")
    if type(provider_selection.get("compatibility")) is str and provider_selection[
        "compatibility"
    ] != "compatible":
        errors.append("provider_selection_compatibility_not_allowed")
    if type(provider_selection.get("selection_status")) is str and provider_selection[
        "selection_status"
    ] != "selected":
        errors.append("provider_selection_status_not_allowed")

    provider_path = provider_selection.get("provider_path")
    selected_path = provider_selection.get("selected_active_provider_path")
    if type(provider_path) is str and type(selected_path) is str:
        if _provider_path_key(provider_path) != _provider_path_key(selected_path):
            errors.append("provider_selection_selected_path_mismatch")
        if not Path(provider_path).expanduser().is_absolute():
            errors.append("provider_selection_provider_path_not_absolute")
    project = provider_selection.get("project")
    if type(project) is str and not Path(project).expanduser().is_absolute():
        errors.append("provider_selection_project_not_absolute")

    gate = provider_selection.get("execution_gate")
    if not isinstance(gate, Mapping):
        errors.append("provider_selection_execution_gate_missing")
    else:
        if gate.get("can_execute") is not True:
            errors.append("provider_selection_execution_blocked")
        status = gate.get("status")
        if type(status) is not str:
            errors.append("provider_selection_execution_gate_status_not_string")
        elif status not in SQL_PROVIDER_SELECTION_GATE_STATUSES:
            errors.append("provider_selection_execution_gate_status_not_allowed")
        reason = gate.get("reason")
        if type(reason) is not str:
            errors.append("provider_selection_execution_gate_reason_not_string")
        elif not reason.strip():
            errors.append("provider_selection_execution_gate_reason_missing")

    route = provider_selection.get("plugin_route")
    if not isinstance(route, Mapping):
        errors.append("provider_selection_route_missing")
        return list(dict.fromkeys(errors))
    route_value = route.get("route")
    if type(route_value) is not str:
        errors.append("provider_selection_route_not_string")
    elif route_value not in {"single", "hybrid"}:
        errors.append("provider_selection_route_not_allowed")
    roles: List[Any] = [route.get("controller")]
    assistants = route.get("assistants", [])
    if isinstance(assistants, list):
        roles.extend(assistants)
    elif assistants is not None:
        errors.append("provider_selection_assistants_not_list")
    matching: List[Mapping[str, Any]] = []
    for role in roles:
        if not isinstance(role, Mapping):
            continue
        if role.get("provider_id") == PACKAGED_PROVIDER_ID or role.get(
            "capability"
        ) == "sql_formatting":
            matching.append(role)
    if len(matching) != 1:
        errors.append("provider_selection_ambiguous" if matching else "provider_selection_missing")
        return list(dict.fromkeys(errors))
    role = matching[0]
    for key, expected in {
        "provider_id": PACKAGED_PROVIDER_ID,
        "capability": "sql_formatting",
    }.items():
        value = role.get(key)
        if type(value) is not str:
            errors.append(f"provider_selection_role_{key}_not_string")
        elif value != expected:
            errors.append(f"provider_selection_role_{key}_mismatch")
    metadata = role.get("metadata")
    if not isinstance(metadata, Mapping):
        errors.append("provider_selection_metadata_missing")
        return list(dict.fromkeys(errors))
    correlations = {
        "path": "provider_path",
        "source": "provider_source",
        "compatibility": "compatibility",
    }
    for metadata_key, selection_key in correlations.items():
        value = metadata.get(metadata_key)
        expected = provider_selection.get(selection_key)
        if type(value) is not str:
            errors.append(f"provider_selection_metadata_{metadata_key}_not_string")
        elif type(expected) is str and (
            _provider_path_key(value) != _provider_path_key(expected)
            if metadata_key == "path"
            else value != expected
        ):
            errors.append(f"provider_selection_metadata_{metadata_key}_mismatch")
    return list(dict.fromkeys(errors))


def _runtime_receipt_identity_errors(
    receipt: Mapping[str, Any],
    *,
    error_prefix: str,
    schema_version: int,
    receipt_id_field: str,
    receipt_id_pattern: re.Pattern[str],
    boundary: RuntimeProducerBoundary,
    producer_name: str,
    claim_kind: str,
) -> List[str]:
    errors: List[str] = []
    actual_schema = receipt.get("schema_version")
    if type(actual_schema) is not int or actual_schema != schema_version:
        errors.append(f"{error_prefix}_schema_version_mismatch")
    receipt_id = receipt.get(receipt_id_field)
    if type(receipt_id) is not str or not receipt_id_pattern.fullmatch(receipt_id):
        errors.append(f"{error_prefix}_id_invalid")
    for key, expected in {
        "authority": "local_runtime_integrity",
        "external_authenticity": "unverified",
    }.items():
        actual = receipt.get(key)
        if type(actual) is not str or actual != expected:
            errors.append(f"{error_prefix}_{key}_mismatch")
    producer_claim = receipt.get("producer_claim")
    if type(producer_claim) is not str or not re.fullmatch(
        r"hmac-sha256:[0-9a-f]{64}", producer_claim
    ):
        errors.append(f"{error_prefix}_producer_claim_invalid")
    producer_boundary = receipt.get("producer_boundary")
    if not isinstance(producer_boundary, Mapping):
        errors.append(f"{error_prefix}_producer_boundary_missing")
        return errors
    expected_boundary = {
        "kind": "durable_local_runtime_integrity_v1",
        "boundary_id": boundary.boundary_id,
        "producer_name": producer_name,
        "claim_kind": claim_kind,
    }
    for key, expected in expected_boundary.items():
        actual = producer_boundary.get(key)
        if type(actual) is not str or actual != expected:
            errors.append(f"{error_prefix}_producer_boundary_{key}_mismatch")
    boundary_id = producer_boundary.get("boundary_id")
    if type(boundary_id) is str and not re.fullmatch(
        r"local-[0-9a-f]{24}", boundary_id
    ):
        errors.append(f"{error_prefix}_producer_boundary_boundary_id_invalid")
    return list(dict.fromkeys(errors))


def _selected_sql_provider_from_front_door(
    provider_selection: Mapping[str, Any],
) -> Dict[str, str]:
    if not isinstance(provider_selection, Mapping) or not provider_selection:
        raise SqlFormattingProviderPathError(
            "provider_selection_missing",
            "Correlated front-door provider selection evidence is required",
            "",
        )
    provenance_errors = validate_sql_provider_selection_runtime_receipt(
        provider_selection
    )
    if provenance_errors:
        raise SqlFormattingProviderPathError(
            "provider_selection_provenance_invalid",
            ",".join(provenance_errors),
            "",
        )
    return _selected_sql_provider_claim(provider_selection)


def _selected_sql_provider_claim(
    provider_selection: Mapping[str, Any],
) -> Dict[str, str]:
    if not isinstance(provider_selection, Mapping) or not provider_selection:
        raise SqlFormattingProviderPathError(
            "provider_selection_missing",
            "Correlated front-door provider selection evidence is required",
            "",
        )
    schema_errors = _sql_provider_selection_schema_errors(provider_selection)
    if schema_errors:
        raise SqlFormattingProviderPathError(
            schema_errors[0],
            ",".join(schema_errors),
            "",
        )
    return _explicit_sql_provider_selection_claim(provider_selection)


def bind_verified_sql_final_response(
    original_sql: str | bytes | os.PathLike[str],
    verified_candidate: str,
    draft_final_response: str,
    *,
    style_contract_path: str | Path | None = None,
    cte_temp_table_reason: str | None = None,
    alias_role_plan: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    scalar_function_refactor: Mapping[str, Any] | None = None,
    runtime_receipt_authenticator: Any = None,
    operation: str | None = None,
) -> SqlFinalResponseBinding:
    if not isinstance(original_sql, (str, bytes, os.PathLike)) or not original_sql:
        raise SqlFinalResponseBindingError(
            "invalid_original_sql",
            "The original SQL must be non-empty text, bytes, or a path.",
        )
    if not isinstance(verified_candidate, str) or not verified_candidate:
        raise SqlFinalResponseBindingError(
            "invalid_verified_candidate",
            "The verified candidate must be a non-empty string.",
        )
    if not isinstance(draft_final_response, str):
        raise SqlFinalResponseBindingError(
            "invalid_final_response",
            "The draft final response must be a string.",
        )
    if operation not in {None, "formatting"}:
        raise SqlFinalResponseBindingError(
            "unsupported_final_binding_operation",
            "SQL formatting final-response binding only accepts operation='formatting'.",
        )

    verifier_kwargs: Dict[str, Any] = {}
    if style_contract_path is not None:
        verifier_kwargs["style_contract_path"] = style_contract_path
    if cte_temp_table_reason is not None:
        verifier_kwargs["cte_temp_table_reason"] = cte_temp_table_reason
    if alias_role_plan is not None:
        verifier_kwargs["alias_role_plan"] = alias_role_plan
    if scalar_function_refactor is not None:
        verifier_kwargs["scalar_function_refactor"] = scalar_function_refactor
    if runtime_receipt_authenticator is not None:
        verifier_kwargs["runtime_receipt_authenticator"] = runtime_receipt_authenticator
    verifier_kwargs["operation"] = "formatting"

    fresh_result = verify_sql_formatting_style(
        original_sql,
        verified_candidate,
        **verifier_kwargs,
    )
    receipt = _verifier_receipt_mapping(fresh_result)
    success = receipt.get("success")
    exit_code = receipt.get("exit_code")
    if (
        success is not True
        or not isinstance(exit_code, int)
        or isinstance(exit_code, bool)
        or exit_code != 0
    ):
        raise SqlFinalResponseBindingError(
            "verifier_not_ready",
            "The fresh verifier result must report success=true and exit_code=0.",
        )

    metadata = receipt.get("metadata")
    if not isinstance(metadata, Mapping):
        raise SqlFinalResponseBindingError(
            "invalid_fresh_verification",
            "The fresh verifier result must contain mapping metadata.",
        )
    formatted_sha256 = metadata.get("formatted_sha256")
    if not isinstance(formatted_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", formatted_sha256
    ):
        raise SqlFinalResponseBindingError(
            "invalid_fresh_verification",
            "Fresh verifier metadata must contain a lowercase formatted_sha256 digest.",
        )
    original_sha256 = metadata.get("original_sha256")
    if not isinstance(original_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", original_sha256
    ):
        raise SqlFinalResponseBindingError(
            "invalid_fresh_verification",
            "Fresh verifier metadata must contain a lowercase original_sha256 digest.",
        )
    candidate_sha256 = _sha256_text(verified_candidate)
    if candidate_sha256 != formatted_sha256:
        raise SqlFinalResponseBindingError(
            "stale_verification_result",
            "Fresh verifier metadata does not identify the supplied candidate.",
        )

    release_readiness = metadata.get("release_readiness")
    if not isinstance(release_readiness, Mapping):
        raise SqlFinalResponseBindingError(
            "invalid_fresh_verification",
            "Fresh verifier metadata must contain release_readiness mapping evidence.",
        )
    if release_readiness.get("status") != "ready":
        raise SqlFinalResponseBindingError(
            "verifier_not_ready",
            "The fresh verifier result is not release-ready.",
        )
    verification_id = metadata.get("verification_id")
    if not isinstance(verification_id, str) or not verification_id.strip():
        raise SqlFinalResponseBindingError(
            "invalid_fresh_verification",
            "Fresh verifier metadata must contain a non-empty verification_id.",
        )

    blocks = _markdown_fenced_blocks(draft_final_response)
    if not blocks:
        raise SqlFinalResponseBindingError(
            "missing_sql_fence",
            "The final response must contain one complete SQL fenced block.",
        )
    if len(blocks) != 1:
        raise SqlFinalResponseBindingError(
            "multiple_fenced_blocks",
            "The final response must not contain extra SQL or non-SQL fenced blocks.",
        )

    block = blocks[0]
    if not block.marker.startswith("`") or block.info.strip().lower() not in SQL_FENCE_LANGUAGES:
        raise SqlFinalResponseBindingError(
            "missing_sql_fence",
            "The single fenced block must be labeled sql, tsql, or t-sql.",
        )
    if draft_final_response[: block.start].strip():
        raise SqlFinalResponseBindingError(
            "sql_fence_not_first",
            "Paste-ready full SQL must be the first substantive final-response content.",
        )
    if block.body != verified_candidate:
        raise SqlFinalResponseBindingError(
            "final_sql_candidate_mismatch",
            "The final SQL is partial, retyped, or otherwise differs from the verified candidate.",
        )
    if _sha256_text(block.body) != formatted_sha256:
        raise SqlFinalResponseBindingError(
            "final_sql_hash_mismatch",
            "The final SQL does not match the verifier receipt hash.",
        )

    return SqlFinalResponseBinding(
        status="bound",
        final_response=draft_final_response,
        formatted_sql=block.body,
        original_sha256=original_sha256,
        formatted_sha256=formatted_sha256,
        final_response_sha256=_sha256_text(draft_final_response),
        verification_id=verification_id,
        sql_fence_count=1,
        verification=dict(receipt),
    )


def guard_and_bind_verified_sql_final_response(
    original_sql: str | bytes | os.PathLike[str],
    verified_candidate: str,
    draft_final_response: str,
    *,
    provider_path: str | Path,
    selected_active_provider_path: str | Path,
    provider_selection: Mapping[str, Any],
    style_contract_path: str | Path | None = None,
    cte_temp_table_reason: str | None = None,
    alias_role_plan: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    verifier_history: Sequence[Mapping[str, Any]] | None = None,
) -> SqlFinalResponseRelease:
    provider_guard = guard_authoritative_sql_formatting_provider_path(
        provider_path,
        selected_active_provider_path=selected_active_provider_path,
        provider_selection=provider_selection,
    )
    binding = bind_verified_sql_final_response(
        original_sql,
        verified_candidate,
        draft_final_response,
        style_contract_path=style_contract_path,
        cte_temp_table_reason=cte_temp_table_reason,
        alias_role_plan=alias_role_plan,
        operation="formatting",
    )
    _require_ready_sql_formatting_repair_history(verifier_history, binding)
    return SqlFinalResponseRelease(
        status="passed",
        provider_path_guard=provider_guard,
        binding=binding,
    )


def _require_ready_sql_formatting_repair_history(
    verifier_history: Sequence[Mapping[str, Any]] | None,
    binding: SqlFinalResponseBinding,
) -> SqlFormattingRepairDecision:
    if (
        not isinstance(verifier_history, Sequence)
        or isinstance(verifier_history, (str, bytes))
        or not verifier_history
    ):
        raise SqlFinalResponseBindingError(
            "sql_formatting_repair_history_required",
            "Public SQL release requires the complete verifier history.",
        )
    if any(not isinstance(item, Mapping) for item in verifier_history):
        raise SqlFinalResponseBindingError(
            "sql_formatting_repair_history_invalid",
            "Every verifier-history item must be a structured verifier result.",
        )
    decision = evaluate_sql_formatting_repair_gate(verifier_history)
    if decision.status != "ready" or not decision.sql_delivery_allowed:
        raise SqlFinalResponseBindingError(
            decision.blocked_reason or "sql_formatting_repair_decision_not_ready",
            "The complete verifier history is not eligible for final SQL release.",
        )
    latest = verifier_history[-1]
    latest_metadata = latest.get("metadata", {})
    if not isinstance(latest_metadata, Mapping):
        raise SqlFinalResponseBindingError(
            "sql_formatting_repair_history_invalid",
            "The final verifier-history item must contain mapping metadata.",
        )
    expected = {
        "original_sha256": binding.original_sha256,
        "formatted_sha256": binding.formatted_sha256,
    }
    if any(latest_metadata.get(key) != value for key, value in expected.items()):
        raise SqlFinalResponseBindingError(
            "sql_formatting_repair_history_candidate_mismatch",
            "The ready verifier history is not bound to the exact final SQL candidate.",
        )
    return decision


def guard_authoritative_sql_formatting_provider_path(
    provider_path: str | Path,
    *,
    selected_active_provider_path: str | Path,
    provider_selection: Mapping[str, Any],
) -> AuthoritativeSqlFormattingProviderPath:
    root = _default_skills_root()
    packaged_fallback = _absolute_provider_path(
        root.expanduser()
        / PACKAGED_PROVIDER_SKILL_DIR
        / "SKILL.md"
    )
    selected_role = _selected_sql_provider_from_front_door(provider_selection)
    selection_sha256 = sql_provider_selection_sha256(provider_selection)
    selected_provider_path = str(selected_role["provider_path"])
    provider_id = str(selected_role["provider_id"])
    provider_source = str(selected_role["provider_source"])
    requested = _coerce_provider_path(provider_path).expanduser()
    requested_absolute = _absolute_provider_path(requested)
    selected_absolute = _absolute_provider_path(
        _coerce_provider_path(selected_active_provider_path).expanduser()
    )
    routed_absolute = _absolute_provider_path(
        _coerce_provider_path(selected_provider_path).expanduser()
    )
    requested_key = _provider_path_key(requested_absolute)
    selected_key = _provider_path_key(selected_absolute)
    routed_key = _provider_path_key(routed_absolute)
    packaged_fallback_key = _provider_path_key(packaged_fallback)

    rejection_code = _prohibited_provider_path_code(requested)
    if rejection_code is None:
        rejection_code = _prohibited_provider_path_code(requested_absolute)
    if rejection_code is not None:
        raise SqlFormattingProviderPathError(
            rejection_code,
            "The provider path is not an authoritative active source",
            str(requested_absolute),
        )
    if provider_source == "host-local-skill" and _looks_like_cached_provider_path(
        requested_absolute
    ):
        raise SqlFormattingProviderPathError(
            "older_cache_provider_path",
            "A host-local selection cannot elevate a plugin cache copy to active authority",
            str(requested_absolute),
        )
    if requested_absolute.name != "SKILL.md":
        raise SqlFormattingProviderPathError(
            "selected_provider_not_compatible",
            "The selected SQL formatting provider must be a SKILL.md file",
            str(requested_absolute),
        )
    if requested_key != selected_key or selected_key != routed_key:
        raise SqlFormattingProviderPathError(
            "provider_selection_path_mismatch",
            "The runtime provider path must match the provider selected by the correlated front-door evidence",
            str(requested_absolute),
        )

    authority = ""
    if provider_source == "packaged-kh-skill":
        if requested_key != packaged_fallback_key:
            raise SqlFormattingProviderPathError(
                "packaged_provider_path_mismatch",
                "The packaged provider must resolve from the running module/repository skill root",
                str(requested_absolute),
            )
        authority = "current-packaged-fallback"
    elif provider_source == "host-local-skill":
        authority = "selected-active-provider"
    elif _looks_like_cached_provider_path(requested_absolute):
        raise SqlFormattingProviderPathError(
            "older_cache_provider_path",
            "An unselected provider cache copy is not authoritative",
            str(requested_absolute),
        )
    else:
        raise SqlFormattingProviderPathError(
            "unselected_provider_copy",
            "The provider path is neither the selected active provider nor the current packaged fallback",
            str(requested_absolute),
        )

    if not requested_absolute.is_file():
        raise SqlFormattingProviderPathError(
            "provider_path_missing",
            "The authoritative provider path does not exist as a file",
            str(requested_absolute),
        )
    if authority == "current-packaged-fallback":
        inspection = inspect_packaged_sql_formatting_provider(root)
        if not inspection.compatible:
            raise SqlFormattingProviderPathError(
                "packaged_provider_not_compatible",
                "The current packaged fallback failed provider inspection",
                str(requested_absolute),
            )
    elif authority == "selected-active-provider":
        inspection = inspect_host_sql_formatting_provider(requested_absolute)
        if not inspection.compatible:
            raise SqlFormattingProviderPathError(
                "selected_provider_not_compatible",
                "The selected active SQL formatting provider failed compatibility inspection",
                str(requested_absolute),
            )

    return AuthoritativeSqlFormattingProviderPath(
        status="accepted",
        authority=authority,
        provider_path=str(requested_absolute),
        selected_active_provider_path=str(selected_absolute),
        current_packaged_fallback_path=str(packaged_fallback),
        provider_id=provider_id,
        provider_source=provider_source,
        provider_selection_sha256=selection_sha256,
    )


def inspect_host_sql_formatting_provider(
    skill_path: str | Path,
) -> HostSqlFormattingProviderInspection:
    path = _coerce_provider_path(skill_path).expanduser().resolve()
    if not path.is_file():
        return HostSqlFormattingProviderInspection(
            status="missing",
            availability="missing",
            compatibility="unknown",
            compatible=False,
            skill_path=str(path),
            issues=["missing_host_sql_formatting_skill"],
        )
    if path.name.casefold() != "skill.md":
        return HostSqlFormattingProviderInspection(
            status="unavailable",
            availability="unavailable",
            compatibility="unknown",
            compatible=False,
            skill_path=str(path),
            issues=["not_a_sql_formatting_skill_file"],
        )
    prohibited_code = _prohibited_provider_path_code(path)
    if prohibited_code:
        return HostSqlFormattingProviderInspection(
            status="unavailable",
            availability="unavailable",
            compatibility="unknown",
            compatible=False,
            skill_path=str(path),
            issues=[prohibited_code],
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
            "alias_plan_requirement": (
                "complete_for_all_multi_source_scopes_and_"
                "alias_changed_single_source_scopes"
            ),
            "final_response_binding_required": True,
            "final_response_binding": "exact_verified_candidate_sha256_single_sql_fence",
            "final_response_binding_helper": (
                "src.skills.sql_formatting_provider."
                "guard_and_bind_verified_sql_final_response"
            ),
            "authoritative_provider_path_required": True,
            "authoritative_provider_path_guard": (
                "src.skills.sql_formatting_provider."
                "guard_authoritative_sql_formatting_provider_path"
            ),
        },
    }


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        dict(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_sql_formatting_cli_artifacts(
    *,
    original_file: str | Path,
    candidate_file: str | Path,
    response_file: str | Path,
    provider_selection_file: str | Path,
) -> SqlFormattingCliArtifacts:
    supplied = {
        "original_file": original_file,
        "candidate_file": candidate_file,
        "response_file": response_file,
        "provider_selection_file": provider_selection_file,
    }
    paths = {
        key: Path(value).expanduser().resolve()
        for key, value in supplied.items()
    }
    for key, path in paths.items():
        if not path.is_file():
            raise SqlFormattingCliArtifactError(
                f"{key}_missing",
                str(path),
                "Required SQL formatting CLI artifact is not a file",
            )
    raw_bytes: Dict[str, bytes] = {}
    for key, path in paths.items():
        try:
            raw_bytes[key] = path.read_bytes()
        except OSError as exc:
            raise SqlFormattingCliArtifactError(
                f"{key}_read_failed",
                str(path),
                str(exc),
            ) from exc
    original_bytes = raw_bytes["original_file"]
    try:
        original_text = original_bytes.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise SqlFormattingCliArtifactError(
            "original_file_read_failed",
            str(paths["original_file"]),
            str(exc),
        ) from exc
    try:
        candidate_text = _decode_utf8_text_mode(raw_bytes["candidate_file"])
    except UnicodeDecodeError as exc:
        raise SqlFormattingCliArtifactError(
            "candidate_file_read_failed",
            str(paths["candidate_file"]),
            str(exc),
        ) from exc
    try:
        response_text = _decode_utf8_text_mode(raw_bytes["response_file"])
    except UnicodeDecodeError as exc:
        raise SqlFormattingCliArtifactError(
            "response_file_read_failed",
            str(paths["response_file"]),
            str(exc),
        ) from exc
    try:
        provider_selection_text = _decode_utf8_text_mode(
            raw_bytes["provider_selection_file"]
        )
        provider_selection = load_json_without_duplicate_keys(provider_selection_text)
        if not isinstance(provider_selection, Mapping):
            raise ValueError("JSON evidence must be an object.")
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise SqlFormattingCliArtifactError(
            "provider_selection_file_read_failed",
            str(paths["provider_selection_file"]),
            str(exc),
        ) from exc
    if provider_selection is None:
        raise SqlFormattingCliArtifactError(
            "provider_selection_file_read_failed",
            str(paths["provider_selection_file"]),
            "Provider selection must contain a JSON object",
        )
    return SqlFormattingCliArtifacts(
        original_bytes=original_bytes,
        candidate_text=candidate_text,
        response_text=response_text,
        provider_selection=provider_selection,
        raw_bytes=raw_bytes,
        resolved_paths={key: str(path) for key, path in paths.items()},
        hashes={
            "original_text_sha256": _sha256_text(original_text),
            "candidate_text_sha256": _sha256_text(candidate_text),
            "response_text_sha256": _sha256_text(response_text),
            "provider_selection_sha256": sql_provider_selection_sha256(
                provider_selection
            ),
            **{
                f"{key}_sha256": _sha256_bytes(content)
                for key, content in raw_bytes.items()
            },
        },
    )


def _decode_utf8_text_mode(value: bytes) -> str:
    return value.decode("utf-8", errors="strict").replace("\r\n", "\n").replace(
        "\r", "\n"
    )


def _sql_provider_receipt_state_dir() -> Path:
    return runtime_root() / "runtime-receipts" / "sql-formatting-provider"


def _sql_provider_selection_receipt_state_dir() -> Path:
    return runtime_root() / "runtime-receipts" / "sql-provider-selection"


def _sql_provider_runtime_boundary() -> RuntimeProducerBoundary:
    return RuntimeProducerBoundary(
        SQL_PROVIDER_RECEIPT_PRODUCER,
        state_dir=_sql_provider_receipt_state_dir(),
    )


def _sql_provider_selection_runtime_boundary() -> RuntimeProducerBoundary:
    return RuntimeProducerBoundary(
        SQL_PROVIDER_SELECTION_RECEIPT_PRODUCER,
        state_dir=_sql_provider_selection_receipt_state_dir(),
    )


def _sql_provider_module_evidence() -> Dict[str, str]:
    module_path = Path(__file__).resolve()
    return {
        "module_path": str(module_path),
        "module_sha256": hashlib.sha256(module_path.read_bytes()).hexdigest(),
    }


def _release_without_runtime_receipt(receipt: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in dict(receipt).items()
        if key != "runtime_receipt"
    }


def _successful_sql_cli_input_errors(
    cli_inputs: Any,
    *,
    expected_session_id: str = "",
    expected_invocation_nonce: str = "",
    expected_provider_selection_sha256: str = "",
) -> List[str]:
    if not isinstance(cli_inputs, Mapping):
        return ["cli_input_receipt_missing"]
    errors: List[str] = []
    for key in sorted(set(cli_inputs) - SQL_CLI_INPUT_FIELDS):
        errors.append(f"cli_input_unexpected_{key}")
    module = cli_inputs.get("module")
    if type(module) is not str:
        errors.append("cli_input_module_not_string")
    elif module != "src.skills.sql_formatting_provider":
        errors.append("cli_input_module_mismatch")
    exit_status = cli_inputs.get("exit_status")
    if type(exit_status) is not int:
        errors.append("cli_input_exit_status_not_integer")
    elif exit_status != 0:
        errors.append("cli_input_exit_status_not_success")

    arguments = cli_inputs.get("arguments")
    if not isinstance(arguments, Mapping):
        errors.append("cli_input_arguments_missing")
        arguments = {}
    else:
        for key in sorted(set(arguments) - SQL_CLI_ARGUMENT_FIELDS):
            errors.append(f"cli_input_argument_unexpected_{key}")
    resolved_paths = cli_inputs.get("resolved_paths")
    if not isinstance(resolved_paths, Mapping):
        errors.append("cli_input_resolved_paths_missing")
        resolved_paths = {}
    else:
        for key in sorted(set(resolved_paths) - SQL_CLI_RESOLVED_PATH_FIELDS):
            errors.append(f"cli_input_resolved_path_unexpected_{key}")
    hashes = cli_inputs.get("hashes")
    if not isinstance(hashes, Mapping):
        errors.append("cli_input_hashes_missing")
        hashes = {}
    else:
        for key in sorted(set(hashes) - SQL_CLI_HASH_FIELDS):
            errors.append(f"cli_input_hash_unexpected_{key}")

    for key in (*SQL_CLI_PATH_ARGUMENTS, *SQL_CLI_SCOPE_ARGUMENTS):
        if key not in arguments:
            errors.append(f"cli_input_argument_{key}_missing")
        elif type(arguments[key]) is not str:
            errors.append(f"cli_input_argument_{key}_not_string")
        elif not arguments[key].strip():
            errors.append(f"cli_input_argument_{key}_missing")
    for key in SQL_CLI_PATH_ARGUMENTS:
        argument_value = arguments.get(key)
        if key not in resolved_paths:
            errors.append(f"cli_input_resolved_path_{key}_missing")
            continue
        resolved_value = resolved_paths[key]
        if type(resolved_value) is not str:
            errors.append(f"cli_input_resolved_path_{key}_not_string")
            continue
        resolved_value = resolved_value.strip()
        if not resolved_value:
            errors.append(f"cli_input_resolved_path_{key}_missing")
            continue
        if not Path(resolved_value).expanduser().is_absolute():
            errors.append(f"cli_input_resolved_path_{key}_not_absolute")
        if type(argument_value) is str and argument_value.strip() and _provider_path_key(
            Path(argument_value.strip()).expanduser()
        ) != _provider_path_key(Path(resolved_value).expanduser()):
            errors.append(f"cli_input_path_{key}_mismatch")

    argument_provider = arguments.get("provider_path")
    argument_selected = arguments.get("selected_active_provider_path")
    resolved_provider = resolved_paths.get("provider_path")
    resolved_selected = resolved_paths.get("selected_active_provider_path")
    if (
        type(argument_provider) is str
        and type(argument_selected) is str
        and _provider_path_key(argument_provider) != _provider_path_key(argument_selected)
    ) or (
        type(resolved_provider) is str
        and type(resolved_selected) is str
        and _provider_path_key(resolved_provider) != _provider_path_key(resolved_selected)
    ):
        errors.append("cli_input_provider_paths_mismatch")

    for key in SQL_CLI_REQUIRED_HASHES:
        if key not in hashes:
            errors.append(f"cli_input_hash_{key}_missing_or_invalid")
            continue
        value = hashes[key]
        if type(value) is not str:
            errors.append(f"cli_input_hash_{key}_not_string")
        elif not re.fullmatch(r"[0-9a-fA-F]{64}", value):
            errors.append(f"cli_input_hash_{key}_missing_or_invalid")

    normalized_session_id = (
        expected_session_id.strip() if type(expected_session_id) is str else ""
    )
    if type(expected_session_id) is not str:
        errors.append("expected_session_id_not_string")
    if normalized_session_id and (
        type(arguments.get("session_id")) is not str
        or arguments["session_id"].strip() != normalized_session_id
    ):
        errors.append("cli_input_argument_session_id_mismatch")
    normalized_nonce = (
        expected_invocation_nonce.strip()
        if type(expected_invocation_nonce) is str
        else ""
    )
    if type(expected_invocation_nonce) is not str:
        errors.append("expected_invocation_nonce_not_string")
    if normalized_nonce and (
        type(arguments.get("invocation_nonce")) is not str
        or arguments["invocation_nonce"].strip() != normalized_nonce
    ):
        errors.append("cli_input_argument_invocation_nonce_mismatch")
    expected_selection = (
        expected_provider_selection_sha256.lower()
        if type(expected_provider_selection_sha256) is str
        else ""
    )
    if type(expected_provider_selection_sha256) is not str:
        errors.append("expected_provider_selection_sha256_not_string")
    actual_selection_value = hashes.get("provider_selection_sha256")
    actual_selection = (
        actual_selection_value.lower()
        if type(actual_selection_value) is str
        else ""
    )
    if expected_selection and actual_selection != expected_selection:
        errors.append("cli_input_provider_selection_sha256_mismatch")
    return list(dict.fromkeys(errors))


def _authoritative_sql_cli_artifact_errors(
    cli_inputs: Any,
    *,
    binding: Any,
    guard: Any,
) -> List[str]:
    if not isinstance(cli_inputs, Mapping):
        return []
    arguments = cli_inputs.get("arguments")
    resolved_paths = cli_inputs.get("resolved_paths")
    hashes = cli_inputs.get("hashes")
    if not all(isinstance(item, Mapping) for item in [arguments, resolved_paths, hashes]):
        return []
    artifact_keys = (
        "original_file",
        "candidate_file",
        "response_file",
        "provider_selection_file",
    )
    if any(type(resolved_paths.get(key)) is not str for key in artifact_keys):
        return []
    try:
        artifacts = load_sql_formatting_cli_artifacts(
            **{key: resolved_paths[key] for key in artifact_keys}
        )
    except SqlFormattingCliArtifactError as exc:
        return [f"cli_input_{exc.code}"]
    except (OSError, ValueError, json.JSONDecodeError):
        return ["cli_input_artifact_reopen_failed"]

    errors: List[str] = []
    for key, actual_path in artifacts.resolved_paths.items():
        receipt_path = resolved_paths.get(key)
        if type(receipt_path) is str and (
            _provider_path_key(receipt_path) != _provider_path_key(actual_path)
        ):
            errors.append(f"cli_input_{key}_resolved_path_mismatch")

    canonical_bindings = {
        "original_file": ("original_text_sha256", "original_sha256"),
        "candidate_file": ("candidate_text_sha256", "formatted_sha256"),
        "response_file": ("response_text_sha256", "final_response_sha256"),
    }
    binding = binding if isinstance(binding, Mapping) else {}
    for artifact_name, (hash_key, binding_key) in canonical_bindings.items():
        actual_hash = artifacts.hashes[hash_key]
        receipt_hash = hashes.get(hash_key)
        binding_hash = binding.get(binding_key)
        if (
            type(receipt_hash) is str
            and type(binding_hash) is str
            and (
                receipt_hash.lower() != actual_hash
                or binding_hash.lower() != actual_hash
            )
        ):
            errors.append(f"cli_input_{artifact_name}_hash_mismatch")

    actual_selection_hash = artifacts.hashes["provider_selection_sha256"]
    selection_hash = hashes.get("provider_selection_sha256")
    if type(selection_hash) is str and selection_hash.lower() != actual_selection_hash:
        errors.append("cli_input_provider_selection_file_hash_mismatch")
    for artifact_name in artifact_keys:
        raw_hash_key = f"{artifact_name}_sha256"
        receipt_hash = hashes.get(raw_hash_key)
        if (
            type(receipt_hash) is str
            and receipt_hash.lower() != artifacts.hashes[raw_hash_key]
        ):
            errors.append(f"cli_input_{artifact_name}_raw_hash_mismatch")

    provenance_errors = validate_sql_provider_selection_runtime_receipt(
        artifacts.provider_selection
    )
    if provenance_errors:
        errors.append("cli_input_provider_selection_provenance_invalid")
    guard = guard if isinstance(guard, Mapping) else {}
    for key in [
        "provider_id",
        "provider_source",
        "provider_path",
        "selected_active_provider_path",
    ]:
        selected_value = artifacts.provider_selection.get(key)
        guard_value = guard.get(key)
        if type(selected_value) is str and type(guard_value) is str:
            if key.endswith("path"):
                matches = _provider_path_key(selected_value) == _provider_path_key(guard_value)
            else:
                matches = selected_value == guard_value
            if not matches:
                errors.append(f"provider_path_guard_{key}_selection_mismatch")
    return list(dict.fromkeys(errors))


def validate_sql_final_response_release_schema(
    receipt: Any,
    *,
    expected_session_id: str = "",
    expected_invocation_nonce: str = "",
    expected_provider_selection_sha256: str = "",
) -> List[str]:
    if not isinstance(receipt, Mapping):
        return ["final_response_release_missing"]
    release = _release_without_runtime_receipt(receipt)
    errors: List[str] = []
    for key in sorted(SQL_FINAL_RELEASE_FIELDS - set(release)):
        errors.append(f"final_response_release_{key}_missing")
    for key in sorted(set(release) - SQL_FINAL_RELEASE_FIELDS):
        errors.append(f"final_response_release_{key}_unexpected")

    status = release.get("status")
    if type(status) is not str:
        errors.append("final_response_release_status_not_string")
    elif status != "passed":
        errors.append("final_response_release_status_not_passed")

    cli_inputs = release.get("cli_inputs")
    errors.extend(
        _successful_sql_cli_input_errors(
            cli_inputs,
            expected_session_id=expected_session_id,
            expected_invocation_nonce=expected_invocation_nonce,
            expected_provider_selection_sha256=expected_provider_selection_sha256,
        )
    )
    cli_inputs = cli_inputs if isinstance(cli_inputs, Mapping) else {}
    resolved_paths = cli_inputs.get("resolved_paths")
    resolved_paths = resolved_paths if isinstance(resolved_paths, Mapping) else {}
    cli_hashes = cli_inputs.get("hashes")
    cli_hashes = cli_hashes if isinstance(cli_hashes, Mapping) else {}

    binding = release.get("binding")
    if not isinstance(binding, Mapping):
        errors.append("final_response_release_binding_missing")
        binding = {}
    else:
        for key in sorted(SQL_FINAL_BINDING_FIELDS - set(binding)):
            errors.append(f"final_response_binding_{key}_missing")
        for key in sorted(set(binding) - SQL_FINAL_BINDING_FIELDS):
            errors.append(f"final_response_binding_{key}_unexpected")
    binding_status = binding.get("status")
    if type(binding_status) is not str:
        errors.append("final_response_binding_status_not_string")
    elif binding_status != "bound":
        errors.append("final_response_binding_status_not_bound")
    for key in [
        "original_sha256",
        "formatted_sha256",
        "final_response_sha256",
        "verification_id",
    ]:
        value = binding.get(key)
        if type(value) is not str:
            errors.append(f"final_response_binding_{key}_not_string")
        elif not re.fullmatch(r"[0-9a-fA-F]{64}", value):
            errors.append(f"final_response_binding_{key}_invalid")
    fence_count = binding.get("sql_fence_count")
    if type(fence_count) is not int:
        errors.append("final_response_binding_sql_fence_count_not_integer")
    elif fence_count != 1:
        errors.append("final_response_binding_sql_fence_count_not_one")

    guard = release.get("provider_path_guard")
    if not isinstance(guard, Mapping):
        errors.append("final_response_release_provider_path_guard_missing")
        guard = {}
    else:
        for key in sorted(SQL_FINAL_PROVIDER_GUARD_FIELDS - set(guard)):
            errors.append(f"provider_path_guard_{key}_missing")
        for key in sorted(set(guard) - SQL_FINAL_PROVIDER_GUARD_FIELDS):
            errors.append(f"provider_path_guard_{key}_unexpected")
    for key, expected in {
        "status": "accepted",
        "provider_id": PACKAGED_PROVIDER_ID,
    }.items():
        value = guard.get(key)
        if type(value) is not str:
            errors.append(f"provider_path_guard_{key}_not_string")
        elif value != expected:
            errors.append(f"provider_path_guard_{key}_mismatch")
    provider_source = guard.get("provider_source")
    if type(provider_source) is not str:
        errors.append("provider_path_guard_provider_source_not_string")
    elif provider_source not in SQL_PROVIDER_SELECTION_SOURCES:
        errors.append("provider_path_guard_provider_source_mismatch")
    authority = guard.get("authority")
    expected_authority = {
        "host-local-skill": "selected-active-provider",
        "packaged-kh-skill": "current-packaged-fallback",
    }.get(provider_source)
    if type(authority) is not str:
        errors.append("provider_path_guard_authority_not_string")
    elif expected_authority is not None and authority != expected_authority:
        errors.append("provider_path_guard_authority_mismatch")
    for key in [
        "provider_path",
        "selected_active_provider_path",
        "current_packaged_fallback_path",
    ]:
        value = guard.get(key)
        if type(value) is not str:
            errors.append(f"provider_path_guard_{key}_not_string")
        elif not value.strip():
            errors.append(f"provider_path_guard_{key}_missing")
        elif not Path(value).expanduser().is_absolute():
            errors.append(f"provider_path_guard_{key}_not_absolute")
    for key in ["provider_path", "selected_active_provider_path"]:
        guard_value = guard.get(key)
        cli_value = resolved_paths.get(key)
        if type(guard_value) is str and type(cli_value) is str and (
            _provider_path_key(guard_value) != _provider_path_key(cli_value)
        ):
            errors.append(f"provider_path_guard_{key}_mismatch")
    guard_provider = guard.get("provider_path")
    guard_selected = guard.get("selected_active_provider_path")
    if (
        type(guard_provider) is str
        and type(guard_selected) is str
        and _provider_path_key(guard_provider) != _provider_path_key(guard_selected)
    ):
        errors.append("provider_path_guard_provider_paths_mismatch")
    fallback = guard.get("current_packaged_fallback_path")
    expected_fallback = str(
        _absolute_provider_path(
            _default_skills_root()
            / PACKAGED_PROVIDER_SKILL_DIR
            / "SKILL.md"
        )
    )
    if type(fallback) is str and (
        _provider_path_key(fallback) != _provider_path_key(expected_fallback)
    ):
        errors.append("provider_path_guard_current_packaged_fallback_path_mismatch")
    guard_selection_hash = guard.get("provider_selection_sha256")
    if type(guard_selection_hash) is not str:
        errors.append("provider_path_guard_provider_selection_sha256_not_string")
    elif not re.fullmatch(r"[0-9a-fA-F]{64}", guard_selection_hash):
        errors.append("provider_path_guard_provider_selection_sha256_invalid")
    cli_selection_hash = cli_hashes.get("provider_selection_sha256")
    if (
        type(guard_selection_hash) is str
        and type(cli_selection_hash) is str
        and guard_selection_hash.lower() != cli_selection_hash.lower()
    ):
        errors.append("provider_path_guard_provider_selection_sha256_mismatch")

    for binding_key, cli_key in {
        "original_sha256": "original_text_sha256",
        "formatted_sha256": "candidate_text_sha256",
        "final_response_sha256": "response_text_sha256",
    }.items():
        binding_value = binding.get(binding_key)
        cli_value = cli_hashes.get(cli_key)
        if (
            type(binding_value) is str
            and type(cli_value) is str
            and binding_value.lower() != cli_value.lower()
        ):
            errors.append(f"final_response_binding_{binding_key}_mismatch")

    verification = release.get("verification")
    if not isinstance(verification, Mapping):
        errors.append("final_response_release_verification_missing")
        verification = {}
    else:
        for key in sorted(SQL_FINAL_VERIFICATION_FIELDS - set(verification)):
            errors.append(f"final_response_verification_{key}_missing")
        for key in sorted(set(verification) - SQL_FINAL_VERIFICATION_FIELDS):
            errors.append(f"final_response_verification_{key}_unexpected")
    success = verification.get("success")
    if type(success) is not bool:
        errors.append("final_response_verification_success_not_boolean")
    elif success is not True:
        errors.append("final_response_verification_not_successful")
    verification_exit = verification.get("exit_code")
    if type(verification_exit) is not int:
        errors.append("final_response_verification_exit_code_not_integer")
    elif verification_exit != 0:
        errors.append("final_response_verification_exit_code_not_success")
    for key in ["stdout", "stderr"]:
        if type(verification.get(key)) is not str:
            errors.append(f"final_response_verification_{key}_not_string")
    if type(verification.get("execution_time")) is not float:
        errors.append("final_response_verification_execution_time_not_float")
    metadata = verification.get("metadata")
    if not isinstance(metadata, Mapping):
        errors.append("final_response_verification_metadata_missing")
        metadata = {}
    for key, expected in {
        "harness": "sql-formatting-style-harness",
        "operation": "formatting",
        "token_optimizer_status": "passthrough",
    }.items():
        value = metadata.get(key)
        if type(value) is not str:
            errors.append(f"final_response_verification_{key}_not_string")
        elif value != expected:
            errors.append(f"final_response_verification_{key}_mismatch")
    not_used_reason = metadata.get("not_used_reason")
    if type(not_used_reason) is not str:
        errors.append("final_response_verification_not_used_reason_not_string")
    elif not not_used_reason.strip():
        errors.append("final_response_verification_not_used_reason_missing")
    for key in ["original_sha256", "formatted_sha256", "verification_id"]:
        value = metadata.get(key)
        if type(value) is not str:
            errors.append(f"final_response_verification_{key}_not_string")
        elif not re.fullmatch(r"[0-9a-fA-F]{64}", value):
            errors.append(f"final_response_verification_{key}_invalid")
    for metadata_key, binding_key in {
        "original_sha256": "original_sha256",
        "formatted_sha256": "formatted_sha256",
        "verification_id": "verification_id",
    }.items():
        metadata_value = metadata.get(metadata_key)
        binding_value = binding.get(binding_key)
        if (
            type(metadata_value) is str
            and type(binding_value) is str
            and metadata_value.lower() != binding_value.lower()
        ):
            errors.append(f"final_response_verification_{metadata_key}_mismatch")
    readiness = metadata.get("release_readiness")
    if not isinstance(readiness, Mapping):
        errors.append("final_response_verification_release_readiness_missing")
    else:
        readiness_status = readiness.get("status")
        if type(readiness_status) is not str:
            errors.append(
                "final_response_verification_release_readiness_status_not_string"
            )
        elif readiness_status != "ready":
            errors.append("final_response_verification_release_readiness_not_ready")
    errors.extend(
        _authoritative_sql_cli_artifact_errors(
            cli_inputs,
            binding=binding,
            guard=guard,
        )
    )
    return list(dict.fromkeys(errors))


def attach_sql_formatting_cli_runtime_receipt(
    receipt: Mapping[str, Any],
    *,
    session_id: str,
    invocation_nonce: str,
    exit_code: int = 0,
) -> Dict[str, Any]:
    if type(session_id) is not str:
        raise SqlFinalResponseBindingError(
            "session_scope_not_string",
            "The SQL provider session id must be a string.",
        )
    if type(invocation_nonce) is not str:
        raise SqlFinalResponseBindingError(
            "invocation_nonce_not_string",
            "The SQL provider invocation nonce must be a string.",
        )
    normalized_session_id = session_id.strip()
    normalized_nonce = invocation_nonce.strip()
    if not normalized_session_id:
        raise SqlFinalResponseBindingError(
            "session_scope_missing",
            "A non-empty session id is required for the SQL provider runtime receipt.",
        )
    if not SQL_PROVIDER_NONCE_PATTERN.fullmatch(normalized_nonce):
        raise SqlFinalResponseBindingError(
            "invocation_nonce_invalid",
            "The SQL provider invocation nonce must be 16-128 safe ASCII characters.",
        )
    if isinstance(exit_code, bool) or not isinstance(exit_code, int) or exit_code != 0:
        raise SqlFinalResponseBindingError(
            "provider_exit_status_not_success",
            "A successful SQL provider runtime receipt requires exit_code=0.",
        )

    unsigned_release = _release_without_runtime_receipt(receipt)
    schema_errors = validate_sql_final_response_release_schema(
        unsigned_release,
        expected_session_id=normalized_session_id,
        expected_invocation_nonce=normalized_nonce,
    )
    if schema_errors:
        raise SqlFinalResponseBindingError(
            schema_errors[0],
            "Successful CLI input evidence is incomplete or inconsistent: "
            + ", ".join(schema_errors),
        )
    cli_inputs = unsigned_release.get("cli_inputs")
    assert isinstance(cli_inputs, Mapping)
    hashes = cli_inputs.get("hashes")
    assert isinstance(hashes, Mapping)
    selection_sha256 = hashes["provider_selection_sha256"].lower()

    module_evidence = _sql_provider_module_evidence()
    runtime_payload = {
        "schema_version": SQL_PROVIDER_RECEIPT_SCHEMA_VERSION,
        "status": "passed",
        "session_id": normalized_session_id,
        "invocation_nonce": normalized_nonce,
        "module": "src.skills.sql_formatting_provider",
        **module_evidence,
        "provider_selection_sha256": selection_sha256,
        "cli_inputs_sha256": _sha256_json(cli_inputs),
        "release_sha256": _sha256_json(unsigned_release),
        "exit_code": exit_code,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    issued = _sql_provider_runtime_boundary().issue_claim(
        runtime_payload,
        claim_kind=SQL_PROVIDER_RECEIPT_CLAIM_KIND,
        claim_id_field="receipt_id",
        claim_id_prefix="sql-provider",
    )
    result = dict(unsigned_release)
    result["runtime_receipt"] = issued
    return result


def validate_sql_formatting_cli_runtime_receipt(
    receipt: Mapping[str, Any],
    *,
    expected_session_id: str,
    expected_invocation_nonce: str,
    expected_provider_selection_sha256: str,
) -> List[str]:
    if not isinstance(receipt, Mapping):
        return ["sql_provider_runtime_receipt_missing"]
    runtime_receipt = receipt.get("runtime_receipt")
    if not isinstance(runtime_receipt, Mapping):
        return ["sql_provider_runtime_receipt_missing"]

    errors = _runtime_receipt_identity_errors(
        runtime_receipt,
        error_prefix="sql_provider_runtime_receipt",
        schema_version=SQL_PROVIDER_RECEIPT_SCHEMA_VERSION,
        receipt_id_field="receipt_id",
        receipt_id_pattern=re.compile(r"^sql-provider-[0-9a-f]{32}$"),
        boundary=_sql_provider_runtime_boundary(),
        producer_name=SQL_PROVIDER_RECEIPT_PRODUCER,
        claim_kind=SQL_PROVIDER_RECEIPT_CLAIM_KIND,
    )
    errors.extend(
        _sql_provider_runtime_boundary().validate_claim(
            runtime_receipt,
            claim_kind=SQL_PROVIDER_RECEIPT_CLAIM_KIND,
            claim_id_field="receipt_id",
            consume=False,
        )
    )
    unsigned_release = _release_without_runtime_receipt(receipt)
    cli_inputs = unsigned_release.get("cli_inputs")
    errors.extend(
        validate_sql_final_response_release_schema(
            unsigned_release,
            expected_session_id=expected_session_id,
            expected_invocation_nonce=expected_invocation_nonce,
            expected_provider_selection_sha256=expected_provider_selection_sha256,
        )
    )
    if not isinstance(cli_inputs, Mapping):
        cli_inputs = {}
    normalized_expected_session = (
        expected_session_id.strip() if type(expected_session_id) is str else ""
    )
    normalized_expected_nonce = (
        expected_invocation_nonce.strip()
        if type(expected_invocation_nonce) is str
        else ""
    )
    normalized_expected_selection = (
        expected_provider_selection_sha256.lower()
        if type(expected_provider_selection_sha256) is str
        else ""
    )
    expected = {
        "schema_version": SQL_PROVIDER_RECEIPT_SCHEMA_VERSION,
        "status": "passed",
        "session_id": normalized_expected_session,
        "invocation_nonce": normalized_expected_nonce,
        "module": "src.skills.sql_formatting_provider",
        "provider_selection_sha256": normalized_expected_selection,
        "cli_inputs_sha256": _sha256_json(cli_inputs),
        "release_sha256": _sha256_json(unsigned_release),
        "exit_code": 0,
        **_sql_provider_module_evidence(),
    }
    for key, value in expected.items():
        actual = runtime_receipt.get(key)
        if type(actual) is not type(value) or actual != value:
            errors.append(f"sql_provider_runtime_receipt_{key}_mismatch")
    for key in [
        "receipt_id",
        "authority",
        "external_authenticity",
        "producer_claim",
    ]:
        if type(runtime_receipt.get(key)) is not str or not runtime_receipt[key].strip():
            errors.append(f"sql_provider_runtime_receipt_{key}_not_string")
    boundary = runtime_receipt.get("producer_boundary")
    if isinstance(boundary, Mapping):
        for key in ["kind", "boundary_id", "producer_name", "claim_kind"]:
            if type(boundary.get(key)) is not str or not boundary[key].strip():
                errors.append(
                    f"sql_provider_runtime_receipt_producer_boundary_{key}_not_string"
                )
    issued_value = runtime_receipt.get("issued_at")
    issued_at = issued_value.strip() if type(issued_value) is str else ""
    if type(issued_value) is not str:
        errors.append("sql_provider_runtime_receipt_issued_at_not_string")
    try:
        parsed = datetime.fromisoformat(issued_at.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is None:
        errors.append("sql_provider_runtime_receipt_issued_at_invalid")
    return list(dict.fromkeys(errors))


def _verifier_receipt_mapping(verifier_result: Any) -> Mapping[str, Any]:
    if verifier_result is None:
        raise SqlFinalResponseBindingError(
            "missing_verifier_receipt",
            "A verifier result or receipt is required before final-response binding.",
        )
    if isinstance(verifier_result, Mapping):
        return verifier_result

    to_dict = getattr(verifier_result, "to_dict", None)
    if not callable(to_dict):
        raise SqlFinalResponseBindingError(
            "invalid_verifier_receipt",
            "The verifier result must be a Mapping or expose to_dict().",
        )
    try:
        receipt = to_dict()
    except Exception as exc:
        raise SqlFinalResponseBindingError(
            "invalid_verifier_receipt",
            f"The verifier result to_dict() call failed with {type(exc).__name__}.",
        ) from exc
    if not isinstance(receipt, Mapping):
        raise SqlFinalResponseBindingError(
            "invalid_verifier_receipt",
            "The verifier result to_dict() value must be a Mapping.",
        )
    return receipt


def _markdown_fenced_blocks(text: str) -> List[_MarkdownFencedBlock]:
    blocks: List[_MarkdownFencedBlock] = []
    active: Dict[str, Any] | None = None
    offset = 0
    for line in text.splitlines(keepends=True):
        line_without_ending = line.rstrip("\r\n")
        match = MARKDOWN_FENCE_LINE_PATTERN.fullmatch(line_without_ending)
        if active is None:
            if match:
                active = {
                    "marker": match.group("marker"),
                    "info": match.group("info").strip(),
                    "start": offset,
                    "body_start": offset + len(line),
                }
        elif _is_closing_fence(match, str(active["marker"])):
            body = text[int(active["body_start"]) : offset]
            if body.endswith("\r\n"):
                body = body[:-2]
            elif body.endswith("\n") or body.endswith("\r"):
                body = body[:-1]
            blocks.append(
                _MarkdownFencedBlock(
                    marker=str(active["marker"]),
                    info=str(active["info"]),
                    body=body,
                    start=int(active["start"]),
                    end=offset + len(line),
                )
            )
            active = None
        offset += len(line)

    if active is not None:
        code = (
            "unterminated_sql_fence"
            if str(active["info"]).strip().lower() in SQL_FENCE_LANGUAGES
            else "unterminated_fenced_block"
        )
        raise SqlFinalResponseBindingError(
            code,
            "The draft final response contains an unterminated fenced block.",
        )
    return blocks


def _is_closing_fence(match: re.Match[str] | None, opening_marker: str) -> bool:
    if match is None or match.group("info").strip():
        return False
    marker = match.group("marker")
    return marker[0] == opening_marker[0] and len(marker) >= len(opening_marker)


def _load_json_mapping(path: str | None) -> Mapping[str, Any] | None:
    if not path:
        return None
    data = load_json_without_duplicate_keys(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("JSON evidence must be an object.")
    return data


def _load_json_sequence(path: str | None) -> Sequence[Mapping[str, Any]] | None:
    if not path:
        return None
    data = load_json_without_duplicate_keys(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, Sequence) or isinstance(data, (str, bytes)):
        raise ValueError("Verifier-history evidence must be an array.")
    return data


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Guard the selected SQL formatter and bind a freshly verified final SQL response."
    )
    parser.add_argument("--original-file", required=True)
    parser.add_argument("--candidate-file", required=True)
    parser.add_argument("--response-file", required=True)
    parser.add_argument("--provider-path", required=True)
    parser.add_argument("--selected-active-provider-path", required=True)
    parser.add_argument("--provider-selection-file", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--invocation-nonce", required=True)
    parser.add_argument("--style-contract")
    parser.add_argument("--alias-role-plan-file")
    parser.add_argument("--verifier-history-file")
    parser.add_argument("--cte-temp-table-reason")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_cli_parser().parse_args(argv)
    try:
        artifacts = load_sql_formatting_cli_artifacts(
            original_file=args.original_file,
            candidate_file=args.candidate_file,
            response_file=args.response_file,
            provider_selection_file=args.provider_selection_file,
        )
        release = guard_and_bind_verified_sql_final_response(
            artifacts.original_bytes,
            artifacts.candidate_text,
            artifacts.response_text,
            provider_path=args.provider_path,
            selected_active_provider_path=args.selected_active_provider_path,
            provider_selection=artifacts.provider_selection,
            style_contract_path=args.style_contract,
            cte_temp_table_reason=args.cte_temp_table_reason,
            alias_role_plan=_load_json_mapping(args.alias_role_plan_file),
            verifier_history=_load_json_sequence(args.verifier_history_file),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        code = getattr(exc, "code", "sql_final_binding_failed")
        print(json.dumps({"status": "blocked", "error_code": code, "message": str(exc)}))
        return 1
    receipt = release.to_receipt_dict()
    receipt["cli_inputs"] = {
        "module": "src.skills.sql_formatting_provider",
        "exit_status": 0,
        "arguments": {
            "original_file": args.original_file,
            "candidate_file": args.candidate_file,
            "response_file": args.response_file,
            "provider_path": args.provider_path,
            "selected_active_provider_path": args.selected_active_provider_path,
            "provider_selection_file": args.provider_selection_file,
            "session_id": args.session_id,
            "invocation_nonce": args.invocation_nonce,
        },
        "resolved_paths": {
            "original_file": artifacts.resolved_paths["original_file"],
            "candidate_file": artifacts.resolved_paths["candidate_file"],
            "response_file": artifacts.resolved_paths["response_file"],
            "provider_path": release.provider_path_guard.provider_path,
            "selected_active_provider_path": (
                release.provider_path_guard.selected_active_provider_path
            ),
            "provider_selection_file": artifacts.resolved_paths[
                "provider_selection_file"
            ],
        },
        "hashes": dict(artifacts.hashes),
    }
    receipt = attach_sql_formatting_cli_runtime_receipt(
        receipt,
        session_id=args.session_id,
        invocation_nonce=args.invocation_nonce,
        exit_code=0,
    )
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


def _normalized_path_parts(path: Path) -> List[str]:
    return [
        re.sub(r"[^a-z0-9]+", "-", part.casefold()).strip("-")
        for part in path.parts
        if part
    ]


def _absolute_provider_path(path: Path) -> Path:
    return Path(os.path.realpath(os.path.abspath(os.fspath(_coerce_provider_path(path)))))


def _provider_path_key(path: Path) -> str:
    return os.path.normcase(
        os.path.realpath(os.path.abspath(os.fspath(_coerce_provider_path(path))))
    )


def _coerce_provider_path(path: str | Path) -> Path:
    raw = os.fspath(path)
    if raw.startswith("\\\\?\\UNC\\"):
        raw = "\\\\" + raw[8:]
    elif raw.startswith("\\\\?\\"):
        raw = raw[4:]
    return Path(raw)


def _prohibited_provider_path_code(path: Path) -> str | None:
    parts = _normalized_path_parts(path)
    if any(
        part in {"disabled", "disabled-skill", "disabled-skills"}
        or part.startswith("disabled-skills-")
        for part in parts
    ):
        return "disabled_provider_path"
    if any(
        part in {"backup", "backups", "bak", "archive", "archives"}
        or part.startswith("backup-")
        or part.endswith("-backup")
        for part in parts
    ) or path.suffix.casefold() in {".bak", ".backup"}:
        return "backup_provider_path"
    if any(
        part in {"stage", "staged", "staging"}
        or part.startswith("staging-")
        or part.endswith("-staging")
        for part in parts
    ):
        return "staging_provider_path"
    return None


def _looks_like_cached_provider_path(path: Path) -> bool:
    parts = _normalized_path_parts(path)
    return "cache" in parts or any(part.endswith("-cache") for part in parts)


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


if __name__ == "__main__":
    raise SystemExit(main())
