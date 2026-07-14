import importlib
import json
import re
import sys
from pathlib import Path


SKILL_NAME = "pb-to-csharp-migration-harness"
REQUIRED_SUPPORT_FILES = [
    "references/usage.md",
    "references/packaged-style-contract.md",
    "references/packaged-style-contract.json",
    "references/profile-update-workflow.md",
    "references/datawindow-layout-mapping.md",
    "references/sql-formatting-bridge.md",
    "references/migration-output-checklist.md",
    "examples/minimal-workflow.md",
    "scripts/smoke_check.py",
    "scripts/demo.py",
]
REMOVED_PRIVATE_PROFILE_FILES = [
    "references/" + "-".join(("author", "tagged", "style", "baseline")) + ".md",
    "references/" + "-".join(("author", "tagged", "program", "style", "profiles")) + ".json",
]
ORDINARY_RUNTIME_FILES = [
    "SKILL.md",
    "references/usage.md",
    "references/packaged-style-contract.md",
    "references/packaged-style-contract.json",
    "references/datawindow-layout-mapping.md",
    "references/sql-formatting-bridge.md",
    "references/migration-output-checklist.md",
    "examples/minimal-workflow.md",
]
SHIPPED_RUNTIME_SOURCE_FILES = [
    "src/skills/pb_to_csharp_migration.py",
]
GENERIC_PRIVATE_FINGERPRINT_PATTERNS = {
    "absolute_windows_path": re.compile(r"\b[A-Za-z]:\\"),
    "sha256_fingerprint": re.compile(r"\b[0-9A-Fa-f]{64}\b"),
    "replacement_character": re.compile("\ufffd"),
}
SYSTEM_DATABASE_NAMES = frozenset({"master", "model", "msdb", "tempdb"})
GENERIC_DATABASE_NAMES = frozenset({
    "database",
    "database_name",
    "dbname",
    "example_database",
    "exampledb",
    "placeholder_database",
    "placeholderdb",
    "sample_database",
    "sampledb",
    "synthetic_database",
    "syntheticdb",
    "test_database",
    "testdb",
})
NON_DATABASE_SCALAR_VALUES = frozenset({"false", "none", "null", "true"})
PUBLIC_NAMESPACE_ROOTS = frozenset({
    "amazon",
    "autofac",
    "azure",
    "communitytoolkit",
    "dapper",
    "devexpress",
    "documentformat",
    "fluentassertions",
    "google",
    "grpc",
    "hangfire",
    "humanizer",
    "microsoft",
    "moq",
    "mysql",
    "newtonsoft",
    "nlog",
    "npgsql",
    "nunit",
    "openai",
    "oracle",
    "polly",
    "quartz",
    "serilog",
    "sqlite",
    "system",
    "xunit",
})
GENERIC_NAMESPACE_ROOTS = frozenset({
    "examplemigration",
    "exampleproject",
    "genericmigration",
    "generatedmigration",
    "migrationexample",
    "placeholdermigration",
    "samplemigration",
    "sampleproject",
    "syntheticmigration",
    "syntheticproject",
    "yourcompany",
    "yournamespace",
})
SYNTHETIC_PLACEHOLDER_PATTERN = re.compile(r"<[^<>\r\n]+>")
SQL_IDENTIFIER_COMPONENT = r"(?:\[[^\]\r\n]+\]|<[^>\r\n]+>|[A-Za-z_][A-Za-z0-9_$#-]*)"
SQL_USE_DATABASE_PATTERN = re.compile(
    rf"^\s*USE\s+(?P<database>{SQL_IDENTIFIER_COMPONENT})\s*;?\s*(?:--[^\r\n]*)?$",
    re.IGNORECASE | re.MULTILINE,
)
DATABASE_VALUE_DECLARATION_PATTERN = re.compile(
    rf"""
    (?:
          \b(?:DATABASE(?:_?(?:NAME|ID))?|DB_?(?:NAME|ID))["']?
          \s*(?:=|:)\s*["']?
        | \bINITIAL\s+CATALOG\s*=\s*["']?
    )
    (?P<database>{SQL_IDENTIFIER_COMPONENT})
    """,
    re.IGNORECASE | re.VERBOSE,
)
BRACKETED_DATABASE_OBJECT_PATTERN = re.compile(
    r"(?<!\.)"
    r"(?P<object>\[[^\]\r\n]+\]\s*\.\s*\[[^\]\r\n]+\]\s*\.\s*\[[^\]\r\n]+\])"
    r"(?!\s*\.)",
    re.IGNORECASE,
)
SQL_DATABASE_OBJECT_PATTERN = re.compile(
    rf"""
    \b(?:FROM|JOIN|UPDATE|INTO|MERGE(?:\s+INTO)?|EXEC(?:UTE)?|DELETE\s+FROM)\s+
    (?P<object>{SQL_IDENTIFIER_COMPONENT}(?:\s*\.\s*{SQL_IDENTIFIER_COMPONENT}){{2,3}})
    """,
    re.IGNORECASE | re.VERBOSE,
)
NAMESPACE_DECLARATION_PATTERN = re.compile(
    r"^\s*(?:global\s+)?(?:"
    r"using\s+(?:static\s+)?(?:[A-Za-z_][A-Za-z0-9_]*\s*=\s*)?"
    r"|namespace\s+)"
    r"(?P<namespace>(?:global::)?[A-Za-z_][A-Za-z0-9_]*"
    r"(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*(?=;|\{|$)",
    re.IGNORECASE | re.MULTILINE,
)
PRODUCTION_PROGRAM_CORE = r"(?:[A-Z]{2}\d{6}|[A-Z]{2}\d{3}T)"
PRODUCTION_PROGRAM_IDENTIFIER_PATTERN = re.compile(
    rf"(?<![A-Z0-9]){PRODUCTION_PROGRAM_CORE}(?:_[A-Z][A-Z0-9]*)?(?![A-Z0-9])",
    re.IGNORECASE,
)
PRODUCTION_PROCEDURE_IDENTIFIER_PATTERN = re.compile(
    rf"(?<![A-Z0-9])(?:SP|USP)_{PRODUCTION_PROGRAM_CORE}(?:_[A-Z0-9]+)*(?![A-Z0-9])",
    re.IGNORECASE,
)
PRODUCTION_SOURCE_FILE_PATTERN = re.compile(
    rf"(?<![A-Za-z0-9_])"
    rf"(?:[A-Za-z0-9_.-]+[\\/])*"
    rf"{PRODUCTION_PROGRAM_CORE}(?:_[A-Z][A-Z0-9]*)?"
    rf"(?:\.Designer)?\.(?:cs|pbl|pbd|sql|srd|srm|sru|srw)\b",
    re.IGNORECASE,
)
PRODUCTION_SOURCE_DIRECTORY_PATTERN = re.compile(
    rf"(?<![A-Za-z0-9_])"
    rf"(?:[A-Za-z0-9_.-]+[\\/])*"
    rf"{PRODUCTION_PROGRAM_CORE}(?:_[A-Z][A-Z0-9]*)?(?=[\\/])",
    re.IGNORECASE,
)
NORMAL_GENERATION_DISCOVERY_TERMS = (
    "PblScripter",
    "ORCA",
    "source_sha256",
    "designer_sha256",
    "snapshot_date",
    "source_root",
)
REQUIRED_CONTRACT_KEYS = {
    "schema_version",
    "contract_id",
    "contract_version",
    "normal_generation",
    "rules",
    "designer_ownership",
    "style_families",
    "naming_grammar",
    "event_method_shapes",
    "control_fallback_order",
    "designer_properties",
    "grid_repository_conventions",
    "caller_parameter_rules",
    "stored_procedure_rules",
    "forbidden_patterns",
    "evidence_requirements",
}
REQUIRED_CSHARP_RULE_IDS = {
    "mapped_form_declaration",
    "designer_initialization",
    "migration_call_path",
    "ui_binding_or_result_mapping",
}
SYNTHETIC_MAPPED_CSHARP = """
public partial class CatalogBrowseForm : Form
{
    public CatalogBrowseForm() { InitializeComponent(); }
    private void CallSelectProcedure() { grdBrowse.DataSource = result; }
}
"""
SYNTHETIC_UNMAPPED_CSHARP = "public class UnmappedWidget {}"
SYNTHETIC_MISPLACED_STATIC_CSHARP = """
this.txtFilterText = new TextBox();
this.txtFilterText.Name = "txtFilterText";
this.grdBrowse.Columns.AddRange(this.colBrowse_ENTITY_ID);
this.colBrowse_ENTITY_ID.ColumnEdit = this.repEntity;
this.gvwBrowse.OptionsView.ShowGroupPanel = false;
"""
IMPLEMENTATION_TARGETS_PATTERN = re.compile(
    r"^## UAF implementation targets\s*(?P<body>.*?)(?:\n## |\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
BACKTICK_REF_PATTERN = re.compile(r"`([^`]+)`")


def find_repo_root(skill_dir: Path) -> Path | None:
    for candidate in [skill_dir, *skill_dir.parents]:
        if (candidate / "src").is_dir() and (candidate / "tests").is_dir():
            return candidate
    return None


def parse_implementation_targets(content: str) -> list[str]:
    match = IMPLEMENTATION_TARGETS_PATTERN.search(content)
    if not match:
        return []
    return BACKTICK_REF_PATTERN.findall(match.group("body"))


def resolve_target(repo_root: Path, ref: str) -> dict[str, str]:
    if "<" in ref or ">" in ref:
        return {"ref": ref, "status": "template"}
    if ref.startswith("skills/"):
        path = repo_root / ref
        return {"ref": ref, "status": "resolved" if path.exists() else "missing"}
    if ref == "tests":
        path = repo_root / "tests"
        return {"ref": ref, "status": "resolved" if path.is_dir() else "missing"}
    if not ref.startswith(("src.", "tests.")):
        return {"ref": ref, "status": "unsupported"}

    root_text = str(repo_root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    parts = ref.split(".")
    for index in range(len(parts), 0, -1):
        module_name = ".".join(parts[:index])
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name != module_name:
                return {"ref": ref, "status": "import_error", "detail": str(exc)}
            continue

        current = module
        for attr in parts[index:]:
            if not hasattr(current, attr):
                return {"ref": ref, "status": "missing_attribute", "detail": attr}
            current = getattr(current, attr)
        return {"ref": ref, "status": "resolved"}

    return {"ref": ref, "status": "missing"}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _default_runtime_privacy_patterns() -> dict[str, re.Pattern[str]]:
    concrete_example_names = (
        "".join(("CUST", "CD")),
        "".join(("ITEM", "CD")),
        "".join(("GIJUN", "DT")),
        "".join(("BAS", "YYYY")),
        "".join(("LAST", "DT")),
        "".join(("ORG", "DIV")),
        "".join(("CUST", "NM")),
        "".join(("ITEM", "NM")),
        "".join(("PRNT", "ITEM", "CD")),
    )
    return {
        **GENERIC_PRIVATE_FINGERPRINT_PATTERNS,
        "legacy_evidence_label": re.compile(
            r"\bauthor(?:[-_ ]+)tagged\b",
            re.IGNORECASE,
        ),
        "legacy_source_corpus_metric": re.compile(
            r"\b(?:primary|designer|source|author)[a-z0-9_]*"
            r"(?:pattern_counts|files_analyzed|baseline_counts)\b",
            re.IGNORECASE,
        ),
        "concrete_business_example_identifier": re.compile(
            r"\b(?:" + "|".join(re.escape(name) for name in concrete_example_names) + r")\b",
            re.IGNORECASE,
        ),
        "private_identity_assignment": re.compile(
            r"\b(?:profile_)?(?:author|owner|maintainer|account|username)\s*=\s*"
            r"[\"'][A-Z][A-Za-z]+(?:[- ][A-Z][A-Za-z]+)+[\"']",
            re.IGNORECASE,
        ),
    }


def _normalize_identifier(value: str) -> str:
    normalized = value.strip().strip("\"'")
    if normalized.startswith("[") and normalized.endswith("]"):
        normalized = normalized[1:-1].strip()
    return normalized


def _is_generic_database_name(value: str) -> bool:
    normalized = _normalize_identifier(value)
    return (
        SYNTHETIC_PLACEHOLDER_PATTERN.fullmatch(normalized) is not None
        or normalized.casefold() in SYSTEM_DATABASE_NAMES
        or normalized.casefold() in GENERIC_DATABASE_NAMES
        or normalized.casefold() in NON_DATABASE_SCALAR_VALUES
    )


def _qualified_identifier_parts(value: str) -> list[str]:
    return re.findall(SQL_IDENTIFIER_COMPONENT, value)


def _has_private_database_identifier(text: str) -> bool:
    declaration_patterns = (
        SQL_USE_DATABASE_PATTERN,
        DATABASE_VALUE_DECLARATION_PATTERN,
    )
    for pattern in declaration_patterns:
        for match in pattern.finditer(text):
            if not _is_generic_database_name(match.group("database")):
                return True

    object_matches = [
        *BRACKETED_DATABASE_OBJECT_PATTERN.finditer(text),
        *SQL_DATABASE_OBJECT_PATTERN.finditer(text),
    ]
    for match in object_matches:
        line_tail = text[match.end():text.find("\n", match.end())]
        if re.match(r"\s+import\b", line_tail, re.IGNORECASE):
            continue
        parts = _qualified_identifier_parts(match.group("object"))
        if len(parts) >= 3 and not _is_generic_database_name(parts[-3]):
            return True
    return False


def _has_private_company_namespace(text: str) -> bool:
    for match in NAMESPACE_DECLARATION_PATTERN.finditer(text):
        namespace = match.group("namespace").split("::", 1)[-1]
        root = namespace.split(".", 1)[0].casefold()
        if root not in PUBLIC_NAMESPACE_ROOTS and root not in GENERIC_NAMESPACE_ROOTS:
            return True
    return False


def _mask_spans(text: str, spans: list[tuple[int, int]]) -> str:
    masked = list(text)
    for start, end in spans:
        for index in range(start, end):
            if masked[index] not in "\r\n":
                masked[index] = " "
    return "".join(masked)


def _structural_privacy_issue_codes(text: str) -> list[str]:
    issue_codes: list[str] = []
    if _has_private_database_identifier(text):
        issue_codes.append("private_database_identifier")
    if _has_private_company_namespace(text):
        issue_codes.append("private_company_namespace")

    source_matches = [
        *PRODUCTION_SOURCE_FILE_PATTERN.finditer(text),
        *PRODUCTION_SOURCE_DIRECTORY_PATTERN.finditer(text),
    ]
    procedure_matches = list(PRODUCTION_PROCEDURE_IDENTIFIER_PATTERN.finditer(text))
    if source_matches:
        issue_codes.append("production_source_identifier")
    if procedure_matches:
        issue_codes.append("production_procedure_identifier")

    # Package docs define angle-bracket placeholders; production-shaped values
    # stay private even when a caller labels them synthetic.
    masked = _mask_spans(
        text,
        [match.span() for match in [*source_matches, *procedure_matches]],
    )
    if PRODUCTION_PROGRAM_IDENTIFIER_PATTERN.search(masked):
        issue_codes.append("production_program_identifier")
    return issue_codes


def collect_privacy_scan_paths(skill_dir: Path, repo_root: Path) -> list[tuple[str, Path]]:
    package_labels = ["SKILL.md", *REQUIRED_SUPPORT_FILES]
    collected = [(label, skill_dir / label) for label in package_labels]
    collected.extend((label, repo_root / label) for label in SHIPPED_RUNTIME_SOURCE_FILES)
    return collected


def scan_private_runtime_fingerprints(
    text: str,
    path: str = "src/skills/pb_to_csharp_migration.py",
    *,
    injected_patterns: dict[str, re.Pattern[str]] | None = None,
) -> list[dict[str, str]]:
    patterns = _default_runtime_privacy_patterns()
    patterns.update(injected_patterns or {})
    issue_codes = [
        code
        for code, pattern in patterns.items()
        if pattern.search(text)
    ]
    issue_codes.extend(_structural_privacy_issue_codes(text))
    return [
        {"code": code, "path": path}
        for code in dict.fromkeys(issue_codes)
    ]


def validate_csharp_contract_rules(contract: dict[str, object]) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    rules = contract.get("rules", {})
    csharp = rules.get("csharp", {}) if isinstance(rules, dict) else {}
    required_patterns = csharp.get("required_patterns", []) if isinstance(csharp, dict) else []
    if not isinstance(required_patterns, list):
        return [{"code": "csharp_required_patterns_invalid"}]

    rule_ids: set[str] = set()
    compiled: list[tuple[str, re.Pattern[str]]] = []
    for item in required_patterns:
        if not isinstance(item, dict):
            issues.append({"code": "csharp_required_pattern_invalid"})
            continue
        rule_id = str(item.get("id") or "")
        pattern = str(item.get("pattern") or "")
        if not rule_id or not pattern:
            issues.append({"code": "csharp_required_pattern_incomplete", "rule_id": rule_id})
            continue
        rule_ids.add(rule_id)
        try:
            compiled.append((rule_id, re.compile(pattern, re.IGNORECASE | re.MULTILINE)))
        except re.error as exc:
            issues.append({
                "code": "csharp_required_pattern_regex_invalid",
                "rule_id": rule_id,
                "detail": str(exc),
            })

    missing_rule_ids = sorted(REQUIRED_CSHARP_RULE_IDS - rule_ids)
    if missing_rule_ids:
        issues.append({"code": "csharp_required_rule_ids_missing", "rule_ids": missing_rule_ids})

    for rule_id, pattern in compiled:
        if not pattern.search(SYNTHETIC_MAPPED_CSHARP):
            issues.append({"code": "mapped_csharp_rule_not_matched", "rule_id": rule_id})
        if pattern.search("") or pattern.search(SYNTHETIC_UNMAPPED_CSHARP):
            issues.append({"code": "unmapped_csharp_rule_too_permissive", "rule_id": rule_id})
    return issues


def validate_designer_ownership_contract(contract: dict[str, object]) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    ownership = contract.get("designer_ownership", {})
    if not isinstance(ownership, dict):
        return [{"code": "designer_ownership_invalid"}]
    if ownership.get("default_owner") != ".Designer.cs":
        issues.append({"code": "designer_default_owner_changed"})
    if not ownership.get("designer_file_owns") or not ownership.get("code_behind_owns"):
        issues.append({"code": "designer_ownership_responsibilities_missing"})
    dynamic_exception = ownership.get("dynamic_state_exception", {})
    if not isinstance(dynamic_exception, dict) or dynamic_exception.get("default") != "blocked":
        issues.append({"code": "dynamic_state_exception_not_fail_closed"})

    patterns = ownership.get("code_behind_static_ui_patterns", [])
    if not isinstance(patterns, list) or not patterns:
        return issues + [{"code": "code_behind_static_ui_patterns_missing"}]
    for item in patterns:
        if not isinstance(item, dict) or not item.get("id") or not item.get("pattern"):
            issues.append({"code": "code_behind_static_ui_pattern_invalid"})
            continue
        rule_id = str(item["id"])
        try:
            pattern = re.compile(str(item["pattern"]), re.IGNORECASE | re.MULTILINE)
        except re.error as exc:
            issues.append({
                "code": "code_behind_static_ui_regex_invalid",
                "rule_id": rule_id,
                "detail": str(exc),
            })
            continue
        if pattern.search(SYNTHETIC_MAPPED_CSHARP):
            issues.append({"code": "runtime_behavior_false_positive", "rule_id": rule_id})
        if not pattern.search(SYNTHETIC_MISPLACED_STATIC_CSHARP):
            issues.append({"code": "misplaced_static_ui_not_detected", "rule_id": rule_id})
    return issues


def main() -> int:
    skill_dir = Path(__file__).resolve().parents[1]
    repo_root = find_repo_root(skill_dir)
    skill_md = skill_dir / "SKILL.md"
    issues: list[dict[str, object]] = []
    target_results: list[dict[str, str]] = []

    content = _read_text(skill_md) if skill_md.exists() else ""
    if not content:
        issues.append({"code": "missing_skill_md", "path": "SKILL.md"})

    for rel_path in REQUIRED_SUPPORT_FILES:
        path = skill_dir / rel_path
        if not path.exists():
            issues.append({"code": "missing_support_file", "path": rel_path})
        elif rel_path not in content:
            issues.append({"code": "support_file_not_referenced", "path": rel_path})

    for rel_path in REMOVED_PRIVATE_PROFILE_FILES:
        if (skill_dir / rel_path).exists():
            issues.append({"code": "private_profile_still_packaged", "path": rel_path})

    contract_path = skill_dir / "references" / "packaged-style-contract.json"
    try:
        contract = json.loads(_read_text(contract_path))
    except (OSError, json.JSONDecodeError) as exc:
        contract = {}
        issues.append({"code": "invalid_packaged_contract", "detail": str(exc)})

    missing_contract_keys = sorted(REQUIRED_CONTRACT_KEYS - set(contract))
    if missing_contract_keys:
        issues.append({"code": "missing_contract_keys", "keys": missing_contract_keys})

    normal_generation = contract.get("normal_generation", {})
    if normal_generation.get("profile_source") != "packaged-only":
        issues.append({"code": "normal_generation_not_packaged_only"})
    if normal_generation.get("external_discovery_allowed") is not False:
        issues.append({"code": "normal_generation_discovery_not_disabled"})
    if normal_generation.get("profile_update_runs_during_normal_generation") is not False:
        issues.append({"code": "profile_update_not_isolated"})
    control_fallback_order = contract.get("control_fallback_order")
    if (
        not isinstance(control_fallback_order, list)
        or len(control_fallback_order) != 4
        or control_fallback_order[0] != "target-wrapper"
        or not isinstance(control_fallback_order[1], str)
        or not control_fallback_order[1].strip()
        or control_fallback_order[2:] != ["devexpress", "winforms"]
        or len(set(control_fallback_order)) != len(control_fallback_order)
    ):
        issues.append({"code": "control_fallback_order_changed"})
    issues.extend(validate_csharp_contract_rules(contract))
    issues.extend(validate_designer_ownership_contract(contract))

    privacy_scan_paths: list[tuple[str, Path]] = []
    if repo_root is None:
        issues.append({"code": "runtime_privacy_repo_root_not_found"})
    else:
        privacy_scan_paths = collect_privacy_scan_paths(skill_dir, repo_root)

    privacy_files_checked: list[str] = []
    for rel_path, path in privacy_scan_paths:
        if not path.is_file():
            issues.append({"code": "privacy_scan_file_missing", "path": rel_path})
            continue
        privacy_files_checked.append(rel_path)
        issues.extend(scan_private_runtime_fingerprints(_read_text(path), rel_path))

    for rel_path in ORDINARY_RUNTIME_FILES:
        text = _read_text(skill_dir / rel_path)
        for term in NORMAL_GENERATION_DISCOVERY_TERMS:
            if term in text:
                issues.append({
                    "code": "discovery_term_in_normal_runtime_doc",
                    "path": rel_path,
                    "term": term,
                })

    update_text = _read_text(skill_dir / "references" / "profile-update-workflow.md")
    for marker in (
        "never runs during normal generation",
        "PblScripter",
        "ORCA",
        "database",
        "scan",
        "Sanitization Gate",
    ):
        if marker not in update_text:
            issues.append({"code": "profile_update_marker_missing", "marker": marker})

    targets = parse_implementation_targets(content)
    if not targets:
        issues.append({"code": "missing_implementation_targets", "path": "SKILL.md"})

    if repo_root is not None:
        for target in targets:
            result = resolve_target(repo_root, target)
            target_results.append(result)
            if result["status"] not in {"resolved", "template"}:
                issues.append({
                    "code": "unresolved_implementation_target",
                    "path": "SKILL.md",
                    "target": target,
                    "status": result["status"],
                })
    else:
        target_results = [
            {"ref": target, "status": "repo_root_not_found"} for target in targets
        ]

    result = {
        "schema_version": "1.0",
        "skill": SKILL_NAME,
        "success": not issues,
        "status": "passed" if not issues else "failed",
        "execution_level": "python-module",
        "contract_id": contract.get("contract_id", ""),
        "contract_version": contract.get("contract_version", ""),
        "support_files": REQUIRED_SUPPORT_FILES,
        "implementation_targets": target_results,
        "privacy_files": privacy_files_checked,
        "privacy_files_checked": len(privacy_files_checked),
        "privacy_files_expected": len(privacy_scan_paths),
        "issues": issues,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
