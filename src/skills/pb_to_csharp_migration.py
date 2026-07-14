import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping
from xml.sax.saxutils import escape

from src.contracts import HarnessResult


_PB_MIGRATION_REFERENCE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "pb_to_csharp_migration_harness"
    / "references"
)
PACKAGED_MIGRATION_PROFILE_PATH = _PB_MIGRATION_REFERENCE_ROOT / "packaged-style-contract.json"


DATAWINDOW_COLUMN_PATTERN = re.compile(r"column\s*=\s*\(", re.IGNORECASE)
DATAWINDOW_VISUAL_COLUMN_PATTERN = re.compile(r"^\s*column\s*\(", re.IGNORECASE)
DATAWINDOW_TEXT_PATTERN = re.compile(r"^\s*text\s*\(", re.IGNORECASE)
DATAWINDOW_NAME_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])name\s*=\s*\"?(?P<name>[a-zA-Z0-9_#$]+)\"?",
    re.IGNORECASE,
)
DATAWINDOW_ATTRIBUTE_PATTERN = re.compile(
    r"(?P<key>[A-Za-z0-9_.#]+)\s*=\s*(?:\"(?P<quoted>[^\"]*)\"|(?P<bare>[^\s)]+))",
    re.IGNORECASE,
)
CSHARP_NEW_CONTROL_PATTERN = re.compile(
    r"^\s*this\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*new\s+(?P<type>[A-Za-z0-9_.]+)\s*\(",
    re.MULTILINE,
)
CSHARP_FIELD_DECLARATION_PATTERN = re.compile(
    r"^\s*private\s+(?P<type>[A-Za-z0-9_.<>]+)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*;",
    re.MULTILINE,
)
CSHARP_PROPERTY_ASSIGNMENT_PATTERN = re.compile(
    r"^\s*this\.(?P<control>[A-Za-z_][A-Za-z0-9_]*)\.(?P<property>[A-Za-z_][A-Za-z0-9_.]*)\s*=\s*(?P<value>.*?);\s*$"
)
CSHARP_CONTROLS_ADD_PATTERN = re.compile(
    r"^\s*this(?:\.(?P<parent>[A-Za-z_][A-Za-z0-9_]*))?\.Controls\.Add\(this\.(?P<child>[A-Za-z_][A-Za-z0-9_]*)\);\s*$"
)
CSHARP_COLLECTION_ADD_RANGE_START_PATTERN = re.compile(
    r"^\s*this\.(?P<control>[A-Za-z_][A-Za-z0-9_]*)\.(?P<method>[A-Za-z_][A-Za-z0-9_.]*AddRange)\s*\("
)
CSHARP_THIS_REFERENCE_PATTERN = re.compile(r"this\.([A-Za-z_][A-Za-z0-9_]*)")

NUMERIC_GRID_FIELD_TOKENS = ("AMT", "QTY", "UNP", "WGT", "PRICE", "RATE", "COST", "TOTAL")
NUMERIC_GRID_FIELD_SUFFIXES = ("TOT", "BAL")
PB_MIGRATION_ANALYSIS_SECTION_RULES = {
    "objective_and_operator": (
        r"\bobjective\b",
        r"\btarget\s+operator\b",
        r"\ubaa9\uc801",
        r"\ub300\uc0c1",
        r"\uc6b4\uc601\uc790",
    ),
    "source_evidence": (
        r"\bPBL\b",
        r"\bSRU\b",
        r"\bSRW\b",
        r"\bSRD\b",
        r"\bDataWindow\b",
        r"PB\s*\uc6d0\ubcf8",
        r"\uc18c\uc2a4",
    ),
    "user_workflow": (
        r"\uc0ac\uc6a9\uc790\s*\ub3d9\uc791",
        r"\uc5c5\ubb34\s*\ud750\ub984",
        r"\ucc98\ub9ac\s*\ud750\ub984",
        r"\bevent\b",
        r"\bworkflow\b",
    ),
    "csharp_scope": (
        r"C#\s*\uac1c\ubc1c\s*\ubc94\uc704",
        r"C#\s*\uad6c\ud604",
        r"\uad6c\ud604\s*\ubc94\uc704",
        r"target\s+C#",
    ),
    "event_and_call_flow": (
        r"\ubc84\ud2bc",
        r"\uc774\ubca4\ud2b8",
        r"\ucc98\ub9ac\s*\uc21c\uc11c",
        r"\bhandler\b",
        r"\bclick\b",
    ),
    "db_sp_mapping": (
        r"DB\s*\ucc98\ub9ac",
        r"\bSP\b",
        r"\bprocedure\b",
        r"\bSELECT\b",
        r"\bSAVE\b",
        r"\bINSERT\b",
        r"\bUPDATE\b",
        r"\bDELETE\b",
    ),
    "transaction_and_error": (
        r"\ud2b8\ub79c\uc7ad\uc158",
        r"\btransaction\b",
        r"\brollback\b",
        r"\bRAISERROR\b",
        r"\uc624\ub958",
        r"\uac80\uc99d",
    ),
    "implementation_order": (
        r"\uad6c\ud604\s*\uc21c\uc11c",
        r"\uac1c\ubc1c\s*\uc21c\uc11c",
        r"\uc791\uc5c5\s*\uc21c\uc11c",
        r"implementation\s*order",
    ),
    "constraints_and_business_rules": (
        r"\uc8fc\uc758\uc810",
        r"\uc81c\uc57d",
        r"\uc5c5\ubb34\s*\uaddc\uce59",
        r"\ud544\uc218",
        r"\bconstraints?\b",
        r"\bbusiness\s+rules?\b",
        r"\brequired\b",
        r"\binvariant\b",
    ),
    "manual_tests": (
        r"\uc218\ub3d9\s*\ud14c\uc2a4\ud2b8",
        r"\ud14c\uc2a4\ud2b8\s*\uc2dc\ub098\ub9ac\uc624",
        r"verification",
        r"\uac80\uc99d\s*\uacc4\ud68d",
    ),
    "llm_handoff": (
        r"LLM\s*\uad6c\ud604\s*\uc694\uccad",
        r"handoff",
        r"\uc694\uc57d",
        r"\uc804\ub2ec",
    ),
}
PB_MIGRATION_ANALYSIS_EVIDENCE_ANCHORS = {
    "source_artifact_evidence": (
        r"\bPBL\b",
        r"\bPBD\b",
        r"\bSRU\b",
        r"\bSRW\b",
        r"\bSRD\b",
        r"\bDataWindow\b",
        r"\bORCA\b",
        r"\bPblScripter\b",
        r"\bpowerscript\b",
    ),
    "target_csharp_evidence": (
        r"\bC#\b",
        r"\bWinForms\b",
        r"\bDevExpress\b",
        r"\bDesigner\b",
        r"\bGridColumn\b",
        r"\bBindingField\b",
        r"\bDbParameter\b",
        r"\bCallProc\b",
        r"\bCallViewQuery\b",
        r"\bCallSelectProcedure\b",
    ),
    "db_sp_contract_evidence": (
        r"\bSP\b",
        r"\bprocedure\b",
        r"\bSELECT\b",
        r"\bSAVE\b",
        r"\bINSERT\b",
        r"\bUPDATE\b",
        r"\bDELETE\b",
        r"@WORKTYPE\b",
        r"\btransaction\b",
        r"\bRAISERROR\b",
    ),
    "implementation_decision_evidence": (
        r"\uad6c\ud604\s*\uc21c\uc11c",
        r"\uac1c\ubc1c\s*\uc21c\uc11c",
        r"\bimplementation\b",
        r"\bhandoff\b",
        r"LLM",
    ),
    "verification_evidence": (
        r"\uc218\ub3d9\s*\ud14c\uc2a4\ud2b8",
        r"\ud14c\uc2a4\ud2b8\s*\uc2dc\ub098\ub9ac\uc624",
        r"\uac80\uc99d",
        r"\bverification\b",
        r"\bbuild\b",
    ),
}
PB_MIGRATION_ANALYSIS_READINESS_RULES = {
    "source_trace_ready": ("source_evidence", "event_and_call_flow", "source_artifact_evidence"),
    "target_csharp_ready": ("csharp_scope", "target_csharp_evidence"),
    "db_sp_ready": ("db_sp_mapping", "db_sp_contract_evidence"),
    "implementation_ready": ("implementation_order", "llm_handoff", "implementation_decision_evidence"),
    "verification_ready": ("transaction_and_error", "manual_tests", "verification_evidence"),
}
PB_MIGRATION_DEVELOPMENT_SPEC_RULES = {
    "cross_agent_handoff_contract": (
        r"\banalysis\s+agent\b",
        r"\bdeveloper\s+agent\b",
        r"\bdevelopment\s+handoff\b",
        r"\bimplementation\s+handoff\b",
        r"\ubd84\uc11d\s*\ub2f4\ub2f9",
        r"\uac1c\ubc1c\s*\ub2f4\ub2f9",
        r"\uc11c\ube0c\uc5d0\uc774\uc804\ud2b8",
    ),
    "target_file_plan": (
        r"\btarget\s+file\b",
        r"\bfile\s+plan\b",
        r"\bDesigner\.cs\b",
        r"\b\.cs\b",
        r"\bprocedure\b",
        r"\ud30c\uc77c\s*\uacc4\ud68d",
    ),
    "user_directive_scope_contract": (
        r"\buser\s+directive\b",
        r"\bapproved\s+scope\b",
        r"\bexplicit\s+approval\b",
        r"\bout[-\s]?of[-\s]?scope\b",
        r"\bproposal[-\s]?only\b",
        r"\bdo\s+not\s+implement\b",
        r"\uc0ac\uc6a9\uc790\s*\uc9c0\uc2dc",
        r"\uc2b9\uc778\s*\ubc94\uc704",
        r"\uc81c\uc548\s*\uc804\uc6a9",
    ),
    "pb_to_csharp_event_mapping": (
        r"\bPB\s+event\b",
        r"\bC#\s+(?:method|handler|event)\b",
        r"\bevent\s+mapping\b",
        r"\bhandler\b",
        r"\ub9e4\ud551",
        r"\uc774\ubca4\ud2b8",
    ),
    "datawindow_field_mapping": (
        r"\bDataWindow\b",
        r"\bPB\s+(?:column|field)\b",
        r"\bGridColumn\b",
        r"\bBindingField\b",
        r"\bCaption\b",
        r"\ud544\ub4dc\s*\ub9e4\ud551",
    ),
    "control_layout_binding_plan": (
        r"\bcontrol\b",
        r"\bTabIndex\b",
        r"\bBindingField\b",
        r"\bLabelControl\b",
        r"\bGridView\b",
        r"\ucee8\ud2b8\ub864",
    ),
    "sp_contract_matrix": (
        r"\bSP\s+contract\b",
        r"\bprocedure\s+contract\b",
        r"@WORKTYPE\b",
        r"\bparameter\b",
        r"\bresult\s+column\b",
        r"\bDML\b",
    ),
    "style_profile_contract": (
        r"\bpackaged\s+style\b",
        r"\breviewed\s+profile\b",
        r"\bprogram\s+key\b",
        r"\bstyle\s+profile\b",
        r"\bfallback\s+program\b",
        r"\bsource\s+hash\b",
        r"\uc2a4\ud0c0\uc77c\s*\uae30\uc900",
    ),
    "implementation_task_breakdown": (
        r"\bimplementation\s+task\b",
        r"\btask\s+list\b",
        r"\bdone\s+criteria\b",
        r"\bacceptance\b",
        r"\uad6c\ud604\s*\uc791\uc5c5",
        r"\uc644\ub8cc\s*\uae30\uc900",
    ),
    "verification_contract": (
        r"\bmanual\s+test\b",
        r"\bexpected\s+UI\b",
        r"\bexpected\s+DB\b",
        r"\bbuild\b",
        r"\brollback\b",
        r"\uac80\uc99d\s*\uacc4\uc57d",
    ),
    "confirmed_inferred_blocked_split": (
        r"\bconfirmed\b",
        r"\binferred\b",
        r"\bblocked\b",
        r"\bassumption\b",
        r"\ud655\uc815",
        r"\ucd94\uc815",
        r"\ucc28\ub2e8",
    ),
}
SP_METADATA_HEADER_PATTERN = re.compile(
    r"^\s*--\s*=+\s*\r?\n"
    r"--\s*AUTHOR\s*:\s*.*\r?\n"
    r"--\s*CREATE\s+DATE\s*:\s*\d{4}-\d{2}-\d{2}\s*\r?\n"
    r"--\s*DESCRIPTION\s*:\s*(?P<description>\S.*)\r?\n"
    r"--\s*=+\s*\r?\n"
    r"\s*(?:CREATE\s+(?:OR\s+ALTER\s+)?|ALTER\s+)PROCEDURE\b",
    re.IGNORECASE,
)
SP_PROCEDURE_NAME_PATTERN = re.compile(
    r"\b(?:CREATE\s+(?:OR\s+ALTER\s+)?|ALTER\s+)PROCEDURE\s+"
    r"(?:\[[^\]]+\]|\w+)?\s*\.?\s*(?:\[(?P<bracketed>U?SP_[A-Z0-9_]+)\]|(?P<plain>U?SP_[A-Z0-9_]+))",
    re.IGNORECASE,
)

AUTHOR_TAGGED_CSHARP_STYLE_BASELINE: Dict[str, Any] = {
    "source": "packaged_sanitized_profile",
    "baseline_exclusions": {
        "MIGRATIONTARGET": "active migration targets cannot seed their own style evidence",
    },
    "positive_generation_recipe": {
        "source_priority": [
            "verified stored-procedure definition",
            "normalized program key from procedure name",
            "same-program primary C# file",
            "same-program Designer file",
            "same-module neighbor only when the active program is excluded or unmapped",
        ],
        "screen_base": {
            "normal_screen": "FrmDevBase",
            "popup_screen": "FrmPopBase",
            "evidence": "use only the immutable packaged profile or explicit reviewed evidence",
        },
        "command_flow": [
            "keep SearchCommand, SaveCommand, and ClearCommand override/event flow when the matched source has it",
            "keep existing local event names and do not invent generic wrapper methods",
            "use focused-row events directly for detail refresh instead of generated CallDetailQuery helpers",
        ],
        "select_flow": [
            "prefer the matched source's CallSelectProcedure or CallViewQuery shape",
            "keep dbClient.GetDataSetFromSP calls local to the procedure-call method",
            "pass explicit new DbParameter entries near the stored-procedure call",
            "pass raw control or focused-row values; let the stored procedure own wildcard and derived-date handling",
        ],
        "save_flow": [
            "serialize changed grid/table data with DataUtil.DataTableToXml when the matched source family does it",
            "use dbClient.ExecSPTrn for transactional saves and dbClient.ExecSP only when the matched source proves that local path",
            "do not create DTO/request/context objects for ordinary save or retrieve parameters",
        ],
        "focused_row_detail_flow": [
            "use gvw*.GetFocusedDataRow() and direct dr[\"FIELD\"].ToString() style when matched evidence supports focused detail refresh",
            "use target-evidenced grid reset helpers instead of inventing a new reset path",
            "avoid DBNull ternary wrappers, null-coalesced wildcard defaults, and generated value helper methods",
        ],
        "designer_flow": [
            "use target custom controls before generic DevExpress controls",
            "when DevExpress is present, use the target project's referenced DevExpress version and existing API surface; do not generate code from the latest DevExpress API by default",
            "declare explicit GridColumn fields named colList_FIELD, colDetail_FIELD, colTABLE_FIELD, or colPURPOSE_FIELD",
            "register columns with Columns.AddRange",
            "preserve BindingField, TabIndex, containment, size, location, and Properties assignments when Designer evidence exists",
            "set header UseFont plus horizontal and vertical center alignment where target columns use them",
            "set cell UseFont where target columns use it",
            "use RepositoryItemSpinEdit through ColumnEdit for numeric grid columns instead of DisplayFormat-only output",
        ],
        "sp_flow": [
            "keep the metadata header immediately above CREATE/ALTER PROCEDURE",
            "preserve procedure names, parameter names, Korean literals, comments, aliases, predicates, calculations, and row contracts",
            "do not add defensive parameter defaults or normalization blocks unless same-procedure evidence proves them",
            "do not invent SELECT TOP 0 schema-only branches, CTEs, #temp tables, MERGE, or NOT EXISTS by default",
        ],
        "evidence_discipline": [
            "do not claim PB behavior parity from generated C# alone",
            "do not upgrade, re-target, or assume newer third-party libraries such as DevExpress; use target project references or mark the dependency contract blocked",
            "mark source-unverified behavior as inferred draft unless PB, pasted source, matched C#, DB schema, or explicit user approval proves it",
            "reading a reference file is not runtime use; require verifier, module, artifact, or blocked/passthrough evidence",
        ],
    },
}

AUTHOR_TAGGED_PROGRAM_CSHARP_MAPPINGS: Dict[str, List[str]] = {
    "GENERALIZED": [
        r"packaged\style\GENERALIZED.cs",
        r"packaged\style\GENERALIZED.Designer.cs",
    ],
    "REFERENCESCREEN": [
        r"packaged\style\ReferenceScreen.cs",
        r"packaged\style\ReferenceScreen.Designer.cs",
    ],
}


def _canonical_profile_payload(profile: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "profile_id": str(profile.get("profile_id") or "").strip(),
        "version": str(profile.get("version") or profile.get("profile_version") or "").strip(),
        "sanitized": bool(profile.get("sanitized")),
        "rules": dict(profile.get("rules") or {}),
    }


def _compute_packaged_profile_hash(profile: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        _canonical_profile_payload(profile),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _profile_rules_hash(rules: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        dict(rules),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _profile_consumption_token(
    profile_id: str,
    profile_version: str,
    profile_hash: str,
    rules_hash: str,
) -> str:
    identity = "\n".join((profile_id, profile_version, profile_hash, rules_hash))
    return "sha256:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _identifier_template_pattern(template: str) -> str:
    value = str(template or "").strip()
    if not value or re.search(r"[^A-Za-z0-9_<>]", value):
        return ""
    chunks: List[str] = []
    cursor = 0
    for match in re.finditer(r"(?:<[A-Za-z][A-Za-z0-9]*>)+", value):
        chunks.append(re.escape(value[cursor : match.start()]))
        chunks.append(r"[A-Za-z][A-Za-z0-9]*")
        cursor = match.end()
    chunks.append(re.escape(value[cursor:]))
    return "".join(chunks) if cursor else ""


def _profile_method_names(value: Any) -> List[str]:
    candidates = value if isinstance(value, list) else [value]
    return [
        str(item)
        for item in candidates
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(item or ""))
    ]


def _generalized_contract_profile_entry(
    payload: Mapping[str, Any],
    raw_bytes: bytes,
) -> Dict[str, Any] | None:
    contract_id = str(payload.get("contract_id") or "").strip()
    contract_version = str(payload.get("contract_version") or "").strip()
    normal_generation = payload.get("normal_generation")
    naming_grammar = payload.get("naming_grammar")
    event_shapes = payload.get("event_method_shapes")
    designer_properties = payload.get("designer_properties")
    grid_repository_conventions = payload.get("grid_repository_conventions")
    stored_procedure_rules = payload.get("stored_procedure_rules")
    packaged_rule_groups = payload.get("rules")
    packaged_csharp_rules = (
        packaged_rule_groups.get("csharp")
        if isinstance(packaged_rule_groups, Mapping)
        else None
    )
    if (
        payload.get("schema_version") != 2
        or not contract_id
        or not contract_version
        or not isinstance(normal_generation, Mapping)
        or not isinstance(naming_grammar, Mapping)
        or not isinstance(event_shapes, Mapping)
        or not isinstance(designer_properties, list)
        or not designer_properties
        or not isinstance(grid_repository_conventions, Mapping)
        or not isinstance(stored_procedure_rules, Mapping)
        or not isinstance(packaged_csharp_rules, Mapping)
    ):
        return None
    sanitized = bool(
        normal_generation.get("profile_source") == "packaged-only"
        and normal_generation.get("external_discovery_allowed") is False
        and normal_generation.get("profile_update_runs_during_normal_generation") is False
    )
    form_template = str(naming_grammar.get("form") or "").strip()
    load_handler_template = str(naming_grammar.get("load_handler") or "").strip()
    focus_handler_template = str(naming_grammar.get("focus_handler") or "").strip()
    form_identifier_pattern = _identifier_template_pattern(form_template)
    load_identifier_pattern = _identifier_template_pattern(load_handler_template)
    focus_identifier_pattern = _identifier_template_pattern(focus_handler_template)
    query_methods = _profile_method_names(naming_grammar.get("query_method"))
    save_methods = _profile_method_names(naming_grammar.get("save_method"))
    command_handlers = _profile_method_names(event_shapes.get("command_handlers"))
    procedure_template = str(naming_grammar.get("procedure") or "").strip()
    if (
        not sanitized
        or not form_identifier_pattern
        or not load_identifier_pattern
        or not focus_identifier_pattern
        or not query_methods
        or not save_methods
        or not command_handlers
        or not procedure_template
    ):
        return None

    artifact_hash = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
    return {
        "profile_id": contract_id,
        "version": contract_version,
        "sanitized": sanitized,
        "profile_hash": artifact_hash,
        "hash_mode": "artifact_sha256",
        "artifact_hash": artifact_hash,
        "rules": {
            "csharp": {
                "required_patterns": _normalized_profile_patterns(
                    packaged_csharp_rules.get("required_patterns")
                ),
                "forbidden_patterns": _normalized_profile_patterns(
                    packaged_csharp_rules.get("forbidden_patterns")
                ),
                "form_contract": {
                    "form_template": form_template,
                    "form_identifier_pattern": form_identifier_pattern,
                    "load_handler_template": load_handler_template,
                    "query_methods": query_methods,
                    "save_methods": save_methods,
                    "focus_handler_template": focus_handler_template,
                    "command_handlers": command_handlers,
                    "requested_mapping_required": True,
                },
                "designer_contract": {
                    "properties": [str(item) for item in designer_properties if str(item)],
                    "grid_repository_conventions": dict(grid_repository_conventions),
                    "static_ui_requires_designer": True,
                    "runtime_dynamic_evidence_required": True,
                },
            },
            "sql": {
                "allowed_procedure_patterns": [
                    r"^U?SP_[A-Z][A-Z0-9_]*_(?:SELECT|SAVE|SELECT_SAVE)$"
                ],
                "forbidden_patterns": [
                    {"id": "temporary_table", "pattern": r"#[A-Za-z][A-Za-z0-9_]*"},
                    {"id": "merge", "pattern": r"\bMERGE\b"},
                    {"id": "not_exists", "pattern": r"\bNOT\s+EXISTS\b"},
                ],
            },
        },
    }


def _profile_load_result(
    *,
    success: bool,
    profile_id: str,
    profile_version: str,
    profile_hash: str,
    issues: List[Dict[str, Any]],
    profile_path: str = "",
    rules: Mapping[str, Any] | None = None,
) -> HarnessResult:
    normalized_rules = dict(rules or {})
    rules_hash = _profile_rules_hash(normalized_rules) if success else ""
    consumption = {
        "status": "loaded" if success else "blocked",
        "consumed": False,
        "source": "packaged_sanitized_profile",
        "profile_id": profile_id,
        "profile_version": profile_version,
        "profile_hash": profile_hash,
        "sanitized": success,
        "profile_hash_verified": success,
        "profile_rules_hash": rules_hash,
        "consumption_token": (
            _profile_consumption_token(
                profile_id,
                profile_version,
                profile_hash,
                rules_hash,
            )
            if success
            else ""
        ),
        "applied_rule_groups": [],
    }
    metadata = {
        "harness": "pb-to-csharp-migration-harness",
        "operation": "load_packaged_migration_profile",
        "status": "loaded" if success else "blocked",
        "profile_path": profile_path,
        "profile_rules": normalized_rules,
        "profile_consumption": consumption,
        "issues": issues,
        "external_sources_consulted": [],
        "token_optimizer_status": "passthrough",
    }
    return HarnessResult(
        success=success,
        stdout=json.dumps(
            {
                "status": metadata["status"],
                "profile_id": profile_id,
                "profile_version": profile_version,
                "profile_hash": profile_hash,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        stderr="" if success else "Packaged migration profile identity validation failed.",
        exit_code=0 if success else 1,
        metadata=metadata,
    )


def load_packaged_migration_profile(
    profile_id: str,
    profile_version: str,
    profile_hash: str,
) -> HarnessResult:
    """Load one sanitized packaged profile by exact immutable identity."""
    requested_id = str(profile_id or "").strip()
    requested_version = str(profile_version or "").strip()
    requested_hash = str(profile_hash or "").strip().lower()
    if not requested_id or not requested_version or not requested_hash:
        return _profile_load_result(
            success=False,
            profile_id=requested_id,
            profile_version=requested_version,
            profile_hash=requested_hash,
            issues=[
                {
                    "code": "packaged_profile_identity_required",
                    "severity": "error",
                    "message": "profile_id, profile_version, and profile_hash are all required.",
                }
            ],
        )

    path = Path(PACKAGED_MIGRATION_PROFILE_PATH)
    if not path.is_file():
        return _profile_load_result(
            success=False,
            profile_id=requested_id,
            profile_version=requested_version,
            profile_hash=requested_hash,
            issues=[
                {
                    "code": "packaged_profile_document_missing",
                    "severity": "error",
                    "message": "The generalized packaged style contract is missing.",
                    "path": str(path),
                }
            ],
        )
    try:
        raw_bytes = path.read_bytes()
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _profile_load_result(
            success=False,
            profile_id=requested_id,
            profile_version=requested_version,
            profile_hash=requested_hash,
            issues=[
                {
                    "code": "packaged_profile_document_invalid",
                    "severity": "error",
                    "message": str(exc),
                    "path": str(path),
                }
            ],
        )
    entry = (
        _generalized_contract_profile_entry(payload, raw_bytes)
        if isinstance(payload, Mapping)
        else None
    )
    if entry is None:
        return _profile_load_result(
            success=False,
            profile_id=requested_id,
            profile_version=requested_version,
            profile_hash=requested_hash,
            issues=[
                {
                    "code": "packaged_profile_contract_invalid",
                    "severity": "error",
                    "message": (
                        "Runtime loading accepts only the schema-v2 generalized packaged-style-contract "
                        "with packaged-only generation and complete C#/SQL structural declarations."
                    ),
                    "path": str(path),
                }
            ],
        )
    available_id = str(entry.get("profile_id") or "").strip()
    available_version = str(entry.get("version") or "").strip()
    if requested_id != available_id:
        return _profile_load_result(
            success=False,
            profile_id=requested_id,
            profile_version=requested_version,
            profile_hash=requested_hash,
            issues=[
                {
                    "code": "packaged_profile_id_not_found",
                    "severity": "error",
                    "message": "The requested profile_id does not match the generalized packaged contract.",
                    "profile_id": requested_id,
                }
            ],
        )
    if requested_version != available_version:
        return _profile_load_result(
            success=False,
            profile_id=requested_id,
            profile_version=requested_version,
            profile_hash=requested_hash,
            issues=[
                {
                    "code": "packaged_profile_version_mismatch",
                    "severity": "error",
                    "message": "The packaged profile version does not match the requested version.",
                    "available_versions": [available_version],
                }
            ],
        )

    canonical = _canonical_profile_payload(entry)
    declared_hash = str(
        entry.get("profile_hash") or entry.get("sha256") or entry.get("hash") or ""
    ).strip().lower()
    computed_hash = (
        str(entry.get("artifact_hash") or "").strip().lower()
        if entry.get("hash_mode") == "artifact_sha256"
        else _compute_packaged_profile_hash(entry).lower()
    )
    issues: List[Dict[str, Any]] = []
    if not canonical["sanitized"]:
        issues.append(
            {
                "code": "packaged_profile_not_sanitized",
                "severity": "error",
                "message": "Runtime generation accepts only explicitly sanitized packaged profiles.",
            }
        )
    if not isinstance(canonical["rules"].get("csharp"), Mapping) or not isinstance(
        canonical["rules"].get("sql"), Mapping
    ):
        issues.append(
            {
                "code": "packaged_profile_domain_rules_missing",
                "severity": "error",
                "message": "The profile must contain generalized csharp and sql rule groups.",
            }
        )
    if not declared_hash or declared_hash != computed_hash or requested_hash != computed_hash:
        issues.append(
            {
                "code": "packaged_profile_hash_mismatch",
                "severity": "error",
                "message": "The declared, computed, and requested profile hashes must match.",
                "declared_hash": declared_hash,
                "computed_hash": computed_hash,
                "requested_hash": requested_hash,
            }
        )
    success = not issues
    return _profile_load_result(
        success=success,
        profile_id=requested_id,
        profile_version=requested_version,
        profile_hash=computed_hash if success else requested_hash,
        issues=issues,
        profile_path=str(path),
        rules=canonical["rules"] if success else {},
    )


def _load_runtime_packaged_migration_profile(
    profile_id: str = "",
    profile_version: str = "",
    profile_hash: str = "",
) -> HarnessResult:
    requested = [
        str(profile_id or "").strip(),
        str(profile_version or "").strip(),
        str(profile_hash or "").strip(),
    ]
    if any(requested):
        return load_packaged_migration_profile(*requested)

    path = Path(PACKAGED_MIGRATION_PROFILE_PATH)
    try:
        raw_bytes = path.read_bytes()
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return load_packaged_migration_profile("packaged-contract", "missing", "sha256:missing")
    entry = (
        _generalized_contract_profile_entry(payload, raw_bytes)
        if isinstance(payload, Mapping)
        else None
    )
    if entry is None:
        return load_packaged_migration_profile("packaged-contract", "invalid", "sha256:invalid")
    return load_packaged_migration_profile(
        str(entry["profile_id"]),
        str(entry["version"]),
        str(entry["profile_hash"]),
    )


def _consume_profile_evidence(
    profile_evidence: Any,
    domain: str,
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    metadata: Mapping[str, Any] = {}
    evidence_success = False
    if isinstance(profile_evidence, HarnessResult):
        metadata = profile_evidence.metadata
        evidence_success = bool(profile_evidence.success)
    elif isinstance(profile_evidence, Mapping):
        candidate_metadata = profile_evidence.get("metadata", profile_evidence)
        metadata = candidate_metadata if isinstance(candidate_metadata, Mapping) else {}
        evidence_success = bool(profile_evidence.get("success", True))
    consumption = dict(metadata.get("profile_consumption") or {})
    rules = dict(metadata.get("profile_rules") or {})
    identity_valid = bool(
        evidence_success
        and metadata.get("status") == "loaded"
        and consumption.get("source") == "packaged_sanitized_profile"
        and consumption.get("sanitized") is True
        and consumption.get("profile_hash_verified") is True
        and consumption.get("profile_id")
        and consumption.get("profile_version")
        and consumption.get("profile_hash")
        and consumption.get("profile_rules_hash") == _profile_rules_hash(rules)
        and consumption.get("consumption_token")
        == _profile_consumption_token(
            str(consumption.get("profile_id")),
            str(consumption.get("profile_version")),
            str(consumption.get("profile_hash")),
            str(consumption.get("profile_rules_hash")),
        )
        and isinstance(rules.get(domain), Mapping)
    )
    if not identity_valid:
        return (
            {
                "status": "blocked",
                "consumed": False,
                "applied_rule_groups": [],
            },
            [
                {
                    "code": "packaged_profile_consumption_required",
                    "severity": "error",
                    "message": (
                        f"{domain} validation requires a successfully loaded sanitized packaged profile "
                        "with matching profile_id, version, hash, and consumption token."
                    ),
                }
            ],
        )
    consumption.update(
        {
            "status": "consumed",
            "consumed": True,
            "domain": domain,
            "applied_rule_groups": [],
        }
    )
    return {"consumption": consumption, "rules": dict(rules[domain])}, []


def _normalized_profile_patterns(value: Any) -> List[Dict[str, str]]:
    if not isinstance(value, (list, tuple)):
        return []
    patterns: List[Dict[str, str]] = []
    for index, item in enumerate(value):
        if isinstance(item, str):
            patterns.append({"id": f"pattern_{index + 1}", "pattern": item})
        elif isinstance(item, Mapping) and str(item.get("pattern") or "").strip():
            patterns.append(
                {
                    "id": str(item.get("id") or f"pattern_{index + 1}"),
                    "pattern": str(item.get("pattern")),
                }
            )
    return patterns


@dataclass(frozen=True)
class _CSharpStringLiteral:
    start: int
    end: int
    value: str | None
    interpolated: bool
    terminated: bool


@dataclass(frozen=True)
class _CSharpLexicalView:
    code: str
    comments_removed: str
    string_literals: tuple[_CSharpStringLiteral, ...]


def _csharp_string_prefix(source: str, index: int) -> tuple[int, bool, bool] | None:
    for prefix, verbatim, interpolated in (
        ('$@"', True, True),
        ('@$"', True, True),
        ('$"', False, True),
        ('@"', True, False),
        ('"', False, False),
    ):
        if source.startswith(prefix, index):
            return len(prefix), verbatim, interpolated
    return None


def _scan_csharp_char_literal(source: str, start: int) -> int:
    index = start + 1
    while index < len(source):
        char = source[index]
        if char == "\\":
            index = min(index + 2, len(source))
            continue
        if char == "'":
            return index + 1
        if char in "\r\n":
            return index
        index += 1
    return len(source)


def _scan_csharp_string_literal(
    source: str,
    start: int,
    prefix_length: int,
    *,
    verbatim: bool,
    interpolated: bool,
) -> tuple[int, int, bool]:
    index = start + prefix_length
    interpolation_depth = 0
    while index < len(source):
        if interpolation_depth:
            if source.startswith("//", index):
                newline = source.find("\n", index + 2)
                index = len(source) if newline < 0 else newline
                continue
            if source.startswith("/*", index):
                closing = source.find("*/", index + 2)
                index = len(source) if closing < 0 else closing + 2
                continue
            nested_prefix = _csharp_string_prefix(source, index)
            if nested_prefix is not None:
                nested_length, nested_verbatim, nested_interpolated = nested_prefix
                index, _, _ = _scan_csharp_string_literal(
                    source,
                    index,
                    nested_length,
                    verbatim=nested_verbatim,
                    interpolated=nested_interpolated,
                )
                continue
            if source[index] == "'":
                index = _scan_csharp_char_literal(source, index)
                continue
            if source[index] == "{":
                interpolation_depth += 1
            elif source[index] == "}":
                interpolation_depth -= 1
            index += 1
            continue

        char = source[index]
        if interpolated and char == "{":
            if index + 1 < len(source) and source[index + 1] == "{":
                index += 2
            else:
                interpolation_depth = 1
                index += 1
            continue
        if interpolated and char == "}" and index + 1 < len(source) and source[index + 1] == "}":
            index += 2
            continue
        if verbatim:
            if char == '"':
                if index + 1 < len(source) and source[index + 1] == '"':
                    index += 2
                    continue
                return index + 1, index, True
            index += 1
            continue
        if char == "\\":
            index = min(index + 2, len(source))
            continue
        if char == '"':
            return index + 1, index, True
        if char in "\r\n":
            return index, index, False
        index += 1
    return len(source), len(source), False


def _decode_csharp_regular_string(value: str) -> str | None:
    simple_escapes = {
        "'": "'",
        '"': '"',
        "\\": "\\",
        "0": "\0",
        "a": "\a",
        "b": "\b",
        "f": "\f",
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "v": "\v",
    }
    decoded: List[str] = []
    index = 0
    while index < len(value):
        if value[index] != "\\":
            decoded.append(value[index])
            index += 1
            continue
        if index + 1 >= len(value):
            return None
        escape = value[index + 1]
        if escape in simple_escapes:
            decoded.append(simple_escapes[escape])
            index += 2
            continue
        if escape in {"u", "U"}:
            digits = 4 if escape == "u" else 8
            encoded = value[index + 2 : index + 2 + digits]
            if len(encoded) != digits or not re.fullmatch(r"[0-9A-Fa-f]+", encoded):
                return None
            try:
                decoded.append(chr(int(encoded, 16)))
            except ValueError:
                return None
            index += 2 + digits
            continue
        if escape == "x":
            match = re.match(r"[0-9A-Fa-f]{1,4}", value[index + 2 :])
            if not match:
                return None
            decoded.append(chr(int(match.group(0), 16)))
            index += 2 + len(match.group(0))
            continue
        return None
    return "".join(decoded)


def _lex_csharp_non_code(source_text: str) -> _CSharpLexicalView:
    source = str(source_text or "")
    masked = list(source)
    comments_removed = list(source)
    literals: List[_CSharpStringLiteral] = []

    def mask(target: List[str], start: int, end: int) -> None:
        for position in range(start, min(end, len(target))):
            if target[position] not in "\r\n":
                target[position] = " "

    index = 0
    while index < len(source):
        if source.startswith("//", index):
            newline = source.find("\n", index + 2)
            end = len(source) if newline < 0 else newline
            mask(masked, index, end)
            mask(comments_removed, index, end)
            index = end
            continue
        if source.startswith("/*", index):
            closing = source.find("*/", index + 2)
            end = len(source) if closing < 0 else closing + 2
            mask(masked, index, end)
            mask(comments_removed, index, end)
            index = end
            continue
        prefix = _csharp_string_prefix(source, index)
        if prefix is not None:
            prefix_length, verbatim, interpolated = prefix
            end, content_end, terminated = _scan_csharp_string_literal(
                source,
                index,
                prefix_length,
                verbatim=verbatim,
                interpolated=interpolated,
            )
            value: str | None = None
            if terminated and not interpolated:
                raw_value = source[index + prefix_length : content_end]
                value = raw_value.replace('""', '"') if verbatim else _decode_csharp_regular_string(raw_value)
            literals.append(
                _CSharpStringLiteral(
                    start=index,
                    end=end,
                    value=value,
                    interpolated=interpolated,
                    terminated=terminated,
                )
            )
            mask(masked, index, end)
            index = end if end > index else index + 1
            continue
        if source[index] == "'":
            end = _scan_csharp_char_literal(source, index)
            mask(masked, index, end)
            index = end if end > index else index + 1
            continue
        index += 1
    return _CSharpLexicalView(
        code="".join(masked),
        comments_removed="".join(comments_removed),
        string_literals=tuple(literals),
    )


def _apply_consumed_profile_rules(
    source_text: str,
    profile_context: Dict[str, Any],
    *,
    domain: str,
    procedure_name: str = "",
    required_source_text: str | None = None,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not profile_context.get("consumption"):
        return [], profile_context
    rules = dict(profile_context.get("rules") or {})
    consumption = dict(profile_context["consumption"])
    applied: List[str] = []
    issues: List[Dict[str, Any]] = []

    required_patterns = _normalized_profile_patterns(rules.get("required_patterns"))
    required_pattern_ids = [item["id"] for item in required_patterns]
    matched_required_pattern_ids: List[str] = []
    missing_required_pattern_ids: List[str] = []
    if required_patterns:
        applied.append(f"{domain}.required_patterns")
    required_source = source_text if required_source_text is None else required_source_text
    for item in required_patterns:
        try:
            matched = re.search(item["pattern"], required_source, flags=re.IGNORECASE | re.MULTILINE) is not None
        except re.error as exc:
            issues.append(
                {
                    "code": "profile_rule_regex_invalid",
                    "severity": "error",
                    "rule_id": item["id"],
                    "message": str(exc),
                }
            )
            continue
        if not matched:
            missing_required_pattern_ids.append(item["id"])
            issues.append(
                {
                    "code": f"profile_required_{domain}_pattern_missing",
                    "severity": "error",
                    "rule_id": item["id"],
                    "message": f"Generated {domain} did not consume required packaged profile convention {item['id']}.",
                }
            )
        else:
            matched_required_pattern_ids.append(item["id"])

    forbidden_patterns = _normalized_profile_patterns(rules.get("forbidden_patterns"))
    if forbidden_patterns:
        applied.append(f"{domain}.forbidden_patterns")
    for item in forbidden_patterns:
        try:
            matched = re.search(item["pattern"], source_text, flags=re.IGNORECASE | re.MULTILINE) is not None
        except re.error as exc:
            issues.append(
                {
                    "code": "profile_rule_regex_invalid",
                    "severity": "error",
                    "rule_id": item["id"],
                    "message": str(exc),
                }
            )
            continue
        if matched:
            issues.append(
                {
                    "code": f"profile_forbidden_{domain}_pattern",
                    "severity": "error",
                    "rule_id": item["id"],
                    "message": f"Generated {domain} matched forbidden packaged profile convention {item['id']}.",
                }
            )

    if domain == "sql":
        allowed_patterns = _normalized_profile_patterns(rules.get("allowed_procedure_patterns"))
        if allowed_patterns:
            applied.append("sql.allowed_procedure_patterns")
        allowed = False
        for item in allowed_patterns:
            try:
                if re.fullmatch(item["pattern"], procedure_name, flags=re.IGNORECASE):
                    allowed = True
                    break
            except re.error as exc:
                issues.append(
                    {
                        "code": "profile_rule_regex_invalid",
                        "severity": "error",
                        "rule_id": item["id"],
                        "message": str(exc),
                    }
                )
        if not procedure_name or not allowed_patterns or not allowed:
            issues.append(
                {
                    "code": "profile_unmapped_sp_output",
                    "severity": "error",
                    "procedure_name": procedure_name,
                    "message": (
                        "The generated procedure must match the loaded profile's generalized procedure mapping; "
                        "path strings or unrelated source evidence do not satisfy this contract."
                    ),
                }
            )

    consumption["applied_rule_groups"] = applied
    consumption["required_pattern_ids"] = required_pattern_ids
    consumption["matched_required_pattern_ids"] = matched_required_pattern_ids
    consumption["missing_required_pattern_ids"] = missing_required_pattern_ids
    profile_context = {"consumption": consumption, "rules": rules}
    return issues, profile_context


def get_author_tagged_csharp_style_baseline() -> Dict[str, Any]:
    """Return the detached generalized style recipe through the legacy API."""
    return json.loads(json.dumps(AUTHOR_TAGGED_CSHARP_STYLE_BASELINE))


def normalize_author_tagged_program_key(procedure_name: str) -> str:
    """Normalize sp_<PROGRAM>_SELECT/SAVE names to the matched C# program key."""
    name = str(procedure_name or "").strip().strip("[]")
    if "." in name:
        name = name.split(".")[-1].strip().strip("[]")
    upper = name.upper()
    if upper.startswith("SP_"):
        upper = upper[3:]
    for suffix in ("_SELECT", "_SAVE"):
        if upper.endswith(suffix):
            upper = upper[: -len(suffix)]
            break
    return upper


def _normalize_author_tagged_evidence_path(path: str) -> str:
    return re.sub(r"[\\/]+", "\\\\", str(path or "").strip()).upper()


def _author_tagged_path_parts(path: str) -> List[str]:
    return [part.upper() for part in re.split(r"[\\/]+", str(path or "").strip()) if part]


def _author_tagged_path_file_name(path: str) -> str:
    parts = _author_tagged_path_parts(path)
    return parts[-1] if parts else ""


def _author_tagged_path_tail(path: str, length: int = 2) -> str:
    parts = _author_tagged_path_parts(path)
    if not parts:
        return ""
    return "\\\\".join(parts[-length:])


def _author_tagged_path_uses_excluded_segment(path: str) -> bool:
    excluded = {"BACKUP", "BIN", "OBJ", ".GIT", ".VS"}
    return bool(excluded.intersection(_author_tagged_path_parts(path)))


def _expected_author_tagged_style_paths(program_key: str) -> List[str]:
    return list(AUTHOR_TAGGED_PROGRAM_CSHARP_MAPPINGS.get(str(program_key or "").upper(), []))


def _author_tagged_evidence_paths_match(program_key: str, evidence_paths: Iterable[str]) -> bool:
    expected_paths = _expected_author_tagged_style_paths(program_key)
    if not expected_paths:
        return False
    actual_paths = [str(path or "") for path in evidence_paths if str(path or "").strip()]
    if any(_author_tagged_path_uses_excluded_segment(path) for path in actual_paths):
        return False
    expected_tails = {_author_tagged_path_tail(path) for path in expected_paths}
    actual_tails = {_author_tagged_path_tail(path) for path in actual_paths}
    return bool(expected_tails) and expected_tails.issubset(actual_tails)


def _discover_author_tagged_csharp_paths(program_key: str, csharp_root: str) -> List[str]:
    """Find same-program C# and Designer files under a root without trusting localized folder text."""
    root = str(csharp_root or "").strip()
    key = str(program_key or "").strip().upper()
    if not root or not key or not os.path.isdir(root):
        return []
    skip_dirs = {"BACKUP", "BIN", "OBJ", ".GIT", ".VS"}
    primary_path = ""
    designer_path = ""
    primary_name = f"{key}.CS"
    designer_name = f"{key}.DESIGNER.CS"
    for current_root, dir_names, file_names in os.walk(root):
        dir_names[:] = [name for name in dir_names if name.upper() not in skip_dirs]
        for file_name in file_names:
            upper_name = file_name.upper()
            full_path = os.path.normpath(os.path.join(current_root, file_name))
            if upper_name == primary_name and not primary_path:
                primary_path = full_path
            elif upper_name == designer_name and not designer_path:
                designer_path = full_path
        if primary_path and designer_path:
            break
    return [path for path in (primary_path, designer_path) if path]


def _build_author_tagged_screen_style_profile(program_key: str, source_text: str, designer_text: str = "") -> Dict[str, Any]:
    """Build a portable same-program style profile from full C#/Designer text."""
    source = str(source_text or "")
    designer = str(designer_text or "")
    combined = source + "\n" + designer
    method_names = sorted(
        set(
            re.findall(
                r"\b(?:private|protected|public|internal)\s+(?:override\s+)?(?:void|DataSet|bool|string|int)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
                source,
            )
        )
    )
    sp_calls = re.findall(r'dbClient\.(GetDataSetFromSP|ExecSPTrn|ExecSP)\s*\(\s*"([^"]+)"', source)
    db_parameters = re.findall(r'new\s+DbParameter\s*\(\s*"(@[A-Za-z0-9_]+)"', source)
    grid_controls = sorted(set(re.findall(r"\b(grd[A-Za-z0-9_]*)\b", combined)))
    grid_views = sorted(set(re.findall(r"\b(gvw[A-Za-z0-9_]*)\b", combined)))
    grid_columns = sorted(set(re.findall(r"\b(col(?:List|Detail|[A-Za-z0-9]+)_[A-Z0-9_]+)\b", designer)))
    binding_fields = sorted(set(re.findall(r'\.BindingField\s*=\s*"([^"]+)"', designer)))
    repository_spin = sorted(set(re.findall(r"\b(rpsSpin[A-Za-z0-9_]*)\b", designer)))
    return {
        "program_key": str(program_key or "").upper(),
        "base_class": (
            "FrmPopBase"
            if re.search(r":\s*FrmPopBase\b", source)
            else "FrmDevBase"
            if re.search(r":\s*FrmDevBase\b", source)
            else ""
        ),
        "method_names": method_names,
        "command_handlers": [name for name in method_names if name in {"SearchCommand", "SaveCommand", "ClearCommand"}],
        "select_methods": [name for name in method_names if name in {"CallSelectProcedure", "CallViewQuery", "CallProc"}],
        "focused_row_methods": [name for name in method_names if "FocusedRow" in name or name == "fnFocusedRowChanged"],
        "sp_calls": [{"method": method, "procedure": procedure} for method, procedure in sp_calls],
        "db_parameters": db_parameters,
        "grid_controls": grid_controls,
        "grid_views": grid_views,
        "grid_columns": grid_columns[:200],
        "grid_column_count": len(grid_columns),
        "binding_fields": binding_fields[:200],
        "binding_field_count": len(binding_fields),
        "repository_spin_controls": repository_spin,
        "has_data_table_to_xml": "DataUtil.DataTableToXml" in source,
        "has_exec_sp_trn": "dbClient.ExecSPTrn" in source,
        "has_get_focused_data_row": "GetFocusedDataRow" in source,
        "has_devfnc_initcontrol": "devFnc.InitControl" in source,
        "has_columns_addrange": ".Columns.AddRange" in designer,
        "has_header_usefont": "AppearanceHeader.Options.UseFont = true" in designer,
        "has_header_center_alignment": "AppearanceHeader.TextOptions.HAlignment = DevExpress.Utils.HorzAlignment.Center" in designer,
        "has_cell_usefont": "AppearanceCell.Options.UseFont = true" in designer,
    }


def build_author_tagged_style_profile_update(
    procedure_name: str,
    *,
    csharp_root: str,
    profile_id: str,
    profile_version: str,
) -> HarnessResult:
    """Inspect live C# only through an explicit, candidate-only relearning operation."""
    program_key = normalize_author_tagged_program_key(procedure_name)
    discovered_paths = _discover_author_tagged_csharp_paths(program_key, csharp_root)
    issues: List[Dict[str, Any]] = []
    if not profile_id or not profile_version:
        issues.append(
            {
                "code": "profile_update_identity_required",
                "severity": "error",
                "message": "Explicit profile update requires profile_id and profile_version.",
            }
        )
    if len(discovered_paths) < 2:
        issues.append(
            {
                "code": "profile_update_csharp_pair_missing",
                "severity": "error",
                "message": "Explicit profile update requires matching primary C# and Designer files.",
            }
        )
    candidate: Dict[str, Any] = {}
    if not issues:
        try:
            source_text = Path(discovered_paths[0]).read_text(encoding="utf-8-sig", errors="ignore")
            designer_text = Path(discovered_paths[1]).read_text(encoding="utf-8-sig", errors="ignore")
        except OSError as exc:
            issues.append(
                {
                    "code": "profile_update_csharp_read_failed",
                    "severity": "error",
                    "message": str(exc),
                }
            )
        else:
            extracted = _build_author_tagged_screen_style_profile(
                program_key,
                source_text,
                designer_text,
            )
            candidate = {
                "profile_id": str(profile_id),
                "version": str(profile_version),
                "sanitized": False,
                "candidate_source": "explicit_live_csharp_update",
                "program_key": program_key,
                "extracted_style": extracted,
            }
    success = not issues
    metadata = {
        "harness": "pb-to-csharp-migration-harness",
        "operation": "explicit_profile_update",
        "status": "candidate_ready" if success else "blocked",
        "write_status": "candidate_only",
        "program_key": program_key,
        "profile_id": str(profile_id or ""),
        "profile_version": str(profile_version or ""),
        "source_paths": discovered_paths,
        "candidate_profile": candidate,
        "issues": issues,
        "runtime_generation_eligible": False,
        "next_action": (
            "Sanitize, generalize, review, hash, and package the candidate before runtime use."
            if success
            else "Provide a valid C# root and explicit profile identity."
        ),
        "token_optimizer_status": "passthrough",
    }
    return HarnessResult(
        success=success,
        stdout=json.dumps(
            {
                "status": metadata["status"],
                "operation": metadata["operation"],
                "program_key": program_key,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        stderr="" if success else "Explicit profile update could not build a candidate.",
        exit_code=0 if success else 1,
        metadata=metadata,
    )


def build_migration_profile_update(
    procedure_name: str,
    *,
    csharp_root: str,
    profile_id: str,
    profile_version: str,
) -> HarnessResult:
    """Public maintenance entrypoint for explicit profile relearning."""
    return build_author_tagged_style_profile_update(
        procedure_name,
        csharp_root=csharp_root,
        profile_id=profile_id,
        profile_version=profile_version,
    )


def resolve_author_tagged_style_evidence(
    procedure_name: str,
    *,
    csharp_root: str = "",
    profile_id: str = "",
    profile_version: str = "",
    profile_hash: str = "",
) -> HarnessResult:
    """Resolve runtime style only from an immutable packaged profile identity."""
    program_key = normalize_author_tagged_program_key(procedure_name)
    if str(csharp_root or "").strip():
        metadata = {
            "harness": "pb-to-csharp-migration-harness",
            "operation": "runtime_profile_resolution",
            "procedure_name": procedure_name,
            "program_key": program_key,
            "status": "explicit_profile_update_required",
            "issues": [
                {
                    "code": "live_csharp_source_forbidden_in_runtime_generation",
                    "severity": "error",
                    "message": (
                        "Runtime generation does not walk or read C# roots. Use "
                        "build_author_tagged_style_profile_update for explicit relearning."
                    ),
                }
            ],
            "external_sources_consulted": [],
        }
        return HarnessResult(
            success=False,
            stdout=json.dumps({"status": metadata["status"], "program_key": program_key}),
            stderr="Live C# style discovery is disabled during runtime generation.",
            exit_code=1,
            metadata=metadata,
        )

    requested_profile_id = str(profile_id or program_key).strip()
    loaded = load_packaged_migration_profile(
        requested_profile_id,
        profile_version,
        profile_hash,
    )
    metadata = dict(loaded.metadata)
    metadata.update(
        {
            "operation": "runtime_profile_resolution",
            "procedure_name": procedure_name,
            "program_key": program_key,
            "primary_style_evidence_paths": [],
            "path_evidence_accepted": False,
            "style_profile": dict(metadata.get("profile_rules") or {}),
        }
    )
    return HarnessResult(
        success=loaded.success,
        stdout=loaded.stdout,
        stderr=loaded.stderr,
        exit_code=loaded.exit_code,
        metadata=metadata,
    )


def _is_numeric_grid_field_name(field_name: str) -> bool:
    normalized = re.sub(r"[^A-Z0-9_]", "", field_name.upper())
    tokens = [token for token in re.split(r"[_0-9]+", normalized) if token]
    if any(token in NUMERIC_GRID_FIELD_TOKENS for token in tokens):
        return True
    return any(
        normalized.endswith(suffix)
        or normalized.endswith(f"{suffix}AMT")
        or normalized.endswith(f"{suffix}QTY")
        for suffix in NUMERIC_GRID_FIELD_SUFFIXES
    )


def _is_numeric_grid_data_type(data_type: str) -> bool | None:
    normalized = re.sub(r"\s+", "", str(data_type or "")).lower()
    if not normalized:
        return None
    base_type = normalized.split("(", 1)[0]
    if base_type in {
        "bigint",
        "byte",
        "decimal",
        "double",
        "float",
        "int",
        "integer",
        "long",
        "money",
        "number",
        "numeric",
        "real",
        "short",
        "smallint",
        "smallmoney",
        "tinyint",
        "uint",
        "ulong",
        "ushort",
    }:
        return True
    return False


def _is_numeric_grid_column(column: "DataWindowColumnSpec") -> bool:
    declared_type_result = _is_numeric_grid_data_type(column.data_type)
    if declared_type_result is not None:
        return declared_type_result
    return _is_numeric_grid_field_name(column.field_name)


def _extract_sp_procedure_name(sql_text: str) -> str:
    match = SP_PROCEDURE_NAME_PATTERN.search(
        _strip_sql_literals_and_comments_for_pb_contract(sql_text)
    )
    if not match:
        return ""
    return str(match.group("bracketed") or match.group("plain") or "").upper()


def _display_format_string_looks_numeric(format_string: str) -> bool:
    stripped = format_string.strip()
    if not stripped:
        return False
    return bool(re.fullmatch(r"[#,0.]+", stripped))

CONTROL_FALLBACKS = {
    "grid": {
        "target_suffixes": ("u_gridcontrol", "gridcontrol"),
        "devexpress": "DevExpress.XtraGrid.GridControl",
        "winforms": "System.Windows.Forms.DataGridView",
        "devexpress_view": "DevExpress.XtraGrid.Views.Grid.GridView",
    },
    "text": {
        "target_suffixes": ("u_textedit", "u_textbox", "textedit", "textbox"),
        "devexpress": "DevExpress.XtraEditors.TextEdit",
        "winforms": "System.Windows.Forms.TextBox",
    },
    "label": {
        "target_suffixes": ("u_label", "labelcontrol", "label"),
        "devexpress": "DevExpress.XtraEditors.LabelControl",
        "winforms": "System.Windows.Forms.Label",
    },
    "group": {
        "target_suffixes": ("u_groupcontrol", "groupcontrol", "groupbox"),
        "devexpress": "DevExpress.XtraEditors.GroupControl",
        "winforms": "System.Windows.Forms.GroupBox",
    },
    "panel": {
        "target_suffixes": ("u_panel", "panelcontrol", "panel"),
        "devexpress": "DevExpress.XtraEditors.PanelControl",
        "winforms": "System.Windows.Forms.Panel",
    },
    "tab": {
        "target_suffixes": ("u_tabcontrol", "xtratabcontrol", "tabcontrol"),
        "devexpress": "DevExpress.XtraTab.XtraTabControl",
        "winforms": "System.Windows.Forms.TabControl",
    },
    "date": {
        "target_suffixes": ("u_dateedit", "dateedit", "datetimepicker"),
        "devexpress": "DevExpress.XtraEditors.DateEdit",
        "winforms": "System.Windows.Forms.DateTimePicker",
    },
    "spin": {
        "target_suffixes": ("u_spinedit", "spinedit", "numericupdown"),
        "devexpress": "DevExpress.XtraEditors.SpinEdit",
        "winforms": "System.Windows.Forms.NumericUpDown",
    },
    "button": {
        "target_suffixes": ("u_buttonedit", "buttonedit", "button"),
        "devexpress": "DevExpress.XtraEditors.ButtonEdit",
        "winforms": "System.Windows.Forms.Button",
    },
    "combo": {
        "target_suffixes": ("u_lookupedit", "u_combobox", "lookupedit", "comboboxedit", "combobox"),
        "devexpress": "DevExpress.XtraEditors.LookUpEdit",
        "winforms": "System.Windows.Forms.ComboBox",
    },
    "memo": {
        "target_suffixes": ("u_memoedit", "memoedit", "memoexedit"),
        "devexpress": "DevExpress.XtraEditors.MemoEdit",
        "winforms": "System.Windows.Forms.TextBox",
    },
    "check": {
        "target_suffixes": ("u_checkedit", "checkedit", "checkbox"),
        "devexpress": "DevExpress.XtraEditors.CheckEdit",
        "winforms": "System.Windows.Forms.CheckBox",
    },
    "tree": {
        "target_suffixes": ("u_treelist", "treelist", "treeview"),
        "devexpress": "DevExpress.XtraTreeList.TreeList",
        "winforms": "System.Windows.Forms.TreeView",
    },
}


DATAWINDOW_TO_XML_GRIDVIEW_TOP_LEVEL_PROPERTIES = [
    ("#LayoutVersion", ""),
    ("BestFitMaxRowCount", "-1"),
    ("PreviewLineCount", "-1"),
    ("HorzScrollStep", "3"),
    ("FocusRectStyle", "CellFocus"),
    ("ScrollStyle", "LiveVertScroll, LiveHorzScroll"),
    ("PreviewIndent", "-1"),
    ("GroupPanelText", ""),
    ("PreviewFieldName", ""),
    ("VertScrollTipFieldName", ""),
    ("LevelIndent", "-1"),
    ("GroupFooterShowMode", "VisibleIfExpanded"),
    ("NewItemRowText", ""),
    ("SynchronizeClones", "true"),
    ("BorderStyle", "Default"),
    ("ViewCaption", ""),
    ("DetailHeight", "350"),
    ("DetailTabHeaderLocation", "Top"),
    ("ActiveFilterEnabled", "true"),
]

DATAWINDOW_TO_XML_OPTIONS_VIEW_DEFAULTS = {
    "ShowViewCaption": "false",
    "EnableAppearanceEvenRow": "true",
    "ShowGroupPanel": "false",
    "ColumnAutoWidth": "false",
    "ShowFooter": "true",
    "ShowAutoFilterRow": "true",
}


@dataclass(frozen=True)
class MigrationInputState:
    """Portable evidence state for PB -> C# migration planning."""

    has_pblscripter: bool = False
    has_orca: bool = False
    has_exported_pb_sources: bool = False
    has_datawindow_converter: bool = False
    has_target_csharp_samples: bool = False
    has_ty_csharp_samples: bool = False
    has_sp_style_reference: bool = False
    has_live_db_access: bool = False
    has_pasted_source: bool = False
    has_behavior_description: bool = False
    target_project_name: str = ""
    target_style: str = ""
    pb_version: str = ""
    pbl_export_tool: str = ""
    procedure_name: str = ""
    program_key: str = ""
    fallback_program_key: str = ""
    profile_id: str = ""
    profile_version: str = ""
    profile_hash: str = ""
    author_tagged_required: bool = False
    primary_style_evidence_paths: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_pblscripter": self.has_pblscripter,
            "has_orca": self.has_orca,
            "has_exported_pb_sources": self.has_exported_pb_sources,
            "has_datawindow_converter": self.has_datawindow_converter,
            "has_target_csharp_samples": self.has_target_csharp_samples or self.has_ty_csharp_samples,
            "has_ty_csharp_samples": self.has_ty_csharp_samples,
            "has_sp_style_reference": self.has_sp_style_reference,
            "has_live_db_access": self.has_live_db_access,
            "has_pasted_source": self.has_pasted_source,
            "has_behavior_description": self.has_behavior_description,
            "target_project_name": self.target_project_name,
            "target_style": self.target_style,
            "pb_version": self.pb_version,
            "pbl_export_tool": self.pbl_export_tool,
            "procedure_name": self.procedure_name,
            "program_key": self.program_key,
            "fallback_program_key": self.fallback_program_key,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "profile_hash": self.profile_hash,
            "author_tagged_required": self.author_tagged_required,
            "primary_style_evidence_paths": list(self.primary_style_evidence_paths),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MigrationInputState":
        return cls(
            has_pblscripter=bool(data.get("has_pblscripter", False)),
            has_orca=bool(data.get("has_orca", data.get("orca_available", False))),
            has_exported_pb_sources=bool(data.get("has_exported_pb_sources", False)),
            has_datawindow_converter=bool(data.get("has_datawindow_converter", False)),
            has_target_csharp_samples=bool(
                data.get("has_target_csharp_samples", data.get("has_ty_csharp_samples", False))
            ),
            has_ty_csharp_samples=bool(data.get("has_ty_csharp_samples", False)),
            has_sp_style_reference=bool(data.get("has_sp_style_reference", False)),
            has_live_db_access=bool(data.get("has_live_db_access", False)),
            has_pasted_source=bool(data.get("has_pasted_source", False)),
            has_behavior_description=bool(data.get("has_behavior_description", False)),
            target_project_name=str(data.get("target_project_name", "")),
            target_style=str(data.get("target_style", "")),
            pb_version=str(data.get("pb_version", data.get("powerbuilder_version", ""))),
            pbl_export_tool=str(data.get("pbl_export_tool", data.get("export_tool", ""))),
            procedure_name=str(data.get("procedure_name", "")),
            program_key=str(data.get("program_key", "")),
            fallback_program_key=str(data.get("fallback_program_key", "")),
            profile_id=str(data.get("profile_id", "")),
            profile_version=str(data.get("profile_version", data.get("version", ""))),
            profile_hash=str(data.get("profile_hash", "")),
            author_tagged_required=bool(data.get("author_tagged_required", False)),
            primary_style_evidence_paths=[
                str(item) for item in data.get("primary_style_evidence_paths", []) if str(item)
            ],
            notes=[str(item) for item in data.get("notes", [])],
        )


@dataclass(frozen=True)
class DataWindowColumnSpec:
    field_name: str
    caption: str
    csharp_name: str
    data_type: str = ""
    source: str = "table-column"
    x: int | None = None
    y: int | None = None
    width: int | None = None
    height: int | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_name": self.field_name,
            "caption": self.caption,
            "csharp_name": self.csharp_name,
            "data_type": self.data_type,
            "source": self.source,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True)
class DetailFormFieldSpec:
    logical_name: str
    field_name: str
    caption: str
    editor_type: str
    csharp_label_name: str
    csharp_editor_name: str
    binding_property: str
    binding_code: str
    tab_index: int
    tab_index_code: str
    row: int
    column: int
    label_bounds: Dict[str, int]
    editor_bounds: Dict[str, int]
    source: str = "provided"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "logical_name": self.logical_name,
            "field_name": self.field_name,
            "caption": self.caption,
            "editor_type": self.editor_type,
            "csharp_label_name": self.csharp_label_name,
            "csharp_editor_name": self.csharp_editor_name,
            "binding_property": self.binding_property,
            "binding_code": self.binding_code,
            "tab_index": self.tab_index,
            "tab_index_code": self.tab_index_code,
            "row": self.row,
            "column": self.column,
            "label_bounds": dict(self.label_bounds),
            "editor_bounds": dict(self.editor_bounds),
            "source": self.source,
        }


@dataclass(frozen=True)
class CSharpDesignerControlSpec:
    name: str
    type_name: str
    parent_name: str = ""
    children: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    raw_properties: Dict[str, str] = field(default_factory=dict)
    collection_calls: Dict[str, List[str]] = field(default_factory=dict)
    field_name: str = ""
    caption: str = ""
    binding_field: str = ""
    tab_index: int | None = None
    location: Dict[str, int] | None = None
    size: Dict[str, int] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type_name": self.type_name,
            "parent_name": self.parent_name,
            "children": list(self.children),
            "properties": dict(self.properties),
            "raw_properties": dict(self.raw_properties),
            "collection_calls": {key: list(value) for key, value in self.collection_calls.items()},
            "field_name": self.field_name,
            "caption": self.caption,
            "binding_field": self.binding_field,
            "tab_index": self.tab_index,
            "location": dict(self.location or {}),
            "size": dict(self.size or {}),
        }


def build_pbl_export_strategy(state: MigrationInputState | Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Choose the portable PBL export provider and version handling strategy."""
    input_state = _coerce_state(state)
    explicit_tool = input_state.pbl_export_tool.strip().lower()
    pb_version = input_state.pb_version.strip()
    runtime_lookup_required = False
    if input_state.has_exported_pb_sources:
        provider = "pre_exported_source"
        status = "not_needed"
        confidence = "strong"
        reason = "Exported .sru/.srw/.srd source is already available; skip PBL export."
    elif input_state.has_pblscripter or explicit_tool in {"pblscripter", "export-pbl", "export-pbl.ps1"}:
        provider = "pblscripter"
        status = "available"
        confidence = "strong"
        reason = "Use the wrapper to list and export PB objects into an external output directory."
    elif input_state.has_orca or explicit_tool == "orca":
        provider = "orca"
        status = "available"
        confidence = "strong"
        reason = "Use ORCA directly to list and export PB objects into an external output directory."
    elif input_state.has_pasted_source:
        provider = "pasted_source"
        status = "fallback"
        confidence = "bounded"
        reason = "Use pasted SRU/SRW/SRD text as the source boundary; PBL export is not available."
    elif input_state.has_behavior_description:
        provider = "described_behavior"
        status = "fallback"
        confidence = "inferred"
        reason = "Use the described PB behavior as inferred requirements; source parity is unverified."
    else:
        provider = "bundled_reference"
        status = "fallback"
        confidence = "low"
        reason = "Use bundled process references only until PB source, ORCA, PblScripter, pasted source, or behavior details are provided."

    if provider in {"pblscripter", "orca"} and not pb_version:
        status = "available_with_version_probe"
        confidence = "bounded"
        runtime_lookup_required = True
        reason = (
            reason
            + " PB version is not confirmed, so list/probe first and block full source parity until the matching runtime is known."
        )

    version_policy = (
        "Match the ORCA/runtime major version to the PBL lineage before opening or exporting. "
        "PB 7.0 libraries should use PB 7.0 ORCA/runtime; PB 12.5 libraries should use PB 12.5 ORCA/runtime. "
        "If the version is unknown, list/probe only and mark full source inspection blocked until the version is confirmed."
    )
    operations = [
        "list PBL objects before export",
        "export the named window/user object first",
        "export linked DataWindows after SRU/SRW references are known",
        "write exports into an external run output directory, never into the source PBL tree",
        "preserve source encoding when reading exported text",
    ]
    blocked_conditions = [
        "missing PBL path",
        "missing matching PB runtime/ORCA version",
        "ORCA session open failure",
        "bad library or incompatible PBL version",
        "license/SySAM failure",
        "encoding damage in exported source",
    ]
    return {
        "provider": provider,
        "status": status,
        "confidence": confidence,
        "reason": reason,
        "pb_version": pb_version,
        "version_policy": version_policy,
        "provider_priority": [
            "PblScripter or equivalent wrapper",
            "direct ORCA",
            "pre-exported SRU/SRW/SRD/SRM source",
            "pasted source",
            "described behavior",
            "bundled reference baseline",
        ],
        "operations": operations,
        "blocked_conditions": blocked_conditions,
        "runtime_lookup_required": runtime_lookup_required,
    }


def classify_migration_mode(state: MigrationInputState | Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Classify whether the migration run is standalone, described-behavior, partial-reference, full-reference, or pasted-source."""
    input_state = _coerce_state(state)
    has_csharp_reference = input_state.has_target_csharp_samples or input_state.has_ty_csharp_samples
    export_strategy = build_pbl_export_strategy(input_state)
    if input_state.has_exported_pb_sources and has_csharp_reference and input_state.has_sp_style_reference:
        mode = "full-reference"
        confidence = 0.9 if input_state.has_live_db_access else 0.82
    elif input_state.has_pasted_source:
        mode = "pasted-source"
        confidence = 0.74
    elif input_state.has_behavior_description and not input_state.has_exported_pb_sources:
        mode = "described-behavior"
        confidence = 0.62
    elif any(
        [
            input_state.has_pblscripter,
            input_state.has_orca,
            input_state.has_exported_pb_sources,
            input_state.has_datawindow_converter,
            has_csharp_reference,
            input_state.has_sp_style_reference,
        ]
    ):
        mode = "partial-reference"
        confidence = 0.68
    else:
        mode = "standalone"
        confidence = 0.55

    strong_evidence = []
    weak_evidence = []
    if input_state.has_exported_pb_sources:
        strong_evidence.append("exported .sru/.srw/.srd source")
    if has_csharp_reference:
        strong_evidence.append("target-project C# samples")
    if input_state.has_sp_style_reference:
        strong_evidence.append("packaged KH SP style reference")
    if input_state.has_live_db_access:
        strong_evidence.append("live DB schema/procedure verification")
    if input_state.has_pblscripter and not input_state.has_exported_pb_sources:
        weak_evidence.append("PblScripter available but export not attached yet")
    if input_state.has_orca and not input_state.has_exported_pb_sources:
        weak_evidence.append("ORCA available but export not attached yet")
    if input_state.has_datawindow_converter:
        weak_evidence.append("DataWindowToXml-style grid column conversion available")
    if input_state.has_pasted_source:
        weak_evidence.append("pasted source can drive a bounded migration pass")
    if input_state.has_behavior_description and not input_state.has_exported_pb_sources:
        weak_evidence.append("user-described PB behavior can drive an inferred rebuild; source parity is unverified")

    return {
        "mode": mode,
        "confidence": confidence,
        "state": input_state.to_dict(),
        "strong_evidence": strong_evidence,
        "weak_evidence": weak_evidence,
        "pbl_export_strategy": export_strategy,
        "runtime_lookup_required": export_strategy["runtime_lookup_required"],
        "fallback_policy": (
            "Use PblScripter when available, direct ORCA when PblScripter is missing, already-exported "
            ".sru/.srw/.srd/.srm files when export tooling is absent, then pasted source or described behavior. "
            "Use bundled references as the portable baseline and do not claim source parity without exported or pasted PB source."
        ),
    }


def resolve_csharp_control_stack(
    available_controls: Dict[str, Any] | Iterable[str] | None = None,
    required_controls: Iterable[str] = (
        "grid",
        "text",
        "label",
        "group",
        "panel",
        "tab",
        "date",
        "spin",
        "button",
        "combo",
        "memo",
        "check",
        "tree",
    ),
) -> Dict[str, Any]:
    """Choose target-project controls first, then DevExpress, then WinForms basics."""
    inventory = _normalize_control_inventory(available_controls)
    selections: Dict[str, Dict[str, Any]] = {}
    missing: List[str] = []
    notes: List[str] = []

    for logical_name in required_controls:
        spec = CONTROL_FALLBACKS.get(str(logical_name).lower())
        if not spec:
            missing.append(str(logical_name))
            continue

        project_control = _find_project_control(str(logical_name).lower(), inventory)
        if project_control:
            selection = {
                "provider": "target-project",
                "type": project_control,
                "fallback_level": 0,
                "reason": "matched target-project/custom control inventory",
            }
            if str(logical_name).lower() == "grid" and inventory["has_devexpress"]:
                selection["view_type"] = spec["devexpress_view"]
            selections[str(logical_name)] = selection
            continue

        if inventory["has_devexpress"]:
            selection = {
                "provider": "devexpress",
                "type": spec["devexpress"],
                "fallback_level": 1,
                "reason": "target-project/custom control was not available",
            }
            if str(logical_name).lower() == "grid":
                selection["view_type"] = spec["devexpress_view"]
            selections[str(logical_name)] = selection
            notes.append(f"{logical_name}: used DevExpress fallback")
            continue

        if inventory["has_winforms"]:
            selections[str(logical_name)] = {
                "provider": "winforms",
                "type": spec["winforms"],
                "fallback_level": 2,
                "reason": "target-project/custom and DevExpress controls were not available",
            }
            notes.append(f"{logical_name}: used WinForms fallback")
            continue

        missing.append(str(logical_name))

    return {
        "status": "passed" if not missing else "blocked",
        "strategy": "target-project-controls-first",
        "project_name": inventory["project_name"],
        "required_controls": [str(item) for item in required_controls],
        "selection": selections,
        "missing_controls": missing,
        "available_control_types": sorted(inventory["types"]),
        "providers_available": {
            "target_project_controls": bool(inventory["types"] or inventory["target_project_controls"]),
            "devexpress": inventory["has_devexpress"],
            "winforms": inventory["has_winforms"],
        },
        "fallback_order": ["target-project/custom controls", "DevExpress controls", "WinForms basic controls"],
        "notes": notes,
    }


def build_detail_form_layout_plan(
    fields: Iterable[Any],
    *,
    columns: int = 3,
    section_caption: str = "detail",
    data_source_name: str = "bindingSource1",
    origin_x: int = 16,
    origin_y: int = 30,
    label_width: int = 90,
    editor_width: int = 130,
    editor_height: int = 24,
    row_height: int = 28,
    label_editor_gap: int = 8,
    column_gap: int = 96,
    provider_contract: Mapping[str, Any] | None = None,
    binding_map: Mapping[str, Any] | None = None,
    result_fields: Iterable[str] | None = None,
) -> HarnessResult:
    """Build a clean target-style detail form layout plan for label/editor pairs."""
    normalized_fields = _normalize_detail_form_fields(fields)
    if not normalized_fields:
        return HarnessResult(
            success=False,
            stdout=json.dumps({"fields": [], "status": "blocked"}, ensure_ascii=False),
            stderr="No detail form fields were provided.",
            exit_code=1,
            metadata={
                "harness": "pb-to-csharp-migration-harness",
                "status": "blocked",
                "blocked_reason": "missing_detail_form_fields",
            },
        )

    safe_columns = max(1, int(columns or 1))
    data_source = str(data_source_name or "bindingSource1")
    provider = dict(provider_contract or {})
    provider_name = str(provider.get("provider") or "winforms").strip().lower()
    supports_binding_field = provider.get("supports_binding_field") is True
    supplied_binding_map = dict(binding_map or {})
    normalized_result_fields = (
        None
        if result_fields is None
        else {
            _normalize_datawindow_field_name(item)
            for item in result_fields
            if _normalize_datawindow_field_name(item)
        }
    )
    pitch = label_width + label_editor_gap + editor_width + column_gap
    specs: List[DetailFormFieldSpec] = []
    issues: List[Dict[str, Any]] = []
    for index, field in enumerate(normalized_fields):
        row = index // safe_columns
        column = index % safe_columns
        label_x = origin_x + column * pitch
        y = origin_y + row * row_height
        editor_x = label_x + label_width + label_editor_gap
        logical_name = field["logical_name"]
        field_name = field["field_name"]
        caption = field["caption"] or field_name
        editor_type = field["editor_type"]
        editor_name = field.get("csharp_editor_name") or _build_editor_control_name(editor_type, logical_name, field_name)
        binding_evidence = supplied_binding_map.get(field_name, supplied_binding_map.get(editor_name, {}))
        if isinstance(binding_evidence, str):
            binding_evidence = {"result_field": binding_evidence}
        binding_evidence = dict(binding_evidence) if isinstance(binding_evidence, Mapping) else {}
        result_field = _normalize_datawindow_field_name(
            binding_evidence.get("result_field") or field_name
        )
        explicit_binding_field = bool(
            str(binding_evidence.get("binding_property") or "").lower() == "bindingfield"
            and isinstance(binding_evidence.get("evidence"), Mapping)
            and binding_evidence["evidence"].get("observed") is True
        )
        if normalized_result_fields is not None and result_field not in normalized_result_fields:
            issues.append(
                {
                    "code": "binding_result_field_mismatch",
                    "severity": "error",
                    "field_name": field_name,
                    "result_field": result_field,
                    "message": "The editor binding field must correspond to a declared result field.",
                }
            )
        if supports_binding_field or explicit_binding_field:
            binding_property = "BindingField"
            binding_code = f'this.{editor_name}.BindingField = "{result_field}";'
        else:
            binding_property = "DataBindings"
            target_property = "Checked" if editor_type == "CheckEdit" else (
                "EditValue" if provider_name in {"devexpress", "konelib"} else "Text"
            )
            data_source_reference = data_source if data_source.startswith("this.") else f"this.{data_source}"
            binding_code = (
                f'this.{editor_name}.DataBindings.Add("{target_property}", '
                f'{data_source_reference}, "{result_field}");'
            )
        specs.append(
            DetailFormFieldSpec(
                logical_name=logical_name,
                field_name=field_name,
                caption=caption,
                editor_type=editor_type,
                csharp_label_name=field.get("csharp_label_name") or f"lbl{_normalize_datawindow_field_name(field_name)}",
                csharp_editor_name=editor_name,
                binding_property=binding_property,
                binding_code=binding_code,
                tab_index=index,
                tab_index_code=f"this.{editor_name}.TabIndex = {index};",
                row=row,
                column=column,
                label_bounds={"x": label_x, "y": y + 3, "width": label_width, "height": editor_height},
                editor_bounds={"x": editor_x, "y": y, "width": editor_width, "height": editor_height},
                source=field["source"],
            )
        )

    metadata = {
        "harness": "pb-to-csharp-migration-harness",
        "status": "passed" if not issues else "blocked",
        "section_caption": str(section_caption or "detail"),
        "data_source_name": data_source,
        "field_count": len(specs),
        "columns": safe_columns,
        "layout_rule": (
            "Target-style aligned detail form: place label/editor pairs in fixed rows and columns; "
            "use PB/source order and captions, but do not copy PB pixel coordinates blindly."
        ),
        "control_pair_rule": (
            "LabelControl + TextEdit/SpinEdit/DateEdit/LookUpEdit/ButtonEdit/CheckEdit/MemoEdit by field type; "
            "fallback names use observed prefixes txt/btn/cbo/Spin/ymd/Chk/memo plus pn/grp/grd/gvw/treeList/tab for containers."
        ),
        "binding_rule": (
            "Each editor carries the source/result field through provider-supported BindingField or an explicit "
            "DataBindings map. Existing target control names override generated fallback names."
        ),
        "provider_contract": provider,
        "result_fields": sorted(normalized_result_fields or []),
        "issues": issues,
        "tab_order_rule": "Input editor TabIndex follows the generated left-to-right, top-to-bottom row/column order.",
        "fields": [spec.to_dict() for spec in specs],
    }
    return HarnessResult(
        success=not issues,
        stdout=json.dumps(metadata, ensure_ascii=False, indent=2),
        stderr="" if not issues else "Detail-form binding/result-field validation failed.",
        exit_code=0 if not issues else 1,
        metadata=metadata,
    )


def build_offline_pb_to_csharp_runtime_generation(
    objective: str,
    *,
    profile_id: str,
    profile_version: str,
    profile_hash: str,
    csharp_root: str = "",
) -> HarnessResult:
    """Build ordinary runtime-generation context from packaged profile data only."""
    loaded = load_packaged_migration_profile(profile_id, profile_version, profile_hash)
    objective_present = bool(str(objective or "").strip())
    success = bool(objective_present and loaded.success)
    issues = list(loaded.metadata.get("issues", []))
    if not objective_present:
        issues.append(
            {
                "code": "runtime_generation_objective_required",
                "severity": "error",
                "message": "Runtime generation objective is required.",
            }
        )
    metadata = {
        "harness": "pb-to-csharp-migration-harness",
        "operation": "runtime_generation",
        "runtime_mode": "offline_packaged_profile",
        "status": "ready" if success else "blocked",
        "objective": str(objective or ""),
        "profile_consumption": dict(loaded.metadata.get("profile_consumption", {})),
        "profile_rules": dict(loaded.metadata.get("profile_rules", {})),
        "profile_path": loaded.metadata.get("profile_path", ""),
        "external_sources_consulted": [],
        "ignored_live_source_request": bool(str(csharp_root or "").strip()),
        "capabilities_invoked": {
            "csharp_root_walk": False,
            "csharp_source_read": False,
            "db": False,
            "pbl": False,
            "orca": False,
            "pblscripter": False,
        },
        "issues": issues,
        "token_optimizer_status": "passthrough",
        "token_optimizer_status_reason": "C#/SQL/PB generation contracts remain exact.",
    }
    return HarnessResult(
        success=success,
        stdout=json.dumps(
            {
                "status": metadata["status"],
                "runtime_mode": metadata["runtime_mode"],
                "profile_id": profile_id,
                "profile_version": profile_version,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        stderr="" if success else "Offline packaged runtime generation context could not be built.",
        exit_code=0 if success else 1,
        metadata=metadata,
    )


def build_pb_to_csharp_migration_plan(
    objective: str,
    state: MigrationInputState | Dict[str, Any] | None = None,
) -> HarnessResult:
    """Build a deterministic migration plan that works without host-local PB/C#/DB assets."""
    mode = classify_migration_mode(state)
    input_state = _coerce_state(state)
    pbl_export_strategy = build_pbl_export_strategy(input_state)
    control_stack = resolve_csharp_control_stack(dict(state or {}).get("available_controls") if isinstance(state, dict) else None)
    resolved_program_key = (
        input_state.program_key.upper()
        if input_state.program_key
        else normalize_author_tagged_program_key(input_state.procedure_name)
    )
    loaded_profile = _load_runtime_packaged_migration_profile(
        input_state.profile_id,
        input_state.profile_version,
        input_state.profile_hash,
    )
    packaged_style_resolution: Dict[str, Any] = {
        "required": True,
        "status": "loaded" if loaded_profile.success else "blocked",
        "program_key": resolved_program_key,
        "profile_id": loaded_profile.metadata.get("profile_consumption", {}).get("profile_id", ""),
        "profile_version": loaded_profile.metadata.get("profile_consumption", {}).get("profile_version", ""),
        "profile_hash": loaded_profile.metadata.get("profile_consumption", {}).get("profile_hash", ""),
        "profile_path": loaded_profile.metadata.get("profile_path", ""),
        "profile_consumption": dict(loaded_profile.metadata.get("profile_consumption", {})),
        "profile_rules": dict(loaded_profile.metadata.get("profile_rules", {})),
        "issues": list(loaded_profile.metadata.get("issues", [])),
        "external_sources_consulted": [],
        "source_analysis_invoked": False,
        "runtime_mode": "offline_packaged_profile",
    }
    steps = [
        "Frame the PB screen/program objective, operator workflow, and target C# surface.",
        "Select the PBL export provider: PblScripter wrapper, direct ORCA, pre-exported source, pasted source, described behavior, or bundled fallback.",
        "Match the PB/ORCA runtime version to the PBL lineage before opening or exporting libraries.",
        "Collect PB evidence from exported .sru/.srw/.srd files, pasted source, user-described behavior, or bundled fallback references.",
        "Separate confirmed behavior from inferred behavior when PB source is absent.",
        "Trace SRU/SRW event flow before DataWindow SQL so popup/save behavior is not missed.",
        "Write a substantial analysis markdown handoff before C# generation and verify it with verify_pb_migration_analysis_document.",
        "Map DataWindow columns to target-project controls; fall back to DevExpress and then WinForms basics when needed.",
        "For detail forms, lay out label/editor pairs in clean aligned rows and columns instead of blindly copying PB coordinates.",
        "Resolve the target-project control stack before generating C# so project-specific controls are not replaced by a fixed private-wrapper assumption.",
        "Load and consume the generalized packaged style contract before generating C# or SQL.",
        "Draft C# flow by preserving existing target-project method paths such as CallViewQuery, CallProc, SelectType, DataTableToXml, and SetModified when present.",
        "Draft SELECT/SAVE stored procedures from the packaged generalized style contract and host-local sql-formatting contract.",
        "Separate formatting-only cleanup from semantic/performance rewrites; require DB-backed evidence for semantic changes.",
        "Produce a migration checklist, traceability table, and verification plan before implementation claims.",
    ]
    deliverables = [
        "PBL export provider and PB version strategy",
        "PB source analysis notes",
        "minimum-depth migration analysis markdown handoff",
        "confirmed vs inferred behavior map",
        "DataWindow column/layout mapping",
        "detail form label/editor layout and binding plan",
        "target-project control fallback map",
        "target C# implementation plan",
        "SELECT/SAVE SP plan",
        "SQL formatting verification checklist",
        "migration traceability matrix",
        "blocked/fallback evidence when local artifacts are absent",
    ]
    payload = {
        "harness": "pb-to-csharp-migration-harness",
        "objective": objective,
        "mode": mode,
        "steps": steps,
        "deliverables": deliverables,
        "target_project_name": input_state.target_project_name,
        "pbl_export_strategy": pbl_export_strategy,
        "control_stack": control_stack,
        "packaged_style_resolution": packaged_style_resolution,
        "token_optimizer_status": "passthrough",
        "token_optimizer_status_reason": (
            "PB source, SQL, C# style rules, and business literals are source-of-truth content; do not compress them."
        ),
    }
    return HarnessResult(
        success=bool(objective.strip() and loaded_profile.success),
        stdout=json.dumps(payload, ensure_ascii=False, sort_keys=True),
        stderr=(
            ""
            if objective.strip() and loaded_profile.success
            else (
                "Migration objective is required."
                if not objective.strip()
                else "Generalized packaged style contract validation failed."
            )
        ),
        exit_code=0 if objective.strip() and loaded_profile.success else 1,
        metadata=payload,
    )


def _user_directive_scope_contract_coverage(text: str) -> Dict[str, bool]:
    """Check the user-scope lock as a small contract, not a one-word match."""
    source = str(text or "")
    rule_groups = {
        "user_instruction_authority": (
            r"\buser\s+directive\b",
            r"\blatest\s+user\s+instruction\b",
            r"\bpasted\s+(?:current\s+)?(?:code|sql|source)\b",
            r"\bnamed\s+path\b",
            r"\bscreenshot\b",
            r"\bverified\s+artifact\b",
            r"\uc0ac\uc6a9\uc790\s*\uc9c0\uc2dc",
            r"\ubd99\uc5ec\uc900\s*(?:\ud604\uc7ac\s*)?(?:\ucf54\ub4dc|SQL|\uc18c\uc2a4)",
        ),
        "approved_scope_boundary": (
            r"\bapproved\s+scope\b",
            r"\bapproved\s+edits?\b",
            r"\bexact\s+requested\s+work\b",
            r"\bexcluded\s+changes?\b",
            r"\bout[-\s]?of[-\s]?scope\b",
            r"\uc2b9\uc778\s*\ubc94\uc704",
            r"\uc81c\uc678\s*\ubcc0\uacbd",
        ),
        "proposal_only_boundary": (
            r"\bproposal[-\s]?only\b",
            r"\bexplicit\s+approval\b",
            r"\bdo\s+not\s+implement\b",
            r"\brequire(?:s|d)?\s+approval\b",
            r"\uc81c\uc548\s*\uc804\uc6a9",
            r"\uba85\uc2dc\s*\uc2b9\uc778",
        ),
    }
    return {
        name: any(re.search(pattern, source, flags=re.IGNORECASE) for pattern in patterns)
        for name, patterns in rule_groups.items()
    }


def verify_pb_migration_analysis_document(markdown_text: str) -> HarnessResult:
    """Require a composition- and evidence-complete PB-to-C# analysis handoff before C# generation."""
    text = str(markdown_text or "")
    lines = text.splitlines()
    headings = [
        line.strip()
        for line in lines
        if re.match(r"^\s*#{1,3}\s+\S", line)
    ]
    code_fence_pairs = text.count("```") // 2
    section_coverage: Dict[str, bool] = {}
    evidence_anchor_coverage: Dict[str, bool] = {}
    development_spec_coverage: Dict[str, bool] = {}
    development_spec_detail_coverage: Dict[str, Dict[str, bool]] = {}
    readiness: Dict[str, bool] = {}
    issues: List[Dict[str, Any]] = []

    for section, patterns in PB_MIGRATION_ANALYSIS_SECTION_RULES.items():
        covered = any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)
        section_coverage[section] = covered
        if not covered:
            issues.append(
                {
                    "code": "migration_analysis_required_section_missing",
                    "severity": "error",
                    "section": section,
                    "message": (
                        "PB-to-C# analysis markdown is below the minimum handoff standard; "
                        "implementation needs this section before C# generation."
                    ),
                }
            )

    for anchor, patterns in PB_MIGRATION_ANALYSIS_EVIDENCE_ANCHORS.items():
        covered = any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)
        evidence_anchor_coverage[anchor] = covered
        if not covered:
            issues.append(
                {
                    "code": "migration_analysis_evidence_anchor_missing",
                    "severity": "error",
                    "anchor": anchor,
                    "message": (
                        "PB-to-C# analysis quality is judged by implementation evidence, not document length. "
                        "This handoff is missing a required evidence anchor."
                    ),
                }
            )

    for rule, requirements in PB_MIGRATION_ANALYSIS_READINESS_RULES.items():
        ready = all(section_coverage.get(item, evidence_anchor_coverage.get(item, False)) for item in requirements)
        readiness[rule] = ready
        if not ready:
            issues.append(
                {
                    "code": "migration_analysis_readiness_missing",
                    "severity": "error",
                    "readiness_rule": rule,
                    "requirements": list(requirements),
                    "message": (
                        "The analysis handoff is not ready for C# implementation because one or more "
                        "composition/evidence requirements are missing."
                    ),
                }
            )

    for item, patterns in PB_MIGRATION_DEVELOPMENT_SPEC_RULES.items():
        if item == "user_directive_scope_contract":
            detail = _user_directive_scope_contract_coverage(text)
            development_spec_detail_coverage[item] = detail
            covered = all(detail.values())
        else:
            covered = any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)
        development_spec_coverage[item] = covered
        if not covered:
            issues.append(
                {
                    "code": "migration_analysis_development_spec_missing",
                    "severity": "error",
                    "spec_item": item,
                    "missing_detail": [
                        name
                        for name, present in development_spec_detail_coverage.get(item, {}).items()
                        if not present
                    ],
                    "message": (
                        "The PB-to-C# analysis handoff must be detailed enough for a separate developer agent "
                        "to implement from the analysis output without re-inferring PB behavior."
                    ),
                }
            )

    readiness["developer_agent_handoff_ready"] = all(development_spec_coverage.values())

    metadata = {
        "harness": "pb-to-csharp-migration-harness",
        "check": "migration_analysis_document_quality",
        "quality_model": "composition_and_evidence_over_length",
        "reference_baseline": "019f178e-7387-7172-b99b-d97f9c5cf441",
        "reference_baseline_use": "content structure and implementation usefulness only; no hard line-count or code-block-count gate",
        "line_count": len(lines),
        "heading_count": len(headings),
        "code_fence_pairs": code_fence_pairs,
        "section_coverage": section_coverage,
        "evidence_anchor_coverage": evidence_anchor_coverage,
        "development_spec_coverage": development_spec_coverage,
        "development_spec_detail_coverage": development_spec_detail_coverage,
        "cross_agent_contract": {
            "analysis_agent_output": "migration analysis plus development specification",
            "developer_agent_input": "same document; no hidden chat context or source re-inference required",
            "developer_agent_handoff_ready": readiness["developer_agent_handoff_ready"],
        },
        "readiness": readiness,
        "issues": issues,
        "token_optimizer_status": "passthrough",
        "token_optimizer_status_reason": (
            "Migration analysis markdown is source-of-truth handoff context for C# generation and is not compressed."
        ),
    }
    return HarnessResult(
        success=not issues,
        stdout=json.dumps(metadata, ensure_ascii=False, sort_keys=True),
        stderr="" if not issues else "PB-to-C# migration analysis markdown is below the minimum handoff standard.",
        exit_code=0 if not issues else 1,
        metadata=metadata,
    )


def extract_datawindow_columns(source_text: str) -> List[str]:
    """Extract SRD column names using the same narrow column=(... name=...) rule as the local HTML helper."""
    return [spec.field_name for spec in extract_datawindow_column_specs(source_text)]


def extract_datawindow_column_specs(source_text: str, *, prefix: str = "colList_") -> List[DataWindowColumnSpec]:
    """Extract DataWindow grid columns, C# column names, and best-effort captions from SRD text."""
    source = str(source_text or "")
    starts = [match.start() for match in DATAWINDOW_COLUMN_PATTERN.finditer(source)]
    table_columns: List[Dict[str, str]] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(source)
        block = source[start:end]
        name_match = DATAWINDOW_NAME_PATTERN.search(block)
        if name_match:
            type_match = re.search(
                r"\btype\s*=\s*(?P<data_type>[A-Za-z][A-Za-z0-9_]*(?:\s*\([^)]*\))?)",
                block,
                flags=re.IGNORECASE,
            )
            table_columns.append(
                {
                    "field_name": _normalize_datawindow_field_name(name_match.group("name")),
                    "data_type": str(type_match.group("data_type") if type_match else "").strip(),
                }
            )

    table_data_types = {
        item["field_name"]: item["data_type"]
        for item in table_columns
        if item["field_name"]
    }

    visual_columns = _extract_visual_datawindow_columns(source)
    text_controls = _extract_datawindow_text_controls(source)
    specs: List[DataWindowColumnSpec] = []
    seen: set[str] = set()

    for column in visual_columns:
        field_name = column["field_name"]
        if not field_name or field_name in seen:
            continue
        caption = _match_datawindow_caption(column, text_controls) or field_name
        specs.append(
            DataWindowColumnSpec(
                field_name=field_name,
                caption=caption,
                csharp_name=build_csharp_grid_column_name(field_name, prefix=prefix),
                data_type=table_data_types.get(field_name, ""),
                source="visual-column",
                x=column.get("x"),
                y=column.get("y"),
                width=column.get("width"),
                height=column.get("height"),
            )
        )
        seen.add(field_name)

    for table_column in table_columns:
        field_name = table_column["field_name"]
        if field_name in seen:
            continue
        specs.append(
            DataWindowColumnSpec(
                field_name=field_name,
                caption=field_name,
                csharp_name=build_csharp_grid_column_name(field_name, prefix=prefix),
                data_type=table_column["data_type"],
            )
        )
        seen.add(field_name)
    return specs


def build_csharp_grid_column_name(field_name: str, *, prefix: str = "colList_") -> str:
    """Build a target C# GridColumn member/control name such as colList_ENTITY_ID."""
    normalized = _normalize_datawindow_field_name(field_name)
    safe = re.sub(r"[^A-Z0-9_]", "_", normalized)
    if safe and safe[0].isdigit():
        safe = f"_{safe}"
    return f"{prefix}{safe}"


def resolve_csharp_grid_column_prefix(
    input_format: str = "list",
    *,
    table_name: str = "",
    purpose_name: str = "",
) -> str:
    """Resolve common target C# GridColumn prefixes: colList_, colDetail_, col<TABLE>_, or col<PURPOSE>_."""
    raw_format = str(input_format or "").strip()
    if raw_format.startswith("col") and raw_format.endswith("_"):
        return raw_format
    lowered = raw_format.lower()
    if lowered in {"", "list", "main", "master"}:
        return "colList_"
    if lowered in {"detail", "line", "child"}:
        return "colDetail_"
    if lowered in {"table", "dbtable", "source-table", "source_table"}:
        table = re.sub(r"[^A-Za-z0-9_]", "", str(table_name or "")).upper()
        purpose = re.sub(r"[^A-Za-z0-9_]", "", str(purpose_name or "")).upper()
        return f"col{table}_" if table else (f"col{purpose}_" if purpose else "colList_")
    if lowered in {"purpose", "domain", "role", "logical"}:
        purpose = re.sub(r"[^A-Za-z0-9_]", "", str(purpose_name or table_name or "")).upper()
        return f"col{purpose}_" if purpose else "colList_"
    if raw_format:
        safe = re.sub(r"[^A-Za-z0-9_]", "", raw_format)
        return f"col{safe}_" if safe.lower().startswith("list") or safe.lower().startswith("detail") else f"col{safe}_"
    return "colList_"


def resolve_csharp_grid_control_names(
    input_format: str = "list",
    *,
    table_name: str = "",
    purpose_name: str = "",
) -> Dict[str, str]:
    """Resolve common GridControl/GridView names: grdList/gvwList, grdDetail/gvwDetail, grd<TABLE>/gvw<TABLE>, or grd<PURPOSE>/gvw<PURPOSE>."""
    raw_format = str(input_format or "").strip()
    lowered = raw_format.lower()
    if lowered in {"", "list", "main", "master"}:
        suffix = "List"
    elif lowered in {"detail", "line", "child"}:
        suffix = "Detail"
    elif lowered in {"table", "dbtable", "source-table", "source_table"}:
        suffix = (
            re.sub(r"[^A-Za-z0-9_]", "", str(table_name or "")).upper()
            or re.sub(r"[^A-Za-z0-9_]", "", str(purpose_name or "")).upper()
            or "List"
        )
    elif lowered in {"purpose", "domain", "role", "logical"}:
        suffix = re.sub(r"[^A-Za-z0-9_]", "", str(purpose_name or table_name or "")).upper() or "List"
    else:
        suffix = re.sub(r"[^A-Za-z0-9_]", "", raw_format) or "List"
        suffix = suffix[0].upper() + suffix[1:] if suffix and not suffix.isupper() else suffix
    return {
        "grid_control_name": f"grd{suffix}",
        "grid_view_name": f"gvw{suffix}",
    }


def generate_devexpress_grid_xml(
    columns: Iterable[Any],
    *,
    prefix: str = "colList_",
    grid_view_name: str = "gridView1",
) -> str:
    """Generate the DevExpress GridView XML produced by the attached DataWindowToXml helper."""
    normalized = _normalize_grid_column_specs(columns, prefix=prefix)
    lines = [
        '<XtraSerializer version="1.0" application="View">',
    ]
    for name, value in DATAWINDOW_TO_XML_GRIDVIEW_TOP_LEVEL_PROPERTIES:
        if name == "#LayoutVersion" or value == "":
            lines.append(f'  <property name="{name}" />')
        elif name == "Name":
            lines.append(f'  <property name="Name">{escape(grid_view_name)}</property>')
        else:
            lines.append(f'  <property name="{name}">{escape(value)}</property>')
    lines.insert(
        next(index for index, line in enumerate(lines) if 'DetailTabHeaderLocation' in line),
        f'  <property name="Name">{escape(grid_view_name)}</property>',
    )
    lines.append(f'  <property name="Columns" iskey="true" value="{len(normalized)}">')
    for index, column in enumerate(normalized, start=1):
        escaped_field_name = escape(column.field_name)
        escaped_name = escape(column.csharp_name)
        escaped_caption = escape(column.caption or column.field_name)
        lines.extend(
            [
                f'    <property name="Item{index}" isnull="true" iskey="true">',
                '      <property name="AppearanceHeader" isnull="true" iskey="true">',
                '        <property name="Options" isnull="true" iskey="true">',
                '          <property name="UseTextOptions">true</property>',
                '          <property name="UseFont">true</property>',
                '        </property>',
                '        <property name="TextOptions" isnull="true" iskey="true">',
                '          <property name="HAlignment">Center</property>',
                '          <property name="VAlignment">Center</property>',
                '        </property>',
                '        <property name="Font">Tahoma, 9pt</property>',
                '      </property>',
                '      <property name="AppearanceCell" isnull="true" iskey="true">',
                '        <property name="Options" isnull="true" iskey="true">',
                '          <property name="UseFont">true</property>',
                '        </property>',
                '        <property name="Font">Tahoma, 9pt</property>',
                '      </property>',
                '      <property name="Visible">true</property>',
                f'      <property name="VisibleIndex">{index}</property>',
                f'      <property name="FieldName">{escaped_field_name}</property>',
                f'      <property name="Name">{escaped_name}</property>',
                f'      <property name="Caption">{escaped_caption}</property>',
                '      <property name="ColumnEditName" />',
                '    </property>',
            ]
        )
    lines.extend(
        [
            '  </property>',
            '  <property name="OptionsView" isnull="true" iskey="true">',
        ]
    )
    for name, value in DATAWINDOW_TO_XML_OPTIONS_VIEW_DEFAULTS.items():
        lines.append(f'    <property name="{name}">{value}</property>')
    lines.extend(
        [
            '  </property>',
            '</XtraSerializer>',
        ]
    )
    return "\n".join(lines)


def build_datawindow_gridview_designer_defaults(view_name: str = "gvwList") -> List[str]:
    """Return safe C# GridView OptionsView assignments matching DataWindowToXml defaults."""
    view = str(view_name or "gvwList").strip() or "gvwList"
    return [
        f"this.{view}.OptionsView.ShowViewCaption = false;",
        f"this.{view}.OptionsView.EnableAppearanceEvenRow = true;",
        f"this.{view}.OptionsView.ShowGroupPanel = false;",
        f"this.{view}.OptionsView.ColumnAutoWidth = false;",
        f"this.{view}.OptionsView.ShowFooter = true;",
        f"this.{view}.OptionsView.ShowAutoFilterRow = true;",
    ]


def build_csharp_grid_column_designer_plan(
    columns: Iterable[Any],
    *,
    prefix: str = "",
    input_format: str = "list",
    table_name: str = "",
    purpose_name: str = "",
    grid_view_name: str = "",
    default_allow_edit: bool = False,
    result_fields: Iterable[str] | None = None,
) -> HarnessResult:
    """Build explicit Designer-style GridColumn declarations and assignments."""
    resolved_prefix = prefix or resolve_csharp_grid_column_prefix(
        input_format, table_name=table_name, purpose_name=purpose_name
    )
    grid_names = resolve_csharp_grid_control_names(input_format, table_name=table_name, purpose_name=purpose_name)
    view_name = str(grid_view_name or grid_names["grid_view_name"]).strip() or "gvwList"
    normalized = _normalize_grid_column_specs(columns, prefix=resolved_prefix)
    if not normalized:
        return HarnessResult(
            success=False,
            stdout=json.dumps({"columns": [], "status": "blocked"}, ensure_ascii=False),
            stderr="No grid columns were provided.",
            exit_code=1,
            metadata={
                "harness": "pb-to-csharp-migration-harness",
                "status": "blocked",
                "blocked_reason": "missing_grid_columns",
            },
        )

    normalized_result_fields = (
        None
        if result_fields is None
        else {
            _normalize_datawindow_field_name(item)
            for item in result_fields
            if _normalize_datawindow_field_name(item)
        }
    )
    issues = [
        {
            "code": "grid_field_result_mismatch",
            "severity": "error",
            "field_name": column.field_name,
            "message": "GridColumn FieldName must correspond to a declared result field.",
        }
        for column in normalized
        if normalized_result_fields is not None
        and column.field_name not in normalized_result_fields
    ]
    numeric_repository_by_column: Dict[str, str] = {}
    for column in normalized:
        field_upper = str(column.field_name or "").upper()
        if _is_numeric_grid_column(column):
            if "QTY" in field_upper or "WGT" in field_upper:
                numeric_repository_by_column[column.csharp_name] = "rpsSpinQty"
            else:
                numeric_repository_by_column[column.csharp_name] = "rpsSpinAmt"
    required_repositories = sorted(set(numeric_repository_by_column.values()))
    declarations = [f"private DevExpress.XtraGrid.Columns.GridColumn {column.csharp_name};" for column in normalized]
    declarations.extend(
        f"private DevExpress.XtraEditors.Repository.RepositoryItemSpinEdit {repository_name};"
        for repository_name in required_repositories
    )
    initializers = [
        f"this.{column.csharp_name} = new DevExpress.XtraGrid.Columns.GridColumn();" for column in normalized
    ]
    initializers.extend(
        f"this.{repository_name} = new DevExpress.XtraEditors.Repository.RepositoryItemSpinEdit();"
        for repository_name in required_repositories
    )
    add_range = [
        f"this.{view_name}.Columns.AddRange(new DevExpress.XtraGrid.Columns.GridColumn[] {{",
        *[
            f"    this.{column.csharp_name}{',' if index < len(normalized) - 1 else ''}"
            for index, column in enumerate(normalized)
        ],
        "});",
    ]
    assignments: List[str] = []
    for index, column in enumerate(normalized):
        visible = "true"
        assignments.extend(
            [
                f'this.{column.csharp_name}.Caption = "{_escape_csharp_string(column.caption or column.field_name)}";',
                f'this.{column.csharp_name}.FieldName = "{_escape_csharp_string(column.field_name)}";',
                f'this.{column.csharp_name}.Name = "{_escape_csharp_string(column.csharp_name)}";',
                f"this.{column.csharp_name}.OptionsColumn.AllowEdit = {str(default_allow_edit).lower()};",
                f"this.{column.csharp_name}.Visible = {visible};",
                f"this.{column.csharp_name}.VisibleIndex = {index};",
            ]
        )
        repository_name = numeric_repository_by_column.get(column.csharp_name, "")
        if repository_name:
            assignments.append(f"this.{column.csharp_name}.ColumnEdit = this.{repository_name};")
        if column.width is not None:
            assignments.append(f"this.{column.csharp_name}.Width = {column.width};")

    repository_registration: List[str] = []
    if required_repositories:
        repository_registration = [
            f"this.{grid_names['grid_control_name']}.RepositoryItems.AddRange(new DevExpress.XtraEditors.Repository.RepositoryItem[] {{",
            *[
                f"    this.{repository_name}{',' if index < len(required_repositories) - 1 else ''}"
                for index, repository_name in enumerate(required_repositories)
            ],
            "});",
        ]
    repository_assignments: List[str] = []
    for repository_name in required_repositories:
        repository_assignments.extend(
            [
                f"this.{repository_name}.AutoHeight = false;",
                f"this.{repository_name}.Buttons.AddRange(new DevExpress.XtraEditors.Controls.EditorButton[] {{",
                "new DevExpress.XtraEditors.Controls.EditorButton(DevExpress.XtraEditors.Controls.ButtonPredefines.Combo)});",
                f'this.{repository_name}.Name = "{repository_name}";',
            ]
        )
    designer_lines = [
        "// GridColumn field declarations",
        *declarations,
        "",
        "// InitializeComponent GridColumn creation",
        *initializers,
        "",
        "// GridView column registration",
        *add_range,
        "",
        "// RepositoryItemSpinEdit registration",
        *repository_registration,
        "",
        "// RepositoryItemSpinEdit properties",
        *repository_assignments,
        "",
        "// GridColumn properties",
        *assignments,
    ]
    metadata = {
        "harness": "pb-to-csharp-migration-harness",
        "status": "passed" if not issues else "blocked",
        "columns": [column.to_dict() for column in normalized],
        "csharp_column_prefix": resolved_prefix,
        "csharp_grid_names": grid_names,
        "grid_view_name": view_name,
        "declarations": declarations,
        "initializers": initializers,
        "add_range": add_range,
        "assignments": assignments,
        "repository_registration": repository_registration,
        "repository_assignments": repository_assignments,
        "numeric_repository_by_column": numeric_repository_by_column,
        "result_fields": sorted(normalized_result_fields or []),
        "issues": issues,
        "designer_contract": (
            "Use explicit GridColumn members and Columns.AddRange with colList_/colDetail_/col<TABLE>_/col<PURPOSE>_ "
            "names. Do not generate runtime AddGridColumn, Columns.AddField, or view.Name + \"_\" + fieldName helpers by default."
        ),
        "token_optimizer_status": "passthrough",
        "token_optimizer_status_reason": "Generated Designer code is contract-sensitive and was not compressed.",
    }
    return HarnessResult(
        success=not issues,
        stdout="\n".join(designer_lines),
        stderr="" if not issues else "Grid FieldName/result-field validation failed.",
        exit_code=0 if not issues else 1,
        metadata=metadata,
    )


def extract_csharp_designer_control_specs(source_text: str) -> HarnessResult:
    """Extract target C# Designer control/property evidence from pasted Designer code."""
    source = str(source_text or "")
    control_types: Dict[str, str] = {}
    properties: Dict[str, Dict[str, Any]] = {}
    raw_properties: Dict[str, Dict[str, str]] = {}
    collection_calls: Dict[str, Dict[str, List[str]]] = {}
    parent_by_child: Dict[str, str] = {}
    children_by_parent: Dict[str, List[str]] = {}

    for match in CSHARP_FIELD_DECLARATION_PATTERN.finditer(source):
        control_types.setdefault(match.group("name"), match.group("type"))
    for match in CSHARP_NEW_CONTROL_PATTERN.finditer(source):
        control_types[match.group("name")] = match.group("type")

    lines = source.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        add_match = CSHARP_CONTROLS_ADD_PATTERN.match(line)
        if add_match:
            parent = add_match.group("parent") or "this"
            child = add_match.group("child")
            parent_by_child[child] = parent
            children_by_parent.setdefault(parent, []).append(child)
            index += 1
            continue

        assign_match = CSHARP_PROPERTY_ASSIGNMENT_PATTERN.match(line)
        if assign_match:
            control = assign_match.group("control")
            property_path = assign_match.group("property")
            raw_value = assign_match.group("value").strip()
            properties.setdefault(control, {})[property_path] = _parse_csharp_designer_value(raw_value)
            raw_properties.setdefault(control, {})[property_path] = raw_value
            index += 1
            continue

        add_range_match = CSHARP_COLLECTION_ADD_RANGE_START_PATTERN.match(line)
        if add_range_match:
            statement_lines = [line]
            while index < len(lines) - 1 and ";" not in lines[index]:
                index += 1
                statement_lines.append(lines[index])
            statement = "\n".join(statement_lines)
            control = add_range_match.group("control")
            method_path = add_range_match.group("method")
            collection_calls.setdefault(control, {}).setdefault(method_path, []).append(statement.strip())
            for child in CSHARP_THIS_REFERENCE_PATTERN.findall(statement):
                if child != control:
                    parent_by_child.setdefault(child, control)
                    children_by_parent.setdefault(control, []).append(child)
            index += 1
            continue

        index += 1

    specs: List[CSharpDesignerControlSpec] = []
    for name in sorted(control_types.keys(), key=lambda item: _csharp_designer_order_key(item, source)):
        prop_map = properties.get(name, {})
        raw_map = raw_properties.get(name, {})
        binding_field = _string_property(prop_map.get("BindingField"))
        field_name = _string_property(prop_map.get("FieldName")) or binding_field
        caption = _string_property(prop_map.get("Caption")) or _string_property(prop_map.get("Text"))
        tab_index = _int_property(prop_map.get("TabIndex"))
        location = _point_or_size_property(prop_map.get("Location"))
        size = _point_or_size_property(prop_map.get("Size"))
        children = _dedupe_preserve_order(children_by_parent.get(name, []))
        specs.append(
            CSharpDesignerControlSpec(
                name=name,
                type_name=control_types.get(name, ""),
                parent_name=parent_by_child.get(name, ""),
                children=children,
                properties=prop_map,
                raw_properties=raw_map,
                collection_calls=collection_calls.get(name, {}),
                field_name=field_name,
                caption=caption,
                binding_field=binding_field,
                tab_index=tab_index,
                location=location,
                size=size,
            )
        )

    grid_columns = [
        spec.to_dict()
        for spec in specs
        if spec.type_name.endswith(".GridColumn") or spec.type_name == "GridColumn" or spec.name.startswith("col")
    ]
    metadata = {
        "harness": "pb-to-csharp-migration-harness",
        "status": "passed" if specs else "blocked",
        "control_count": len(specs),
        "controls": [spec.to_dict() for spec in specs],
        "grid_columns_present": bool(grid_columns),
        "grid_column_count": len(grid_columns),
        "grid_columns": grid_columns,
        "property_contract": (
            "Designer evidence preserves target control type, parent/child containment, BindingField/FieldName, "
            "caption/text, TabIndex, bounds, project-specific flags, Properties.* assignments, and AddRange calls."
        ),
        "token_optimizer_status": "passthrough",
        "token_optimizer_status_reason": (
            "C# Designer source is contract-sensitive style evidence and was not compressed."
        ),
    }
    return HarnessResult(
        success=bool(specs),
        stdout=json.dumps(metadata, ensure_ascii=False, indent=2),
        stderr="" if specs else "No C# Designer controls were found.",
        exit_code=0 if specs else 1,
        metadata=metadata,
    )


def _requested_csharp_form_class(program_key: str, form_class: str) -> str:
    explicit = str(form_class or "").strip()
    if explicit:
        return explicit
    program = str(program_key or "").strip().strip("[]")
    if "." in program:
        program = program.split(".")[-1].strip().strip("[]")
    program = re.sub(r"^(?:U?SP_)", "", program, flags=re.IGNORECASE)
    program = re.sub(r"_(?:SELECT|SAVE|SELECT_SAVE)$", "", program, flags=re.IGNORECASE)
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", program):
        return ""
    return program if program.lower().endswith("form") else f"{program}Form"


def _validate_csharp_program_form_contract(
    source: str,
    rules: Mapping[str, Any],
    *,
    program_key: str,
    form_class: str,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    contract = rules.get("form_contract")
    contract = dict(contract) if isinstance(contract, Mapping) else {}
    expected_form = _requested_csharp_form_class(program_key, form_class)
    declared_forms = re.findall(
        r"\b(?:(?:public|internal|protected|private|abstract|sealed|partial)\s+)*class\s+"
        r"([A-Za-z_][A-Za-z0-9_]*)\b",
        source,
    )
    mapped = bool(expected_form and expected_form.lower() in {item.lower() for item in declared_forms})
    issues: List[Dict[str, Any]] = []
    if contract.get("requested_mapping_required") is not True or not expected_form:
        issues.append(
            {
                "code": "generated_csharp_program_form_contract_required",
                "severity": "error",
                "message": "Generated C# validation requires a requested program key or explicit form class.",
            }
        )
    elif not mapped:
        issues.append(
            {
                "code": "generated_csharp_form_contract_mismatch",
                "severity": "error",
                "message": "Generated C# must declare the form mapped to the requested program/form contract.",
                "expected_form_class": expected_form,
                "declared_form_classes": declared_forms,
            }
        )
    return issues, {
        "requested_program_key": str(program_key or ""),
        "requested_form_class": str(form_class or ""),
        "expected_form_class": expected_form,
        "declared_form_classes": declared_forms,
        "profile_form_template": str(contract.get("form_template") or ""),
        "mapped": mapped,
    }


def _runtime_dynamic_ui_allowances(
    evidence: Any,
) -> tuple[set[tuple[str, str]], bool]:
    if not isinstance(evidence, Mapping):
        return set(), False

    reason = str(evidence.get("reason") or "").strip()
    source_evidence = evidence.get("source_evidence")
    verification = evidence.get("verification")

    def has_evidence(value: Any) -> bool:
        if isinstance(value, (Mapping, list, tuple, set)):
            return bool(value)
        return bool(str(value or "").strip())

    def has_observed_verification_receipt(value: Any) -> bool:
        if not isinstance(value, Mapping):
            return False
        receipt_kind = str(value.get("kind") or value.get("type") or "").strip().lower()
        status = str(value.get("status") or "").strip().lower()
        if value.get("observed") is not True or status not in {
            "completed",
            "passed",
            "success",
            "verified",
        }:
            return False
        if receipt_kind == "command":
            return bool(str(value.get("command") or "").strip()) and value.get("exit_code") == 0
        if receipt_kind == "artifact":
            return bool(str(value.get("artifact") or value.get("path") or "").strip()) and bool(
                str(value.get("sha256") or value.get("content_hash") or "").strip()
            )
        if receipt_kind == "test":
            return bool(str(value.get("test") or value.get("test_name") or "").strip())
        if receipt_kind == "tool_receipt":
            return bool(
                str(value.get("receipt") or value.get("result_id") or value.get("tool_call_id") or "").strip()
            )
        return False

    has_source_evidence = has_evidence(source_evidence)
    has_verification = has_observed_verification_receipt(verification)
    core_accepted = bool(
        evidence.get("kind") == "runtime_dynamic_ui"
        and evidence.get("approved") is True
        and reason
        and has_source_evidence
        and has_verification
    )
    if not core_accepted:
        return set(), False

    allowances: set[tuple[str, str]] = set()
    transitions = evidence.get("transitions", [])
    if isinstance(transitions, Mapping):
        transitions = [transitions]
    if isinstance(transitions, (list, tuple)):
        for item in transitions:
            if not isinstance(item, Mapping):
                continue
            member = str(item.get("member") or "").strip()
            property_path = str(item.get("property") or "").strip()
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", member) and re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_.]*",
                property_path,
            ):
                allowances.add((member.lower(), property_path.lower()))

    members = [
        str(item)
        for item in evidence.get("members", [])
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(item or ""))
    ]
    properties = [
        str(item)
        for item in evidence.get("properties", [])
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", str(item or ""))
    ]
    allowances.update(
        (member.lower(), property_path.lower())
        for member in members
        for property_path in properties
    )
    return allowances, bool(allowances)


def _designer_owned_ui_findings(source: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    ui_type_pattern = (
        r"(?:System\.Windows\.Forms|System\.ComponentModel|DevExpress\.)[A-Za-z0-9_.<>]+|"
        r"[A-Za-z_][A-Za-z0-9_.<>]*(?:Button|CheckBox|ComboBox|Component|Container|Control|"
        r"DataGridView|DateTimePicker|Edit|GridColumn|GridView|GridControl|GroupBox|Label|"
        r"NumericUpDown|Panel|RepositoryItem[A-Za-z0-9_]*|TabControl|TextBox|Timer)"
    )
    declaration_pattern = re.compile(
        rf"(?m)^\s*(?:public|protected|internal|private)\s+"
        rf"(?:(?:static|readonly)\s+)*(?P<type>{ui_type_pattern})\s+"
        r"(?P<member>[A-Za-z_][A-Za-z0-9_]*)\s*(?:=[^;]+)?;",
    )
    for match in declaration_pattern.finditer(source):
        findings.append(
            {
                "member": match.group("member"),
                "category": "declaration",
                "property": "",
                "token": match.group(0).strip(),
                "dynamic_eligible": False,
            }
        )

    for match in re.finditer(
        rf"(?:this\.)?(?P<member>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*new\s+"
        rf"(?P<type>{ui_type_pattern})\s*\(",
        source,
    ):
        findings.append(
            {
                "member": match.group("member"),
                "category": "construction",
                "property": "",
                "token": match.group(0),
                "dynamic_eligible": False,
            }
        )

    property_categories = {
        "Appearance": "appearance",
        "Options": "options",
        "DisplayFormat": "display_format",
        "Location": "layout",
        "Size": "layout",
        "Dock": "layout",
        "Anchor": "layout",
        "Margin": "layout",
        "MinimumSize": "layout",
        "MaximumSize": "layout",
        "Name": "name",
        "TabIndex": "tab_index",
        "BindingField": "binding",
        "FieldName": "binding",
        "DataPropertyName": "binding",
        "ColumnEdit": "repository",
        "MainView": "grid",
        "GridControl": "grid",
        "VisibleIndex": "designer_property",
        "Text": "designer_property",
        "Caption": "designer_property",
        "EditValue": "designer_property",
        "Enabled": "designer_property",
        "Visible": "designer_property",
        "ReadOnly": "designer_property",
        "Checked": "designer_property",
        "SelectedIndex": "designer_property",
        "Properties": "designer_property",
    }
    dynamic_roots = {
        "Text",
        "Caption",
        "EditValue",
        "Enabled",
        "Visible",
        "ReadOnly",
        "Checked",
        "SelectedIndex",
        "Properties",
    }
    assignment_pattern = re.compile(
        r"(?:this\.)?(?P<member>[A-Za-z_][A-Za-z0-9_]*)\."
        r"(?P<property>[A-Za-z_][A-Za-z0-9_.]*)\s*=",
    )
    for match in assignment_pattern.finditer(source):
        property_path = match.group("property")
        root = property_path.split(".", 1)[0]
        category = next(
            (
                value
                for key, value in property_categories.items()
                if root == key or root.startswith(key)
            ),
            "",
        )
        if category:
            findings.append(
                {
                    "member": match.group("member"),
                    "category": category,
                    "property": property_path,
                    "token": match.group(0),
                    "dynamic_eligible": root in dynamic_roots,
                }
            )

    collection_pattern = (
        r"(?:Controls|Columns|RepositoryItems|ViewCollection|Items|Buttons|"
        r"Properties\.[A-Za-z0-9_.]+)"
    )
    for match in re.finditer(
        rf"(?:this\.)?(?P<member>[A-Za-z_][A-Za-z0-9_]*)\."
        rf"(?P<property>{collection_pattern})\.(?:Add|AddRange)\s*\(",
        source,
    ):
        findings.append(
            {
                "member": match.group("member"),
                "category": "collection",
                "property": match.group("property"),
                "token": match.group(0),
                "dynamic_eligible": False,
            }
        )
    for match in re.finditer(
        rf"\bthis\.(?P<property>{collection_pattern})\.(?:Add|AddRange)\s*\(",
        source,
    ):
        findings.append(
            {
                "member": "$form",
                "category": "collection",
                "property": match.group("property"),
                "token": match.group(0),
                "dynamic_eligible": False,
            }
        )

    unique: Dict[tuple[str, str, str], Dict[str, Any]] = {}
    for finding in findings:
        key = (
            str(finding["member"]),
            str(finding["category"]),
            str(finding.get("property") or ""),
        )
        unique.setdefault(key, finding)
    return list(unique.values())


def _declared_partial_class_names(source: str) -> set[str]:
    return {
        match.group(1).lower()
        for match in re.finditer(
            r"\bpartial\s+class\s+([A-Za-z_][A-Za-z0-9_]*)\b",
            source,
            flags=re.IGNORECASE,
        )
    }


def _extract_csharp_result_field_mappings(
    lexical_view: _CSharpLexicalView,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    mappings: List[Dict[str, Any]] = []
    unresolved: List[Dict[str, Any]] = []
    assignment_pattern = re.compile(
        r'(?:this\.)?(?P<member>[A-Za-z_][A-Za-z0-9_]*)\.'
        r'(?P<property>BindingField|FieldName|DataPropertyName)\s*='
    )
    for match in assignment_pattern.finditer(lexical_view.code):
        literal = next(
            (
                item
                for item in lexical_view.string_literals
                if item.start >= match.end()
                and not lexical_view.code[match.end() : item.start].strip()
            ),
            None,
        )
        literal_start = literal.start if literal is not None else match.end()
        location = {
            "offset": literal_start,
            "line": lexical_view.code.count("\n", 0, literal_start) + 1,
            "column": literal_start - lexical_view.code.rfind("\n", 0, literal_start),
        }
        base = {
            "member": match.group("member"),
            "property": match.group("property"),
            **location,
        }
        if literal is None or not literal.terminated or literal.value is None:
            unresolved.append(
                {
                    **base,
                    "interpolated": bool(literal and literal.interpolated),
                    "message": "Result-field assignment does not use a statically comparable direct string literal.",
                }
            )
            continue
        mappings.append(
            {
                **base,
                "field_name": _normalize_datawindow_field_name(literal.value),
            }
        )
    return mappings, unresolved


def _validate_csharp_result_field_contract(
    source_view: _CSharpLexicalView,
    designer_view: _CSharpLexicalView,
    result_fields: Iterable[str] | None,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if result_fields is None:
        return [], {"status": "not_requested", "declared_result_fields": [], "mappings": []}
    declared = {
        _normalize_datawindow_field_name(item)
        for item in result_fields
        if _normalize_datawindow_field_name(item)
    }
    source_mappings, source_unresolved = _extract_csharp_result_field_mappings(source_view)
    designer_mappings, designer_unresolved = _extract_csharp_result_field_mappings(designer_view)
    mappings = source_mappings + designer_mappings
    unresolved = source_unresolved + designer_unresolved
    mismatches = [item for item in mappings if item["field_name"] not in declared]
    issues = [
        {
            "code": "csharp_result_field_mapping_mismatch",
            "severity": "error",
            **item,
            "message": "C# BindingField/FieldName must correspond to a declared result field.",
        }
        for item in mismatches
    ]
    return issues, {
        "status": "passed" if not issues else "blocked",
        "declared_result_fields": sorted(declared),
        "mappings": mappings,
        "mismatches": mismatches,
        "unresolved_mappings": unresolved,
    }


def _runtime_dynamic_finding_allowed(
    finding: Mapping[str, Any],
    allowances: set[tuple[str, str]],
) -> bool:
    if finding.get("dynamic_eligible") is not True:
        return False
    member = str(finding.get("member") or "").lower()
    property_path = str(finding.get("property") or "").lower()
    return any(
        member == allowed_member
        and (
            property_path == allowed_property
            or property_path.startswith(allowed_property + ".")
        )
        for allowed_member, allowed_property in allowances
    )


def _validate_designer_owned_ui_contract(
    source: str,
    rules: Mapping[str, Any],
    *,
    source_role: str,
    designer_source: str,
    runtime_dynamic_ui_evidence: Any,
    require_designer_companion: bool,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    contract = rules.get("designer_contract")
    contract = dict(contract) if isinstance(contract, Mapping) else {}
    role = str(source_role or "code-behind").strip().lower()
    if role in {"codebehind", "code_behind", "runtime"}:
        role = "code-behind"
    findings = _designer_owned_ui_findings(source) if role != "designer" else []
    designer_findings = _designer_owned_ui_findings(designer_source) if designer_source.strip() else []
    dynamic_allowances, evidence_accepted = _runtime_dynamic_ui_allowances(
        runtime_dynamic_ui_evidence
    )
    blocked = [
        item
        for item in findings
        if not _runtime_dynamic_finding_allowed(item, dynamic_allowances)
    ]
    issues = [
        {
            "code": "designer_owned_ui_in_code_behind",
            "severity": "error",
            "member": item["member"],
            "category": item["category"],
            "message": (
                "Static UI construction and Designer-owned property setup belong in Designer.cs; "
                "code-behind is limited to events, data flow, and evidenced runtime-dynamic UI behavior."
            ),
        }
        for item in blocked
        if contract.get("static_ui_requires_designer") is True
    ]
    source_classes = _declared_partial_class_names(source)
    designer_classes = _declared_partial_class_names(designer_source)
    companion_class_matches = bool(source_classes.intersection(designer_classes))
    if require_designer_companion and role == "code-behind" and not designer_source.strip():
        issues.append(
            {
                "code": "designer_companion_required",
                "severity": "error",
                "message": "Generated code-behind validation requires its paired Designer source.",
            }
        )
    if designer_source.strip() and source_classes and not companion_class_matches:
        issues.append(
            {
                "code": "designer_companion_class_mismatch",
                "severity": "error",
                "message": "The supplied Designer companion must declare the same partial form class as code-behind.",
                "code_behind_classes": sorted(source_classes),
                "designer_classes": sorted(designer_classes),
            }
        )
    if designer_source.strip() and not designer_findings:
        issues.append(
            {
                "code": "designer_companion_static_setup_missing",
                "severity": "error",
                "message": "The supplied Designer companion must contain the form's static control setup.",
            }
        )
    split_contract_validated = bool(
        role == "code-behind"
        and designer_source.strip()
        and designer_findings
        and companion_class_matches
        and not blocked
    )
    return issues, {
        "source_role": role,
        "profile_rule_applied": contract.get("static_ui_requires_designer") is True,
        "detected_categories": sorted({item["category"] for item in findings}),
        "detected_members": sorted({item["member"] for item in findings}),
        "blocked_members": sorted({item["member"] for item in blocked}),
        "runtime_dynamic_evidence_accepted": evidence_accepted,
        "runtime_dynamic_allowances": [
            {"member": member, "property": property_path}
            for member, property_path in sorted(dynamic_allowances)
        ],
        "designer_static_finding_count": len(designer_findings),
        "designer_detected_categories": sorted(
            {item["category"] for item in designer_findings}
        ),
        "companion_class_matches": companion_class_matches,
        "split_contract_validated": split_contract_validated,
        "designer_companion_required": bool(require_designer_companion),
    }


def verify_migration_generated_csharp_style(
    source_text: str,
    *,
    designer_source_text: str = "",
    profile_evidence: Any = None,
    program_key: str = "",
    fallback_program_key: str = "",
    form_class: str = "",
    source_role: str = "code-behind",
    runtime_dynamic_ui_evidence: Any = None,
    result_fields: Iterable[str] | None = None,
    require_designer_companion: bool = False,
    primary_style_evidence_paths: Any = None,
    excluded_paths: Any = None,
    require_author_tagged_evidence: bool = False,
) -> HarnessResult:
    """Block generated C# patterns that do not match the target Designer/grid style."""
    source_view = _lex_csharp_non_code(source_text)
    designer_view = _lex_csharp_non_code(designer_source_text)
    source = source_view.comments_removed
    designer_source = designer_view.comments_removed
    issues: List[Dict[str, Any]] = []
    if not source_view.code.strip():
        issues.append(
            {
                "code": "generated_csharp_empty",
                "severity": "error",
                "message": "Generated C# source must not be empty.",
            }
        )
    normalized_program_key = str(program_key or "").upper()
    primary_paths = [str(path) for path in (primary_style_evidence_paths or []) if str(path)]
    excluded = [str(path) for path in (excluded_paths or []) if str(path)]
    profile_context, profile_issues = _consume_profile_evidence(profile_evidence, "csharp")
    issues.extend(profile_issues)
    if not profile_issues:
        applied_issues, profile_context = _apply_consumed_profile_rules(
            f"{source}\n{designer_source}",
            profile_context,
            domain="csharp",
            required_source_text=f"{source_view.code}\n{designer_view.code}",
        )
        issues.extend(applied_issues)
    profile_rules = dict(profile_context.get("rules") or {}) if isinstance(profile_context, dict) else {}
    program_form_issues, program_form_contract = _validate_csharp_program_form_contract(
        source_view.code,
        profile_rules,
        program_key=program_key,
        form_class=form_class,
    )
    issues.extend(program_form_issues)
    designer_issues, designer_owned_ui_contract = _validate_designer_owned_ui_contract(
        source_view.code,
        profile_rules,
        source_role=source_role,
        designer_source=designer_view.code,
        runtime_dynamic_ui_evidence=runtime_dynamic_ui_evidence,
        require_designer_companion=require_designer_companion,
    )
    issues.extend(designer_issues)
    result_field_issues, result_field_contract = _validate_csharp_result_field_contract(
        source_view,
        designer_view,
        result_fields,
    )
    issues.extend(result_field_issues)
    profile_consumption = dict(
        profile_context.get("consumption", profile_context)
        if isinstance(profile_context, dict)
        else {}
    )
    if profile_consumption.get("consumed"):
        applied_groups = list(profile_consumption.get("applied_rule_groups", []))
        for group in ("csharp.program_form_contract", "csharp.designer_contract"):
            if group not in applied_groups:
                applied_groups.append(group)
        profile_consumption["applied_rule_groups"] = applied_groups

    if require_author_tagged_evidence and not primary_paths and not profile_consumption.get("consumed"):
        issues.append(
            {
                "code": "author_tagged_style_evidence_required",
                "severity": "error",
                "message": (
                    "Target-style generated C# must name primary style evidence resolved from "
                    "a reviewed procedure-to-program mapping."
                ),
            }
        )
    excluded_keys = (
        {key.upper() for key in AUTHOR_TAGGED_CSHARP_STYLE_BASELINE["baseline_exclusions"]}
        if require_author_tagged_evidence
        else set()
    )
    excluded_seed_used = any(key in path.upper() for key in excluded_keys for path in primary_paths)
    expected_style_program_key = normalized_program_key
    normalized_fallback_program_key = str(fallback_program_key or "").upper()
    if require_author_tagged_evidence and normalized_program_key in excluded_keys:
        expected_style_program_key = normalized_fallback_program_key
        if not normalized_fallback_program_key:
            issues.append(
                {
                    "code": "author_tagged_fallback_program_key_required",
                    "severity": "error",
                    "message": (
                        "Excluded or current repair targets cannot seed their own style. Provide a fallback_program_key "
                        "resolved from established same-module evidence."
                    ),
                    "program_key": normalized_program_key,
                }
            )
    if require_author_tagged_evidence and expected_style_program_key and primary_paths:
        expected_paths = _expected_author_tagged_style_paths(expected_style_program_key)
        if expected_paths and not _author_tagged_evidence_paths_match(expected_style_program_key, primary_paths):
            issues.append(
                {
                    "code": "author_tagged_style_evidence_path_mismatch",
                    "severity": "error",
                    "message": (
                        "Primary style evidence must match the reviewed procedure-to-program same-program "
                        "C# and Designer mapping, not an arbitrary same-project file."
                    ),
                    "program_key": normalized_program_key,
                    "expected_style_program_key": expected_style_program_key,
                    "expected_paths": expected_paths,
                    "actual_paths": primary_paths,
                }
            )
        elif not expected_paths:
            issues.append(
                {
                    "code": "author_tagged_style_mapping_missing",
                    "severity": "error",
                    "message": "No bundled generalized C# mapping exists for the requested style program key.",
                    "program_key": normalized_program_key,
                    "expected_style_program_key": expected_style_program_key,
                }
            )
    if require_author_tagged_evidence and normalized_program_key in excluded_keys and not primary_paths:
        issues.append(
            {
                "code": "excluded_program_cannot_seed_author_tagged_style",
                "severity": "error",
                "message": "This program is excluded from seed style evidence and must be verified against another matched baseline source.",
                "program_key": normalized_program_key,
            }
        )
    if require_author_tagged_evidence and excluded_seed_used:
        issues.append(
            {
                "code": "excluded_path_cannot_seed_author_tagged_style",
                "severity": "error",
                "message": "Current repair targets or SP-only/non-screen mappings cannot be used as primary C# style evidence.",
                "program_key": normalized_program_key,
            }
        )

    if require_author_tagged_evidence and re.search(
        r"dbClient\.(?:GetDataSetFromSP|ExecSPTrn|ExecSP)\s*\(",
        source,
    ) and not re.search(
        r"new\s+DbParameter\s*\(", source
    ):
        issues.append(
            {
                "code": "author_tagged_sp_call_missing_explicit_dbparameters",
                "severity": "error",
                "message": (
                    "Matched target screen retrieve code keeps explicit DbParameter entries near "
                    "dbClient.GetDataSetFromSP; do not present a bare SP call as style-complete generated C#."
                ),
            }
        )

    if re.search(r"<PackageReference\s+Include=\"DevExpress", source, flags=re.IGNORECASE) or re.search(
        r"\bdotnet\s+add\s+package\s+DevExpress", source, flags=re.IGNORECASE
    ):
        issues.append(
            {
                "code": "generated_devexpress_package_reference_detected",
                "severity": "error",
                "message": (
                    "Do not add or upgrade DevExpress packages during PB-to-C# migration generation. "
                    "Use the target project's existing references and API surface."
                ),
            }
        )
    if re.search(r"DevExpress\.[A-Za-z0-9_.]+,\s*Version=\d+", source):
        issues.append(
            {
                "code": "generated_unverified_devexpress_version_reference_detected",
                "severity": "error",
                "message": (
                    "Do not emit unverified DevExpress assembly version references. The migration must follow "
                    "the target project references, not the latest library version."
                ),
            }
        )

    has_designer_grid_column_members = bool(
        re.search(r"\bprivate\s+DevExpress\.XtraGrid\.Columns\.GridColumn\s+col(?:List|Detail|[A-Za-z0-9]+)_[A-Z0-9_]+\s*;", source)
        and re.search(r"this\.col(?:List|Detail|[A-Za-z0-9]+)_[A-Z0-9_]+\s*=\s*new\s+DevExpress\.XtraGrid\.Columns\.GridColumn\s*\(\s*\)\s*;", source)
        and re.search(r"\.Columns\.AddRange\s*\([\s\S]*this\.col(?:List|Detail|[A-Za-z0-9]+)_[A-Z0-9_]+", source)
    )

    if re.search(r"\bAddGridColumn\s*\(", source):
        issues.append(
            {
                "code": "runtime_add_grid_column_helper_detected",
                "severity": "error",
                "message": (
                    "Migration-generated grid columns should be explicit Designer/GridColumn members or "
                    "DataWindowToXml layout artifacts, not a runtime AddGridColumn helper by default."
                ),
            }
        )
    if re.search(r"\.Columns\.AddField\s*\(", source):
        issues.append(
            {
                "code": "runtime_columns_addfield_detected",
                "severity": "error",
                "message": (
                    "Generated columns should preserve names such as colList_FIELD or colDetail_FIELD; "
                    "Columns.AddField hides that Designer naming contract."
                ),
            }
        )
    if re.search(r"\.Columns\.Add\s*\(", source):
        issues.append(
            {
                "code": "runtime_columns_add_detected",
                "severity": "error",
                "message": "Generated grid columns must not be registered through runtime Columns.Add; use explicit Designer Columns.AddRange registration.",
            }
        )
    for constructor_match in re.finditer(r"(?m)^.*new\s+(?:DevExpress\.XtraGrid\.Columns\.)?GridColumn\s*\(\s*\)\s*;", source):
        statement = constructor_match.group(0)
        is_designer_member_initializer = bool(
            re.match(
                r"\s*this\.col(?:List|Detail|[A-Za-z0-9]+)_[A-Z0-9_]+\s*=\s*new\s+DevExpress\.XtraGrid\.Columns\.GridColumn\s*\(\s*\)\s*;\s*$",
                statement,
            )
        )
        if not is_designer_member_initializer:
            issues.append(
                {
                    "code": "runtime_gridcolumn_constructor_without_designer_contract",
                    "severity": "error",
                    "message": "Generated GridColumn construction must be a this.col*_<FIELD> Designer member initializer, not local runtime construction.",
                }
            )
            break
    if re.search(r"\.Name\s*=\s*[^;\n]*view\.Name\s*\+\s*\"_\"\s*\+\s*fieldName", source):
        issues.append(
            {
                "code": "view_name_fieldname_column_name_detected",
                "severity": "error",
                "message": (
                    "Column Name must follow colList_<COLUMN>, colDetail_<COLUMN>, col<TABLE>_<COLUMN>, "
                    "or col<PURPOSE>_<COLUMN>, not view.Name + \"_\" + fieldName."
                ),
            }
        )
    if "GridColumn" in source and not re.search(r"\bcol(?:List|Detail|[A-Za-z0-9]+)_[A-Z0-9_]+\b", source):
        issues.append(
            {
                "code": "missing_target_grid_column_name_pattern",
                "severity": "warning",
                "message": (
                    "GridColumn generation did not expose target-style column names such as colList_ENTITY_ID."
                ),
            }
        )

    if re.search(r"\bprivate\s+sealed\s+class\s+[A-Za-z_][A-Za-z0-9_]*\s*", source):
        issues.append(
            {
                "code": "generated_internal_dto_class_detected",
                "severity": "error",
                "message": (
                    "Target-style screen retrieval code should not invent private sealed DTO/context "
                    "classes such as RetrieveContext. Keep ordinary retrieve parameters as local variables "
                    "near the procedure call unless the target source already proves this pattern."
                ),
            }
        )
    if re.search(r"\bclass\s+[A-Za-z_][A-Za-z0-9_]*Context\b", source) or re.search(
        r"\bGet[A-Za-z_][A-Za-z0-9_]*Context\s*\(", source
    ):
        issues.append(
            {
                "code": "generated_context_flow_detected",
                "severity": "error",
                "message": (
                    "Generated C# should not create a context object flow for ordinary screen retrieve "
                    "parameters unless the target program already uses that style."
                ),
            }
        )
    if re.search(r"\bprivate\s+class\s+[A-Za-z_][A-Za-z0-9_]*(?:Params|Parameters|Request|Criteria)\b", source):
        issues.append(
            {
                "code": "generated_private_parameter_helper_class_detected",
                "severity": "error",
                "message": "Do not generate private SearchParams/Request/Criteria helper classes for target-style screen code.",
            }
        )
    if re.search(
        r"\b(?:private|protected|public|internal)?\s*(?:static\s+)?[A-Za-z0-9_.<>?]+\s+GetEditValue\s*\(",
        source,
    ):
        issues.append(
            {
                "code": "generated_get_edit_value_helper_detected",
                "severity": "error",
                "message": "Do not generate a generic GetEditValue helper for ordinary target-style screen code.",
            }
        )
    if re.search(
        r"\b(?:private|protected|public|internal)?\s*(?:static\s+)?[A-Za-z0-9_.<>?]+\s+GetColumnText\s*\(",
        source,
    ):
        issues.append(
            {
                "code": "generated_get_column_text_helper_detected",
                "severity": "error",
                "message": "Do not generate a generic GetColumnText helper for ordinary target-style screen code.",
            }
        )
    if re.search(r"\b(?:private|protected|public|internal)?\s*(?:static\s+)?void\s+SetVisibleIndex\s*\(", source):
        issues.append(
            {
                "code": "generated_set_visible_index_helper_detected",
                "severity": "error",
                "message": "Do not generate a runtime SetVisibleIndex helper when the target style expects explicit Designer columns and direct column property assignments.",
            }
        )
    generated_helper_patterns = {
        "generated_call_detail_query_helper_detected": (
            r"\b(?:private|protected|public|internal)?\s*(?:static\s+)?void\s+CallDetailQuery\s*\(",
            "Do not invent CallDetailQuery for target focused-row detail handling; use the target event shape or proven fnFocusedRowChanged/CallViewQuery pattern.",
        ),
        "generated_default_search_values_helper_detected": (
            r"\b(?:private|protected|public|internal)?\s*(?:static\s+)?void\s+SetDefaultSearchValues\s*\(",
            "Do not invent SetDefaultSearchValues for ordinary target screens; set default control values directly in Load/Clear unless a target file proves that helper.",
        ),
        "generated_list_column_layout_helper_detected": (
            r"\b(?:private|protected|public|internal)?\s*(?:static\s+)?void\s+ApplyListColumnLayout\s*\(",
            "Do not invent ApplyListColumnLayout/runtime column-layout helpers; preserve Designer columns and use narrow direct assignments only when required.",
        ),
        "generated_basis_year_helper_detected": (
            r"\b(?:private|protected|public|internal)?\s*(?:static\s+)?string\s+GetDerivedYear\s*\(",
            "Do not invent GetDerivedYear for date inputs; read the date control near the procedure call in the same style as existing screens.",
        ),
        "generated_customer_like_helper_detected": (
            r"\b(?:private|protected|public|internal)?\s*(?:static\s+)?string\s+GetEntityCodeLike\s*\(",
            "Do not invent GetEntityCodeLike wrappers; keep simple LIKE parameter composition near the SP call unless target code already has the helper.",
        ),
        "generated_validate_search_helper_detected": (
            r"\b(?:private|protected|public|internal)?\s*(?:static\s+)?bool\s+ValidateSearch\s*\(",
            "Do not add generic ValidateSearch helpers for simple search screens; use existing required-control behavior or proven local validation patterns.",
        ),
    }
    for code, (pattern, message) in generated_helper_patterns.items():
        if re.search(pattern, source):
            issues.append({"code": code, "severity": "error", "message": message})
    if re.search(r"for\s*\(\s*int\s+\w+\s*=\s*1\s*;\s*\w+\s*<=\s*12\s*;[\s\S]{0,500}\.VisibleIndex\s*=", source):
        issues.append(
            {
                "code": "generated_month_column_visibleindex_loop_detected",
                "severity": "error",
                "message": "Do not lay out monthly AMT columns through a runtime VisibleIndex loop; preserve explicit Designer column order.",
            }
        )
    if "EntityLookupDialog" in source and re.search(r"DialogResult\.Yes\s*\|\|\s*di\s*==\s*DialogResult\.OK|DialogResult\.OK\s*\|\|\s*di\s*==\s*DialogResult\.Yes", source):
        issues.append(
            {
                "code": "popcust_dialogresult_yes_or_ok_detected",
                "severity": "error",
                "message": "Entity lookup selection should follow the target popup contract; do not broaden it to DialogResult.Yes || DialogResult.OK without source evidence.",
            }
        )
    mojibake_tokens = (
        "\u6e72\uacd7",
        "\u907a\x80\u81fe",
        "?\uc497",
        "\u6028\uafa9",
        "\u6028\uc889",
        "\u8b70\uace0",
        "\uf9cd\u317c",
        "\u8a98\uba83",
    )
    if any(token in source for token in mojibake_tokens):
        issues.append(
            {
                "code": "mojibake_korean_literal_detected",
                "severity": "error",
                "message": "Generated C# contains mojibake Korean text; preserve Korean captions/messages as readable UTF-8 text.",
            }
        )
    if re.search(r'\[\s*"[^"]+"\s*\]\s*==\s*DBNull\.Value\s*\?', source):
        issues.append(
            {
                "code": "generated_dbnull_ternary_row_value_detected",
                "severity": "error",
                "message": "Do not generate DBNull ternary wrappers around focused-row values for ordinary target detail lookups; follow target direct row-value access unless source proves otherwise.",
            }
        )
    dbnull_variant_patterns = {
        "generated_convert_isdbnull_ternary_detected": r"Convert\.IsDBNull\s*\([^)]+\)\s*\?",
        "generated_datarow_isnull_ternary_detected": r"\.\s*IsNull\s*\(\s*\"[^\"]+\"\s*\)\s*\?",
        "generated_is_dbnull_check_detected": r"\bis\s+DBNull\b",
        "generated_focused_cell_dbnull_check_detected": r"GetFocusedRowCellValue\s*\([^)]+\)\s*==\s*DBNull\.Value",
    }
    for code, pattern in dbnull_variant_patterns.items():
        if re.search(pattern, source):
            issues.append(
                {
                    "code": code,
                    "severity": "error",
                    "message": "Do not generate alternate DBNull/DataRow null wrappers for ordinary matched-source C# row access.",
                }
            )
    if re.search(r"_selectType\s*==\s*SelectType\.DETAIL\s*\?", source):
        issues.append(
            {
                "code": "generated_selecttype_detail_ternary_detected",
                "severity": "error",
                "message": "Do not generate _selectType == SelectType.DETAIL ternary parameter routing; keep select/detail parameters explicit and same-shape with target procedure calls.",
            }
        )
    if re.search(r"CallSelectProcedure\s*\([^)]*,\s*string\s+_[A-Za-z0-9_]+\s*=\s*\"(?:%|)\"", source):
        issues.append(
            {
                "code": "generated_callselect_string_literal_default_detected",
                "severity": "error",
                "message": "Do not generate CallSelectProcedure string parameters defaulting to empty string or '%'; pass verified caller values explicitly.",
            }
        )
    if re.search(r"CallSelectProcedure\s*\([\s\S]{0,300}\+\s*\"%\"", source):
        issues.append(
            {
                "code": "generated_callselect_inline_wildcard_argument_detected",
                "severity": "error",
                "message": "Do not generate CallSelectProcedure call-site arguments that inline LIKE wildcards such as txtFilter.Text + \"%\" or rowValue + \"%\"; pass raw values and let the stored procedure own LIKE shaping.",
            }
        )
    if re.search(r"\b[A-Za-z_][A-Za-z0-9_]*(?:_?code)\s*=\s*[^;\n]+\+\s*\"%\"\s*;", source, re.IGNORECASE) or re.search(
        r"\b[A-Za-z_][A-Za-z0-9_]*(?:_?code)\s*=\s*\"%\"\s*;",
        source,
        re.IGNORECASE,
    ):
        issues.append(
            {
                "code": "generated_csharp_like_wildcard_shaping_detected",
                "severity": "error",
                "message": "Do not generate C# wildcard shaping such as entityCode = entityCode + \"%\" or filterCode = \"%\" for migration SELECT parameters; pass raw values and handle LIKE defaults in the stored procedure.",
            }
        )
    if re.search(
        r"if\s*\(\s*(ymd[A-Za-z0-9_]*)\.EditValue\s*==\s*null\s*\)\s*(?:\{\s*)?\1\.SetToDay\s*\(\s*0\s*\)",
        source,
    ):
        issues.append(
            {
                "code": "generated_dateedit_settoday_null_default_detected",
                "severity": "error",
                "message": "Do not generate DateEdit null guards that silently call SetToDay(0) inside search/procedure paths; initialize in Load/Clear or validate before execution.",
            }
        )
    if re.search(r'new\s+DbParameter\s*\(\s*"@(?:DERIVED_YEAR|BASE_YEAR|BOUNDARY_DATE)"\s*,\s*ymd[A-Za-z0-9_]*\.DateTime\.Year\.ToString\s*\(\s*\)\s*\)', source) or re.search(
        r'new\s+DbParameter\s*\(\s*"@(?:DERIVED_MONTH|DERIVED_YEAR|BASE_YEAR|BOUNDARY_DATE)"\s*,\s*DateTime\.Now\.[A-Za-z]+\.ToString\s*\(',
        source,
    ):
        issues.append(
            {
                "code": "generated_dateedit_year_or_now_parameter_shaping_detected",
                "severity": "error",
                "message": "Do not generate C# parameters that split a date input into @DERIVED_YEAR/@DERIVED_MONTH/@BASE_YEAR/@BOUNDARY_DATE with DateTime.Year.ToString() or DateTime.Now; pass the raw date value and let the stored procedure derive related values.",
            }
        )
    if re.search(r"\bgrd[A-Za-z0-9_]*\.DataSource\s*=\s*null\s*;", source):
        issues.append(
            {
                "code": "generated_direct_grid_datasource_null_reset_detected",
                "severity": "error",
                "message": "Do not generate direct grd*.DataSource = null resets for target-wrapper screens; use the reset helper proven by active target evidence.",
            }
        )
    if any(
        re.search(pattern, source)
        for pattern in (
            r"new\s+DateTime\s*\(\s*DateTime\.Now\.Year\s*,\s*DateTime\.Now\.Month\s*,\s*1\s*\)\s*\.AddDays\s*\(\s*-1\s*\)",
            r"DateTime\s+[A-Za-z_][A-Za-z0-9_]*\s*=\s*DateTime\.Now\.AddDays\s*\(\s*1\s*-\s*DateTime\.Now\.Day\s*\)\s*\.AddDays\s*\(\s*-1\s*\)",
            r"new\s+DateTime\s*\([\s\S]{0,120}DateTime\.DaysInMonth\s*\(",
            r"\.AddMonths\s*\(\s*1\s*\)\s*\.AddDays\s*\(\s*-1\s*\)",
        )
    ):
        issues.append(
            {
                "code": "generated_month_end_datetime_block_detected",
                "severity": "error",
                "message": "Do not generate ad hoc month-end DateTime construction blocks in migrated screen code unless matched target evidence proves that exact pattern.",
            }
        )
    if re.search(r"new\s+DateTime\s*\(\s*ymd[A-Za-z0-9_]*\.DateTime\.Year\s*-\s*1\s*,\s*12\s*,\s*31\s*\)", source):
        issues.append(
            {
                "code": "generated_year_end_datetime_block_detected",
                "severity": "error",
                "message": "Do not generate ad hoc year-end DateTime construction blocks from DateEdit values unless matched target evidence proves that exact pattern.",
            }
        )
    if re.search(r"\(\s*ymd[A-Za-z0-9_]*\.DateTime\.Year\s*-\s*1\s*\)\s*\.ToString\s*\(\s*\"0000\"\s*\)\s*\+\s*\"1231\"", source):
        issues.append(
            {
                "code": "generated_year_end_string_boundary_detected",
                "severity": "error",
                "message": "Do not generate year-end boundary strings such as (ymdInput.DateTime.Year - 1).ToString(\"0000\") + \"1231\" in C#; let the stored procedure own derived date boundaries.",
            }
        )
    if re.search(r"\?\?\s*\"%\"", source):
        issues.append(
            {
                "code": "generated_percent_null_coalesce_detected",
                "severity": "error",
                "message": "Do not generate null-coalescing wildcard defaults such as _entityCode ?? \"%\" for migration C# unless the target code proves that pattern.",
            }
        )
    if re.search(r"btn[A-Z0-9_]*\.EditValue\s*==\s*null\s*\?\s*string\.Empty", source):
        issues.append(
            {
                "code": "generated_buttonedit_null_stringempty_ternary_detected",
                "severity": "error",
                "message": "Do not generate ButtonEdit null/string.Empty ternary extraction for ordinary search parameters; use the target's direct Text/EditValue style.",
            }
        )
    if re.search(r"string\s+[A-Za-z_][A-Za-z0-9_]*\s*=\s*Convert\.ToString\s*\(\s*rad[A-Z0-9_]*\.EditValue\s*\)", source):
        issues.append(
            {
                "code": "generated_radio_convert_tostring_local_detected",
                "severity": "error",
                "message": "Do not generate extra Convert.ToString(rad*.EditValue) local variables for SP parameters; pass the target control value in the existing style.",
            }
        )
    if re.search(
        r"(?:[A-Za-z_][A-Za-z0-9_]*\.)+(?:u_)?DateEdit\s+txt[A-Z0-9_]*(?:NAME|TEXT)\b",
        source,
        re.IGNORECASE,
    ):
        issues.append(
            {
                "code": "text_name_field_generated_as_dateedit",
                "severity": "error",
                "message": "Name/display fields such as txtDisplayName should use a text edit, not u_DateEdit.",
            }
        )

    numeric_column_names = set()
    for column_name in re.findall(r"this\.(col(?:List|Detail|[A-Za-z0-9]+)_([A-Z0-9_]+))\.", source):
        full_name, field_name = column_name
        if _is_numeric_grid_field_name(field_name):
            numeric_column_names.add(full_name)
    numeric_column_names.update(
        re.findall(
            r"this\.(col(?:List|Detail|[A-Za-z0-9]+)_[A-Z0-9_]+)\.DisplayFormat\.FormatType\s*=\s*DevExpress\.Utils\.FormatType\.Numeric",
            source,
        )
    )
    for match in re.finditer(
        r'this\.(col(?:List|Detail|[A-Za-z0-9]+)_[A-Z0-9_]+)\.DisplayFormat\.FormatString\s*=\s*"([^"]+)"',
        source,
    ):
        if _display_format_string_looks_numeric(match.group(2)):
            numeric_column_names.add(match.group(1))
    for column_name in sorted(numeric_column_names):
        spin_repository_match = re.search(
            rf"this\.{re.escape(column_name)}\.ColumnEdit\s*=\s*this\.(rpsSpin[A-Za-z0-9_]*)\s*;",
            source,
        )
        has_spin_repository = bool(spin_repository_match)
        has_column_numeric_display = bool(
            re.search(rf"this\.{re.escape(column_name)}\.DisplayFormat\.Format(?:String|Type)\s*=", source)
        )
        if not has_spin_repository:
            issues.append(
                {
                    "code": "numeric_grid_column_missing_spin_repository",
                    "severity": "error",
                    "message": f"Numeric GridColumn {column_name} must use a RepositoryItemSpinEdit via ColumnEdit, not column DisplayFormat-only output.",
                }
            )
        else:
            repository_name = spin_repository_match.group(1)
            repository_declared = bool(
                re.search(
                    rf"(?:private\s+)?(?:DevExpress\.XtraEditors\.Repository\.)?RepositoryItemSpinEdit\s+{re.escape(repository_name)}\s*;",
                    source,
                )
            )
            repository_initialized = bool(
                re.search(
                    rf"this\.{re.escape(repository_name)}\s*=\s*new\s+(?:DevExpress\.XtraEditors\.Repository\.)?RepositoryItemSpinEdit\s*\(",
                    source,
                )
            )
            if not repository_declared or not repository_initialized:
                issues.append(
                    {
                        "code": "numeric_grid_spin_repository_not_declared_or_initialized",
                        "severity": "error",
                        "message": (
                            f"Numeric GridColumn {column_name} references {repository_name}, but that repository must be "
                            "declared and initialized as RepositoryItemSpinEdit in Designer-style code."
                        ),
                    }
                )
        if has_column_numeric_display:
            issues.append(
                {
                    "code": "numeric_grid_column_displayformat_detected",
                    "severity": "error",
                    "message": f"Numeric GridColumn {column_name} should not carry GridColumn.DisplayFormat as the primary numeric formatting path; use a Spin repository control.",
                }
            )

    passed = not any(issue["severity"] == "error" for issue in issues)
    metadata = {
        "harness": "pb-to-csharp-migration-harness",
        "status": "passed" if passed else "blocked",
        "issues": issues,
        "program_key": normalized_program_key,
        "fallback_program_key": normalized_fallback_program_key,
        "expected_style_program_key": expected_style_program_key,
        "require_author_tagged_evidence": bool(require_author_tagged_evidence),
        "profile_consumption": profile_consumption,
        "program_form_contract": program_form_contract,
        "designer_owned_ui_contract": designer_owned_ui_contract,
        "result_field_contract": result_field_contract,
        "primary_style_evidence_paths": primary_paths,
        "excluded_paths": excluded,
        "author_tagged_generation_recipe": (
            AUTHOR_TAGGED_CSHARP_STYLE_BASELINE["positive_generation_recipe"]
            if require_author_tagged_evidence
            else {}
        ),
        "column_style_contract": (
            "Generated grid columns must use explicit target-style names, Designer/AddRange registration, "
            "and RepositoryItemSpinEdit ColumnEdit for numeric AMT/QTY/UNP/WGT/PRICE/RATE/COST/TOTAL columns instead of GridColumn DisplayFormat."
        ),
        "token_optimizer_status": "passthrough",
        "token_optimizer_status_reason": (
            "Generated C# source is contract-sensitive style evidence and was not compressed."
        ),
    }
    return HarnessResult(
        success=passed,
        stdout=json.dumps({"status": metadata["status"], "issue_count": len(issues)}, ensure_ascii=False, sort_keys=True),
        stderr="" if passed else "Generated C# style verification blocked by grid column issues.",
        exit_code=0 if passed else 1,
        metadata=metadata,
    )

def verify_pb_migration_sp_generation_contract(
    sql_text: str,
    *,
    source_evidence: Any = None,
    allow_inferred_draft: bool = False,
    profile_evidence: Any = None,
) -> HarnessResult:
    """Check that generated SELECT/SAVE SP work is evidence-gated before it is presented as migration output."""
    sql = str(sql_text or "")
    issues: List[Dict[str, Any]] = []
    profile_context, profile_issues = _consume_profile_evidence(profile_evidence, "sql")
    issues.extend(profile_issues)
    if not profile_issues:
        applied_issues, profile_context = _apply_consumed_profile_rules(
            _strip_sql_literals_and_comments_for_pb_contract(sql),
            profile_context,
            domain="sql",
            procedure_name=_extract_sp_procedure_name(sql),
        )
        issues.extend(applied_issues)
    profile_consumption = dict(
        profile_context.get("consumption", profile_context)
        if isinstance(profile_context, dict)
        else {}
    )
    upper_unprotected = _strip_sql_literals_and_comments_for_pb_contract(sql).upper()
    comments_stripped = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    comments_stripped = re.sub(r"--.*?$", " ", comments_stripped, flags=re.MULTILINE)
    upper_comments_stripped = comments_stripped.upper()
    normalized_source_evidence: List[Dict[str, Any]] = []
    unstructured_source_evidence = False
    if isinstance(source_evidence, dict):
        normalized_source_evidence = [dict(source_evidence)]
    elif isinstance(source_evidence, (list, tuple)):
        normalized_source_evidence = [dict(item) for item in source_evidence if isinstance(item, dict)]
    elif source_evidence is True:
        unstructured_source_evidence = True
    elif source_evidence:
        unstructured_source_evidence = True
    allowed_evidence_kinds = {"pb_srd_sql", "existing_sp", "pasted_sql", "db_schema", "approved_inferred_draft"}
    accepted_source_evidence = []
    for item in normalized_source_evidence:
        kind = str(item.get("kind") or "")
        if kind not in allowed_evidence_kinds:
            continue
        path_or_summary = bool(str(item.get("path") or item.get("summary") or "").strip())
        path_only = bool(str(item.get("path") or "").strip())
        object_name = bool(str(item.get("object") or "").strip())
        hash_or_definition = bool(
            str(
                item.get("sha256")
                or item.get("definition_hash")
                or item.get("definition_path")
                or item.get("definition_text")
                or ""
            ).strip()
        )
        verified = bool(item.get("verified"))
        if kind == "existing_sp":
            has_detail = verified and (object_name or path_only) and hash_or_definition
        elif kind == "approved_inferred_draft":
            has_detail = bool(item.get("approved") and path_or_summary)
        elif kind == "db_schema":
            has_detail = path_or_summary or hash_or_definition or (object_name and verified)
        else:
            has_detail = path_or_summary or hash_or_definition
        if has_detail:
            accepted_source_evidence.append(item)

    if unstructured_source_evidence:
        issues.append(
            {
                "code": "unstructured_source_evidence_flag",
                "severity": "error",
                "message": "source_evidence=True is not enough. Record structured evidence with kind plus path/object/summary.",
            }
        )
    if not sql.strip():
        issues.append({"code": "missing_sql_text", "severity": "error", "message": "No SQL text was provided."})
    header_match = SP_METADATA_HEADER_PATTERN.search(sql)
    if sql.strip() and not header_match:
        issues.append(
            {
                "code": "missing_sp_metadata_header",
                "severity": "error",
                "message": (
                    "Target-style procedure output must include the standard metadata comment block "
                    "immediately above CREATE/ALTER PROCEDURE: AUTHOR, CREATE DATE, and DESCRIPTION."
                ),
            }
        )
    elif header_match:
        header_description = str(header_match.group("description") or "").strip()
        procedure_name = _extract_sp_procedure_name(sql)
        expected_descriptions = [
            str(item.get(key) or "").strip()
            for item in normalized_source_evidence
            for key in ("program_description", "screen_name", "program_name", "description")
            if str(item.get(key) or "").strip()
        ]
        if re.search(r"<[^>]+>|TODO|SAMPLE|PROGRAM\s*NAME", header_description, flags=re.IGNORECASE):
            issues.append(
                {
                    "code": "sp_metadata_description_placeholder",
                    "severity": "error",
                    "message": "DESCRIPTION must be the target program/screen description, not a placeholder or sample text.",
                }
            )
        description_mismatch = bool(expected_descriptions) and not any(
            expected in header_description or header_description in expected
            for expected in expected_descriptions
        )
        if description_mismatch:
            issues.append(
                {
                    "code": "sp_metadata_description_mismatch",
                    "severity": "error",
                    "message": "DESCRIPTION must match the target program/screen name recorded in source evidence.",
                    "expected_descriptions": expected_descriptions,
                    "actual_description": header_description,
                }
            )
        if description_mismatch or re.search(
            r"\b(?:COPIED|UNRELATED)\b",
            header_description,
            flags=re.IGNORECASE,
        ):
            issues.append(
                {
                    "code": "sp_metadata_description_not_program_specific",
                    "severity": "error",
                    "message": "Do not reuse another program's DESCRIPTION; set it for the target program/screen.",
                    "procedure_name": procedure_name,
                    "actual_description": header_description,
                }
            )
    if sql.strip() and not accepted_source_evidence:
        issues.append(
            {
                "code": "inferred_draft_not_complete" if allow_inferred_draft else "missing_pb_or_db_source_evidence_for_sp_generation",
                "severity": "error",
                "message": (
                    "Do not present a full migration SELECT/SAVE procedure as completed unless PB/DataWindow SQL, "
                    "verified existing SP, pasted SQL, DB schema, or explicit user-approved inferred draft evidence is recorded."
                ),
            }
        )
    if "@WORKTYPE" not in upper_unprotected:
        issues.append(
            {
                "code": "missing_worktype_contract",
                "severity": "error",
                "message": "Migration SELECT/SAVE procedures must expose the @WORKTYPE branch contract.",
            }
        )
    if re.search(r"@WORKTYPE\s+VARCHAR\s*\(\s*20\s*\)\s*=\s*''", upper_comments_stripped):
        issues.append(
            {
                "code": "worktype_empty_string_default_detected",
                "severity": "error",
                "message": "Target-style procedures do not default @WORKTYPE to an empty string; use NULL or the verified required parameter contract.",
            }
        )
    if re.search(r"@[A-Z][A-Z0-9_]*\s+(?:N?VARCHAR|N?CHAR)\s*\([^)]*\)\s*=\s*'%'", upper_comments_stripped):
        issues.append(
            {
                "code": "wildcard_filter_parameter_default_detected",
                "severity": "error",
                "message": "Do not default text filter parameters to '%' unless verified target procedure evidence uses that exact contract.",
            }
        )
    if re.search(r"@[A-Z][A-Z0-9_]*\s+(?:N?VARCHAR|N?CHAR)\s*\([^)]*\)\s*=\s*'(?:T|1)'", upper_comments_stripped):
        issues.append(
            {
                "code": "business_flag_parameter_default_detected",
                "severity": "error",
                "message": "Do not default business selector parameters to generated literals unless verified target procedure evidence uses them.",
            }
        )
    signature_match = re.search(
        r"(?:CREATE\s+(?:OR\s+ALTER\s+)?|ALTER\s+)PROCEDURE[\s\S]*?\bAS\b",
        upper_comments_stripped,
    )
    procedure_parameters: List[str] = []
    if signature_match:
        signature_text = signature_match.group(0)
        procedure_parameters = sorted(
            set(
                re.findall(
                    r"@([A-Z][A-Z0-9_]*)\s+(?:\[[^\]]+\]|[A-Z][A-Z0-9_]*)(?:\s*\.\s*(?:\[[^\]]+\]|[A-Z][A-Z0-9_]*))?(?:\s*\([^)]*\))?",
                    signature_text,
                )
            )
        )
        caller_parameter_names: set[str] = set()
        for item in normalized_source_evidence:
            for key in (
                "caller_parameters",
                "db_parameters",
                "csharp_db_parameters",
                "procedure_call_parameters",
                "sp_call_parameters",
            ):
                values = item.get(key)
                if isinstance(values, str):
                    values = re.findall(r"@[A-Za-z][A-Za-z0-9_]*", values)
                if isinstance(values, (list, tuple, set)):
                    for value in values:
                        match = re.search(r"@?([A-Za-z][A-Za-z0-9_]*)", str(value or ""))
                        if match:
                            caller_parameter_names.add(match.group(1).upper())
        if caller_parameter_names:
            non_caller_params = [name for name in procedure_parameters if name not in caller_parameter_names]
            if non_caller_params:
                issues.append(
                    {
                        "code": "non_caller_procedure_parameter_detected",
                        "severity": "error",
                        "message": (
                            "Generated SP parameters must match values actually sent by the C# caller. "
                            "SP-internal calculation/helper values must be local DECLARE variables assigned with SET."
                        ),
                        "parameters": [f"@{name}" for name in non_caller_params],
                        "caller_parameters": [f"@{name}" for name in sorted(caller_parameter_names)],
                    }
                )
        helper_date_params = sorted(
            set(
                re.findall(
                    r"@(DERIVED_YEAR|DERIVED_MONTH|BASE_YEAR|BOUNDARY_DATE)\s+(?:\[[^\]]+\]|[A-Z][A-Z0-9_]*)(?:\s*\.\s*(?:\[[^\]]+\]|[A-Z][A-Z0-9_]*))?(?:\s*\([^)]*\))?",
                    signature_text,
                )
            )
        )
        if helper_date_params:
            issues.append(
                {
                    "code": "derived_date_helper_parameter_detected",
                    "severity": "error",
                    "message": (
                        "Do not expose derived helper date values such as @DERIVED_YEAR, @DERIVED_MONTH, @BASE_YEAR, or @BOUNDARY_DATE "
                        "as generated procedure parameters. Accept the raw target-style date input, then use local DECLARE and SET "
                        "inside the procedure when derived values are needed."
                    ),
                    "parameters": [f"@{name}" for name in helper_date_params],
                }
            )
    if re.search(
        r"IF\s*\(?\s*ISNULL\s*\(\s*@(INPUT_DATE|DERIVED_YEAR|DERIVED_MONTH|BASE_YEAR|BOUNDARY_DATE)\s*,\s*''\s*\)",
        upper_comments_stripped,
    ):
        issues.append(
            {
                "code": "if_isnull_date_derivation_block_detected",
                "severity": "error",
                "message": (
                    "Do not generate IF ISNULL(...) guard/default blocks for date-derived SP values. "
                    "Use local DECLARE plus SET for derived variables, and avoid source-unbacked fallback branches."
                ),
            }
        )
    if re.search(
        r"SET\s+@(DERIVED_YEAR|DERIVED_MONTH|BASE_YEAR|BOUNDARY_DATE)\s*=\s*(?:LEFT\s*\(\s*@INPUT_DATE|SUBSTRING\s*\(\s*@INPUT_DATE|RIGHT\s*\(\s*'0'\s*\+|CONVERT\s*\(\s*VARCHAR\s*\(\s*[48]\s*\)\s*,\s*(?:YEAR|DATEADD|CONVERT))",
        upper_comments_stripped,
    ) and re.search(
        r"IF\s*\(?\s*(?:ISNULL\s*\(\s*@(INPUT_DATE|DERIVED_YEAR|DERIVED_MONTH|BASE_YEAR|BOUNDARY_DATE)|@(INPUT_DATE|DERIVED_YEAR|DERIVED_MONTH|BASE_YEAR|BOUNDARY_DATE)\s*(?:<>|=|>|<|>=|<=))",
        upper_comments_stripped,
    ):
        issues.append(
            {
                "code": "generated_if_wrapped_date_set_block_detected",
                "severity": "error",
                "message": (
                    "Do not wrap generated date SET assignments in IF/default logic. "
                    "If the target SP needs derived year/month/base dates, derive them as local variables with DECLARE and SET only."
                ),
            }
        )
    if re.search(
        r"IF\s*\(?\s*@(INPUT_DATE|DERIVED_YEAR|DERIVED_MONTH|BASE_YEAR|BOUNDARY_DATE)\s*(?:<>|=|>|<|>=|<=)[\s\S]{0,240}\bSET\s+@(DERIVED_YEAR|DERIVED_MONTH|BASE_YEAR|BOUNDARY_DATE)\s*=",
        upper_comments_stripped,
    ):
        issues.append(
            {
                "code": "generated_if_wrapped_date_set_block_detected",
                "severity": "error",
                "message": (
                    "Do not wrap generated date SET assignments in IF/default logic. "
                    "If the target SP needs derived year/month/base dates, derive them as local variables with DECLARE and SET only."
                ),
            }
        )
    if re.search(r"SET\s+@WORKTYPE\s*=\s*ISNULL\s*\(", upper_comments_stripped):
        issues.append(
            {
                "code": "worktype_isnull_normalization_detected",
                "severity": "error",
                "message": "Do not add SET @WORKTYPE = ISNULL(...) normalization in generated KH-style SP output.",
            }
        )
    if re.search(r"SET\s+@[A-Z0-9_]+\s*=\s*\(\s*CASE\s+WHEN\s+ISNULL\s*\(", upper_comments_stripped):
        issues.append(
            {
                "code": "case_isnull_parameter_normalization_detected",
                "severity": "error",
                "message": "Do not add generated CASE/ISNULL parameter normalization blocks unless verified target SP evidence already uses that pattern.",
            }
        )
    parameter_normalization_patterns = {
        "set_isnull_parameter_normalization_detected": r"SET\s+@[A-Z0-9_]+\s*=\s*ISNULL\s*\(",
        "select_isnull_parameter_normalization_detected": r"SELECT\s+@[A-Z0-9_]+\s*=\s*ISNULL\s*\(",
        "set_coalesce_parameter_normalization_detected": r"(?:SET|SELECT)\s+@[A-Z0-9_]+\s*=\s*COALESCE\s*\(",
        "set_nullif_parameter_normalization_detected": r"(?:SET|SELECT)\s+@[A-Z0-9_]+\s*=\s*NULLIF\s*\(",
        "if_isnull_parameter_normalization_detected": r"IF\s+ISNULL\s*\(\s*@[A-Z0-9_]+",
        "trim_parameter_normalization_detected": r"(?:SET|SELECT)\s+@[A-Z0-9_]+\s*=\s*(?:LTRIM|RTRIM)\s*\(",
    }
    for code, pattern in parameter_normalization_patterns.items():
        if re.search(pattern, upper_comments_stripped):
            issues.append(
                {
                    "code": code,
                    "severity": "error",
                    "message": "Do not add generated parameter normalization blocks unless verified target SP evidence already uses that exact pattern.",
                }
            )
    if re.search(r"(^|[;\s])WITH\s+(?:\[[^\]]+\]|[A-Z0-9_]+)\s+AS\s*\(", upper_unprotected):
        issues.append(
            {
                "code": "cte_in_generated_sp",
                "severity": "error",
                "message": "Do not introduce CTEs in migration SP generation by default.",
            }
        )
    if re.search(r"SELECT\s+TOP\s*\(?\s*0\s*\)?[\s\S]{0,800}(?:CAST|CONVERT|TRY_CONVERT)\s*\(", upper_unprotected):
        issues.append(
            {
                "code": "schema_only_select_top_0_fallback_in_generated_sp",
                "severity": "error",
                "message": "Do not add source-unbacked SELECT TOP 0/SELECT TOP (0) CAST/CONVERT/TRY_CONVERT(...) schema-only fallback blocks to migration SP output.",
            }
        )
    if re.search(r"#[A-Z0-9_]+", upper_unprotected):
        issues.append(
            {
                "code": "temp_table_in_generated_sp",
                "severity": "error",
                "message": "Do not introduce # temporary tables in migration SP generation by default.",
            }
        )
    if "MERGE " in upper_unprotected:
        issues.append(
            {
                "code": "merge_in_generated_sp",
                "severity": "error",
                "message": "Do not introduce MERGE in migration SP generation by default.",
            }
        )
    if "NOT EXISTS" in upper_unprotected:
        issues.append(
            {
                "code": "not_exists_in_generated_sp",
                "severity": "error",
                "message": "Do not introduce NOT EXISTS in migration SP generation by default.",
            }
        )
    if _pb_contract_contains_if_exists_where_subquery(upper_unprotected):
        issues.append(
            {
                "code": "if_exists_where_subquery_in_generated_sp",
                "severity": "error",
                "message": (
                    "Do not put a nested subquery under WHERE inside IF EXISTS guards in migration SP generation by default. "
                    "Use direct JOIN/derived-table style or record explicit source evidence."
                ),
            }
        )

    passed = not any(issue["severity"] == "error" for issue in issues)
    metadata = {
        "harness": "pb-to-csharp-migration-harness",
        "status": "passed" if passed else "blocked",
        "source_evidence": accepted_source_evidence,
        "source_evidence_count": len(accepted_source_evidence),
        "allow_inferred_draft": bool(allow_inferred_draft),
        "profile_consumption": profile_consumption,
        "issues": issues,
        "sp_generation_contract": (
            "Full migration SP output must be backed by structured PB/DataWindow SQL, existing SP, pasted SQL, DB evidence, "
            "or an explicit approved inferred-draft marker; object-only existing_sp evidence is not enough. SQL style verification remains separate."
        ),
        "token_optimizer_status": "passthrough",
        "token_optimizer_status_reason": "SQL/stored procedure text is contract-sensitive and was not compressed.",
    }
    return HarnessResult(
        success=passed,
        stdout=json.dumps({"status": metadata["status"], "issue_count": len(issues)}, ensure_ascii=False, sort_keys=True),
        stderr="" if passed else "SP generation contract verification blocked by missing evidence or style issues.",
        exit_code=0 if passed else 1,
        metadata=metadata,
    )


def _pb_contract_contains_if_exists_where_subquery(upper_unprotected_sql: str) -> bool:
    for block in _pb_contract_extract_if_exists_blocks(upper_unprotected_sql):
        where_index = _pb_contract_find_top_level_keyword(block, "WHERE")
        if where_index < 0:
            continue
        where_text = block[where_index:]
        subquery_patterns = [
            r"\b(?:NOT\s+)?EXISTS\s*\(\s*SELECT\b",
            r"\b(?:NOT\s+)?IN\s*\(\s*SELECT\b",
            r"(?:=|<>|!=|<=|>=|<|>)\s*\(\s*SELECT\b",
        ]
        if any(re.search(pattern, where_text, flags=re.IGNORECASE | re.DOTALL) for pattern in subquery_patterns):
            return True
    return False


def _pb_contract_extract_if_exists_blocks(upper_unprotected_sql: str) -> List[str]:
    blocks: List[str] = []
    pattern = re.compile(r"\bIF\s+EXISTS\s*\(", flags=re.IGNORECASE)
    for match in pattern.finditer(upper_unprotected_sql):
        open_index = upper_unprotected_sql.find("(", match.start())
        if open_index < 0:
            continue
        close_index = _pb_contract_find_matching_parenthesis(upper_unprotected_sql, open_index)
        if close_index > open_index:
            blocks.append(upper_unprotected_sql[open_index + 1 : close_index])
    return blocks


def _pb_contract_find_top_level_keyword(text: str, keyword: str) -> int:
    depth = 0
    keyword_re = re.compile(rf"\b{re.escape(keyword)}\b", flags=re.IGNORECASE)
    for index, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif depth == 0 and keyword_re.match(text, index):
            return index
    return -1


def _pb_contract_find_matching_parenthesis(text: str, open_index: int) -> int:
    depth = 0
    for index in range(open_index, len(text)):
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1

def verify_pb_migration_sp_with_sql_formatting(
    original_sql_text: str,
    formatted_sql_text: str,
    *,
    source_evidence: Any = None,
    allow_inferred_draft: bool = False,
    cte_temp_table_reason: str = "",
    profile_evidence: Any = None,
) -> HarnessResult:
    """Verify migration SP evidence and host-local SQL formatting style as one composed gate."""
    from src.skills.sql_formatting_style import verify_sql_formatting_style

    contract_result = verify_pb_migration_sp_generation_contract(
        formatted_sql_text,
        source_evidence=source_evidence,
        allow_inferred_draft=allow_inferred_draft,
        profile_evidence=profile_evidence,
    )
    style_result = verify_sql_formatting_style(
        original_sql_text,
        formatted_sql_text,
        cte_temp_table_reason=cte_temp_table_reason,
    )
    success = bool(contract_result.success and style_result.success)
    metadata = {
        "harness": "pb-to-csharp-migration-harness",
        "status": "passed" if success else "blocked",
        "sp_generation_contract": contract_result.metadata,
        "sql_formatting_style": style_result.metadata,
        "token_optimizer_status": "passthrough",
        "token_optimizer_status_reason": "SQL/stored procedure text is contract-sensitive and was not compressed.",
    }
    return HarnessResult(
        success=success,
        stdout=json.dumps(
            {
                "status": metadata["status"],
                "sp_contract_status": contract_result.metadata.get("status"),
                "sql_formatting_status": style_result.metadata.get("mechanical_checks", {}).get("status"),
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        stderr="" if success else "Composed PB migration SP and SQL formatting verification failed.",
        exit_code=0 if success else 1,
        metadata=metadata,
    )


def orchestrate_pb_migration_validation(
    *,
    csharp_source_text: str,
    designer_source_text: str,
    original_sql_text: str,
    formatted_sql_text: str,
    profile_id: str,
    profile_version: str,
    profile_hash: str,
    program_key: str = "",
    form_class: str = "",
    csharp_source_role: str = "code-behind",
    runtime_dynamic_ui_evidence: Any = None,
    result_fields: Iterable[str] | None = None,
    source_evidence: Any = None,
    allow_inferred_draft: bool = False,
    cte_temp_table_reason: str = "",
) -> HarnessResult:
    """Run the fail-closed offline profile, C#, SP, and formatting validation contract."""
    required_order = [
        "load-profile",
        "validate-csharp",
        "validate-sp",
        "formatting-evidence",
    ]
    stages: List[Dict[str, Any]] = []
    evidence: Dict[str, Any] = {}

    def finish(success: bool) -> HarnessResult:
        completed_order = [stage["name"] for stage in stages]
        profile_consumptions = [
            evidence.get("csharp", {}).get("profile_consumption", {}),
            evidence.get("sp", {}).get("profile_consumption", {}),
        ]
        identities = {
            (
                str(item.get("profile_id") or ""),
                str(item.get("profile_version") or ""),
                str(item.get("profile_hash") or ""),
            )
            for item in profile_consumptions
            if item.get("consumed")
        }
        identity_match = bool(
            evidence.get("profile", {}).get("status") == "loaded"
            and (not profile_consumptions or len(identities) <= 1)
        )
        completion_allowed = bool(
            success
            and completed_order == required_order
            and identity_match
            and all(item.get("consumed") for item in profile_consumptions)
        )
        contract = {
            "contract_id": "offline-packaged-pb-migration-validation-v1",
            "required_stage_order": required_order,
            "completed_stage_order": completed_order,
            "stages": stages,
            "profile_identity_match": identity_match,
            "completion_allowed": completion_allowed,
            "database_execution_attempted": False,
            "database_execution_allowed": False,
            "failure_boundary": stages[-1]["name"] if stages and not completion_allowed else "",
        }
        metadata = {
            "harness": "pb-to-csharp-migration-harness",
            "operation": "orchestrated_offline_validation",
            "status": "passed" if completion_allowed else "blocked",
            "validation_contract": contract,
            "evidence": evidence,
            "token_optimizer_status": "passthrough",
            "token_optimizer_status_reason": "C#/SQL validation inputs remained exact.",
        }
        return HarnessResult(
            success=completion_allowed,
            stdout=json.dumps(
                {
                    "status": metadata["status"],
                    "completed_stage_order": completed_order,
                    "profile_identity_match": identity_match,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            stderr="" if completion_allowed else "Offline PB migration validation contract failed closed.",
            exit_code=0 if completion_allowed else 1,
            metadata=metadata,
        )

    loaded_profile = load_packaged_migration_profile(profile_id, profile_version, profile_hash)
    stages.append(
        {
            "name": "load-profile",
            "status": "passed" if loaded_profile.success else "blocked",
        }
    )
    evidence["profile"] = loaded_profile.metadata
    if not loaded_profile.success:
        return finish(False)

    csharp_result = verify_migration_generated_csharp_style(
        csharp_source_text,
        designer_source_text=designer_source_text,
        profile_evidence=loaded_profile,
        program_key=program_key,
        form_class=form_class,
        source_role=csharp_source_role,
        runtime_dynamic_ui_evidence=runtime_dynamic_ui_evidence,
        result_fields=result_fields,
        require_designer_companion=True,
    )
    stages.append(
        {
            "name": "validate-csharp",
            "status": "passed" if csharp_result.success else "blocked",
        }
    )
    evidence["csharp"] = csharp_result.metadata
    if not csharp_result.success:
        return finish(False)

    sp_result = verify_pb_migration_sp_generation_contract(
        formatted_sql_text,
        source_evidence=source_evidence,
        allow_inferred_draft=allow_inferred_draft,
        profile_evidence=loaded_profile,
    )
    stages.append(
        {
            "name": "validate-sp",
            "status": "passed" if sp_result.success else "blocked",
        }
    )
    evidence["sp"] = sp_result.metadata
    if not sp_result.success:
        return finish(False)

    from src.skills.sql_formatting_style import verify_sql_formatting_style

    formatting_result = verify_sql_formatting_style(
        original_sql_text,
        formatted_sql_text,
        cte_temp_table_reason=cte_temp_table_reason,
    )
    stages.append(
        {
            "name": "formatting-evidence",
            "status": "passed" if formatting_result.success else "blocked",
        }
    )
    evidence["formatting"] = formatting_result.metadata
    return finish(bool(formatting_result.success))


def build_datawindow_grid_layout(
    source_text: str,
    *,
    prefix: str = "",
    input_format: str = "list",
    table_name: str = "",
    purpose_name: str = "",
    grid_view_name: str = "",
) -> HarnessResult:
    """Build grid XML from SRD text and return contract-shaped evidence."""
    resolved_prefix = prefix or resolve_csharp_grid_column_prefix(
        input_format, table_name=table_name, purpose_name=purpose_name
    )
    grid_names = resolve_csharp_grid_control_names(input_format, table_name=table_name, purpose_name=purpose_name)
    resolved_grid_view_name = grid_view_name or grid_names["grid_view_name"]
    column_specs = extract_datawindow_column_specs(source_text, prefix=resolved_prefix)
    if not column_specs:
        return HarnessResult(
            success=False,
            stdout=json.dumps({"columns": [], "status": "blocked"}, ensure_ascii=False),
            stderr="No DataWindow column=(...) name=... entries were found.",
            exit_code=1,
            metadata={
                "harness": "pb-to-csharp-migration-harness",
                "status": "blocked",
                "blocked_reason": "missing_datawindow_columns",
            },
        )
    xml = generate_devexpress_grid_xml(column_specs, prefix=resolved_prefix, grid_view_name=resolved_grid_view_name)
    metadata = {
        "harness": "pb-to-csharp-migration-harness",
        "status": "passed",
        "columns": [spec.field_name for spec in column_specs],
        "column_specs": [spec.to_dict() for spec in column_specs],
        "column_count": len(column_specs),
        "csharp_column_prefix": resolved_prefix,
        "csharp_column_prefix_rule": "{input_format}_{column}: colList_, colDetail_, col<TABLE>_, or col<PURPOSE>_",
        "csharp_grid_names": grid_names,
        "csharp_grid_name_rule": "grdList/gvwList, grdDetail/gvwDetail, grd<TABLE>/gvw<TABLE>, or grd<PURPOSE>/gvw<PURPOSE>",
        "converter_contract": (
            "DataWindowToXml-compatible SRD visual-column/table-column to DevExpress GridView XML mapping "
            "with target C# column names and matched DataWindow captions when available"
        ),
        "gridview_defaults": DATAWINDOW_TO_XML_OPTIONS_VIEW_DEFAULTS,
    }
    return HarnessResult(
        success=True,
        stdout=xml,
        stderr="",
        exit_code=0,
        metadata=metadata,
    )


def _normalize_grid_column_specs(columns: Iterable[Any], *, prefix: str) -> List[DataWindowColumnSpec]:
    specs: List[DataWindowColumnSpec] = []
    for item in columns:
        if isinstance(item, DataWindowColumnSpec):
            if item.field_name:
                specs.append(
                    DataWindowColumnSpec(
                        field_name=_normalize_datawindow_field_name(item.field_name),
                        caption=str(item.caption or item.field_name),
                        csharp_name=item.csharp_name
                        or build_csharp_grid_column_name(item.field_name, prefix=prefix),
                        data_type=item.data_type,
                        source=item.source,
                        x=item.x,
                        y=item.y,
                        width=item.width,
                        height=item.height,
                    )
                )
            continue
        if isinstance(item, dict):
            field_name = _normalize_datawindow_field_name(
                item.get("field_name") or item.get("field") or item.get("name") or ""
            )
            if field_name:
                specs.append(
                    DataWindowColumnSpec(
                        field_name=field_name,
                        caption=str(item.get("caption") or field_name),
                        csharp_name=str(item.get("csharp_name") or build_csharp_grid_column_name(field_name, prefix=prefix)),
                        data_type=str(
                            item.get("data_type")
                            or item.get("datatype")
                            or item.get("type")
                            or ""
                        ).strip(),
                        source=str(item.get("source") or "provided"),
                        x=_parse_optional_int(item.get("x")),
                        y=_parse_optional_int(item.get("y")),
                        width=_parse_optional_int(item.get("width")),
                        height=_parse_optional_int(item.get("height")),
                    )
                )
            continue
        field_name = _normalize_datawindow_field_name(str(item))
        if field_name:
            specs.append(
                DataWindowColumnSpec(
                    field_name=field_name,
                    caption=field_name,
                    csharp_name=build_csharp_grid_column_name(field_name, prefix=prefix),
                    source="provided",
                )
            )
    return specs


def _csharp_designer_order_key(name: str, source: str) -> int:
    index = source.find(f"this.{name} = new ")
    if index >= 0:
        return index
    index = source.find(f"private ")
    declaration_index = source.find(f" {name};", index if index >= 0 else 0)
    return declaration_index if declaration_index >= 0 else len(source)


def _parse_csharp_designer_value(raw_value: str) -> Any:
    value = str(raw_value or "").strip()
    string_match = re.fullmatch(r"\"(?P<value>(?:\\.|[^\"])*)\"", value)
    if string_match:
        return _unescape_csharp_string_literal(string_match.group("value"))
    if value in {"true", "false"}:
        return value == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    point_match = re.search(r"System\.Drawing\.Point\((?P<x>-?\d+),\s*(?P<y>-?\d+)\)", value)
    if point_match:
        return {"x": int(point_match.group("x")), "y": int(point_match.group("y"))}
    size_match = re.search(r"System\.Drawing\.Size\((?P<width>-?\d+),\s*(?P<height>-?\d+)\)", value)
    if size_match:
        return {"width": int(size_match.group("width")), "height": int(size_match.group("height"))}
    padding_match = re.search(
        r"System\.Windows\.Forms\.Padding\((?P<values>-?\d+(?:\s*,\s*-?\d+)*)\)",
        value,
    )
    if padding_match:
        parts = [int(part.strip()) for part in padding_match.group("values").split(",")]
        if len(parts) == 1:
            return {"all": parts[0]}
        if len(parts) == 4:
            return {"left": parts[0], "top": parts[1], "right": parts[2], "bottom": parts[3]}
        return {"values": parts}
    return value


def _unescape_csharp_string_literal(value: str) -> str:
    return (
        str(value or "")
        .replace(r"\\", "\\")
        .replace(r"\"", '"')
        .replace(r"\n", "\n")
        .replace(r"\r", "\r")
        .replace(r"\t", "\t")
    )


def _string_property(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _int_property(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _point_or_size_property(value: Any) -> Dict[str, int] | None:
    if isinstance(value, dict) and all(isinstance(item, int) for item in value.values()):
        return dict(value)
    return None


def _dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _escape_csharp_string(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace('"', '\\"')


def _strip_sql_literals_and_comments_for_pb_contract(sql: str) -> str:
    text = re.sub(r"'(?:''|[^'])*'", "''", str(sql or ""))
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"--.*?$", " ", text, flags=re.MULTILINE)
    return text


def _normalize_datawindow_field_name(value: str) -> str:
    return str(value or "").strip().strip('"').upper()


def _normalize_detail_form_fields(fields: Iterable[Any]) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for item in fields or []:
        if isinstance(item, dict):
            field_name = _normalize_datawindow_field_name(
                item.get("field_name") or item.get("name") or item.get("column") or item.get("logical_name") or ""
            )
            if not field_name:
                continue
            logical_name = str(item.get("logical_name") or item.get("control_stem") or field_name).strip().strip('"')
            normalized.append(
                {
                    "logical_name": logical_name,
                    "field_name": field_name,
                    "caption": str(item.get("caption") or item.get("label") or field_name),
                    "editor_type": _normalize_editor_type(
                        str(item.get("editor_type") or item.get("control_type") or item.get("type") or "")
                    ),
                    "csharp_label_name": str(item.get("csharp_label_name") or item.get("label_name") or ""),
                    "csharp_editor_name": str(item.get("csharp_editor_name") or item.get("control_name") or ""),
                    "source": str(item.get("source") or "provided"),
                }
            )
            continue
        field_name = _normalize_datawindow_field_name(str(item))
        if field_name:
            normalized.append(
                {
                    "logical_name": field_name,
                    "field_name": field_name,
                    "caption": field_name,
                    "editor_type": "TextEdit",
                    "csharp_label_name": "",
                    "csharp_editor_name": "",
                    "source": "provided",
                }
            )
    return normalized


def _normalize_editor_type(value: str) -> str:
    lowered = str(value or "").strip().lower()
    if lowered in {"spin", "spinedit", "spin_edit", "u_spinedit", "number", "numeric", "decimal", "int", "integer"}:
        return "SpinEdit"
    if lowered in {"date", "datetime", "dateedit", "date_edit", "u_dateedit", "calendar"}:
        return "DateEdit"
    if lowered in {
        "combo",
        "combobox",
        "comboboxedit",
        "combo_box",
        "combo_box_edit",
        "u_combobox",
        "lookup",
        "lookupedit",
        "u_lookupedit",
        "look_up",
        "select",
    }:
        return "LookUpEdit"
    if lowered in {"button", "buttonedit", "u_buttonedit", "search", "popup", "code"}:
        return "ButtonEdit"
    if lowered in {"check", "checkbox", "checkedit", "u_checkedit", "bool", "boolean", "yn"}:
        return "CheckEdit"
    if lowered in {"memo", "memoedit", "memo_edit", "memoexedit", "u_memoedit", "textarea", "multiline"}:
        return "MemoEdit"
    if lowered in {"panel", "panelcontrol", "u_panel"}:
        return "PanelControl"
    if lowered in {"group", "groupcontrol", "groupbox"}:
        return "GroupControl"
    if lowered in {"grid", "gridcontrol", "u_gridcontrol"}:
        return "GridControl"
    if lowered in {"gridview", "view"}:
        return "GridView"
    if lowered in {"treelist", "tree", "treeview"}:
        return "TreeList"
    if lowered in {"tab", "tabcontrol", "xtratabcontrol"}:
        return "TabControl"
    if lowered in {"label", "labelcontrol", "u_label"}:
        return "LabelControl"
    return "TextEdit"


def _editor_prefix(editor_type: str) -> str:
    mapping = {
        "TextEdit": "txt",
        "SpinEdit": "Spin",
        "DateEdit": "ymd",
        "LookUpEdit": "cbo",
        "ButtonEdit": "btn",
        "CheckEdit": "Chk",
        "MemoEdit": "memo",
        "PanelControl": "pn",
        "GroupControl": "grp",
        "GridControl": "grd",
        "GridView": "gvw",
        "TreeList": "treeList",
        "TabControl": "tab",
        "LabelControl": "lbl",
    }
    return mapping.get(editor_type, "txt")


def build_csharp_control_name(control_type: str, logical_name: str = "", field_name: str = "") -> str:
    """Build a fallback target-style C# control name from observed WinForms conventions."""
    normalized_type = _normalize_editor_type(control_type)
    prefix = _editor_prefix(normalized_type)
    logical = str(logical_name or "").strip()
    field = _normalize_datawindow_field_name(field_name or logical)

    if normalized_type in {"PanelControl", "GroupControl", "GridControl", "GridView", "TreeList", "TabControl"}:
        return f"{prefix}{_to_control_suffix(logical or field)}"
    if normalized_type == "SpinEdit":
        return f"{prefix}{field}"
    return f"{prefix}{field}"


def _build_editor_control_name(editor_type: str, logical_name: str, field_name: str) -> str:
    return build_csharp_control_name(editor_type, logical_name=logical_name, field_name=field_name)


def _to_pascal_identifier(value: str) -> str:
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", str(value or "")) if part]
    if not parts:
        return "Field"
    return "".join(part[:1].upper() + part[1:].lower() for part in parts)


def _to_control_suffix(value: str) -> str:
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", str(value or "")) if part]
    if not parts:
        return "Field"
    suffix = "".join(part[:1].upper() + part[1:] for part in parts)
    return suffix or "Field"


def _extract_visual_datawindow_columns(source: str) -> List[Dict[str, Any]]:
    columns: List[Dict[str, Any]] = []
    for line_index, line in enumerate(source.splitlines()):
        if not DATAWINDOW_VISUAL_COLUMN_PATTERN.search(line):
            continue
        attrs = _parse_datawindow_attributes(line)
        field_name = _normalize_datawindow_field_name(attrs.get("name", ""))
        if not field_name:
            continue
        columns.append(
            {
                "field_name": field_name,
                "band": str(attrs.get("band", "")).lower(),
                "x": _parse_optional_int(attrs.get("x")),
                "y": _parse_optional_int(attrs.get("y")),
                "width": _parse_optional_int(attrs.get("width")),
                "height": _parse_optional_int(attrs.get("height")),
                "line_index": line_index,
            }
        )
    return sorted(columns, key=lambda item: (_sort_int(item.get("y")), _sort_int(item.get("x")), item["line_index"]))


def _extract_datawindow_text_controls(source: str) -> List[Dict[str, Any]]:
    controls: List[Dict[str, Any]] = []
    for line_index, line in enumerate(source.splitlines()):
        if not DATAWINDOW_TEXT_PATTERN.search(line):
            continue
        attrs = _parse_datawindow_attributes(line)
        caption = str(attrs.get("text", "")).strip()
        if not caption:
            continue
        controls.append(
            {
                "caption": caption,
                "name": str(attrs.get("name", "")),
                "band": str(attrs.get("band", "")).lower(),
                "x": _parse_optional_int(attrs.get("x")),
                "y": _parse_optional_int(attrs.get("y")),
                "width": _parse_optional_int(attrs.get("width")),
                "height": _parse_optional_int(attrs.get("height")),
                "line_index": line_index,
            }
        )
    return controls


def _parse_datawindow_attributes(text: str) -> Dict[str, str]:
    attrs: Dict[str, str] = {}
    for match in DATAWINDOW_ATTRIBUTE_PATTERN.finditer(text):
        attrs[match.group("key").lower()] = match.group("quoted") if match.group("quoted") is not None else match.group("bare")
    return attrs


def _match_datawindow_caption(column: Dict[str, Any], text_controls: List[Dict[str, Any]]) -> str:
    column_x = column.get("x")
    column_y = column.get("y")
    column_width = column.get("width") or 0
    column_height = column.get("height") or 0
    if column_x is None or column_y is None:
        return ""

    candidates = []
    column_right = column_x + column_width
    column_center = column_x + (column_width / 2)
    column_band = str(column.get("band") or "").lower()
    column_token = re.sub(r"[^a-z0-9]", "", str(column.get("field_name") or "").lower())
    for text in text_controls:
        text_x = text.get("x")
        text_y = text.get("y")
        text_width = text.get("width") or 0
        text_height = text.get("height") or 0
        if text_x is None or text_y is None:
            continue
        text_right = text_x + text_width
        text_center = text_x + (text_width / 2)
        text_band = str(text.get("band") or "").lower()
        same_row = _ranges_overlap(column_y, column_y + column_height, text_y, text_y + text_height)
        same_band = bool(column_band and text_band and column_band == text_band)
        header_band = text_band == "header"
        name_hint = bool(column_token and column_token in re.sub(r"[^a-z0-9]", "", str(text.get("name") or "").lower()))
        if same_row and text_right <= column_x and (same_band or not header_band):
            score = (0 if same_band else 5) + (column_x - text_right) / 1000
            if name_hint:
                score -= 2
            candidates.append((score, text["caption"]))

        horizontal_overlap = _ranges_overlap(column_x, column_right, text_x, text_x + text_width)
        vertical_gap = abs(column_y - (text_y + text_height)) if text_y <= column_y else 10_000
        if horizontal_overlap and text_y <= column_y:
            score = (8 if header_band else 12) + vertical_gap / 1000 + abs(column_center - text_center) / 10_000
            if name_hint:
                score -= 2
            candidates.append((score, text["caption"]))

    if candidates:
        return sorted(candidates, key=lambda item: item[0])[0][1]
    return ""


def _ranges_overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    return max(start_a, start_b) <= min(end_a, end_b)


def _parse_optional_int(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _sort_int(value: int | None) -> int:
    return value if value is not None else 1_000_000


def _coerce_state(state: MigrationInputState | Dict[str, Any] | None) -> MigrationInputState:
    if isinstance(state, MigrationInputState):
        return state
    return MigrationInputState.from_dict(dict(state or {}))


def _normalize_control_inventory(available_controls: Dict[str, Any] | Iterable[str] | None) -> Dict[str, Any]:
    inventory: Dict[str, Any] = {
        "types": set(),
        "target_project_controls": {},
        "has_devexpress": False,
        "has_winforms": True,
        "project_name": "",
    }
    if available_controls is None:
        return inventory

    if isinstance(available_controls, dict):
        inventory["project_name"] = str(available_controls.get("project_name", ""))
        inventory["has_winforms"] = bool(available_controls.get("has_winforms", True))
        inventory["has_devexpress"] = bool(
            available_controls.get("has_devexpress", available_controls.get("devexpress", False))
        )
        for key in ("control_types", "types", "available_types"):
            for type_name in available_controls.get(key, []) or []:
                inventory["types"].add(str(type_name))
        for logical_name, type_name in (available_controls.get("target_project_controls") or {}).items():
            inventory["target_project_controls"][str(logical_name).lower()] = str(type_name)
            inventory["types"].add(str(type_name))
        if available_controls.get("has_devexpress") or available_controls.get("devexpress"):
            inventory["types"].update(
                [
                    "DevExpress.XtraGrid.GridControl",
                    "DevExpress.XtraGrid.Views.Grid.GridView",
                    "DevExpress.XtraGrid.Columns.GridColumn",
                    "DevExpress.XtraEditors.TextEdit",
                    "DevExpress.XtraEditors.LabelControl",
                    "DevExpress.XtraEditors.GroupControl",
                    "DevExpress.XtraEditors.PanelControl",
                    "DevExpress.XtraEditors.DateEdit",
                    "DevExpress.XtraEditors.SpinEdit",
                    "DevExpress.XtraEditors.ButtonEdit",
                    "DevExpress.XtraEditors.LookUpEdit",
                    "DevExpress.XtraEditors.MemoEdit",
                    "DevExpress.XtraEditors.CheckEdit",
                    "DevExpress.XtraTreeList.TreeList",
                    "DevExpress.XtraTab.XtraTabControl",
                ]
            )
    else:
        for type_name in available_controls:
            inventory["types"].add(str(type_name))

    if any("devexpress." in item.lower() for item in inventory["types"]):
        inventory["has_devexpress"] = True
    return inventory


def _find_project_control(logical_name: str, inventory: Dict[str, Any]) -> str:
    explicit = inventory["target_project_controls"].get(logical_name)
    if explicit:
        return explicit

    spec = CONTROL_FALLBACKS[logical_name]
    for type_name in sorted(inventory["types"]):
        lowered = type_name.lower()
        if lowered.startswith("devexpress.") or lowered.startswith("system.windows.forms."):
            continue
        tail = lowered.rsplit(".", 1)[-1]
        if any(tail == suffix or tail.endswith(suffix) for suffix in spec["target_suffixes"]):
            return type_name
    return ""
