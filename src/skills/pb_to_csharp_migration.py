import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence
from xml.etree import ElementTree as ET
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
    r"^\s*(?:USE\s+(?:\[[^\]]+\]|\S+)\s*\r?\n\s*GO\s*\r?\n\s*)?"
    r"(?:/\*+[\s\S]*?\bObject\s*:\s*StoredProcedure\b[\s\S]*?\*+/\s*)?"
    r"(?:(?:SET\s+(?:ANSI_NULLS|QUOTED_IDENTIFIER)\s+(?:ON|OFF)\s*\r?\n\s*GO\s*\r?\n\s*){0,2})"
    r"--\s*=+\s*\r?\n"
    r"(?:--\s*AUTHOR\s*:\s*(?P<author>.*)\r?\n)?"
    r"(?:--\s*CREATE\s+DATE\s*:\s*(?P<create_date>\d{4}-\d{2}-\d{2})\s*\r?\n)?"
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
    expected_control_contract = payload.get("expected_control_contract")
    generated_csharp_verification = payload.get("generated_csharp_verification")
    raw_konelib_defaults = payload.get("konelib_defaults")
    konelib_defaults = (
        dict(raw_konelib_defaults)
        if isinstance(raw_konelib_defaults, Mapping)
        else ({} if raw_konelib_defaults is None else None)
    )
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
        or (
            expected_control_contract is not None
            and not isinstance(expected_control_contract, Mapping)
        )
        or (
            generated_csharp_verification is not None
            and not isinstance(generated_csharp_verification, Mapping)
        )
        or konelib_defaults is None
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
    generated_required_inputs = (
        generated_csharp_verification.get("required_inputs", [])
        if isinstance(generated_csharp_verification, Mapping)
        else []
    )
    expected_control_contract_required = bool(
        isinstance(expected_control_contract, Mapping)
        and "expected_control_contracts" in generated_required_inputs
    )
    normalized_required_inputs = {
        str(item).strip().lower() for item in generated_required_inputs if str(item).strip()
    }
    control_contract_feature_enabled = bool(
        isinstance(expected_control_contract, Mapping)
        and expected_control_contract_required
    )
    target_artifact_binding_required = bool(
        control_contract_feature_enabled
        and normalized_required_inputs.intersection(
            {"actual target files", "actual target artifacts"}
        )
    )
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
                    "expected_control_contract": (
                        dict(expected_control_contract)
                        if isinstance(expected_control_contract, Mapping)
                        else {}
                    ),
                    "expected_control_contract_required": expected_control_contract_required,
                    "control_contract_feature_enabled": control_contract_feature_enabled,
                    "control_contract_completeness_required": bool(
                        control_contract_feature_enabled
                        and expected_control_contract.get("complete_inventory_required") is True
                    ),
                    "structured_evidence_registry_required": bool(
                        control_contract_feature_enabled
                        and expected_control_contract.get("evidence_registry_required") is True
                    ),
                    "initialize_component_scope_required": bool(
                        control_contract_feature_enabled
                        and expected_control_contract.get("initialize_component_scope_required") is True
                    ),
                    "target_artifact_binding_required": target_artifact_binding_required,
                    "konelib_defaults": konelib_defaults,
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


def _evaluate_csharp_preprocessor_literal(expression: str) -> bool | None:
    value = re.sub(r"\s+", "", str(expression or "")).lower()
    while value.startswith("(") and value.endswith(")"):
        value = value[1:-1]
    if value == "false":
        return False
    return None


def _mask_inactive_csharp_preprocessor(source_text: str) -> str:
    """Mask only branches that cannot be active under any symbol definition."""
    source = str(source_text or "")
    masked = list(source)
    stack: List[Dict[str, Any]] = []
    active = True

    def mask(start: int, end: int) -> None:
        for position in range(start, min(end, len(masked))):
            if masked[position] not in "\r\n":
                masked[position] = " "

    offset = 0
    for line in source.splitlines(keepends=True):
        line_end = offset + len(line)
        directive = re.match(r"^[ \t]*#\s*(?P<name>if|elif|else|endif)\b(?P<value>.*)$", line)
        if directive:
            name = directive.group("name")
            value = _evaluate_csharp_preprocessor_literal(directive.group("value"))
            mask(offset, line_end)
            if name == "if":
                frame = {
                    "parent_active": active,
                    "remaining_possible": bool(active and value is not True),
                }
                stack.append(frame)
                active = bool(active and value is not False)
            elif name == "elif" and stack:
                frame = stack[-1]
                remaining_possible = bool(frame["remaining_possible"])
                active = bool(remaining_possible and value is not False)
                frame["remaining_possible"] = bool(remaining_possible and value is not True)
            elif name == "else" and stack:
                frame = stack[-1]
                active = bool(frame["remaining_possible"])
                frame["remaining_possible"] = False
            elif name == "endif" and stack:
                frame = stack.pop()
                active = bool(frame["parent_active"])
            offset = line_end
            continue
        if not active:
            mask(offset, line_end)
        offset = line_end
    return "".join(masked)


def _has_unknown_csharp_preprocessor(source_text: str) -> bool:
    for match in re.finditer(
        r"(?m)^[ \t]*#\s*(?:if|elif)\b(?P<value>.*)$",
        str(source_text or ""),
    ):
        if _evaluate_csharp_preprocessor_literal(match.group("value")) is None:
            return True
    return False


def _csharp_raw_string_prefix(source: str, index: int) -> tuple[int, int, bool] | None:
    cursor = index
    dollar_count = 0
    while cursor < len(source) and source[cursor] == "$":
        dollar_count += 1
        cursor += 1
    quote_start = cursor
    while cursor < len(source) and source[cursor] == '"':
        cursor += 1
    quote_count = cursor - quote_start
    if quote_count < 3:
        return None
    return cursor - index, quote_count, dollar_count > 0


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
    source = _mask_inactive_csharp_preprocessor(source_text)
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
        raw_prefix = _csharp_raw_string_prefix(source, index)
        if raw_prefix is not None:
            prefix_length, quote_count, interpolated = raw_prefix
            delimiter = '"' * quote_count
            content_start = index + prefix_length
            content_end = source.find(delimiter, content_start)
            terminated = content_end >= 0
            end = len(source) if not terminated else content_end + quote_count
            literals.append(
                _CSharpStringLiteral(
                    start=index,
                    end=end,
                    value=(source[content_start:content_end] if terminated and not interpolated else None),
                    interpolated=interpolated,
                    terminated=terminated,
                )
            )
            mask(masked, index, end)
            index = end if end > index else index + 1
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
    preserve_existing: bool = False,
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

    forbidden_patterns = (
        [] if preserve_existing else _normalized_profile_patterns(rules.get("forbidden_patterns"))
    )
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

DATAWINDOW_TO_CSHARP_GRIDVIEW_DEFAULTS = [
    ("BestFitMaxRowCount", "-1"),
    ("PreviewLineCount", "-1"),
    ("HorzScrollStep", "3"),
    ("FocusRectStyle", "DevExpress.XtraGrid.Views.Grid.DrawFocusRectStyle.CellFocus"),
    (
        "ScrollStyle",
        "DevExpress.XtraGrid.Views.Grid.ScrollStyleFlags.LiveVertScroll | "
        "DevExpress.XtraGrid.Views.Grid.ScrollStyleFlags.LiveHorzScroll",
    ),
    ("PreviewIndent", "-1"),
    ("GroupPanelText", "string.Empty"),
    ("PreviewFieldName", "string.Empty"),
    ("VertScrollTipFieldName", "string.Empty"),
    ("LevelIndent", "-1"),
    (
        "GroupFooterShowMode",
        "DevExpress.XtraGrid.Views.Grid.GroupFooterShowMode.VisibleIfExpanded",
    ),
    ("NewItemRowText", "string.Empty"),
    ("SynchronizeClones", "true"),
    ("BorderStyle", "DevExpress.XtraEditors.Controls.BorderStyles.Default"),
    ("ViewCaption", "string.Empty"),
    ("DetailHeight", "350"),
    ("DetailTabHeaderLocation", "DevExpress.XtraTab.TabHeaderLocation.Top"),
    ("ActiveFilterEnabled", "true"),
]

DEVEXPRESS_GRID_XML_MAX_BYTES = 1024 * 1024
DEVEXPRESS_GRID_XML_MAX_DEPTH = 8
DEVEXPRESS_GRID_XML_MAX_ELEMENTS = 10000


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
    xml_column_name: str = ""
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
            "xml_column_name": self.xml_column_name,
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


COMPOSITE_DISPLAY_KEY_EVIDENCE_KINDS = frozenset(
    {
        "business-key-contract",
        "datawindow",
        "pb-source",
        "result-contract",
        "user-supplied-contract",
    }
)


@dataclass(frozen=True)
class CompositeBusinessKeyDisplaySpec:
    """Authoritative evidence for one UI display field backed by raw key fields."""

    base_field: str
    sequence_fields: List[str] = field(default_factory=list)
    evidence_kind: str = ""
    evidence_refs: List[str] = field(default_factory=list)
    display_field: str = ""
    display_caption: str = ""
    raw_visible_fields: List[str] = field(default_factory=list)
    table_alias: str = ""
    base_type_family: str = "character"
    sequence_type_family: str = "numeric"
    sequence_format: str = "##0"

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CompositeBusinessKeyDisplaySpec":
        return cls(
            base_field=str(data.get("base_field") or ""),
            sequence_fields=[str(item) for item in data.get("sequence_fields", [])],
            evidence_kind=str(data.get("evidence_kind") or ""),
            evidence_refs=[str(item) for item in data.get("evidence_refs", [])],
            display_field=str(data.get("display_field") or ""),
            display_caption=str(data.get("display_caption") or ""),
            raw_visible_fields=[str(item) for item in data.get("raw_visible_fields", [])],
            table_alias=str(data.get("table_alias") or ""),
            base_type_family=str(data.get("base_type_family") or "character"),
            sequence_type_family=str(data.get("sequence_type_family") or "numeric"),
            sequence_format=str(data.get("sequence_format") or "##0"),
        )


@dataclass(frozen=True)
class CompositeBusinessKeyDisplayObservation:
    """Generated SELECT and Designer/Grid evidence checked against a display-key plan."""

    result_fields: List[str] = field(default_factory=list)
    display_expression: str = ""
    display_alias: str = ""
    component_order: List[str] = field(default_factory=list)
    visible_grid_field: str = ""
    hidden_raw_fields: List[str] = field(default_factory=list)
    grid_caption: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CompositeBusinessKeyDisplayObservation":
        return cls(
            result_fields=[str(item) for item in data.get("result_fields", [])],
            display_expression=str(data.get("display_expression") or ""),
            display_alias=str(data.get("display_alias") or ""),
            component_order=[str(item) for item in data.get("component_order", [])],
            visible_grid_field=str(data.get("visible_grid_field") or ""),
            hidden_raw_fields=[str(item) for item in data.get("hidden_raw_fields", [])],
            grid_caption=str(data.get("grid_caption") or ""),
        )


def _coerce_composite_display_spec(
    value: CompositeBusinessKeyDisplaySpec | Mapping[str, Any],
) -> CompositeBusinessKeyDisplaySpec:
    if isinstance(value, CompositeBusinessKeyDisplaySpec):
        return value
    return CompositeBusinessKeyDisplaySpec.from_dict(value)


def _coerce_composite_display_observation(
    value: CompositeBusinessKeyDisplayObservation | Mapping[str, Any],
) -> CompositeBusinessKeyDisplayObservation:
    if isinstance(value, CompositeBusinessKeyDisplayObservation):
        return value
    return CompositeBusinessKeyDisplayObservation.from_dict(value)


def _composite_display_identifier(value: str) -> str:
    return str(value or "").strip().strip('"')


def _composite_display_name_key(value: str) -> str:
    return _composite_display_identifier(value).casefold()


def _normalize_composite_display_sql(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def build_composite_business_key_display_plan(
    spec: CompositeBusinessKeyDisplaySpec | Mapping[str, Any],
) -> HarnessResult:
    """Plan a composite display field only from declared business-key and UI evidence."""
    contract = _coerce_composite_display_spec(spec)
    base_field = _composite_display_identifier(contract.base_field)
    sequence_fields = [
        _composite_display_identifier(item)
        for item in contract.sequence_fields
        if _composite_display_identifier(item)
    ]
    components = [base_field, *sequence_fields] if base_field else sequence_fields
    issues: List[Dict[str, Any]] = []

    def add_issue(code: str, message: str, **details: Any) -> None:
        issues.append({"code": code, "severity": "error", "message": message, **details})

    if contract.evidence_kind not in COMPOSITE_DISPLAY_KEY_EVIDENCE_KINDS or not any(
        str(item).strip() for item in contract.evidence_refs
    ):
        add_issue(
            "composite_display_key_evidence_required",
            "Composite display fields require authoritative PB/DataWindow/result/business-key evidence.",
        )
    if not base_field:
        add_issue("composite_display_key_base_field_required", "A base business-key field is required.")
    if not sequence_fields:
        add_issue(
            "composite_display_key_sequence_field_required",
            "At least one sequence key is required for a composite display field.",
        )
    invalid_identifiers = [
        item for item in [*components, contract.display_field, contract.table_alias]
        if item and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_#$]*", item)
    ]
    if invalid_identifiers:
        add_issue(
            "composite_display_key_identifier_invalid",
            "Business-key fields, display aliases, and table aliases must be simple supplied identifiers.",
            identifiers=invalid_identifiers,
        )
    component_keys = [_composite_display_name_key(item) for item in components]
    if len(component_keys) != len(set(component_keys)):
        add_issue(
            "composite_display_key_component_duplicate",
            "Business-key components must be unique and retain authoritative key order.",
        )

    display_field = _composite_display_identifier(contract.display_field)
    display_field_source = "supplied"
    if not display_field and base_field:
        display_field = f"{base_field}S"
        display_field_source = "packaged-business-key-default"
    if display_field and _composite_display_name_key(display_field) in component_keys:
        add_issue(
            "composite_display_key_alias_conflicts_with_raw_field",
            "The dedicated display alias must not replace a raw identity field.",
            display_field=display_field,
        )
    if str(contract.base_type_family).strip().lower() != "character":
        add_issue(
            "composite_display_key_base_type_unsupported",
            "The packaged plus/FORMAT expression requires authoritative character base-key type evidence.",
        )
    if str(contract.sequence_type_family).strip().lower() != "numeric":
        add_issue(
            "composite_display_key_sequence_type_unsupported",
            "FORMAT(..., '##0') requires authoritative numeric sequence-key type evidence.",
        )
    if not str(contract.sequence_format):
        add_issue(
            "composite_display_key_sequence_format_required",
            "A supplied or target-approved sequence format is required.",
        )
    raw_visible_keys = {
        _composite_display_name_key(item) for item in contract.raw_visible_fields if str(item).strip()
    }
    unknown_visible = [
        item for item in contract.raw_visible_fields
        if _composite_display_name_key(item) not in component_keys
    ]
    if unknown_visible:
        add_issue(
            "composite_display_key_raw_visibility_field_unknown",
            "Only raw business-key components may be declared visible.",
            fields=unknown_visible,
        )

    alias = _composite_display_identifier(contract.table_alias)
    refs = [f"{alias}.{item}" if alias else item for item in components]
    format_literal = str(contract.sequence_format).replace("'", "''")
    concatenation = refs[0] if refs else ""
    for sequence_ref in refs[1:]:
        concatenation += f" + '-' + FORMAT({sequence_ref}, '{format_literal}')"
    display_expression = concatenation

    hidden_raw_fields = [
        item for item in components if _composite_display_name_key(item) not in raw_visible_keys
    ]
    display_caption = str(contract.display_caption or display_field)
    plan = {
        "raw_result_fields": components,
        "display_result_field": display_field,
        "select_result_fields": [*components, display_field] if display_field else components,
        "display_expression": display_expression,
        "display_select_item": f"{display_expression} AS {display_field}" if display_field else "",
        "component_order": components,
        "visible_grid_field": display_field,
        "hidden_raw_identity_fields": hidden_raw_fields,
        "raw_visible_fields": [
            item for item in components if _composite_display_name_key(item) in raw_visible_keys
        ],
        "grid_caption": display_caption,
        "caption_source": "pb-mapping" if contract.display_caption else "field-name-fallback",
        "display_field_source": display_field_source,
        "null_behavior": "direct-plus-concatenation",
        "type_behavior": "character base plus nvarchar FORMAT output; raw component types remain unchanged",
        "sequence_format": contract.sequence_format,
        "evidence_kind": contract.evidence_kind,
        "evidence_refs": list(contract.evidence_refs),
    }
    passed = not issues
    metadata = {
        "harness": "pb-to-csharp-migration-harness",
        "status": "passed" if passed else "blocked",
        "contract": "composite-business-key-display-v1",
        "plan": plan,
        "issues": issues,
        "token_optimizer_status": "passthrough",
    }
    return HarnessResult(
        success=passed,
        stdout=json.dumps(plan, ensure_ascii=False, sort_keys=True),
        stderr="" if passed else "Composite business-key display planning failed.",
        exit_code=0 if passed else 1,
        metadata=metadata,
    )


def verify_composite_business_key_display_contract(
    spec: CompositeBusinessKeyDisplaySpec | Mapping[str, Any],
    observation: CompositeBusinessKeyDisplayObservation | Mapping[str, Any],
) -> HarnessResult:
    """Verify raw identity retention, display SQL, component order, and grid visibility."""
    planned = build_composite_business_key_display_plan(spec)
    observed = _coerce_composite_display_observation(observation)
    if not planned.success:
        return planned

    plan = planned.metadata["plan"]
    issues: List[Dict[str, Any]] = []

    def add_issue(code: str, message: str, **details: Any) -> None:
        issues.append({"code": code, "severity": "error", "message": message, **details})

    result_keys = {_composite_display_name_key(item) for item in observed.result_fields}
    missing_raw = [
        item for item in plan["raw_result_fields"]
        if _composite_display_name_key(item) not in result_keys
    ]
    if missing_raw:
        add_issue(
            "composite_display_key_raw_result_field_missing",
            "SELECT must retain every raw business-key field for identity and logic.",
            fields=missing_raw,
        )
    if _composite_display_name_key(plan["display_result_field"]) not in result_keys:
        add_issue(
            "composite_display_key_display_result_field_missing",
            "SELECT must emit the dedicated display result field.",
        )
    if _composite_display_name_key(observed.display_alias) != _composite_display_name_key(
        plan["display_result_field"]
    ):
        add_issue(
            "composite_display_key_alias_mismatch",
            "The SELECT display alias must match the evidence-backed display result field.",
            expected=plan["display_result_field"],
            actual=observed.display_alias,
        )
    if [_composite_display_name_key(item) for item in observed.component_order] != [
        _composite_display_name_key(item) for item in plan["component_order"]
    ]:
        add_issue(
            "composite_display_key_component_order_mismatch",
            "Display components must follow authoritative business-key order.",
            expected=plan["component_order"],
            actual=list(observed.component_order),
        )
    if _normalize_composite_display_sql(observed.display_expression) != _normalize_composite_display_sql(
        plan["display_expression"]
    ):
        add_issue(
            "composite_display_key_expression_mismatch",
            "The observed display expression must preserve the planned SQL style and null behavior.",
            expected=plan["display_expression"],
            actual=observed.display_expression,
        )
    if _composite_display_name_key(observed.visible_grid_field) != _composite_display_name_key(
        plan["visible_grid_field"]
    ):
        add_issue(
            "composite_display_key_grid_field_mismatch",
            "The visible Designer/Grid FieldName must bind to the display result field.",
            expected=plan["visible_grid_field"],
            actual=observed.visible_grid_field,
        )
    hidden_keys = {_composite_display_name_key(item) for item in observed.hidden_raw_fields}
    missing_hidden = [
        item for item in plan["hidden_raw_identity_fields"]
        if _composite_display_name_key(item) not in hidden_keys
    ]
    if missing_hidden:
        add_issue(
            "composite_display_key_hidden_raw_field_missing",
            "Raw identity fields remain available and are hidden unless source/UI evidence requires visibility.",
            fields=missing_hidden,
        )
    if plan["caption_source"] == "pb-mapping" and observed.grid_caption != plan["grid_caption"]:
        add_issue(
            "composite_display_key_caption_mismatch",
            "The grid caption must preserve the supplied PB mapping.",
            expected=plan["grid_caption"],
            actual=observed.grid_caption,
        )

    passed = not issues
    metadata = {
        "harness": "pb-to-csharp-migration-harness",
        "status": "passed" if passed else "blocked",
        "contract": "composite-business-key-display-v1",
        "plan": plan,
        "observation": {
            "result_fields": list(observed.result_fields),
            "display_expression": observed.display_expression,
            "display_alias": observed.display_alias,
            "component_order": list(observed.component_order),
            "visible_grid_field": observed.visible_grid_field,
            "hidden_raw_fields": list(observed.hidden_raw_fields),
            "grid_caption": observed.grid_caption,
        },
        "issues": issues,
        "token_optimizer_status": "passthrough",
    }
    return HarnessResult(
        success=passed,
        stdout=json.dumps({"status": metadata["status"], "issue_count": len(issues)}, sort_keys=True),
        stderr="" if passed else "Composite business-key display verification failed.",
        exit_code=0 if passed else 1,
        metadata=metadata,
    )


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
    """Extract DataWindow columns in exact column=( occurrence order."""
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

    visual_columns = _extract_visual_datawindow_columns(source)
    text_controls = _extract_datawindow_text_controls(source)
    specs: List[DataWindowColumnSpec] = []

    visual_by_field: Dict[str, List[Dict[str, Any]]] = {}
    for column in visual_columns:
        visual_by_field.setdefault(column["field_name"], []).append(column)

    for table_column in table_columns:
        field_name = table_column["field_name"]
        visual_matches = visual_by_field.get(field_name, [])
        visual = visual_matches.pop(0) if visual_matches else {}
        caption = _match_datawindow_caption(visual, text_controls) if visual else ""
        specs.append(
            DataWindowColumnSpec(
                field_name=field_name,
                caption=caption or field_name,
                csharp_name=build_csharp_grid_column_name(field_name, prefix=prefix),
                xml_column_name=f"{prefix}{field_name}",
                data_type=table_column["data_type"],
                source="table-column",
                x=visual.get("x"),
                y=visual.get("y"),
                width=visual.get("width"),
                height=visual.get("height"),
            )
        )

    if specs:
        return specs

    # Visual-only snippets remain supported, but source occurrence order is
    # authoritative; coordinates are metadata for form placement only.
    for column in visual_columns:
        field_name = column["field_name"]
        specs.append(
            DataWindowColumnSpec(
                field_name=field_name,
                caption=_match_datawindow_caption(column, text_controls) or field_name,
                csharp_name=build_csharp_grid_column_name(field_name, prefix=prefix),
                xml_column_name=f"{prefix}{field_name}",
                source="visual-column",
                x=column.get("x"),
                y=column.get("y"),
                width=column.get("width"),
                height=column.get("height"),
            )
        )
    return specs


def build_csharp_grid_column_name(field_name: str, *, prefix: str = "colList_") -> str:
    """Build a target C# GridColumn member/control name such as colList_ENTITY_ID."""
    normalized = _normalize_datawindow_field_name(field_name)
    candidate = f"{prefix}{normalized}"
    return candidate if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", candidate) else ""


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
        return f"col{table}_" if table else (f"col{purpose}_" if purpose else "colTable_")
    if lowered in {"purpose", "domain", "role", "logical"}:
        purpose = re.sub(r"[^A-Za-z0-9_]", "", str(purpose_name or table_name or "")).upper()
        return f"col{purpose}_" if purpose else "colPurpose_"
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
            or "Table"
        )
    elif lowered in {"purpose", "domain", "role", "logical"}:
        suffix = re.sub(r"[^A-Za-z0-9_]", "", str(purpose_name or table_name or "")).upper() or "Purpose"
    else:
        suffix = re.sub(r"[^A-Za-z0-9_]", "", raw_format) or "List"
        suffix = suffix[0].upper() + suffix[1:] if suffix and not suffix.isupper() else suffix
    return {
        "grid_control_name": f"grd{suffix}",
        "grid_view_name": f"gvw{suffix}",
    }


def _caller_grid_column_csharp_name(value: Any) -> str:
    if isinstance(value, DataWindowColumnSpec):
        return str(value.csharp_name or "")
    if isinstance(value, Mapping):
        return str(value.get("csharp_name") or "")
    return ""


def _grid_column_mapping_issues(
    column_inputs: Iterable[Any],
    normalized: Iterable[DataWindowColumnSpec],
    *,
    prefix: str,
) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    seen_csharp: set[str] = set()
    for raw, column in zip(column_inputs, normalized):
        expected_xml_name = f"{prefix}{column.field_name}"
        if column.xml_column_name != expected_xml_name:
            issues.append(
                {
                    "code": "grid_xml_column_name_mapping_mismatch",
                    "severity": "error",
                    "field_name": column.field_name,
                    "expected": expected_xml_name,
                    "actual": column.xml_column_name,
                    "message": "XML Name must preserve the converter prefix plus exact uppercase FieldName.",
                }
            )
        if not column.csharp_name:
            issues.append(
                {
                    "code": "grid_column_csharp_name_mapping_required",
                    "severity": "error",
                    "field_name": column.field_name,
                    "xml_column_name": column.xml_column_name,
                    "message": "FieldName cannot be used as a C# member identifier; provide an explicit valid csharp_name mapping.",
                }
            )
            continue
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", column.csharp_name):
            issues.append(
                {
                    "code": "grid_column_csharp_name_invalid",
                    "severity": "error",
                    "field_name": column.field_name,
                    "actual": column.csharp_name,
                    "message": "GridColumn csharp_name must be a valid C# identifier distinct from XML Name.",
                }
            )
        elif not column.csharp_name.startswith(prefix):
            issues.append(
                {
                    "code": "grid_column_csharp_prefix_mismatch",
                    "severity": "error",
                    "field_name": column.field_name,
                    "expected_prefix": prefix,
                    "actual": column.csharp_name,
                    "message": "GridColumn csharp_name must use the verified custom or role prefix.",
                }
            )
        elif column.csharp_name in seen_csharp:
            issues.append(
                {
                    "code": "grid_column_csharp_name_duplicate",
                    "severity": "error",
                    "field_name": column.field_name,
                    "actual": column.csharp_name,
                    "message": "Each GridColumn requires a distinct C# member identifier.",
                }
            )
        seen_csharp.add(column.csharp_name)
    return issues


def generate_devexpress_grid_xml(
    columns: Iterable[Any],
    *,
    prefix: str = "colList_",
    grid_view_name: str = "gridView1",
    serialized_view_name: str | None = None,
) -> str:
    """Generate the DevExpress GridView XML produced by the attached DataWindowToXml helper."""
    normalized = _normalize_grid_column_specs(columns, prefix=prefix)
    xml_view_name = str(serialized_view_name or grid_view_name or "gridView1")
    lines = [
        '<XtraSerializer version="1.0" application="View">',
    ]
    for name, value in DATAWINDOW_TO_XML_GRIDVIEW_TOP_LEVEL_PROPERTIES:
        if name == "#LayoutVersion" or value == "":
            lines.append(f'  <property name="{name}" />')
        elif name == "Name":
            lines.append(f'  <property name="Name">{escape(xml_view_name)}</property>')
        else:
            lines.append(f'  <property name="{name}">{escape(value)}</property>')
    lines.insert(
        next(index for index, line in enumerate(lines) if 'DetailTabHeaderLocation' in line),
        f'  <property name="Name">{escape(xml_view_name)}</property>',
    )
    lines.append(f'  <property name="Columns" iskey="true" value="{len(normalized)}">')
    for index, column in enumerate(normalized, start=1):
        escaped_field_name = escape(column.field_name)
        escaped_name = escape(column.xml_column_name)
        escaped_caption = escaped_field_name
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
        indent = "\t" if name == "ShowAutoFilterRow" else "    "
        lines.append(f'{indent}<property name="{name}">{value}</property>')
    lines.extend(
        [
            '  </property>',
            '</XtraSerializer>',
        ]
    )
    return "\n".join(lines)


def _xml_property_map(parent: ET.Element | None) -> Dict[str, ET.Element]:
    if parent is None:
        return {}
    return {
        str(child.attrib.get("name") or ""): child
        for child in parent.findall("property")
        if child.attrib.get("name")
    }


def _xml_property_text(element: ET.Element | None) -> str:
    return "" if element is None or element.text is None else element.text


def verify_devexpress_grid_xml_contract(
    xml_text: str,
    *,
    expected_columns: Iterable[Any] | None = None,
    input_format: str = "list",
    table_name: str = "",
    purpose_name: str = "",
    expected_grid_view_name: str = "gridView1",
    expected_serialized_view_name: str | None = None,
    expected_column_prefix: str = "",
) -> HarnessResult:
    """Verify DataWindow-generated View XML values before DevExpress Designer Layout Load."""
    issues: List[Dict[str, Any]] = []

    def add_issue(code: str, message: str, **details: Any) -> None:
        issues.append({"code": code, "severity": "error", "message": message, **details})

    raw_xml = str(xml_text or "")
    encoded_size = len(raw_xml.encode("utf-8"))
    root: ET.Element | None = None
    if encoded_size > DEVEXPRESS_GRID_XML_MAX_BYTES:
        add_issue(
            "grid_xml_size_limit_exceeded",
            "Generated GridView XML exceeds the verifier size limit.",
            actual=encoded_size,
            maximum=DEVEXPRESS_GRID_XML_MAX_BYTES,
        )
    elif re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", raw_xml, flags=re.IGNORECASE):
        add_issue(
            "grid_xml_dtd_or_entity_forbidden",
            "DTD and entity declarations are forbidden in GridView layout XML.",
        )
    else:
        try:
            root = ET.fromstring(raw_xml)
        except ET.ParseError as exc:
            add_issue("grid_xml_parse_error", "Generated GridView XML must be well-formed.", detail=str(exc))

    def element_depth(element: ET.Element) -> int:
        maximum = 0
        pending = [(element, 1)]
        while pending:
            current, depth = pending.pop()
            maximum = max(maximum, depth)
            pending.extend((child, depth + 1) for child in list(current))
        return maximum

    def property_map(
        parent: ET.Element | None,
        *,
        path: str,
        allowed_names: set[str],
    ) -> Dict[str, ET.Element]:
        mapped: Dict[str, ET.Element] = {}
        if parent is None:
            return mapped
        for child in list(parent):
            if child.tag != "property":
                add_issue(
                    "grid_xml_unexpected_element",
                    "GridView layout hierarchy accepts property elements only.",
                    path=path,
                    actual=child.tag,
                )
                continue
            name = str(child.attrib.get("name") or "")
            if not name or name not in allowed_names:
                add_issue(
                    "grid_xml_unexpected_property",
                    "GridView layout contains an unexpected property name.",
                    path=path,
                    actual=name,
                )
            if name in mapped:
                add_issue(
                    "grid_xml_duplicate_property",
                    "GridView layout properties must be unique within each serializer scope.",
                    path=path,
                    property=name,
                )
                continue
            mapped[name] = child
        return mapped

    def require_attributes(element: ET.Element | None, expected: Dict[str, str], *, path: str) -> None:
        if element is not None and dict(element.attrib) != expected:
            add_issue(
                "grid_xml_attribute_mismatch",
                "GridView layout element attributes must match the DataWindowToXml hierarchy exactly.",
                path=path,
                expected=expected,
                actual=dict(element.attrib),
            )

    def require_leaf(element: ET.Element | None, *, path: str) -> None:
        if element is not None and list(element):
            add_issue(
                "grid_xml_leaf_hierarchy_mismatch",
                "Scalar GridView layout properties must not contain nested elements.",
                path=path,
            )

    resolved_prefix = str(expected_column_prefix or "") or resolve_csharp_grid_column_prefix(
        input_format, table_name=table_name, purpose_name=purpose_name
    )
    expected_columns_list = None if expected_columns is None else list(expected_columns)
    normalized_expected = (
        None
        if expected_columns_list is None
        else _normalize_grid_column_specs(expected_columns_list, prefix=resolved_prefix)
    )
    for column in normalized_expected or []:
        expected_xml_name = f"{resolved_prefix}{column.field_name}"
        if column.xml_column_name != expected_xml_name:
            add_issue(
                "grid_xml_column_name_mapping_mismatch",
                "Expected XML Name must preserve the verified prefix plus exact uppercase FieldName.",
                field_name=column.field_name,
                expected=expected_xml_name,
                actual=column.xml_column_name,
            )
    verified_columns: List[Dict[str, Any]] = []
    if root is not None:
        element_count = sum(1 for _ in root.iter())
        depth = element_depth(root)
        if element_count > DEVEXPRESS_GRID_XML_MAX_ELEMENTS:
            add_issue(
                "grid_xml_element_limit_exceeded",
                "Generated GridView XML contains too many elements.",
                actual=element_count,
                maximum=DEVEXPRESS_GRID_XML_MAX_ELEMENTS,
            )
        if depth > DEVEXPRESS_GRID_XML_MAX_DEPTH:
            add_issue(
                "grid_xml_depth_limit_exceeded",
                "Generated GridView XML exceeds the permitted hierarchy depth.",
                actual=depth,
                maximum=DEVEXPRESS_GRID_XML_MAX_DEPTH,
            )
        if root.tag != "XtraSerializer":
            add_issue("grid_xml_serializer_element_mismatch", "Root element must be XtraSerializer.")
        require_attributes(root, {"version": "1.0", "application": "View"}, path="XtraSerializer")
        if root.attrib.get("version") != "1.0":
            add_issue("grid_xml_serializer_version_mismatch", "Serializer version must be 1.0.")
        if root.attrib.get("application") != "View":
            add_issue("grid_xml_serializer_application_mismatch", "Serializer application must be View.")

        top_names = {name for name, _ in DATAWINDOW_TO_XML_GRIDVIEW_TOP_LEVEL_PROPERTIES}
        top_names.update({"Name", "Columns", "OptionsView"})
        top = property_map(root, path="XtraSerializer", allowed_names=top_names)
        for property_name, expected_value in DATAWINDOW_TO_XML_GRIDVIEW_TOP_LEVEL_PROPERTIES:
            element = top.get(property_name)
            actual_value = _xml_property_text(element)
            require_attributes(element, {"name": property_name}, path=f"XtraSerializer/{property_name}")
            require_leaf(element, path=f"XtraSerializer/{property_name}")
            if element is None or actual_value != expected_value:
                add_issue(
                    "grid_xml_top_level_value_mismatch",
                    f"GridView XML property {property_name} must equal the authoritative Layout Load value.",
                    property=property_name,
                    expected=expected_value,
                    actual=None if element is None else actual_value,
                )
        serialized_view_name = str(expected_serialized_view_name or expected_grid_view_name or "gridView1")
        name_element = top.get("Name")
        require_attributes(name_element, {"name": "Name"}, path="XtraSerializer/Name")
        require_leaf(name_element, path="XtraSerializer/Name")
        if name_element is None or _xml_property_text(name_element) != serialized_view_name:
            add_issue(
                "grid_xml_view_name_mismatch",
                "The serialized View Name must match the generated XML artifact name; C# target naming is verified separately.",
                expected=serialized_view_name,
                actual=None if name_element is None else _xml_property_text(name_element),
            )

        columns_element = top.get("Columns")
        column_elements = list(columns_element.findall("property")) if columns_element is not None else []
        if columns_element is None:
            add_issue("grid_xml_columns_missing", "GridView XML must contain the keyed Columns property.")
        else:
            for child in list(columns_element):
                if child.tag != "property":
                    add_issue(
                        "grid_xml_unexpected_element",
                        "Columns may contain serialized Item properties only.",
                        path="XtraSerializer/Columns",
                        actual=child.tag,
                    )
            require_attributes(
                columns_element,
                {"name": "Columns", "iskey": "true", "value": str(len(column_elements))},
                path="XtraSerializer/Columns",
            )
            if columns_element.attrib.get("value") != str(len(column_elements)):
                add_issue(
                    "grid_xml_column_count_mismatch",
                    "Columns value must equal the number of serialized column items.",
                    expected=str(len(column_elements)),
                    actual=columns_element.attrib.get("value"),
                )
        if normalized_expected is not None and len(column_elements) != len(normalized_expected):
            add_issue(
                "grid_xml_expected_column_count_mismatch",
                "Serialized column count must match the expected DataWindow mapping.",
                expected=len(normalized_expected),
                actual=len(column_elements),
            )

        for index, column_element in enumerate(column_elements, start=1):
            require_attributes(
                column_element,
                {"name": f"Item{index}", "isnull": "true", "iskey": "true"},
                path=f"XtraSerializer/Columns/Item{index}",
            )
            column_property_names = {
                "AppearanceHeader", "AppearanceCell", "Visible", "VisibleIndex", "FieldName", "Name", "Caption", "ColumnEditName"
            }
            props = property_map(
                column_element,
                path=f"XtraSerializer/Columns/Item{index}",
                allowed_names=column_property_names,
            )
            expected = (
                normalized_expected[index - 1]
                if normalized_expected is not None and index <= len(normalized_expected)
                else None
            )
            field_name = _xml_property_text(props.get("FieldName"))
            expected_field = expected.field_name if expected is not None else field_name.upper()
            expected_name = (
                expected.xml_column_name
                if expected is not None
                else f"{resolved_prefix}{expected_field}"
            )
            expected_caption = expected_field
            value_checks = {
                "Visible": "true",
                "VisibleIndex": str(index),
                "FieldName": expected_field,
                "Name": expected_name,
                "Caption": expected_caption,
                "ColumnEditName": "",
            }
            for property_name, expected_value in value_checks.items():
                element = props.get(property_name)
                actual_value = _xml_property_text(element)
                require_attributes(
                    element,
                    {"name": property_name},
                    path=f"XtraSerializer/Columns/Item{index}/{property_name}",
                )
                require_leaf(element, path=f"XtraSerializer/Columns/Item{index}/{property_name}")
                if element is None or actual_value != expected_value:
                    add_issue(
                        "grid_xml_column_value_mismatch",
                        f"Serialized column {index} property {property_name} has the wrong value.",
                        column=index,
                        property=property_name,
                        expected=expected_value,
                        actual=None if element is None else actual_value,
                    )
            if field_name != field_name.upper() or not re.fullmatch(r"[A-Z_#$][A-Z0-9_#$]*", field_name):
                add_issue(
                    "grid_xml_field_name_not_upper_source_field",
                    "Column FieldName must be the uppercase source field.",
                    column=index,
                    actual=field_name,
                )

            header_element = props.get("AppearanceHeader")
            cell_element = props.get("AppearanceCell")
            require_attributes(header_element, {"name": "AppearanceHeader", "isnull": "true", "iskey": "true"}, path=f"Item{index}/AppearanceHeader")
            require_attributes(cell_element, {"name": "AppearanceCell", "isnull": "true", "iskey": "true"}, path=f"Item{index}/AppearanceCell")
            header = property_map(header_element, path=f"Item{index}/AppearanceHeader", allowed_names={"Options", "TextOptions", "Font"})
            header_options_element = header.get("Options")
            header_text_element = header.get("TextOptions")
            cell = property_map(cell_element, path=f"Item{index}/AppearanceCell", allowed_names={"Options", "Font"})
            cell_options_element = cell.get("Options")
            for nested, nested_name, nested_path in (
                (header_options_element, "Options", f"Item{index}/AppearanceHeader/Options"),
                (header_text_element, "TextOptions", f"Item{index}/AppearanceHeader/TextOptions"),
                (cell_options_element, "Options", f"Item{index}/AppearanceCell/Options"),
            ):
                require_attributes(nested, {"name": nested_name, "isnull": "true", "iskey": "true"}, path=nested_path)
            header_options = property_map(header_options_element, path=f"Item{index}/AppearanceHeader/Options", allowed_names={"UseTextOptions", "UseFont"})
            header_text = property_map(header_text_element, path=f"Item{index}/AppearanceHeader/TextOptions", allowed_names={"HAlignment", "VAlignment"})
            cell_options = property_map(cell_options_element, path=f"Item{index}/AppearanceCell/Options", allowed_names={"UseFont"})
            appearance_checks = [
                ("AppearanceHeader.Options.UseTextOptions", header_options.get("UseTextOptions"), "true"),
                ("AppearanceHeader.Options.UseFont", header_options.get("UseFont"), "true"),
                ("AppearanceHeader.TextOptions.HAlignment", header_text.get("HAlignment"), "Center"),
                ("AppearanceHeader.TextOptions.VAlignment", header_text.get("VAlignment"), "Center"),
                ("AppearanceHeader.Font", header.get("Font"), "Tahoma, 9pt"),
                ("AppearanceCell.Options.UseFont", cell_options.get("UseFont"), "true"),
                ("AppearanceCell.Font", cell.get("Font"), "Tahoma, 9pt"),
            ]
            for property_path, element, expected_value in appearance_checks:
                actual_value = _xml_property_text(element)
                require_attributes(element, {"name": property_path.split(".")[-1]}, path=f"Item{index}/{property_path}")
                require_leaf(element, path=f"Item{index}/{property_path}")
                if element is None or actual_value != expected_value:
                    add_issue(
                        "grid_xml_column_appearance_value_mismatch",
                        f"Serialized column {index} {property_path} must match the authoritative Layout Load value.",
                        column=index,
                        property=property_path,
                        expected=expected_value,
                        actual=None if element is None else actual_value,
                    )
            verified_columns.append(
                {"field_name": field_name, "name": _xml_property_text(props.get("Name")), "caption": _xml_property_text(props.get("Caption"))}
            )

        options_element = top.get("OptionsView")
        require_attributes(options_element, {"name": "OptionsView", "isnull": "true", "iskey": "true"}, path="XtraSerializer/OptionsView")
        options = property_map(
            options_element,
            path="XtraSerializer/OptionsView",
            allowed_names=set(DATAWINDOW_TO_XML_OPTIONS_VIEW_DEFAULTS),
        )
        for property_name, expected_value in DATAWINDOW_TO_XML_OPTIONS_VIEW_DEFAULTS.items():
            element = options.get(property_name)
            actual_value = _xml_property_text(element)
            require_attributes(element, {"name": property_name}, path=f"XtraSerializer/OptionsView/{property_name}")
            require_leaf(element, path=f"XtraSerializer/OptionsView/{property_name}")
            if element is None or actual_value != expected_value:
                add_issue(
                    "grid_xml_options_view_value_mismatch",
                    f"OptionsView.{property_name} must match the authoritative Layout Load value.",
                    property=property_name,
                    expected=expected_value,
                    actual=None if element is None else actual_value,
                )

    passed = not issues
    metadata = {
        "harness": "pb-to-csharp-migration-harness",
        "status": "passed" if passed else "blocked",
        "serializer_version": "1.0",
        "serializer_application": "View",
        "xml_size_bytes": encoded_size,
        "csharp_column_prefix": resolved_prefix,
        "columns": verified_columns,
        "issues": issues,
        "layout_load_semantics": (
            "Static verification proves exact Layout-Load-ready XML only; it does not prove that DevExpress Designer loaded it."
        ),
        "actual_live_layout_load_observed": False,
        "token_optimizer_status": "passthrough",
    }
    return HarnessResult(
        success=passed,
        stdout=json.dumps({"status": metadata["status"], "issue_count": len(issues)}, ensure_ascii=False, sort_keys=True),
        stderr="" if passed else "Generated DevExpress GridView XML contract verification failed.",
        exit_code=0 if passed else 1,
        metadata=metadata,
    )


def build_datawindow_gridview_designer_defaults(view_name: str = "gvwList") -> List[str]:
    """Return C# assignments equivalent to authoritative DataWindow XML Layout Load defaults."""
    view = str(view_name or "gvwList").strip() or "gvwList"
    return [
        *[
            f"this.{view}.{property_name} = {value};"
            for property_name, value in DATAWINDOW_TO_CSHARP_GRIDVIEW_DEFAULTS
        ],
        *[
            f"this.{view}.OptionsView.{property_name} = {value};"
            for property_name, value in DATAWINDOW_TO_XML_OPTIONS_VIEW_DEFAULTS.items()
        ],
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
    """Build an explicit Designer grid equivalent to the authoritative XML Layout Load result."""
    column_inputs = list(columns)
    resolved_prefix = prefix or resolve_csharp_grid_column_prefix(
        input_format, table_name=table_name, purpose_name=purpose_name
    )
    grid_names = resolve_csharp_grid_control_names(input_format, table_name=table_name, purpose_name=purpose_name)
    requested_view_name = str(grid_view_name or "").strip()
    view_name = grid_names["grid_view_name"]
    normalized = _normalize_grid_column_specs(column_inputs, prefix=resolved_prefix)
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
    issues.extend(_grid_column_mapping_issues(column_inputs, normalized, prefix=resolved_prefix))
    role = str(input_format or "list").strip().lower()
    if role in {"table", "dbtable", "source-table", "source_table"} and not str(table_name or purpose_name).strip():
        issues.append(
            {
                "code": "grid_table_suffix_required",
                "severity": "error",
                "message": "Table-role grids require an explicit table or purpose suffix; colList_ is reserved for list role.",
            }
        )
    if role in {"purpose", "domain", "role", "logical"} and not str(purpose_name or table_name).strip():
        issues.append(
            {
                "code": "grid_purpose_suffix_required",
                "severity": "error",
                "message": "Purpose-role grids require an explicit purpose suffix; colList_ is reserved for list role.",
            }
        )
    if requested_view_name and requested_view_name != view_name:
        issues.append(
            {
                "code": "grid_view_name_role_mismatch",
                "severity": "error",
                "expected": view_name,
                "actual": requested_view_name,
                "message": "C# GridView naming follows the target role and must not copy the serialized XML view name.",
            }
        )
    numeric_repository_by_column: Dict[str, str] = {}
    for column in normalized:
        field_upper = str(column.field_name or "").upper()
        if _is_numeric_grid_column(column):
            if "QTY" in field_upper or "WGT" in field_upper:
                numeric_repository_by_column[column.csharp_name] = "rpsSpinQty"
            else:
                numeric_repository_by_column[column.csharp_name] = "rpsSpinAmt"
    required_repositories = sorted(set(numeric_repository_by_column.values()))
    declarations = [
        f"private DevExpress.XtraGrid.GridControl {grid_names['grid_control_name']};",
        f"private DevExpress.XtraGrid.Views.Grid.GridView {view_name};",
        *[f"private DevExpress.XtraGrid.Columns.GridColumn {column.csharp_name};" for column in normalized],
    ]
    declarations.extend(
        f"private DevExpress.XtraEditors.Repository.RepositoryItemSpinEdit {repository_name};"
        for repository_name in required_repositories
    )
    initializers = [
        f"this.{grid_names['grid_control_name']} = new DevExpress.XtraGrid.GridControl();",
        f"this.{view_name} = new DevExpress.XtraGrid.Views.Grid.GridView();",
        *[f"this.{column.csharp_name} = new DevExpress.XtraGrid.Columns.GridColumn();" for column in normalized],
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
    grid_wiring = [
        f"this.{grid_names['grid_control_name']}.MainView = this.{view_name};",
        f"this.{grid_names['grid_control_name']}.Name = \"{grid_names['grid_control_name']}\";",
        f"this.{grid_names['grid_control_name']}.ViewCollection.AddRange(new DevExpress.XtraGrid.Views.Base.BaseView[] {{",
        f"    this.{view_name}",
        "});",
        f"this.{view_name}.GridControl = this.{grid_names['grid_control_name']};",
        f"this.{view_name}.Name = \"{view_name}\";",
    ]
    view_defaults = build_datawindow_gridview_designer_defaults(view_name)
    assignments: List[str] = []
    for index, column in enumerate(normalized, start=1):
        visible = "true"
        assignments.extend(
            [
                f'this.{column.csharp_name}.Caption = "{_escape_csharp_string(column.caption or column.field_name)}";',
                f'this.{column.csharp_name}.FieldName = "{_escape_csharp_string(column.field_name)}";',
                f'this.{column.csharp_name}.Name = "{_escape_csharp_string(column.csharp_name)}";',
                f"this.{column.csharp_name}.OptionsColumn.AllowEdit = {str(default_allow_edit).lower()};",
                f"this.{column.csharp_name}.AppearanceHeader.Options.UseTextOptions = true;",
                f"this.{column.csharp_name}.AppearanceHeader.Options.UseFont = true;",
                f"this.{column.csharp_name}.AppearanceHeader.TextOptions.HAlignment = DevExpress.Utils.HorzAlignment.Center;",
                f"this.{column.csharp_name}.AppearanceHeader.TextOptions.VAlignment = DevExpress.Utils.VertAlignment.Center;",
                f'this.{column.csharp_name}.AppearanceHeader.Font = new System.Drawing.Font("Tahoma", 9F);',
                f"this.{column.csharp_name}.AppearanceCell.Options.UseFont = true;",
                f'this.{column.csharp_name}.AppearanceCell.Font = new System.Drawing.Font("Tahoma", 9F);',
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
        "// GridControl and GridView wiring",
        *grid_wiring,
        "",
        "// Authoritative DataWindow XML Layout Load defaults",
        *view_defaults,
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
        "grid_wiring": grid_wiring,
        "view_defaults": view_defaults,
        "assignments": assignments,
        "repository_registration": repository_registration,
        "repository_assignments": repository_assignments,
        "numeric_repository_by_column": numeric_repository_by_column,
        "result_fields": sorted(normalized_result_fields or []),
        "issues": issues,
        "designer_contract": (
            "Use explicit grd<Role>/gvw<Role>/col<Role>_<FIELD> members, GridControl/GridView wiring, Columns.AddRange, "
            "and the authoritative DataWindow XML Layout Load defaults. Register repositories before ColumnEdit and "
            "do not copy the serialized gridView1 name into C# Designer output."
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
    issues.extend(
        {
            "code": "csharp_result_field_mapping_unresolved",
            "severity": "error",
            **item,
            "message": "C# BindingField/FieldName/DataPropertyName mappings must use a resolvable direct string literal.",
        }
        for item in unresolved
    )
    has_errors = any(item.get("severity") == "error" for item in issues)
    return issues, {
        "status": "passed" if not has_errors else "blocked",
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
    allow_empty_designer: bool = False,
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
    if designer_source.strip() and not designer_findings and not allow_empty_designer:
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


def _grid_contract_suffix(
    role: str,
    suffix: str,
    designer_source: str,
) -> tuple[str, List[Dict[str, Any]]]:
    issues: List[Dict[str, Any]] = []
    normalized_role = str(role or "").strip().lower()
    normalized_suffix = re.sub(r"[^A-Za-z0-9_]", "", str(suffix or "").strip())
    if normalized_role in {"", "list", "main", "master"} and not normalized_suffix:
        if normalized_role:
            return "List", issues
    if normalized_role in {"detail", "line", "child"} and not normalized_suffix:
        return "Detail", issues
    if normalized_role in {"table", "dbtable", "source-table", "source_table", "purpose", "domain", "role", "logical"}:
        if not normalized_suffix:
            issues.append(
                {
                    "code": "expected_grid_suffix_required",
                    "severity": "error",
                    "message": "Table or purpose grid verification requires an explicit expected suffix; List is not a fallback for these roles.",
                }
            )
            return "Table" if normalized_role.startswith(("table", "dbtable", "source")) else "Purpose", issues
        return normalized_suffix.upper(), issues
    if normalized_suffix:
        return normalized_suffix if normalized_suffix.isupper() else normalized_suffix[0].upper() + normalized_suffix[1:], issues
    column_match = re.search(r"\bcol(?P<suffix>[A-Za-z0-9]+)_[A-Z][A-Z0-9_]*\b", designer_source)
    if column_match:
        return column_match.group("suffix"), issues
    view_match = re.search(r"\bgvw(?P<suffix>[A-Za-z0-9_]+)\b", designer_source)
    return (view_match.group("suffix") if view_match else "List"), issues


def _csharp_class_scopes(structural_source: str) -> List[Dict[str, Any]]:
    scopes: List[Dict[str, Any]] = []
    class_pattern = re.compile(
        r"\b(?:(?:public|internal|protected|private|abstract|sealed|static|partial)\s+)*"
        r"class\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
    )
    for match in class_pattern.finditer(structural_source):
        body_start = structural_source.find("{", match.end())
        if body_start < 0:
            continue
        depth = 0
        body_end = -1
        for position in range(body_start, len(structural_source)):
            token = structural_source[position]
            if token == "{":
                depth += 1
            elif token == "}":
                depth -= 1
                if depth == 0:
                    body_end = position + 1
                    break
        if body_end < 0:
            continue
        scopes.append(
            {
                "name": match.group("name"),
                "start": match.start(),
                "body_start": body_start,
                "end": body_end,
            }
        )
    return scopes


def _csharp_owning_class_scope(
    class_scopes: Iterable[Mapping[str, Any]],
    position: int,
) -> Dict[str, Any] | None:
    containing = [
        dict(scope)
        for scope in class_scopes
        if int(scope.get("body_start", -1)) < position < int(scope.get("end", -1))
    ]
    if not containing:
        return None
    return min(containing, key=lambda item: int(item["end"]) - int(item["start"]))


def _csharp_scope_key(scope: Mapping[str, Any] | None) -> tuple[int, int]:
    if not scope:
        return (-1, -1)
    return (int(scope.get("start", -1)), int(scope.get("end", -1)))


def _csharp_scope_keys(scope: Mapping[str, Any] | None) -> set[tuple[int, int]]:
    if not scope:
        return set()
    partial_scopes = scope.get("partial_scopes")
    if isinstance(partial_scopes, list):
        return {
            _csharp_scope_key(item)
            for item in partial_scopes
            if isinstance(item, Mapping)
        }
    return {_csharp_scope_key(scope)}


def _csharp_scope_is_selected(
    owner: Mapping[str, Any] | None,
    selected: Mapping[str, Any] | None,
) -> bool:
    return _csharp_scope_key(owner) in _csharp_scope_keys(selected)


def _csharp_position_in_scopes(
    position: int,
    scopes: Iterable[Mapping[str, Any]],
) -> bool:
    return any(
        int(scope.get("body_start", -1)) < position < int(scope.get("end", -1))
        for scope in scopes
    )


def _csharp_initialize_component_scopes(
    structural_source: str,
    *,
    class_scope: Mapping[str, Any] | None,
    class_scopes: Iterable[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    scopes: List[Dict[str, Any]] = []
    pattern = re.compile(
        r"\b(?:(?:public|protected|internal|private|static|virtual|override)\s+)*"
        r"void\s+InitializeComponent\s*\(\s*\)"
    )
    all_class_scopes = list(class_scopes)
    for match in pattern.finditer(structural_source):
        owner = _csharp_owning_class_scope(all_class_scopes, match.start())
        if not _csharp_scope_is_selected(owner, class_scope):
            continue
        owner_body_start = int(owner.get("body_start", -1)) if owner else -1
        if owner_body_start < 0:
            continue
        member_prefix = structural_source[owner_body_start + 1 : match.start()]
        if member_prefix.count("{") != member_prefix.count("}"):
            continue
        body_start = structural_source.find("{", match.end())
        if body_start < 0 or not owner or body_start >= int(owner.get("end", -1)):
            continue
        if structural_source[match.end() : body_start].strip():
            continue
        depth = 0
        body_end = -1
        for position in range(body_start, int(owner["end"])):
            token = structural_source[position]
            if token == "{":
                depth += 1
            elif token == "}":
                depth -= 1
                if depth == 0:
                    body_end = position + 1
                    break
        if body_end > 0:
            scopes.append(
                {
                    "name": "InitializeComponent",
                    "start": match.start(),
                    "body_start": body_start,
                    "end": body_end,
                    "class_scope": dict(owner),
                }
            )
    return scopes


def _resolve_csharp_designer_form_scope(
    structural_source: str,
    *,
    requested_form_class: str,
    required: bool,
) -> tuple[List[Dict[str, Any]], Dict[str, Any] | None, List[Dict[str, Any]], Dict[str, Any]]:
    scopes = _csharp_class_scopes(structural_source)
    requested = str(requested_form_class or "").strip()
    candidates = (
        [scope for scope in scopes if str(scope["name"]).lower() == requested.lower()]
        if requested
        else list(scopes)
    )
    candidate_names = {str(scope["name"]).lower() for scope in candidates}
    selected = None
    if candidates and len(candidate_names) == 1:
        selected = dict(candidates[0])
        selected["partial_scopes"] = [dict(scope) for scope in candidates]
    issues: List[Dict[str, Any]] = []
    if required and not candidates:
        issues.append(
            {
                "code": "control_contract_form_scope_missing",
                "severity": "error",
                "expected_form_class": requested,
                "message": "Expected control evidence requires one matching Designer form class.",
            }
        )
    elif required and selected is None:
        issues.append(
            {
                "code": "control_contract_form_scope_ambiguous",
                "severity": "error",
                "expected_form_class": requested,
                "matching_class_count": len(candidates),
                "message": "Expected control evidence is ambiguous across multiple Designer class bodies.",
            }
        )
    metadata = {
        "status": "selected" if selected else ("blocked" if required else "not_selected"),
        "requested_form_class": requested,
        "selected_form_class": str(selected.get("name") or "") if selected else "",
        "declared_form_classes": [str(scope["name"]) for scope in scopes],
        "matching_class_count": len(candidates),
        "partial_declaration_count": len(candidates) if selected else 0,
    }
    return issues, selected, scopes, metadata


def _csharp_designer_assignments(
    source: str,
    structural_source: str = "",
    *,
    class_scope: Mapping[str, Any] | None = None,
    class_scopes: Iterable[Mapping[str, Any]] | None = None,
    method_scopes: Iterable[Mapping[str, Any]] | None = None,
) -> Dict[tuple[str, str], List[Dict[str, Any]]]:
    assignments: Dict[tuple[str, str], List[Dict[str, Any]]] = {}
    structural = structural_source or source
    scopes = list(class_scopes or [])
    selected_method_scopes = list(method_scopes or [])
    scope_filter_requested = class_scopes is not None
    method_filter_requested = method_scopes is not None
    for match in re.finditer(
        r"^[ \t]*this\.(?P<member>[A-Za-z_][A-Za-z0-9_]*)\."
        r"(?P<property>[A-Za-z_][A-Za-z0-9_.]*)[ \t]*=",
        structural,
        flags=re.MULTILINE,
    ):
        if scope_filter_requested:
            owner = _csharp_owning_class_scope(scopes, match.start())
            if not _csharp_scope_is_selected(owner, class_scope):
                continue
        if method_filter_requested and not _csharp_position_in_scopes(
            match.start(), selected_method_scopes
        ):
            continue
        value_start = match.end()
        value_end = structural.find(";", value_start)
        if value_end < 0:
            continue
        owner_scope = _csharp_owning_class_scope(scopes, match.start())
        assignments.setdefault((match.group("member"), match.group("property")), []).append(
            {
                "value": source[value_start:value_end].strip(),
                "position": match.start(),
                "conditional": _csharp_assignment_is_conditional(
                    structural,
                    match.start(),
                    owner_scope,
                ),
            }
        )
    return assignments


def _csharp_assignment_is_conditional(
    structural_source: str,
    position: int,
    class_scope: Mapping[str, Any] | None,
) -> bool:
    start = int(class_scope.get("body_start", -1)) + 1 if class_scope else 0
    immediate_prefix = structural_source[
        max(start, position - 512) : position
    ].rstrip()
    if re.search(
        r"\b(?:if|else|switch|for|foreach|while|do|catch)\b"
        r"(?:\s*\([^{};]*\))?\s*$",
        immediate_prefix,
        flags=re.DOTALL,
    ):
        return True
    open_braces: List[int] = []
    for cursor in range(max(start, 0), min(position, len(structural_source))):
        token = structural_source[cursor]
        if token == "{":
            open_braces.append(cursor)
        elif token == "}" and open_braces:
            open_braces.pop()
    for brace_position in open_braces:
        prefix = structural_source[max(start, brace_position - 512) : brace_position].rstrip()
        if re.search(
            r"\b(?:if|else|switch|for|foreach|while|do|catch)\b"
            r"(?:\s*\([^{};]*\))?\s*$",
            prefix,
            flags=re.DOTALL,
        ):
            return True
    return False


def _csharp_assignment_values(
    assignments: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
    key: tuple[str, str],
) -> List[str]:
    return [str(item.get("value") or "") for item in assignments.get(key, [])]


def _csharp_last_assignment_value(
    assignments: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
    key: tuple[str, str],
    default: Any = None,
) -> Any:
    values = _csharp_assignment_values(assignments, key)
    return values[-1] if values else default


def _csharp_direct_string_value(value: str) -> str | None:
    raw = str(value or "").strip()
    if raw in {"string.Empty", "System.String.Empty", '""'}:
        return ""
    verbatim_match = re.fullmatch(r'@"((?:""|[^"])*)"', raw, flags=re.DOTALL)
    if verbatim_match:
        return verbatim_match.group(1).replace('""', '"')
    match = re.fullmatch(r'"((?:\\.|[^"\\])*)"', raw)
    if not match:
        return None
    content = match.group(1)
    content = re.sub(
        r"\\u([0-9A-Fa-f]{4})",
        lambda item: chr(int(item.group(1), 16)),
        content,
    )
    content = re.sub(
        r"\\U([0-9A-Fa-f]{8})",
        lambda item: chr(int(item.group(1), 16)),
        content,
    )
    escapes = {
        r"\0": "\0",
        r"\a": "\a",
        r"\b": "\b",
        r"\f": "\f",
        r"\n": "\n",
        r"\r": "\r",
        r"\t": "\t",
        r"\v": "\v",
        r'\"': '"',
        r"\'": "'",
        r"\\": "\\",
    }
    return re.sub(
        r"\\[0abfnrtv\"'\\]",
        lambda item: escapes.get(item.group(0), item.group(0)),
        content,
    )


def _normalize_csharp_type_name(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").replace("global::", ""))


def _csharp_type_matches(actual: str, expected: str) -> bool:
    normalized_actual = _normalize_csharp_type_name(actual)
    normalized_expected = _normalize_csharp_type_name(expected)
    if not normalized_actual or not normalized_expected:
        return False
    if "." in normalized_actual and "." in normalized_expected:
        return normalized_actual == normalized_expected
    return normalized_actual.rsplit(".", 1)[-1] == normalized_expected.rsplit(".", 1)[-1]


def _csharp_exact_property_matches(actual: str, expected: Any) -> bool:
    raw_actual = str(actual or "").strip()
    scalar_actual = re.sub(r"\s+", "", raw_actual)
    while scalar_actual.startswith("(") and scalar_actual.endswith(")"):
        scalar_actual = scalar_actual[1:-1]
    parsed_actual = _parse_csharp_designer_value(scalar_actual)
    if expected is None:
        return raw_actual == "null"
    if type(expected) in {bool, int, float}:
        return parsed_actual == expected
    return re.sub(r"\s+", "", raw_actual) == re.sub(r"\s+", "", str(expected).strip())


def _designer_control_types(
    source: str,
    *,
    class_scope: Mapping[str, Any] | None = None,
    class_scopes: Iterable[Mapping[str, Any]] | None = None,
    initializer_scopes: Iterable[Mapping[str, Any]] | None = None,
) -> tuple[Dict[str, str], Dict[str, str]]:
    declarations: Dict[str, str] = {}
    initializers: Dict[str, str] = {}
    scopes = list(class_scopes or [])
    selected_initializer_scopes = list(initializer_scopes or [])
    scope_filter_requested = class_scopes is not None
    initializer_filter_requested = initializer_scopes is not None
    declaration_pattern = re.compile(
        r"(?m)^\s*(?:public|protected|internal|private)\s+"
        r"(?:(?:static|readonly)\s+)*(?P<type>(?:global::)?[A-Za-z_][A-Za-z0-9_.<>]*)\s+"
        r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*;"
    )
    initializer_pattern = re.compile(
        r"(?m)^\s*this\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*new\s+"
        r"(?P<type>(?:global::)?[A-Za-z_][A-Za-z0-9_.<>]*)\s*\("
    )
    for match in declaration_pattern.finditer(source):
        if scope_filter_requested and not _csharp_scope_is_selected(
            _csharp_owning_class_scope(scopes, match.start()), class_scope
        ):
            continue
        declarations[match.group("name")] = match.group("type")
    for match in initializer_pattern.finditer(source):
        if scope_filter_requested and not _csharp_scope_is_selected(
            _csharp_owning_class_scope(scopes, match.start()), class_scope
        ):
            continue
        if initializer_filter_requested and not _csharp_position_in_scopes(
            match.start(), selected_initializer_scopes
        ):
            continue
        initializers[match.group("name")] = match.group("type")
    return declarations, initializers


def _normalized_evidence_references(value: Any) -> List[str]:
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, Mapping):
        candidates = value.get("evidence_refs", value.get("references", []))
        if isinstance(candidates, str):
            candidates = [candidates]
    elif isinstance(value, Iterable):
        candidates = list(value)
    else:
        candidates = []
    return [str(item).strip() for item in candidates if str(item).strip()]


def _strict_evidence_references(value: Any) -> tuple[List[str], bool]:
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
        candidates = list(value)
    else:
        return [], False
    references = [item.strip() for item in candidates if isinstance(item, str) and item.strip()]
    valid = bool(references) and len(references) == len(candidates)
    valid = valid and len(references) == len(set(references))
    valid = valid and all(
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]*", reference)
        for reference in references
    )
    return references, bool(valid)


def _normalized_sha256(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw.startswith("sha256:"):
        raw = raw.split(":", 1)[1]
    return raw if re.fullmatch(r"[0-9a-f]{64}", raw) else ""


def _validate_text_artifact_binding(
    supplied_text: str,
    *,
    path_value: str | Path,
    expected_sha256: str,
    role: str,
    required: bool,
) -> tuple[List[Dict[str, Any]], Dict[str, Any], str]:
    path_text = str(path_value or "").strip()
    expected_digest = _normalized_sha256(expected_sha256)
    issues: List[Dict[str, Any]] = []
    metadata = {
        "role": role,
        "status": "not_requested",
        "path": "",
        "expected_sha256": f"sha256:{expected_digest}" if expected_digest else "",
        "actual_sha256": "",
        "readback_matches_supplied_text": False,
    }
    if not path_text and not expected_digest:
        if required:
            issues.append(
                {
                    "code": f"target_{role}_artifact_required",
                    "severity": "error",
                    "message": f"Current profile verification requires the exact target {role} path and SHA-256.",
                }
            )
            metadata["status"] = "blocked"
        return issues, metadata, ""
    if not path_text or not expected_digest:
        issues.append(
            {
                "code": f"target_{role}_artifact_binding_incomplete",
                "severity": "error",
                "message": f"Target {role} artifact binding requires both path and SHA-256.",
            }
        )
        metadata["status"] = "blocked"
        return issues, metadata, ""
    path = Path(path_text)
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        issues.append(
            {
                "code": f"target_{role}_artifact_unreadable",
                "severity": "error",
                "message": f"Target {role} artifact path must be readable.",
                "detail": str(exc),
            }
        )
        metadata["status"] = "blocked"
        return issues, metadata, ""
    actual_digest = hashlib.sha256(raw_bytes).hexdigest()
    metadata["path"] = str(path.resolve())
    metadata["actual_sha256"] = f"sha256:{actual_digest}"
    if actual_digest != expected_digest:
        issues.append(
            {
                "code": f"target_{role}_artifact_digest_mismatch",
                "severity": "error",
                "message": f"Target {role} artifact SHA-256 does not match the expected digest.",
            }
        )
    try:
        readback = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        issues.append(
            {
                "code": f"target_{role}_artifact_decode_failed",
                "severity": "error",
                "message": f"Target {role} artifact must be UTF-8 or UTF-8 with BOM.",
                "detail": str(exc),
            }
        )
        readback = ""
    metadata["readback_matches_supplied_text"] = readback == str(supplied_text or "")
    if not metadata["readback_matches_supplied_text"]:
        issues.append(
            {
                "code": f"target_{role}_artifact_text_mismatch",
                "severity": "error",
                "message": f"Supplied {role} text is not the exact decoded content of the bound target file.",
            }
        )
    metadata["status"] = "passed" if not issues else "blocked"
    return issues, metadata, readback


def _validate_target_artifact_path_separation(
    source_binding: Mapping[str, Any],
    designer_binding: Mapping[str, Any],
    baseline_binding: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    source_path = str(source_binding.get("path") or "")
    designer_path = str(designer_binding.get("path") or "")
    baseline_path = str(baseline_binding.get("path") or "")
    if source_path and designer_path and source_path.lower() == designer_path.lower():
        issues.append(
            {
                "code": "target_artifact_role_path_collision",
                "severity": "error",
                "roles": ["source", "designer"],
                "path": source_path,
                "message": "Code-behind and Designer evidence must bind to distinct target files.",
            }
        )
    if designer_path and baseline_path and designer_path.lower() == baseline_path.lower():
        issues.append(
            {
                "code": "baseline_designer_target_path_collision",
                "severity": "error",
                "roles": ["designer", "baseline_designer"],
                "path": designer_path,
                "message": "A preservation baseline must be a separately captured pre-edit artifact, not the current target Designer file.",
            }
        )
    return issues


def _normalize_evidence_registry(
    value: Any,
    *,
    required: bool,
) -> tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    if isinstance(value, Mapping):
        raw_entries = []
        for key, raw_entry in value.items():
            entry = dict(raw_entry) if isinstance(raw_entry, Mapping) else {}
            entry.setdefault("evidence_id", str(key))
            raw_entries.append(entry)
    elif isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        raw_entries = list(value)
    else:
        raw_entries = []
    registry: Dict[str, Dict[str, Any]] = {}
    issues: List[Dict[str, Any]] = []
    if required and value is None:
        issues.append(
            {
                "code": "control_evidence_registry_required",
                "severity": "error",
                "message": "Current control verification requires a structured evidence_registry ledger.",
            }
        )
    for index, raw_entry in enumerate(raw_entries):
        if not isinstance(raw_entry, Mapping):
            issues.append(
                {
                    "code": "control_evidence_registry_entry_invalid",
                    "severity": "error",
                    "entry_index": index,
                    "evidence_id": "",
                    "message": "Each evidence registry entry must be a structured mapping.",
                }
            )
            continue
        entry = dict(raw_entry)
        evidence_id = str(entry.get("evidence_id") or entry.get("id") or "").strip()
        kind = str(entry.get("kind") or "").strip().lower()
        locator = str(entry.get("locator") or "").strip()
        digest = _normalized_sha256(entry.get("sha256") or entry.get("digest"))
        stable_locator = bool(
            re.fullmatch(r"(?:artifact|file|review|user|memory)://[^\s]+", locator)
        )
        if (
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]*", evidence_id)
            or kind not in {"source", "user"}
            or not (stable_locator or digest)
            or evidence_id in registry
        ):
            issues.append(
                {
                    "code": "control_evidence_registry_entry_invalid",
                    "severity": "error",
                    "entry_index": index,
                    "evidence_id": evidence_id,
                    "message": (
                        "Each evidence registry entry requires a unique stable evidence_id, "
                        "source/user kind, and a stable locator URI or SHA-256 digest."
                    ),
                }
            )
            continue
        registry[evidence_id] = {
            "evidence_id": evidence_id,
            "kind": kind,
            "locator": locator,
            "sha256": f"sha256:{digest}" if digest else "",
        }
    return registry, issues, {
        "status": "passed" if not issues else "blocked",
        "required": required,
        "entries": [dict(item) for item in registry.values()],
    }


def _resolve_control_evidence_references(
    value: Any,
    evidence_registry: Mapping[str, Mapping[str, Any]],
    *,
    issue_code: str,
    context: Mapping[str, Any] | None = None,
) -> tuple[List[str], List[Dict[str, Any]], List[Dict[str, Any]]]:
    references = _normalized_evidence_references(value)
    resolved: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []
    for reference in references:
        entry = evidence_registry.get(reference)
        if not isinstance(entry, Mapping):
            issues.append(
                {
                    "code": issue_code,
                    "severity": "error",
                    "evidence_ref": reference,
                    **dict(context or {}),
                    "message": "Evidence references must resolve to a structured source/user registry entry.",
                }
            )
            continue
        resolved.append(dict(entry))
    return references, resolved, issues


def _validate_control_contract_evidence_fields(
    contract: Mapping[str, Any],
    properties: Mapping[str, Any],
    evidence_registry: Mapping[str, Mapping[str, Any]],
    *,
    control: str,
    structured_required: bool,
) -> List[Dict[str, Any]]:
    if not structured_required:
        return []
    issues: List[Dict[str, Any]] = []

    def validate_references(value: Any, *, property_path: str = "") -> None:
        references, valid = _strict_evidence_references(value)
        context = {"control": control}
        if property_path:
            context["property"] = property_path
        if not valid:
            issues.append(
                {
                    "code": "control_contract_evidence_references_invalid",
                    "severity": "error",
                    **context,
                    "message": "Evidence references must be a non-empty unique string ID or list of string IDs.",
                }
            )
            return
        _, _, reference_issues = _resolve_control_evidence_references(
            references,
            evidence_registry,
            issue_code="control_contract_evidence_reference_unresolved",
            context=context,
        )
        issues.extend(reference_issues)

    if "evidence_refs" in contract:
        validate_references(contract.get("evidence_refs"))

    property_evidence = contract.get("property_evidence")
    if "property_evidence" not in contract:
        return issues
    if not isinstance(property_evidence, Mapping):
        issues.append(
            {
                "code": "control_contract_property_evidence_invalid",
                "severity": "error",
                "control": control,
                "message": "property_evidence must map declared property paths to evidence IDs.",
            }
        )
        return issues
    for raw_property_path, value in property_evidence.items():
        property_path = str(raw_property_path or "").strip()
        if (
            not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", property_path)
            or property_path not in properties
        ):
            issues.append(
                {
                    "code": "control_contract_property_evidence_invalid",
                    "severity": "error",
                    "control": control,
                    "property": property_path,
                    "message": "property_evidence may reference only a property declared in the same control contract.",
                }
            )
            continue
        validate_references(value, property_path=property_path)
    return issues


def _control_property_provenance(
    contract: Mapping[str, Any],
    property_path: str,
    evidence_registry: Mapping[str, Mapping[str, Any]],
    *,
    structured_required: bool,
) -> Dict[str, Any]:
    property_evidence = contract.get("property_evidence")
    if isinstance(property_evidence, Mapping) and property_path in property_evidence:
        references = _normalized_evidence_references(property_evidence[property_path])
        source = "property_evidence"
    else:
        references = _normalized_evidence_references(contract.get("evidence_refs"))
        source = "evidence_refs"
    resolved: List[Dict[str, Any]] = []
    if structured_required:
        _, resolved, _ = _resolve_control_evidence_references(
            references,
            evidence_registry,
            issue_code="control_contract_evidence_reference_unresolved",
        )
    return {
        "source": source,
        "references": references,
        "resolved": resolved,
        "valid": bool(resolved) if structured_required else bool(references),
    }


def _normalize_no_control_contract_evidence(
    value: Any,
    evidence_registry: Mapping[str, Mapping[str, Any]],
    *,
    structured_required: bool,
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    evidence = dict(value) if isinstance(value, Mapping) else {}
    reason = str(
        evidence.get("reason")
        or (evidence.get("rationale") if not structured_required else "")
        or ""
    ).strip()
    references, resolved, issues = _resolve_control_evidence_references(
        evidence,
        evidence_registry,
        issue_code="no_control_evidence_reference_unresolved",
    )
    if value is not None and not reason:
        issues.append(
            {
                "code": "no_control_evidence_reason_required",
                "severity": "error",
                "message": "no_control_contract_evidence requires a non-empty reason.",
            }
        )
    if value is not None and not references:
        issues.append(
            {
                "code": "no_control_evidence_references_required",
                "severity": "error",
                "message": "no_control_contract_evidence requires one or more evidence_refs.",
            }
        )
    normalized = {
        "provided": value is not None,
        "reason": reason,
        "references": references,
        "resolved_evidence": resolved,
        "provenance_valid": bool(reason and references)
        and (bool(resolved) and len(resolved) == len(references) if structured_required else True),
    }
    return normalized, issues


def _is_designer_control_type(type_name: str) -> bool:
    normalized = _normalize_csharp_type_name(type_name)
    short_name = normalized.rsplit(".", 1)[-1].lower()
    if not short_name:
        return False
    if short_name.startswith("u_"):
        return True
    if normalized.startswith(("DevExpress.", "System.Windows.Forms.")):
        return True
    return bool(
        re.search(
            r"(?:Button|CheckBox|ComboBox|Component|Container|Control|DateEdit|Edit|"
            r"GridColumn|GridControl|GridView|GroupBox|Label|LayoutControl|Memo|Panel|"
            r"RepositoryItem[A-Za-z0-9_]*|SpinEdit|TabControl|TabPage|TextBox|View)$",
            normalized,
            flags=re.IGNORECASE,
        )
    )


def _designer_has_mapped_konelib_control_evidence(
    designer_code: str,
    *,
    target_form_class: str,
) -> bool:
    _, selected_scope, class_scopes, _ = _resolve_csharp_designer_form_scope(
        designer_code,
        requested_form_class=target_form_class,
        required=False,
    )
    scopes_to_check: List[Mapping[str, Any] | None] = (
        [selected_scope] if selected_scope is not None else list(class_scopes)
    )
    for scope in scopes_to_check:
        declarations, initializers = _designer_control_types(
            designer_code,
            class_scope=scope,
            class_scopes=class_scopes,
        )
        control_types = dict(declarations)
        control_types.update(initializers)
        assignments = _csharp_designer_assignments(
            designer_code,
            designer_code,
            class_scope=scope,
            class_scopes=class_scopes,
        )
        if any(
            _is_konelib_input_type(control_type)
            and bool(_csharp_assignment_values(assignments, (control, "BindingField")))
            for control, control_type in control_types.items()
        ):
            return True
    return False


def _designer_control_inventory(
    declarations: Mapping[str, str],
    initializers: Mapping[str, str],
    assignments: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
) -> Dict[str, Dict[str, Any]]:
    inventory: Dict[str, Dict[str, Any]] = {}
    for name in sorted(set(declarations).union(initializers)):
        declared_type = str(declarations.get(name) or "")
        initialized_type = str(initializers.get(name) or "")
        if not (
            (name in declarations and name in initializers)
            or
            _is_designer_control_type(declared_type)
            or _is_designer_control_type(initialized_type)
        ):
            continue
        inventory[name] = {
            "control": name,
            "declared_type": declared_type,
            "initialized_type": initialized_type,
            "bindings": {},
        }
    for (name, property_path), records in assignments.items():
        if property_path not in {"BindingField", "FieldName", "DataPropertyName"}:
            continue
        item = inventory.setdefault(
            name,
            {
                "control": name,
                "declared_type": str(declarations.get(name) or ""),
                "initialized_type": str(initializers.get(name) or ""),
                "bindings": {},
            },
        )
        item["bindings"][property_path] = [
            str(record.get("value") or "") for record in records
        ]
    return inventory


def _validate_designer_initialize_component_ownership(
    designer_code: str,
    *,
    class_scope: Mapping[str, Any] | None,
    class_scopes: Iterable[Mapping[str, Any]],
    initialize_scopes: Iterable[Mapping[str, Any]],
    required: bool,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    all_class_scopes = list(class_scopes)
    selected_initialize_scopes = list(initialize_scopes)
    issues: List[Dict[str, Any]] = []
    if required and len(selected_initialize_scopes) != 1:
        issues.append(
            {
                "code": (
                    "designer_initialize_component_missing"
                    if not selected_initialize_scopes
                    else "designer_initialize_component_ambiguous"
                ),
                "severity": "error",
                "matching_method_count": len(selected_initialize_scopes),
                "message": "The selected partial form requires exactly one InitializeComponent method.",
            }
        )
    declarations, all_initializers = _designer_control_types(
        designer_code,
        class_scope=class_scope,
        class_scopes=all_class_scopes,
    )
    ui_names = {
        name
        for name in set(declarations).union(all_initializers)
        if (name in declarations and name in all_initializers)
        or _is_designer_control_type(declarations.get(name, ""))
        or _is_designer_control_type(all_initializers.get(name, ""))
    }
    initializer_pattern = re.compile(
        r"(?m)^\s*this\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*new\s+"
        r"(?P<type>(?:global::)?[A-Za-z_][A-Za-z0-9_.<>]*)\s*\("
    )
    outside: List[Dict[str, Any]] = []
    for match in initializer_pattern.finditer(designer_code):
        owner = _csharp_owning_class_scope(all_class_scopes, match.start())
        if not _csharp_scope_is_selected(owner, class_scope):
            continue
        if _is_designer_control_type(match.group("type")) and not _csharp_position_in_scopes(
            match.start(), selected_initialize_scopes
        ):
            outside.append(
                {
                    "control": match.group("name"),
                    "category": "initializer",
                }
            )
    all_assignments = _csharp_designer_assignments(
        designer_code,
        designer_code,
        class_scope=class_scope,
        class_scopes=all_class_scopes,
    )
    for (control, property_path), records in all_assignments.items():
        if control not in ui_names:
            continue
        for record in records:
            if not _csharp_position_in_scopes(
                int(record.get("position", -1)), selected_initialize_scopes
            ):
                outside.append(
                    {
                        "control": control,
                        "category": "property",
                        "property": property_path,
                    }
                )
    if required and outside:
        issues.append(
            {
                "code": "designer_static_evidence_outside_initialize_component",
                "severity": "error",
                "findings": outside,
                "message": (
                    "Designer control initialization and static property evidence must be "
                    "inside the selected partial form's InitializeComponent method."
                ),
            }
        )
    return issues, {
        "status": "passed" if not issues else "blocked",
        "required": required,
        "initialize_component_count": len(selected_initialize_scopes),
        "outside_findings": outside,
    }


def _validate_expected_control_contracts(
    designer_source: str,
    designer_code: str,
    expected_control_contracts: Iterable[Any] | None,
    *,
    target_form_class: str = "",
    expected_control_contract_required: bool = False,
    no_control_contract_evidence: Any = None,
    evidence_registry: Mapping[str, Mapping[str, Any]] | None = None,
    structured_evidence_required: bool = False,
    complete_inventory_required: bool = False,
    initialize_component_scope_required: bool = False,
) -> tuple[List[Dict[str, Any]], Dict[str, Any], Dict[tuple[str, str], Any]]:
    registry = dict(evidence_registry or {})
    no_control_evidence, no_control_evidence_issues = _normalize_no_control_contract_evidence(
        no_control_contract_evidence,
        registry,
        structured_required=structured_evidence_required,
    )
    contracts = None if expected_control_contracts is None else list(expected_control_contracts)
    strict_scope = bool(expected_control_contract_required and designer_code.strip())
    scope_issues, class_scope, class_scopes, scope_metadata = _resolve_csharp_designer_form_scope(
        designer_code,
        requested_form_class=target_form_class,
        required=bool(strict_scope or contracts),
    )
    initialize_scopes = _csharp_initialize_component_scopes(
        designer_code,
        class_scope=class_scope,
        class_scopes=class_scopes,
    )
    ownership_issues, ownership_metadata = _validate_designer_initialize_component_ownership(
        designer_code,
        class_scope=class_scope,
        class_scopes=class_scopes,
        initialize_scopes=initialize_scopes,
        required=bool(initialize_component_scope_required and designer_code.strip()),
    )
    declarations, initializers = _designer_control_types(
        designer_code,
        class_scope=class_scope,
        class_scopes=class_scopes,
        initializer_scopes=(initialize_scopes if initialize_component_scope_required else None),
    )
    assignments = _csharp_designer_assignments(
        designer_source,
        designer_code,
        class_scope=class_scope,
        class_scopes=class_scopes,
        method_scopes=(initialize_scopes if initialize_component_scope_required else None),
    )
    inventory = _designer_control_inventory(declarations, initializers, assignments)
    inventory_names = set(inventory)
    if contracts is None:
        issues = list(scope_issues) + list(ownership_issues)
        if expected_control_contract_required:
            issues.append(
                {
                    "code": "expected_control_contracts_required",
                    "severity": "error",
                    "message": "Current packaged profile verification always requires expected_control_contracts.",
                }
            )
        return issues, {
            "status": "blocked" if issues else "not_requested",
            "input_state": "omitted",
            "contracts": [],
            "designer_control_inventory": list(inventory.values()),
            "form_scope": scope_metadata,
            "initialize_component_ownership": ownership_metadata,
            "no_control_contract_evidence": no_control_evidence,
        }, {}

    if not contracts:
        issues = list(scope_issues) + list(ownership_issues) + list(no_control_evidence_issues)
        if not no_control_evidence["provenance_valid"]:
            issues.append(
                {
                    "code": "empty_control_contract_requires_no_control_evidence",
                    "severity": "error",
                    "message": (
                        "An explicit empty control contract requires a reason and fully resolved "
                        "structured source/user evidence."
                    ),
                }
            )
        if inventory_names:
            issues.append(
                {
                    "code": "empty_control_contract_conflicts_with_designer_controls",
                    "severity": "error",
                    "controls": sorted(inventory_names),
                    "message": "An explicit empty contract is invalid when the selected Designer scope contains generated controls.",
                }
            )
        return issues, {
            "status": "blocked" if issues else "proven_no_mapped_controls",
            "input_state": "explicit_empty",
            "contracts": [],
            "designer_control_inventory": list(inventory.values()),
            "form_scope": scope_metadata,
            "initialize_component_ownership": ownership_metadata,
            "no_control_contract_evidence": no_control_evidence,
        }, {}

    issues: List[Dict[str, Any]] = list(scope_issues) + list(ownership_issues)
    results: List[Dict[str, Any]] = []
    exact_properties: Dict[tuple[str, str], Any] = {}
    seen_names: set[str] = set()

    for index, raw_contract in enumerate(contracts):
        if not isinstance(raw_contract, Mapping):
            issues.append(
                {
                    "code": "control_contract_invalid",
                    "severity": "error",
                    "contract_index": index,
                    "message": "Each expected control contract must be a mapping.",
                }
            )
            continue
        contract = dict(raw_contract)
        name = str(
            contract.get("instance_name")
            or contract.get("control_name")
            or contract.get("name")
            or ""
        ).strip()
        expected_type = str(
            contract.get("expected_type") or contract.get("type_name") or contract.get("type") or ""
        ).strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) or not expected_type:
            issues.append(
                {
                    "code": "control_contract_invalid",
                    "severity": "error",
                    "contract_index": index,
                    "message": "Each expected control contract requires a valid instance_name and expected_type.",
                }
            )
            continue
        if name in seen_names:
            issues.append(
                {
                    "code": "control_contract_duplicate_instance",
                    "severity": "error",
                    "contract_index": index,
                    "control": name,
                    "message": "Expected control contracts must name each Designer instance once.",
                }
            )
            continue
        seen_names.add(name)

        properties_value = contract.get("properties", contract.get("exact_properties", {}))
        if not isinstance(properties_value, Mapping):
            issues.append(
                {
                    "code": "control_contract_properties_invalid",
                    "severity": "error",
                    "contract_index": index,
                    "control": name,
                    "message": "Control contract properties must be a property-path to exact-value mapping.",
                }
            )
            properties: Dict[str, Any] = {}
        else:
            properties = {str(key): value for key, value in properties_value.items()}
        issues.extend(
            _validate_control_contract_evidence_fields(
                contract,
                properties,
                registry,
                control=name,
                structured_required=structured_evidence_required,
            )
        )
        for property_path, expected_value in properties.items():
            provenance = _control_property_provenance(
                contract,
                property_path,
                registry,
                structured_required=structured_evidence_required,
            )
            exact_properties[(name, property_path)] = {
                "expected": expected_value,
                "provenance": provenance,
            }

        declared_type = declarations.get(name, "")
        initialized_type = initializers.get(name, "")
        if not declared_type:
            issues.append(
                {
                    "code": "control_contract_declaration_missing",
                    "severity": "error",
                    "control": name,
                    "expected_type": expected_type,
                    "message": "Expected Designer control declaration is missing.",
                }
            )
        elif not _csharp_type_matches(declared_type, expected_type):
            issues.append(
                {
                    "code": "control_contract_declaration_type_mismatch",
                    "severity": "error",
                    "control": name,
                    "expected_type": expected_type,
                    "actual_type": declared_type,
                    "message": "Designer control declaration type does not match the expected contract.",
                }
            )
        if not initialized_type:
            issues.append(
                {
                    "code": "control_contract_initializer_missing",
                    "severity": "error",
                    "control": name,
                    "expected_type": expected_type,
                    "message": "Expected Designer control initialization is missing.",
                }
            )
        elif not _csharp_type_matches(initialized_type, expected_type):
            issues.append(
                {
                    "code": "control_contract_initializer_type_mismatch",
                    "severity": "error",
                    "control": name,
                    "expected_type": expected_type,
                    "actual_type": initialized_type,
                    "message": "Designer control initialization type does not match the expected contract.",
                }
            )

        bindings_value = contract.get("bindings", {})
        if not isinstance(bindings_value, Mapping):
            issues.append(
                {
                    "code": "control_contract_bindings_invalid",
                    "severity": "error",
                    "control": name,
                    "message": "Control contract bindings must be a binding-property to exact-value mapping.",
                }
            )
            expected_bindings: Dict[str, Any] = {}
        else:
            expected_bindings = {str(key): value for key, value in bindings_value.items()}
        if "BindingField" in contract or "binding_field" in contract:
            expected_bindings["BindingField"] = (
                contract.get("BindingField")
                if "BindingField" in contract
                else contract.get("binding_field")
            )
        observed_binding_paths = set(inventory.get(name, {}).get("bindings", {}))
        missing_binding_expectations = sorted(observed_binding_paths.difference(expected_bindings))
        if complete_inventory_required and missing_binding_expectations:
            issues.append(
                {
                    "code": "control_contract_binding_expectation_missing",
                    "severity": "error",
                    "control": name,
                    "bindings": missing_binding_expectations,
                    "message": "Every observed Designer binding must be declared in the expected control contract.",
                }
            )
        actual_bindings: Dict[str, Any] = {}
        for binding_path, expected_binding_value in expected_bindings.items():
            actual_values = _csharp_assignment_values(assignments, (name, binding_path))
            actual_raw: Any = (
                actual_values[0]
                if len(actual_values) == 1
                else (actual_values if actual_values else None)
            )
            actual_value = (
                _csharp_direct_string_value(actual_raw)
                if isinstance(actual_raw, str)
                else None
            )
            actual_bindings[binding_path] = actual_value
            expected_string = str(expected_binding_value or "")
            if not actual_values:
                issues.append(
                    {
                        "code": "control_contract_binding_field_missing",
                        "severity": "error",
                        "control": name,
                        "binding": binding_path,
                        "expected": expected_string,
                        "message": "Expected Designer binding assignment is missing.",
                    }
                )
            elif len(actual_values) > 1:
                issues.append(
                    {
                        "code": "control_contract_binding_field_assignment_ambiguous",
                        "severity": "error",
                        "control": name,
                        "binding": binding_path,
                        "expected": expected_string,
                        "actual": actual_values,
                        "message": "Designer bindings must have exactly one assignment.",
                    }
                )
            elif actual_value != expected_string:
                issues.append(
                    {
                        "code": "control_contract_binding_field_mismatch",
                        "severity": "error",
                        "control": name,
                        "binding": binding_path,
                        "expected": expected_string,
                        "actual": actual_raw,
                        "message": "Designer binding does not match the expected control contract.",
                    }
                )
        expected_binding = str(expected_bindings.get("BindingField") or "")
        actual_binding = actual_bindings.get("BindingField")

        actual_properties: Dict[str, Any] = {}
        for property_path, expected_value in properties.items():
            actual_values = _csharp_assignment_values(
                assignments, (name, property_path)
            )
            actual_value: Any = (
                actual_values[0]
                if len(actual_values) == 1
                else (actual_values if actual_values else None)
            )
            actual_properties[property_path] = actual_value
            if not actual_values:
                issues.append(
                    {
                        "code": "control_contract_property_missing",
                        "severity": "error",
                        "control": name,
                        "property": property_path,
                        "expected": expected_value,
                        "message": "Expected exact Designer property assignment is missing.",
                    }
                )
            elif len(actual_values) > 1:
                issues.append(
                    {
                        "code": "control_contract_property_assignment_ambiguous",
                        "severity": "error",
                        "control": name,
                        "property": property_path,
                        "expected": expected_value,
                        "actual": actual_values,
                        "message": "Protected Designer properties must have exactly one assignment.",
                    }
                )
            elif not _csharp_exact_property_matches(actual_values[0], expected_value):
                issues.append(
                    {
                        "code": "control_contract_property_mismatch",
                        "severity": "error",
                        "control": name,
                        "property": property_path,
                        "expected": expected_value,
                        "actual": actual_value,
                        "message": "Designer property assignment does not match the exact expected value.",
                    }
                )

        results.append(
            {
                "contract_index": index,
                "control": name,
                "expected_type": expected_type,
                "declared_type": declared_type,
                "initialized_type": initialized_type,
                "status": (
                    "blocked"
                    if class_scope is None
                    or any(issue.get("control") == name for issue in issues)
                    else "passed"
                ),
                "expected_binding_field": (
                    expected_binding if "BindingField" in expected_bindings else None
                ),
                "actual_binding_field": actual_binding,
                "expected_bindings": expected_bindings,
                "actual_bindings": actual_bindings,
                "expected_properties": properties,
                "actual_properties": actual_properties,
                "consumed_explicit_exceptions": [],
            }
        )

    if complete_inventory_required:
        missing_controls = sorted(inventory_names.difference(seen_names))
        unexpected_controls = sorted(seen_names.difference(inventory_names))
        if missing_controls or unexpected_controls:
            issues.append(
                {
                    "code": "control_contract_inventory_incomplete",
                    "severity": "error",
                    "missing_controls": missing_controls,
                    "unexpected_controls": unexpected_controls,
                    "message": "Expected control contracts must exactly account for the selected Designer control inventory.",
                }
            )
    return issues, {
        "status": "passed" if not issues else "blocked",
        "input_state": "provided",
        "contracts": results,
        "designer_control_inventory": list(inventory.values()),
        "form_scope": scope_metadata,
        "initialize_component_ownership": ownership_metadata,
        "no_control_contract_evidence": no_control_evidence,
    }, exact_properties


def _is_konelib_input_type(type_name: str) -> bool:
    short_name = _normalize_csharp_type_name(type_name).rsplit(".", 1)[-1].lower()
    return short_name.startswith("u_") and (
        short_name.endswith("edit")
        or any(
            token in short_name
            for token in (
                "textbox",
                "combobox",
                "memo",
                "check",
                "radio",
                "numeric",
                "masked",
            )
        )
    )


def _validate_konelib_default_guards(
    designer_source: str,
    designer_code: str,
    exact_properties: Mapping[tuple[str, str], Any],
    profile_rules: Mapping[str, Any],
    *,
    target_form_class: str = "",
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    designer_contract = profile_rules.get("designer_contract")
    designer_contract = dict(designer_contract) if isinstance(designer_contract, Mapping) else {}
    raw_defaults = designer_contract.get("konelib_defaults")
    if not isinstance(raw_defaults, Mapping) or not raw_defaults:
        return [], {
            "status": "not_enabled",
            "consumed_explicit_exceptions": [],
            "form_scope": {
                "status": "not_selected",
                "requested_form_class": str(target_form_class or ""),
                "selected_form_class": "",
                "declared_form_classes": [],
                "matching_class_count": 0,
                "partial_declaration_count": 0,
            },
        }

    _, class_scope, class_scopes, scope_metadata = _resolve_csharp_designer_form_scope(
        designer_code,
        requested_form_class=target_form_class,
        required=False,
    )
    initialize_scopes = _csharp_initialize_component_scopes(
        designer_code,
        class_scope=class_scope,
        class_scopes=class_scopes,
    )
    scope_initializers = (
        initialize_scopes
        if designer_contract.get("initialize_component_scope_required") is True
        else None
    )
    declarations, initializers = _designer_control_types(
        designer_code,
        class_scope=class_scope,
        class_scopes=class_scopes,
        initializer_scopes=scope_initializers,
    )
    control_types = dict(declarations)
    control_types.update(initializers)
    assignments = _csharp_designer_assignments(
        designer_source,
        designer_code,
        class_scope=class_scope,
        class_scopes=class_scopes,
        method_scopes=scope_initializers,
    )
    defaults = dict(raw_defaults)
    auto_height_property = str(defaults.get("input_auto_height_property") or "Properties.AutoHeight")
    label_defaults = defaults.get("label_alignment")
    label_defaults = dict(label_defaults) if isinstance(label_defaults, Mapping) else {
        "Appearance.TextOptions.HAlignment": "DevExpress.Utils.HorzAlignment.Far",
        "Appearance.TextOptions.VAlignment": "DevExpress.Utils.VertAlignment.Center",
    }
    even_row_property = str(
        defaults.get("even_row_back_color_property") or "Appearance.EvenRow.BackColor"
    )
    issues: List[Dict[str, Any]] = []
    consumed_exceptions: List[Dict[str, Any]] = []
    consumed_keys: set[tuple[str, str]] = set()

    def authorization(
        control: str, property_path: str
    ) -> tuple[Any, Dict[str, Any]] | None:
        key = (control, property_path)
        raw_authorization = exact_properties.get(key)
        if not isinstance(raw_authorization, Mapping):
            return None
        return (
            raw_authorization.get("expected"),
            dict(raw_authorization.get("provenance") or {}),
        )

    def explicitly_allowed(control: str, property_path: str, actual: str) -> bool:
        resolved = authorization(control, property_path)
        if resolved is None:
            return False
        expected, provenance = resolved
        return bool(provenance.get("valid")) and _csharp_exact_property_matches(
            actual, expected
        )

    def record_missing_provenance(
        control: str, property_path: str, actual: str
    ) -> None:
        resolved = authorization(control, property_path)
        if resolved is None:
            return
        expected, provenance = resolved
        if provenance.get("valid") or not _csharp_exact_property_matches(
            actual, expected
        ):
            return
        if any(
            issue.get("code") == "control_contract_override_provenance_missing"
            and issue.get("control") == control
            and issue.get("property") == property_path
            for issue in issues
        ):
            return
        issues.append(
            {
                "code": "control_contract_override_provenance_missing",
                "severity": "error",
                "control": control,
                "property": property_path,
                "actual": actual,
                "message": (
                    "A protected Designer default override requires non-empty "
                    "evidence_refs or property_evidence provenance."
                ),
            }
        )

    def consume_exception(control: str, property_path: str, actual: str) -> None:
        key = (control, property_path)
        if key in consumed_keys:
            return
        consumed_keys.add(key)
        resolved = authorization(control, property_path)
        if resolved is None:
            return
        expected, provenance = resolved
        consumed_exceptions.append(
            {
                "control": control,
                "property": property_path,
                "expected": expected,
                "actual": actual,
                "provenance": provenance,
            }
        )

    for (control, property_path), assignment_records in assignments.items():
        control_type = control_types.get(control, "")
        short_type = _normalize_csharp_type_name(control_type).rsplit(".", 1)[-1]
        protected_property = bool(
            (
                property_path == auto_height_property
                and _is_konelib_input_type(control_type)
            )
            or (short_type.lower() == "u_label" and property_path in label_defaults)
            or property_path == even_row_property
        )
        if not protected_property:
            continue
        if len(assignment_records) != 1:
            issues.append(
                {
                    "code": "konelib_guard_assignment_ambiguous",
                    "severity": "error",
                    "control": control,
                    "property": property_path,
                    "actual": [str(item.get("value") or "") for item in assignment_records],
                    "message": "Protected Designer properties must have exactly one unconditional assignment.",
                }
            )
            continue
        assignment = assignment_records[0]
        actual = str(assignment.get("value") or "")
        if assignment.get("conditional"):
            issues.append(
                {
                    "code": "konelib_guard_conditional_assignment",
                    "severity": "error",
                    "control": control,
                    "property": property_path,
                    "actual": actual,
                    "message": "Protected Designer properties must not be assigned conditionally.",
                }
            )
            continue
        parsed_actual = _parse_csharp_designer_value(re.sub(r"[\s()]", "", actual))
        direct_member_value = bool(
            re.fullmatch(
                r"(?:global::)?[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+",
                re.sub(r"\s+", "", actual),
            )
        )
        if (
            (property_path == auto_height_property and type(parsed_actual) is not bool)
            or (
                property_path != auto_height_property
                and not direct_member_value
            )
        ):
            issues.append(
                {
                    "code": "konelib_guard_nonliteral_assignment",
                    "severity": "error",
                    "control": control,
                    "property": property_path,
                    "actual": actual,
                    "message": "Protected Designer properties require one direct literal or member value.",
                }
            )
            continue
        if (
            property_path == auto_height_property
            and _is_konelib_input_type(control_type)
            and parsed_actual is True
        ):
            if explicitly_allowed(control, property_path, actual):
                consume_exception(control, property_path, actual)
            else:
                record_missing_provenance(control, property_path, actual)
                issues.append(
                    {
                        "code": "konelib_input_autoheight_true_override",
                        "severity": "error",
                        "control": control,
                        "property": property_path,
                        "actual": actual,
                        "message": "KoneLib u_* input controls must not explicitly set Properties.AutoHeight to true unless the expected control contract requires it.",
                    }
                )
        if short_type.lower() == "u_label" and property_path in label_defaults:
            expected_default = str(label_defaults[property_path])
            if not _csharp_exact_property_matches(actual, expected_default):
                if explicitly_allowed(control, property_path, actual):
                    consume_exception(control, property_path, actual)
                else:
                    record_missing_provenance(control, property_path, actual)
                    issues.append(
                        {
                            "code": "konelib_label_alignment_override",
                            "severity": "error",
                            "control": control,
                            "property": property_path,
                            "expected_default": expected_default,
                            "actual": actual,
                            "message": "KoneLib u_Label alignment must preserve packaged Far/Center defaults unless the expected control contract requires an override.",
                        }
                    )
        if property_path == even_row_property:
            if explicitly_allowed(control, property_path, actual):
                consume_exception(control, property_path, actual)
            else:
                record_missing_provenance(control, property_path, actual)
                issues.append(
                    {
                        "code": "even_row_backcolor_override",
                        "severity": "error",
                        "control": control,
                        "property": property_path,
                        "actual": actual,
                        "message": "Custom Appearance.EvenRow.BackColor assignments require an exact expected control contract.",
                    }
                )

    return issues, {
        "status": "passed" if not issues else "blocked",
        "input_auto_height_property": auto_height_property,
        "label_alignment_defaults": label_defaults,
        "even_row_back_color_property": even_row_property,
        "consumed_explicit_exceptions": consumed_exceptions,
        "form_scope": scope_metadata,
    }


def _validate_baseline_designer_preservation(
    designer_source: str,
    designer_code: str,
    baseline_source: str,
    baseline_code: str,
    exact_properties: Mapping[tuple[str, str], Any],
    profile_rules: Mapping[str, Any],
    *,
    target_form_class: str,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not baseline_code.strip():
        return [], {
            "status": "not_supplied",
            "evaluated_controls": [],
            "new_controls_not_evaluable": [],
            "changes": [],
        }
    designer_contract = profile_rules.get("designer_contract")
    designer_contract = dict(designer_contract) if isinstance(designer_contract, Mapping) else {}
    defaults = designer_contract.get("konelib_defaults")
    defaults = dict(defaults) if isinstance(defaults, Mapping) else {}
    preserved_properties = [
        str(item)
        for item in defaults.get("preserve_existing_properties", [])
        if str(item).strip()
    ]
    label_properties = [
        str(item)
        for item in dict(defaults.get("label_alignment") or {}).keys()
        if str(item).strip()
    ]
    if not preserved_properties and not label_properties:
        return [], {
            "status": "not_enabled",
            "evaluated_controls": [],
            "new_controls_not_evaluable": [],
            "changes": [],
        }

    def context(
        source: str,
        structural: str,
    ) -> tuple[
        List[Dict[str, Any]],
        Dict[str, Dict[str, Any]],
        Dict[tuple[str, str], List[Dict[str, Any]]],
    ]:
        scope_issues, class_scope, class_scopes, _ = _resolve_csharp_designer_form_scope(
            structural,
            requested_form_class=target_form_class,
            required=True,
        )
        initialize_scopes = _csharp_initialize_component_scopes(
            structural,
            class_scope=class_scope,
            class_scopes=class_scopes,
        )
        if len(initialize_scopes) != 1:
            scope_issues.append(
                {
                    "code": "baseline_designer_initialize_component_invalid",
                    "severity": "error",
                    "matching_method_count": len(initialize_scopes),
                    "message": "Baseline preservation requires exactly one selected InitializeComponent method.",
                }
            )
        declarations, initializers = _designer_control_types(
            structural,
            class_scope=class_scope,
            class_scopes=class_scopes,
            initializer_scopes=initialize_scopes,
        )
        assignments = _csharp_designer_assignments(
            source,
            structural,
            class_scope=class_scope,
            class_scopes=class_scopes,
            method_scopes=initialize_scopes,
        )
        return scope_issues, _designer_control_inventory(
            declarations, initializers, assignments
        ), assignments

    current_context_issues, current_inventory, current_assignments = context(
        designer_source,
        designer_code,
    )
    baseline_context_issues, baseline_inventory, baseline_assignments = context(
        baseline_source,
        baseline_code,
    )
    issues = list(current_context_issues) + list(baseline_context_issues)
    new_controls = sorted(set(current_inventory).difference(baseline_inventory))
    removed_controls = sorted(set(baseline_inventory).difference(current_inventory))
    if removed_controls:
        issues.append(
            {
                "code": "baseline_designer_control_removed",
                "severity": "error",
                "controls": removed_controls,
                "message": "Existing baseline Designer controls cannot disappear without an explicit migration contract.",
            }
        )
    evaluated_controls: List[str] = []
    changes: List[Dict[str, Any]] = []
    for control in sorted(set(current_inventory).intersection(baseline_inventory)):
        evaluated_controls.append(control)
        current_type = (
            current_inventory[control].get("declared_type")
            or current_inventory[control].get("initialized_type")
            or ""
        )
        property_paths = list(preserved_properties)
        if _normalize_csharp_type_name(str(current_type)).rsplit(".", 1)[-1].lower() == "u_label":
            property_paths.extend(label_properties)
        for property_path in dict.fromkeys(property_paths):
            current_values = _csharp_assignment_values(
                current_assignments, (control, property_path)
            )
            baseline_values = _csharp_assignment_values(
                baseline_assignments, (control, property_path)
            )
            if current_values == baseline_values:
                continue
            current_value: Any = current_values[0] if len(current_values) == 1 else current_values
            baseline_value: Any = baseline_values[0] if len(baseline_values) == 1 else baseline_values
            authorization = exact_properties.get((control, property_path))
            authorized = bool(
                isinstance(authorization, Mapping)
                and dict(authorization.get("provenance") or {}).get("valid")
                and len(current_values) == 1
                and _csharp_exact_property_matches(
                    current_values[0], authorization.get("expected")
                )
            )
            change = {
                "control": control,
                "property": property_path,
                "baseline": baseline_value if baseline_values else None,
                "current": current_value if current_values else None,
                "authorized": authorized,
            }
            changes.append(change)
            if not authorized:
                issues.append(
                    {
                        "code": "baseline_designer_property_changed_without_evidence",
                        "severity": "error",
                        **change,
                        "message": "Existing Designer property changes require an exact contract value and resolved source/user evidence.",
                    }
                )
    return issues, {
        "status": "passed" if not issues else "blocked",
        "evaluated_controls": evaluated_controls,
        "new_controls_not_evaluable": new_controls,
        "removed_controls": removed_controls,
        "changes": changes,
        "preserved_properties": preserved_properties,
        "label_alignment_properties": label_properties,
    }


def _csharp_layout_value_matches(property_name: str, actual: str, expected: str) -> bool:
    raw = str(actual or "").strip()
    if expected == "string.Empty":
        return _csharp_direct_string_value(raw) == ""
    if property_name == "ScrollStyle":
        if re.search(r"[^|]\+|\+[^|]", raw):
            return False
        flags = [
            part.strip().strip("()").split(".")[-1]
            for part in raw.split("|")
            if part.strip()
        ]
        return len(flags) == 2 and set(flags) == {"LiveVertScroll", "LiveHorzScroll"}
    if expected in {"true", "false"} or re.fullmatch(r"-?\d+", expected):
        return re.sub(r"\s+", "", raw).lower() == expected.lower()
    return raw.split(".")[-1] == expected.split(".")[-1]


def _csharp_tahoma_nine_font(value: str) -> bool:
    font = r"(?:System\.Drawing\.)?Font"
    match = re.fullmatch(
        rf"new\s+{font}\s*\(\s*(?P<arguments>[^\r\n]*)\s*\)",
        str(value or "").strip(),
    )
    if not match:
        return False

    arguments = [argument.strip() for argument in match.group("arguments").split(",")]
    if len(arguments) < 2 or arguments[0] != '"Tahoma"':
        return False
    if not re.fullmatch(r"9(?:\.0+)?[Ff]?", arguments[1]):
        return False

    optional = arguments[2:]
    regular = {"FontStyle.Regular", "System.Drawing.FontStyle.Regular"}
    point = {"GraphicsUnit.Point", "System.Drawing.GraphicsUnit.Point"}
    if not optional:
        return True
    if len(optional) == 1:
        return optional[0] in regular or optional[0] in point
    if optional[0] not in regular or optional[1] not in point:
        return False
    if len(optional) == 2:
        return True
    if not re.fullmatch(r"(?:1|\(\s*byte\s*\)\s*1)", optional[2]):
        return False
    return len(optional) == 3 or (len(optional) == 4 and optional[3] == "false")


def _validate_input_tab_order(designer_source: str) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    source = str(designer_source or "")
    if not source.strip():
        return [], {"status": "not_requested", "inputs": []}
    control_types: Dict[str, str] = {}
    for match in CSHARP_FIELD_DECLARATION_PATTERN.finditer(source):
        control_types[match.group("name")] = match.group("type")
    for match in CSHARP_NEW_CONTROL_PATTERN.finditer(source):
        control_types[match.group("name")] = match.group("type")
    locations = {
        match.group("name"): (int(match.group("x")), int(match.group("y")))
        for match in re.finditer(
            r"this\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\.Location\s*=\s*"
            r"new\s+(?:System\.Drawing\.)?Point\s*\(\s*(?P<x>-?\d+)\s*,\s*(?P<y>-?\d+)\s*\)\s*;",
            source,
        )
    }
    tab_indexes = {
        match.group("name"): int(match.group("index"))
        for match in re.finditer(
            r"this\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\.TabIndex\s*=\s*(?P<index>\d+)\s*;",
            source,
        )
    }
    parents: Dict[str, str] = {}
    for match in re.finditer(
        r"this\.(?:(?P<container>[A-Za-z_][A-Za-z0-9_]*)\.)?Controls\.Add\s*\(\s*this\.(?P<child>[A-Za-z_][A-Za-z0-9_]*)\s*\)\s*;",
        source,
    ):
        parents[match.group("child")] = match.group("container") or "<form>"

    def is_input(name: str, type_name: str) -> bool:
        lowered_type = str(type_name or "").lower()
        if any(token in lowered_type for token in ("label", "grid", "column", "repository", "panel", "group", "tabpage", "container")):
            return False
        if any(
            token in lowered_type
            for token in (
                "textedit", "spinedit", "dateedit", "lookupedit", "buttonedit", "checkedit", "memoedit",
                "radiogroup", "textbox", "combobox", "datetimepicker", "numericupdown", "checkbox", "radiobutton",
            )
        ):
            return True
        return bool(re.match(r"^(?:txt|spn|spin|ymd|dt|cbo|btn|chk|memo|rad)[A-Z0-9_]", name, re.IGNORECASE))

    inputs = [
        {
            "name": name,
            "type": type_name,
            "container": parents.get(name, "<form>"),
            "x": locations[name][0],
            "y": locations[name][1],
            "tab_index": tab_indexes.get(name),
        }
        for name, type_name in control_types.items()
        if name in locations and is_input(name, type_name)
    ]
    if not inputs:
        return [], {"status": "not_applicable", "inputs": inputs}
    issues: List[Dict[str, Any]] = []
    for item in inputs:
        if item["tab_index"] is None:
            issues.append(
                {
                    "code": "input_tabindex_missing_with_layout",
                    "severity": "error",
                    "member": item["name"],
                    "message": "Input controls with Designer Location evidence require explicit TabIndex values.",
                }
            )
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in inputs:
        grouped.setdefault(str(item["container"]), []).append(item)
    container_contracts: List[Dict[str, Any]] = []
    spatial: List[Dict[str, Any]] = []
    for container, members in sorted(grouped.items()):
        ordered = sorted(members, key=lambda item: (int(item["y"]), int(item["x"]), str(item["name"])))
        spatial.extend(ordered)
        actual = [item["tab_index"] for item in ordered]
        container_contracts.append(
            {
                "container": container,
                "spatial_order": [item["name"] for item in ordered],
                "tab_indexes": actual,
            }
        )
        if any(value is None for value in actual):
            continue
        indexes = [int(value) for value in actual]
        if indexes != sorted(indexes):
            issues.append(
                {
                    "code": "input_tabindex_spatial_order_mismatch",
                    "severity": "error",
                    "message": "Input TabIndex must increase in left-to-right, then top-to-bottom order within its parent container.",
                    "container": container,
                    "spatial_order": [item["name"] for item in ordered],
                    "tab_indexes": indexes,
                }
            )
        expected_contiguous = list(range(min(indexes), min(indexes) + len(indexes)))
        if indexes != expected_contiguous:
            issues.append(
                {
                    "code": "input_tabindex_not_container_contiguous",
                    "severity": "error",
                    "message": "Input TabIndex values must be contiguous within each parent container.",
                    "container": container,
                    "expected": expected_contiguous,
                    "actual": indexes,
                }
            )
    return issues, {
        "status": "passed" if not issues else "blocked",
        "inputs": spatial,
        "containers": container_contracts,
        "labels_and_non_inputs_ignored": True,
        "unrelated_containers_compared": False,
    }


def _validate_devexpress_designer_grid_contract(
    designer_source: str,
    *,
    designer_code: str,
    expected_grid_role: str,
    expected_grid_suffix: str,
    expected_grid_prefix: str,
    expected_grid_columns: Iterable[Any] | None,
    result_fields: Iterable[str] | None,
    layout_load_artifact_path: str,
    layout_load_artifact_text: str,
    layout_load_evidence: Any,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    source = str(designer_source or "")
    code_source = str(designer_code or "")
    expected_requested = bool(
        str(expected_grid_role or "").strip()
        or str(expected_grid_suffix or "").strip()
        or expected_grid_columns is not None
        or str(layout_load_artifact_path or "").strip()
        or str(layout_load_artifact_text or "").strip()
        or layout_load_evidence is not None
    )
    if not code_source.strip() or not re.search(r"\b(?:GridView|GridColumn|XtraGrid\.)\b", code_source):
        if expected_requested:
            issue = {
                "code": "expected_grid_designer_missing",
                "severity": "error",
                "message": "Explicit grid metadata requires a real C# Designer GridControl/GridView contract.",
            }
            return [issue], {
                "status": "blocked",
                "layout_load_artifact_verified": False,
                "layout_load_evidence_verified": False,
                "actual_live_layout_load_observed": False,
                "verification_scope": "static_xml_and_post_load_equivalent_designer_state",
                "designer_source_used": False,
            }
        return [], {
            "status": "not_requested",
            "layout_load_artifact_verified": False,
            "layout_load_evidence_verified": False,
            "actual_live_layout_load_observed": False,
            "verification_scope": "static_xml_and_post_load_equivalent_designer_state",
        }
    issues: List[Dict[str, Any]] = []
    suffix, suffix_issues = _grid_contract_suffix(expected_grid_role, expected_grid_suffix, code_source)
    issues.extend(suffix_issues)
    grid_name = f"grd{suffix}"
    view_name = f"gvw{suffix}"
    prefix = str(expected_grid_prefix or "").strip() or f"col{suffix}_"
    assignments = _csharp_designer_assignments(source, code_source)
    expected_input_source = expected_grid_columns if expected_grid_columns is not None else result_fields
    expected_input = None if expected_input_source is None else list(expected_input_source)
    normalized_expected = (
        _normalize_grid_column_specs(expected_input, prefix=prefix)
        if expected_input is not None
        else []
    )
    if expected_input is not None:
        issues.extend(_grid_column_mapping_issues(expected_input, normalized_expected, prefix=prefix))
    observed_columns = [
        {"name": match.group(0), "field_name": match.group("field")}
        for match in re.finditer(
            rf"\b{re.escape(prefix)}(?P<field>[A-Z][A-Z0-9_]*)\b",
            code_source,
        )
    ]
    observed_by_name = {item["name"]: item for item in observed_columns}
    if not normalized_expected:
        normalized_columns: List[Dict[str, Any]] = [
            {"field_name": item["field_name"], "csharp_name": item["name"], "caption": None}
            for item in observed_by_name.values()
        ]
    else:
        normalized_columns = [
            {
                "field_name": item.field_name,
                "csharp_name": item.csharp_name,
                "caption": item.caption or item.field_name,
                "data_type": item.data_type,
            }
            for item in normalized_expected
        ]

    artifact_verified = False
    artifact_issue_codes: List[str] = []
    artifact_path_resolved = ""
    artifact_sha256 = ""
    artifact_source = ""
    artifact_text = str(layout_load_artifact_text or "")
    if str(layout_load_artifact_path or "").strip():
        path = Path(layout_load_artifact_path)
        try:
            path_xml_text = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            issues.append(
                {
                    "code": "layout_load_artifact_unreadable",
                    "severity": "error",
                    "message": "The explicit Layout Load artifact path must be readable.",
                    "detail": str(exc),
                }
            )
        else:
            artifact_path_resolved = str(path.resolve())
            if artifact_text and artifact_text != path_xml_text:
                issues.append(
                    {
                        "code": "layout_load_artifact_text_path_mismatch",
                        "severity": "error",
                        "message": "When both XML text and path are supplied, their exact content must match.",
                    }
                )
            else:
                artifact_text = path_xml_text
                artifact_source = "path"
    elif artifact_text:
        artifact_source = "text"

    if expected_requested and not artifact_text:
        issues.append(
            {
                "code": "layout_load_artifact_required",
                "severity": "error",
                "message": "An explicit grid contract requires valid Layout-Load-ready XML text or an XML artifact path plus matching Designer source.",
            }
        )
    if artifact_text:
        artifact_sha256 = "sha256:" + hashlib.sha256(artifact_text.encode("utf-8")).hexdigest()
        xml_result = verify_devexpress_grid_xml_contract(
            artifact_text,
            expected_columns=expected_input,
            input_format=expected_grid_role or "list",
            table_name=expected_grid_suffix if str(expected_grid_role).lower() == "table" else "",
            purpose_name=expected_grid_suffix if str(expected_grid_role).lower() in {"purpose", "domain", "role", "logical"} else "",
            expected_column_prefix=prefix,
        )
        artifact_verified = xml_result.success
        artifact_issue_codes = [item["code"] for item in xml_result.metadata.get("issues", [])]
        if not artifact_verified:
            issues.append(
                {
                    "code": "layout_load_artifact_contract_failed",
                    "severity": "error",
                    "message": "The Layout-Load-ready XML did not pass exact value-level contract verification.",
                    "artifact_issue_codes": artifact_issue_codes,
                }
            )

    # Local dictionaries and hashes are caller assertions, not DevExpress host receipts.
    layout_load_evidence_verified = False
    layout_load_evidence_status = (
        "caller_assertion_ignored" if layout_load_evidence is not None else "not_supplied"
    )

    def add_missing(code: str, message: str, **details: Any) -> None:
        issues.append({"code": code, "severity": "error", "message": message, **details})

    declarations = {
        "grid": bool(re.search(rf"\bprivate\s+DevExpress\.XtraGrid\.GridControl\s+{re.escape(grid_name)}\s*;", code_source)),
        "view": bool(re.search(rf"\bprivate\s+DevExpress\.XtraGrid\.Views\.Grid\.GridView\s+{re.escape(view_name)}\s*;", code_source)),
    }
    initializers = {
        "grid": bool(re.search(rf"this\.{re.escape(grid_name)}\s*=\s*new\s+DevExpress\.XtraGrid\.GridControl\s*\(", code_source)),
        "view": bool(re.search(rf"this\.{re.escape(view_name)}\s*=\s*new\s+DevExpress\.XtraGrid\.Views\.Grid\.GridView\s*\(", code_source)),
    }
    for kind, present in {**{f"declaration_{k}": v for k, v in declarations.items()}, **{f"initializer_{k}": v for k, v in initializers.items()}}.items():
        if not present:
            add_missing("grid_designer_member_or_initializer_missing", "GridControl and GridView must be explicit Designer members and initializers.", item=kind)
    main_view_targets = re.findall(
        rf"this\.{re.escape(grid_name)}\.MainView\s*=\s*this\.([A-Za-z_][A-Za-z0-9_]*)\s*;",
        code_source,
    )
    if main_view_targets != [view_name]:
        add_missing(
            "grid_designer_wiring_identity_mismatch",
            "GridControl.MainView must reference exactly the expected GridView member.",
            item="MainView",
            expected=[view_name],
            actual=main_view_targets,
        )
    view_collection_calls = list(
        re.finditer(
            rf"this\.{re.escape(grid_name)}\.ViewCollection\.AddRange\s*\((?P<body>[\s\S]*?)\)\s*;",
            code_source,
        )
    )
    view_collection_members = (
        re.findall(r"this\.(gvw[A-Za-z_][A-Za-z0-9_]*)", view_collection_calls[0].group("body"))
        if len(view_collection_calls) == 1
        else []
    )
    if len(view_collection_calls) != 1 or view_collection_members != [view_name]:
        add_missing(
            "grid_designer_wiring_identity_mismatch",
            "GridControl.ViewCollection.AddRange must contain exactly the expected GridView member.",
            item="ViewCollection",
            expected=[view_name],
            actual=view_collection_members,
        )
    grid_control_targets = re.findall(
        rf"this\.{re.escape(view_name)}\.GridControl\s*=\s*this\.([A-Za-z_][A-Za-z0-9_]*)\s*;",
        code_source,
    )
    if grid_control_targets != [grid_name]:
        add_missing(
            "grid_designer_wiring_identity_mismatch",
            "GridView.GridControl must reference exactly the expected GridControl member.",
            item="GridControl",
            expected=[grid_name],
            actual=grid_control_targets,
        )
    columns_add_range_pattern = rf"this\.{re.escape(view_name)}\.Columns\.AddRange\s*\((?P<body>[\s\S]*?)\)\s*;"
    column_add_range_calls = list(re.finditer(columns_add_range_pattern, code_source))
    if len(column_add_range_calls) != 1:
        add_missing(
            "grid_designer_wiring_missing",
            "GridView.Columns.AddRange must be present exactly once.",
            item="Columns.AddRange",
        )
    for member, expected_value in ((grid_name, grid_name), (view_name, view_name)):
        actual = _csharp_direct_string_value(
            _csharp_last_assignment_value(assignments, (member, "Name"), "")
        )
        if actual != expected_value:
            add_missing(
                "grid_component_name_mismatch",
                "C# component Name must use the target role naming contract, not the XML gridView1 name.",
                member=member,
                expected=expected_value,
                actual=actual,
            )
    for property_name, expected_value in DATAWINDOW_TO_CSHARP_GRIDVIEW_DEFAULTS:
        actual = _csharp_last_assignment_value(assignments, (view_name, property_name))
        if actual is None:
            add_missing(
                "authoritative_gridview_default_missing",
                "C# Designer must contain the post-load-equivalent authoritative GridView value.",
                property=property_name,
                expected=expected_value,
            )
        elif not _csharp_layout_value_matches(property_name, actual, expected_value):
            add_missing(
                "authoritative_gridview_default_mismatch",
                "C# Designer GridView value conflicts with the authoritative Layout Load baseline.",
                property=property_name,
                expected=expected_value,
                actual=actual,
            )
    for property_name, expected_value in DATAWINDOW_TO_XML_OPTIONS_VIEW_DEFAULTS.items():
        property_path = f"OptionsView.{property_name}"
        actual = _csharp_last_assignment_value(assignments, (view_name, property_path))
        if actual is None:
            add_missing(
                "authoritative_optionsview_default_missing",
                "C# Designer must contain the post-load-equivalent authoritative OptionsView value.",
                property=property_path,
                expected=expected_value,
            )
        elif not _csharp_layout_value_matches(property_name, actual, expected_value):
            add_missing(
                "authoritative_optionsview_default_mismatch",
                "C# Designer OptionsView value conflicts with the authoritative Layout Load baseline.",
                property=property_path,
                expected=expected_value,
                actual=actual,
            )

    if re.search(r"\.ColumnEditName\s*=", code_source):
        add_missing(
            "csharp_column_edit_name_assignment_detected",
            "ColumnEditName is an empty XML serializer value only and must not be emitted as a C# Designer assignment.",
        )
    expected_order = [item["csharp_name"] for item in normalized_columns]
    if expected_order and len(column_add_range_calls) == 1:
        actual_order = re.findall(
            r"this\.(col[A-Za-z_][A-Za-z0-9_]*)",
            column_add_range_calls[0].group("body"),
        )
        if actual_order != expected_order:
            add_missing(
                "grid_columns_addrange_identity_order_mismatch",
                "GridView.Columns.AddRange must contain exactly the expected GridColumn members in loaded VisibleIndex order.",
                expected=expected_order,
                actual=actual_order,
            )
    for visible_index, item in enumerate(normalized_columns, start=1):
        column_name = item["csharp_name"]
        field_name = item["field_name"]
        if not re.search(
            rf"\bprivate\s+DevExpress\.XtraGrid\.Columns\.GridColumn\s+{re.escape(column_name)}\s*;",
            code_source,
        ) or not re.search(
            rf"this\.{re.escape(column_name)}\s*=\s*new\s+DevExpress\.XtraGrid\.Columns\.GridColumn\s*\(",
            code_source,
        ):
            add_missing(
                "grid_column_member_or_initializer_missing",
                "Each targeted GridColumn must be an explicit Designer member and initializer.",
                column=column_name,
            )
        checks = [
            ("Name", column_name, "string"),
            ("FieldName", field_name, "string"),
            ("Visible", "true", "value"),
            ("VisibleIndex", str(visible_index), "value"),
            ("AppearanceHeader.Options.UseTextOptions", "true", "value"),
            ("AppearanceHeader.Options.UseFont", "true", "value"),
            ("AppearanceHeader.TextOptions.HAlignment", "Center", "enum"),
            ("AppearanceHeader.TextOptions.VAlignment", "Center", "enum"),
            ("AppearanceHeader.Font", "Tahoma, 9", "font"),
            ("AppearanceCell.Options.UseFont", "true", "value"),
            ("AppearanceCell.Font", "Tahoma, 9", "font"),
        ]
        if item.get("caption") is not None:
            checks.insert(2, ("Caption", str(item["caption"]), "string"))
        for property_path, expected_value, value_kind in checks:
            actual = _csharp_last_assignment_value(
                assignments, (column_name, property_path)
            )
            if actual is None:
                add_missing(
                    "authoritative_grid_column_default_missing",
                    "C# Designer column must contain the post-load-equivalent authoritative value.",
                    column=column_name,
                    property=property_path,
                    expected=expected_value,
                )
                continue
            matched = (
                _csharp_direct_string_value(actual) == expected_value
                if value_kind == "string"
                else _csharp_tahoma_nine_font(actual)
                if value_kind == "font"
                else actual.split(".")[-1] == expected_value
                if value_kind == "enum"
                else re.sub(r"\s+", "", actual).lower() == expected_value.lower()
            )
            if not matched:
                add_missing(
                    "authoritative_grid_column_default_mismatch",
                    "C# Designer column value conflicts with the authoritative Layout Load baseline.",
                    column=column_name,
                    property=property_path,
                    expected=expected_value,
                    actual=actual,
                )
        if item.get("caption") is None:
            caption = _csharp_direct_string_value(
                _csharp_last_assignment_value(
                    assignments, (column_name, "Caption"), ""
                )
            )
            if caption is None or caption == "":
                add_missing(
                    "grid_column_caption_missing",
                    "GridColumn Caption must use supplied PB text when mapped and otherwise fall back to FieldName.",
                    column=column_name,
                )

        declared_numeric = _is_numeric_grid_data_type(str(item.get("data_type") or ""))
        is_numeric = declared_numeric is True or (
            declared_numeric is None and not normalized_expected and _is_numeric_grid_field_name(field_name)
        )
        if is_numeric:
            repository_rhs = _csharp_last_assignment_value(
                assignments, (column_name, "ColumnEdit"), ""
            )
            repository_match = re.fullmatch(r"this\.(rpsSpin[A-Za-z0-9_]*)", repository_rhs)
            if not repository_match:
                add_missing(
                    "numeric_grid_column_missing_spin_repository",
                    "Numeric GridColumns require RepositoryItemSpinEdit through ColumnEdit.",
                    column=column_name,
                )
            else:
                repository_name = repository_match.group(1)
                repository_declared = bool(
                    re.search(
                        rf"\b(?:private\s+)?(?:DevExpress\.XtraEditors\.Repository\.)?RepositoryItemSpinEdit\s+{re.escape(repository_name)}\s*;",
                        code_source,
                    )
                )
                repository_initialized = bool(
                    re.search(
                        rf"this\.{re.escape(repository_name)}\s*=\s*new\s+(?:DevExpress\.XtraEditors\.Repository\.)?RepositoryItemSpinEdit\s*\(",
                        code_source,
                    )
                )
                if not repository_declared or not repository_initialized:
                    add_missing(
                        "numeric_grid_spin_repository_not_declared_or_initialized",
                        "Numeric GridColumns require a declared and initialized RepositoryItemSpinEdit.",
                        column=column_name,
                        repository=repository_name,
                    )
                registration = re.search(
                    rf"this\.{re.escape(grid_name)}\.RepositoryItems\.AddRange\s*\([\s\S]*?this\.{re.escape(repository_name)}[\s\S]*?\)\s*;",
                    code_source,
                )
                column_edit_offset = code_source.find(f"this.{column_name}.ColumnEdit")
                if registration is None or registration.start() > column_edit_offset:
                    add_missing(
                        "numeric_grid_repository_registration_order_invalid",
                        "RepositoryItemSpinEdit must be registered on the GridControl before ColumnEdit assignment.",
                        column=column_name,
                        repository=repository_name,
                    )
            if re.search(rf"this\.{re.escape(column_name)}\.DisplayFormat\.Format(?:String|Type)\s*=", code_source):
                add_missing(
                    "numeric_grid_column_displayformat_detected",
                    "Numeric GridColumns must use SpinEdit behavior and must not emit GridColumn DisplayFormat.",
                    column=column_name,
                )

    return issues, {
        "status": "passed" if not issues else "blocked",
        "expected_grid_role": expected_grid_role or "inferred",
        "expected_grid_suffix": suffix,
        "grid_control_name": grid_name,
        "grid_view_name": view_name,
        "grid_column_prefix": prefix,
        "expected_columns": normalized_columns,
        "layout_load_artifact_verified": artifact_verified,
        "layout_load_evidence_verified": layout_load_evidence_verified,
        "layout_load_evidence_status": layout_load_evidence_status,
        "actual_live_layout_load_observed": False,
        "verification_scope": "static_xml_and_post_load_equivalent_designer_state",
        "layout_load_artifact_source": artifact_source,
        "layout_load_artifact_path": artifact_path_resolved,
        "layout_load_artifact_sha256": artifact_sha256,
        "layout_load_artifact_issue_codes": artifact_issue_codes,
        "designer_source_used": True,
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
    expected_control_contracts: Iterable[Mapping[str, Any]] | None = None,
    no_control_contract_evidence: Any = None,
    evidence_registry: Any = None,
    target_source_path: str | Path = "",
    target_source_sha256: str = "",
    target_designer_path: str | Path = "",
    target_designer_sha256: str = "",
    baseline_designer_path: str | Path = "",
    baseline_designer_sha256: str = "",
    expected_grid_role: str = "",
    expected_grid_suffix: str = "",
    expected_grid_prefix: str = "",
    expected_grid_columns: Iterable[Any] | None = None,
    expected_grid_contracts: Iterable[Mapping[str, Any]] | None = None,
    layout_load_artifact_path: str = "",
    layout_load_artifact_text: str = "",
    layout_load_evidence: Any = None,
    require_designer_companion: bool = False,
    primary_style_evidence_paths: Any = None,
    excluded_paths: Any = None,
    require_author_tagged_evidence: bool = False,
) -> HarnessResult:
    """Block generated C# patterns that do not match control, Designer, and grid contracts."""
    result_fields_list = None if result_fields is None else list(result_fields)
    expected_control_contracts_list = (
        None if expected_control_contracts is None else list(expected_control_contracts)
    )
    expected_grid_columns_list = None if expected_grid_columns is None else list(expected_grid_columns)
    expected_grid_contracts_list = [dict(item) for item in (expected_grid_contracts or [])]
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
    designer_contract_rules = profile_rules.get("designer_contract")
    designer_contract_rules = (
        dict(designer_contract_rules)
        if isinstance(designer_contract_rules, Mapping)
        else {}
    )
    target_artifact_required = bool(
        designer_contract_rules.get("target_artifact_binding_required")
    )
    source_artifact_issues, source_artifact_binding, _ = _validate_text_artifact_binding(
        source_text,
        path_value=target_source_path,
        expected_sha256=target_source_sha256,
        role="source",
        required=target_artifact_required,
    )
    issues.extend(source_artifact_issues)
    designer_artifact_issues, designer_artifact_binding, _ = _validate_text_artifact_binding(
        designer_source_text,
        path_value=target_designer_path,
        expected_sha256=target_designer_sha256,
        role="designer",
        required=bool(target_artifact_required and designer_source_text.strip()),
    )
    issues.extend(designer_artifact_issues)
    baseline_artifact_issues, baseline_artifact_binding, baseline_designer_source = (
        _validate_text_artifact_binding(
            "",
            path_value=baseline_designer_path,
            expected_sha256=baseline_designer_sha256,
            role="baseline_designer",
            required=False,
        )
    )
    if baseline_designer_source:
        baseline_artifact_binding["readback_matches_supplied_text"] = True
        baseline_artifact_issues = [
            issue
            for issue in baseline_artifact_issues
            if issue.get("code") != "target_baseline_designer_artifact_text_mismatch"
        ]
        baseline_artifact_binding["status"] = (
            "passed" if not baseline_artifact_issues else "blocked"
        )
    issues.extend(baseline_artifact_issues)
    artifact_path_issues = _validate_target_artifact_path_separation(
        source_artifact_binding,
        designer_artifact_binding,
        baseline_artifact_binding,
    )
    if artifact_path_issues:
        for binding in (
            source_artifact_binding,
            designer_artifact_binding,
            baseline_artifact_binding,
        ):
            if binding.get("status") == "passed":
                binding["status"] = "blocked"
    issues.extend(artifact_path_issues)
    registry, registry_issues, registry_metadata = _normalize_evidence_registry(
        evidence_registry,
        required=bool(
            designer_contract_rules.get("structured_evidence_registry_required")
            and (
                no_control_contract_evidence is not None
                or any(
                    isinstance(item, Mapping)
                    and (
                        item.get("evidence_refs")
                        or item.get("property_evidence")
                    )
                    for item in (expected_control_contracts_list or [])
                )
            )
        ),
    )
    issues.extend(registry_issues)
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
        allow_empty_designer=expected_control_contracts_list == [],
    )
    issues.extend(designer_issues)
    result_field_issues, result_field_contract = _validate_csharp_result_field_contract(
        source_view,
        designer_view,
        result_fields_list,
    )
    issues.extend(result_field_issues)
    control_designer_source = (
        designer_source
        if designer_view.code.strip()
        else (source if str(source_role).lower() == "designer" else "")
    )
    control_designer_code = (
        designer_view.code
        if designer_view.code.strip()
        else (source_view.code if str(source_role).lower() == "designer" else "")
    )
    control_contract_issues, control_contracts, exact_control_properties = (
        _validate_expected_control_contracts(
            control_designer_source,
            control_designer_code,
            expected_control_contracts_list,
            target_form_class=str(program_form_contract.get("expected_form_class") or ""),
            expected_control_contract_required=bool(
                designer_contract_rules.get("expected_control_contract_required")
            ),
            no_control_contract_evidence=no_control_contract_evidence,
            evidence_registry=registry,
            structured_evidence_required=bool(
                designer_contract_rules.get("structured_evidence_registry_required")
            ),
            complete_inventory_required=bool(
                designer_contract_rules.get("control_contract_completeness_required")
            ),
            initialize_component_scope_required=bool(
                designer_contract_rules.get("initialize_component_scope_required")
            ),
        )
    )
    issues.extend(control_contract_issues)
    konelib_guard_issues, konelib_default_guards = _validate_konelib_default_guards(
        control_designer_source,
        control_designer_code,
        exact_control_properties,
        profile_rules,
        target_form_class=str(program_form_contract.get("expected_form_class") or ""),
    )
    issues.extend(konelib_guard_issues)
    baseline_view = _lex_csharp_non_code(baseline_designer_source)
    baseline_preservation_issues, baseline_designer_preservation = (
        _validate_baseline_designer_preservation(
            control_designer_source,
            control_designer_code,
            baseline_view.comments_removed,
            baseline_view.code,
            exact_control_properties,
            profile_rules,
            target_form_class=str(program_form_contract.get("expected_form_class") or ""),
        )
    )
    issues.extend(baseline_preservation_issues)
    consumed_control_exceptions = konelib_default_guards.get(
        "consumed_explicit_exceptions", []
    )
    for control_contract in control_contracts.get("contracts", []):
        control_contract["consumed_explicit_exceptions"] = [
            dict(item)
            for item in consumed_control_exceptions
            if item.get("control") == control_contract.get("control")
        ]
    grid_designer_source = designer_source if designer_view.code.strip() else (source if str(source_role).lower() == "designer" else "")
    grid_designer_code = (
        designer_view.code
        if designer_view.code.strip()
        else (source_view.code if str(source_role).lower() == "designer" else "")
    )
    explicit_grid_requested = bool(
        expected_grid_contracts_list
        or str(expected_grid_role or expected_grid_suffix or expected_grid_prefix).strip()
        or expected_grid_columns_list is not None
        or str(layout_load_artifact_path or layout_load_artifact_text).strip()
    )
    raw_grid_source = designer_source_text if str(designer_source_text or "").strip() else (
        source_text if str(source_role).lower() == "designer" else ""
    )
    if explicit_grid_requested and _has_unknown_csharp_preprocessor(raw_grid_source):
        issues.append(
            {
                "code": "grid_designer_unknown_conditional_compilation",
                "severity": "error",
                "message": "Unknown conditional-compilation branches cannot serve as unconditional Designer grid evidence.",
            }
        )
    if expected_grid_contracts_list:
        contract_results: List[Dict[str, Any]] = []
        for contract_index, contract in enumerate(expected_grid_contracts_list):
            contract_issues, contract_metadata = _validate_devexpress_designer_grid_contract(
                grid_designer_source,
                designer_code=grid_designer_code,
                expected_grid_role=str(contract.get("role") or contract.get("expected_grid_role") or ""),
                expected_grid_suffix=str(contract.get("suffix") or contract.get("expected_grid_suffix") or ""),
                expected_grid_prefix=str(contract.get("prefix") or contract.get("expected_grid_prefix") or ""),
                expected_grid_columns=contract.get("columns", contract.get("expected_grid_columns")),
                result_fields=contract.get("result_fields", result_fields_list),
                layout_load_artifact_path=str(contract.get("artifact_path") or contract.get("layout_load_artifact_path") or ""),
                layout_load_artifact_text=str(contract.get("artifact_text") or contract.get("layout_load_artifact_text") or ""),
                layout_load_evidence=contract.get("layout_load_evidence"),
            )
            for item in contract_issues:
                item.setdefault("grid_contract_index", contract_index)
                if contract.get("id"):
                    item.setdefault("grid_contract_id", str(contract["id"]))
            issues.extend(contract_issues)
            contract_metadata["grid_contract_index"] = contract_index
            contract_metadata["grid_contract_id"] = str(contract.get("id") or "")
            contract_results.append(contract_metadata)
        grid_designer_contract = {
            "status": "passed" if all(item.get("status") == "passed" for item in contract_results) else "blocked",
            "contracts": contract_results,
            "actual_live_layout_load_observed": False,
            "verification_scope": "static_xml_and_post_load_equivalent_designer_state",
        }
    else:
        grid_contract_issues, grid_designer_contract = _validate_devexpress_designer_grid_contract(
            grid_designer_source,
            designer_code=grid_designer_code,
            expected_grid_role=expected_grid_role,
            expected_grid_suffix=expected_grid_suffix,
            expected_grid_prefix=expected_grid_prefix,
            expected_grid_columns=expected_grid_columns_list,
            result_fields=result_fields_list,
            layout_load_artifact_path=layout_load_artifact_path,
            layout_load_artifact_text=layout_load_artifact_text,
            layout_load_evidence=layout_load_evidence,
        )
        issues.extend(grid_contract_issues)
    tab_order_issues, input_tab_order_contract = _validate_input_tab_order(
        designer_view.code if designer_view.code.strip() else (source_view.code if str(source_role).lower() == "designer" else "")
    )
    issues.extend(tab_order_issues)
    profile_consumption = dict(
        profile_context.get("consumption", profile_context)
        if isinstance(profile_context, dict)
        else {}
    )
    if profile_consumption.get("consumed"):
        applied_groups = list(profile_consumption.get("applied_rule_groups", []))
        for group in (
            "csharp.program_form_contract",
            "csharp.designer_contract",
            "csharp.control_contracts",
            "csharp.konelib_defaults",
            "csharp.target_artifact_binding",
            "csharp.evidence_registry",
            "csharp.baseline_designer_preservation",
        ):
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

    grid_source = designer_view.code if designer_view.code.strip() else source_view.code
    combined_grid_source = f"{source_view.code}\n{designer_view.code}"
    has_designer_grid_column_members = bool(
        re.search(r"\bprivate\s+DevExpress\.XtraGrid\.Columns\.GridColumn\s+col(?:List|Detail|[A-Za-z0-9]+)_[A-Z0-9_]+\s*;", grid_source)
        and re.search(r"this\.col(?:List|Detail|[A-Za-z0-9]+)_[A-Z0-9_]+\s*=\s*new\s+DevExpress\.XtraGrid\.Columns\.GridColumn\s*\(\s*\)\s*;", grid_source)
        and re.search(r"\.Columns\.AddRange\s*\([\s\S]*this\.col(?:List|Detail|[A-Za-z0-9]+)_[A-Z0-9_]+", grid_source)
    )

    if re.search(r"\bAddGridColumn\s*\(", combined_grid_source):
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
    if re.search(r"\.Columns\.AddField\s*\(", combined_grid_source):
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
    if re.search(r"\.Columns\.Add\s*\(", combined_grid_source):
        issues.append(
            {
                "code": "runtime_columns_add_detected",
                "severity": "error",
                "message": "Generated grid columns must not be registered through runtime Columns.Add; use explicit Designer Columns.AddRange registration.",
            }
        )
    for constructor_match in re.finditer(r"(?m)^.*new\s+(?:DevExpress\.XtraGrid\.Columns\.)?GridColumn\s*\(\s*\)\s*;", combined_grid_source):
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
    if re.search(r"\.Name\s*=\s*[^;\n]*view\.Name\s*\+[^;\n]*\+\s*fieldName", combined_grid_source):
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
    if "GridColumn" in grid_source and not re.search(r"\bcol(?:List|Detail|[A-Za-z0-9]+)_[A-Z0-9_]+\b", grid_source):
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

    numeric_column_names: set[str] = set()
    if expected_grid_contracts_list:
        # Each targeted contract already validates its own type-driven repositories.
        pass
    elif expected_grid_columns_list is not None:
        expected_prefix = str(grid_designer_contract.get("grid_column_prefix") or "colList_")
        numeric_column_names.update(
            item.csharp_name
            for item in _normalize_grid_column_specs(expected_grid_columns_list, prefix=expected_prefix)
            if _is_numeric_grid_data_type(item.data_type) is True
        )
    else:
        for column_name in re.findall(r"this\.(col(?:List|Detail|[A-Za-z0-9]+)_([A-Z0-9_]+))\.", grid_source):
            full_name, field_name = column_name
            if _is_numeric_grid_field_name(field_name):
                numeric_column_names.add(full_name)
        numeric_column_names.update(
            re.findall(
                r"this\.(col(?:List|Detail|[A-Za-z0-9]+)_[A-Z0-9_]+)\.DisplayFormat\.FormatType\s*=\s*DevExpress\.Utils\.FormatType\.Numeric",
                grid_source,
            )
        )
        for match in re.finditer(
            r'this\.(col(?:List|Detail|[A-Za-z0-9]+)_[A-Z0-9_]+)\.DisplayFormat\.FormatString\s*=\s*"([^"]+)"',
            designer_source if designer_source.strip() else source,
        ):
            if _display_format_string_looks_numeric(match.group(2)):
                numeric_column_names.add(match.group(1))
    for column_name in sorted(numeric_column_names):
        spin_repository_match = re.search(
            rf"this\.{re.escape(column_name)}\.ColumnEdit\s*=\s*this\.(rpsSpin[A-Za-z0-9_]*)\s*;",
            grid_source,
        )
        has_spin_repository = bool(spin_repository_match)
        has_column_numeric_display = bool(
            re.search(rf"this\.{re.escape(column_name)}\.DisplayFormat\.Format(?:String|Type)\s*=", grid_source)
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
                    grid_source,
                )
            )
            repository_initialized = bool(
                re.search(
                    rf"this\.{re.escape(repository_name)}\s*=\s*new\s+(?:DevExpress\.XtraEditors\.Repository\.)?RepositoryItemSpinEdit\s*\(",
                    grid_source,
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
        "control_contracts": control_contracts,
        "konelib_default_guards": konelib_default_guards,
        "target_artifact_binding": {
            "source": source_artifact_binding,
            "designer": designer_artifact_binding,
            "baseline_designer": baseline_artifact_binding,
        },
        "control_evidence_registry": registry_metadata,
        "baseline_designer_preservation": baseline_designer_preservation,
        "grid_designer_contract": grid_designer_contract,
        "input_tab_order_contract": input_tab_order_contract,
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
        stderr="" if passed else "Generated C# style verification blocked by contract issues.",
        exit_code=0 if passed else 1,
        metadata=metadata,
    )

def _split_sp_parameter_list(text: str) -> List[str]:
    parts: List[str] = []
    start = 0
    depth = 0
    in_string = False
    index = 0
    while index < len(text):
        char = text[index]
        if char == "'":
            if in_string and index + 1 < len(text) and text[index + 1] == "'":
                index += 2
                continue
            in_string = not in_string
        elif not in_string:
            if char == "(":
                depth += 1
            elif char == ")" and depth > 0:
                depth -= 1
            elif char == "," and depth == 0:
                part = text[start:index].strip()
                if part:
                    parts.append(part)
                start = index + 1
        index += 1
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _mask_sql_comments_and_strings(sql_text: str, *, mask_strings: bool) -> str:
    text = str(sql_text or "")
    result = list(text)
    state = "code"
    index = 0
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            if char == "'":
                state = "string"
                if mask_strings:
                    result[index] = " "
            elif char == "-" and next_char == "-":
                state = "line_comment"
                result[index] = result[index + 1] = " "
                index += 1
            elif char == "/" and next_char == "*":
                state = "block_comment"
                result[index] = result[index + 1] = " "
                index += 1
        elif state == "string":
            if mask_strings:
                result[index] = " "
            if char == "'" and next_char == "'":
                if mask_strings:
                    result[index + 1] = " "
                index += 1
            elif char == "'":
                state = "code"
        elif state == "line_comment":
            if char not in "\r\n":
                result[index] = " "
            else:
                state = "code"
        elif state == "block_comment":
            if char == "*" and next_char == "/":
                result[index] = result[index + 1] = " "
                index += 1
                state = "code"
            elif char not in "\r\n":
                result[index] = " "
        index += 1
    return "".join(result)


def _extract_sp_parameter_text(sql_text: str) -> str:
    source = str(sql_text or "")
    searchable = _mask_sql_comments_and_strings(source, mask_strings=True)
    match = re.search(
        r"(?:CREATE\s+(?:OR\s+ALTER\s+)?|ALTER\s+)PROCEDURE\s+"
        r"(?:\[[^\]]+\]|[A-Z0-9_]+)(?:\s*\.\s*(?:\[[^\]]+\]|[A-Z0-9_]+))?",
        searchable,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    depth = 0
    index = match.end()
    while index < len(searchable):
        char = searchable[index]
        if char == "(":
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1
        elif depth == 0 and searchable[index : index + 2].upper() == "AS":
            before = searchable[index - 1] if index > 0 else " "
            after = searchable[index + 2] if index + 2 < len(searchable) else " "
            if not (before.isalnum() or before in "_@") and not (
                after.isalnum() or after == "_"
            ):
                return source[match.end() : index]
        index += 1
    return ""


def _normalize_sp_default(value: str) -> str:
    result: List[str] = []
    pending_space = False
    in_string = False
    index = 0
    while index < len(value):
        char = value[index]
        if char == "'":
            if pending_space and result and not result[-1].isspace():
                result.append(" ")
            pending_space = False
            result.append(char)
            if in_string and index + 1 < len(value) and value[index + 1] == "'":
                result.append("'")
                index += 2
                continue
            in_string = not in_string
        elif not in_string and char.isspace():
            pending_space = True
        else:
            if pending_space and result and not result[-1].isspace():
                result.append(" ")
            pending_space = False
            result.append(char)
        index += 1
    return "".join(result).strip()


def _extract_sp_parameter_contract(sql_text: str) -> List[Dict[str, Any]]:
    parameter_text = _extract_sp_parameter_text(sql_text)
    if not parameter_text:
        return []
    parameter_text = _mask_sql_comments_and_strings(
        parameter_text,
        mask_strings=False,
    )
    parameters: List[Dict[str, Any]] = []
    for ordinal, raw in enumerate(_split_sp_parameter_list(parameter_text)):
        parameter = re.match(
            r"^\s*@(?P<name>[A-Z][A-Z0-9_]*)\s+"
            r"(?P<type>(?:\[[^\]]+\]|[A-Z][A-Z0-9_]*)(?:\s*\.\s*(?:\[[^\]]+\]|[A-Z][A-Z0-9_]*))?)"
            r"(?P<type_args>\s*\([^)]*\))?(?P<rest>[\s\S]*)$",
            raw,
            flags=re.IGNORECASE,
        )
        if not parameter:
            continue
        rest = parameter.group("rest").strip()
        searchable_rest = _mask_sql_comments_and_strings(rest, mask_strings=True)
        option_matches = list(
            re.finditer(r"\b(?:OUT(?:PUT)?|READONLY)\b", searchable_rest, flags=re.IGNORECASE)
        )
        output = any(match.group(0).upper() in {"OUT", "OUTPUT"} for match in option_matches)
        readonly = any(match.group(0).upper() == "READONLY" for match in option_matches)
        default_index = searchable_rest.find("=")
        default_end = len(rest)
        if default_index >= 0:
            trailing_options = [match.start() for match in option_matches if match.start() > default_index]
            if trailing_options:
                default_end = min(trailing_options)
        default_value = (
            _normalize_sp_default(rest[default_index + 1 : default_end].strip())
            if default_index >= 0
            else ""
        )
        type_name = re.sub(r"\s*\.\s*", ".", parameter.group("type")).upper()
        type_args = re.sub(r"\s+", "", parameter.group("type_args") or "").upper()
        parameters.append(
            {
                "ordinal": ordinal,
                "name": f"@{parameter.group('name').upper()}",
                "type": type_name,
                "type_args": type_args,
                "type_spec": f"{type_name}{type_args}",
                "default_present": default_index >= 0,
                "default": default_value,
                "output": output,
                "readonly": readonly,
            }
        )
    return parameters


def _normalize_caller_parameter_contract(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, str):
        value = re.findall(r"@[A-Za-z][A-Za-z0-9_]*", value)
    if not isinstance(value, (list, tuple)):
        return []
    result: List[Dict[str, Any]] = []
    for ordinal, item in enumerate(value):
        if isinstance(item, dict):
            raw_name = item.get("name") or item.get("parameter") or item.get("parameter_name")
            match = re.fullmatch(r"@?([A-Za-z][A-Za-z0-9_]*)", str(raw_name or "").strip())
            if not match:
                continue
            type_spec = re.sub(r"\s+", "", str(item.get("type_spec") or item.get("sql_type") or "")).upper()
            result.append(
                {
                    "ordinal": ordinal,
                    "name": f"@{match.group(1).upper()}",
                    "type_spec": type_spec,
                    "type_specified": bool(type_spec),
                    "default_present": bool(item.get("default_present", "default" in item)),
                    "default_specified": "default_present" in item or "default" in item,
                    "default": _normalize_sp_default(str(item.get("default") or "").strip()),
                    "output": bool(item.get("output")),
                    "output_specified": "output" in item,
                    "readonly": bool(item.get("readonly")),
                    "readonly_specified": "readonly" in item,
                }
            )
            continue
        match = re.search(r"@?([A-Za-z][A-Za-z0-9_]*)", str(item or ""))
        if match:
            result.append(
                {
                    "ordinal": ordinal,
                    "name": f"@{match.group(1).upper()}",
                    "type_spec": "",
                    "type_specified": False,
                    "default_present": False,
                    "default_specified": False,
                    "default": "",
                    "output": False,
                    "output_specified": False,
                    "readonly": False,
                    "readonly_specified": False,
                }
            )
    return result


def _sp_signatures_equal(
    candidate: List[Dict[str, Any]],
    original: List[Dict[str, Any]],
) -> bool:
    fields = ["name", "type_spec", "default_present", "default", "output", "readonly"]
    return len(candidate) == len(original) and all(
        all(candidate[index].get(field) == original[index].get(field) for field in fields)
        for index in range(len(candidate))
    )


def _sql_contract_tokens(
    sql_text: str,
    *,
    include_comments: bool,
    ignore_statement_terminators: bool = False,
) -> List[tuple[str, str]]:
    """Tokenize SQL for preservation checks without changing string/comment payloads."""
    text = str(sql_text or "")
    tokens: List[tuple[str, str]] = []
    index = 0
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if char.isspace():
            index += 1
            continue
        if char == "-" and next_char == "-":
            end = text.find("\n", index + 2)
            if end < 0:
                end = len(text)
            if include_comments:
                tokens.append(("comment", text[index:end].rstrip("\r")))
            index = end
            continue
        if char == "/" and next_char == "*":
            end = text.find("*/", index + 2)
            end = len(text) if end < 0 else end + 2
            if include_comments:
                tokens.append(("comment", text[index:end].replace("\r\n", "\n")))
            index = end
            continue
        if char == "'" or (char in "Nn" and next_char == "'"):
            start = index
            if char in "Nn":
                index += 1
            index += 1
            while index < len(text):
                if text[index] == "'":
                    if index + 1 < len(text) and text[index + 1] == "'":
                        index += 2
                        continue
                    index += 1
                    break
                index += 1
            tokens.append(("string", text[start:index]))
            continue
        if char == "[":
            start = index
            index += 1
            while index < len(text):
                if text[index] == "]":
                    if index + 1 < len(text) and text[index + 1] == "]":
                        index += 2
                        continue
                    index += 1
                    break
                index += 1
            tokens.append(("identifier", text[start:index].upper()))
            continue
        if char.isalpha() or char in "_@#$":
            start = index
            index += 1
            while index < len(text) and (text[index].isalnum() or text[index] in "_@#$"):
                index += 1
            tokens.append(("word", text[start:index].upper()))
            continue
        if char.isdigit():
            start = index
            index += 1
            while index < len(text) and (text[index].isalnum() or text[index] in ".xX"):
                index += 1
            tokens.append(("number", text[start:index].upper()))
            continue
        if char == ";" and ignore_statement_terminators:
            index += 1
            continue
        if text[index : index + 2] in {"<=", ">=", "<>", "!=", "!<", "!>", "+=", "-=", "*=", "/=", "%="}:
            tokens.append(("symbol", text[index : index + 2]))
            index += 2
            continue
        tokens.append(("symbol", char))
        index += 1
    return tokens


def _sql_code_tokens(sql_text: str, *, ignore_statement_terminators: bool = False) -> List[tuple[str, str]]:
    return _sql_contract_tokens(
        sql_text,
        include_comments=False,
        ignore_statement_terminators=ignore_statement_terminators,
    )


def _sql_comment_tokens(sql_text: str) -> List[str]:
    return [
        value
        for kind, value in _sql_contract_tokens(sql_text, include_comments=True)
        if kind == "comment"
    ]


def _contains_token_sequence(haystack: Sequence[tuple[str, str]], needle: Sequence[tuple[str, str]]) -> bool:
    if not needle or len(needle) > len(haystack):
        return False
    limit = len(haystack) - len(needle) + 1
    return any(list(haystack[index : index + len(needle)]) == list(needle) for index in range(limit))


def _meaningful_sql_fragment_tokens(sql_text: str) -> List[tuple[str, str]]:
    tokens = _sql_code_tokens(sql_text, ignore_statement_terminators=True)
    structural_keywords = {"SELECT", "FROM", "WHERE", "JOIN", "INSERT", "UPDATE", "DELETE", "EXEC", "EXECUTE"}
    significant = [
        value
        for kind, value in tokens
        if kind in {"identifier", "word", "number"}
        and value not in structural_keywords | {"INNER", "LEFT", "OUTER", "AS", "ON"}
    ]
    has_structure = any(value in structural_keywords for _, value in tokens)
    return tokens if len(tokens) >= 2 and has_structure and significant else []


def _source_correlates_to_candidate(
    item: Dict[str, Any],
    source_text: str,
    candidate_sql: str,
) -> tuple[bool, str]:
    candidate_name = _extract_sp_procedure_name(candidate_sql)
    source_name = _extract_sp_procedure_name(source_text)
    kind = str(item.get("kind") or "")
    role = str(item.get("evidence_role") or "")
    source_tokens = _meaningful_sql_fragment_tokens(source_text)
    candidate_tokens = _sql_code_tokens(candidate_sql, ignore_statement_terminators=True)

    if kind == "pasted_sql" and role == "body_fragment":
        return (
            bool(source_tokens and _contains_token_sequence(candidate_tokens, source_tokens)),
            "body_fragment",
        )
    if source_name and candidate_name and source_name == candidate_name:
        return True, "same_procedure_identity"
    source_statement_fingerprints = {
        unit["fingerprint"] for unit in _sql_traceability_units(source_text)
    }
    candidate_statement_fingerprints = {
        unit["fingerprint"] for unit in _sql_traceability_units(candidate_sql)
    }
    if source_statement_fingerprints & candidate_statement_fingerprints:
        return True, "source_statement_preserved"
    if source_tokens and _contains_token_sequence(candidate_tokens, source_tokens):
        return True, "source_sql_preserved_verbatim"

    provenance = item.get("candidate_provenance")
    if not isinstance(provenance, Mapping):
        return False, "candidate_provenance_missing"
    target_name = _normalized_sp_object_name(provenance.get("target_procedure"))
    if not candidate_name or target_name != candidate_name:
        return False, "candidate_provenance_target_mismatch"
    fragments = provenance.get("preserved_fragments")
    if not isinstance(fragments, (list, tuple)) or not fragments:
        return False, "candidate_provenance_fragments_missing"
    source_all_tokens = _sql_code_tokens(source_text, ignore_statement_terminators=True)
    for fragment in fragments:
        fragment_tokens = _meaningful_sql_fragment_tokens(str(fragment or ""))
        if not fragment_tokens:
            return False, "candidate_provenance_fragment_too_weak"
        if not _contains_token_sequence(source_all_tokens, fragment_tokens):
            return False, "candidate_provenance_fragment_missing_from_source"
        if not _contains_token_sequence(candidate_tokens, fragment_tokens):
            return False, "candidate_provenance_fragment_missing_from_candidate"
    return True, "explicit_preserved_fragments"


_SQL_TRACEABLE_STATEMENT_STARTS = {
    "DECLARE",
    "DELETE",
    "EXEC",
    "EXECUTE",
    "IF",
    "INSERT",
    "MERGE",
    "PRINT",
    "RAISERROR",
    "RETURN",
    "SELECT",
    "SET",
    "THROW",
    "TRUNCATE",
    "UPDATE",
    "WHILE",
}
def _extract_sp_body_or_sql_fragment(sql_text: str) -> str:
    source = str(sql_text or "")
    searchable = _mask_sql_comments_and_strings(source, mask_strings=True)
    match = re.search(
        r"(?:CREATE\s+(?:OR\s+ALTER\s+)?|ALTER\s+)PROCEDURE\s+"
        r"(?:\[[^\]]+\]|[A-Z0-9_]+)(?:\s*\.\s*(?:\[[^\]]+\]|[A-Z0-9_]+))?",
        searchable,
        flags=re.IGNORECASE,
    )
    if not match:
        return source
    depth = 0
    index = match.end()
    while index < len(searchable):
        char = searchable[index]
        if char == "(":
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1
        elif depth == 0 and searchable[index : index + 2].upper() == "AS":
            before = searchable[index - 1] if index > 0 else " "
            after = searchable[index + 2] if index + 2 < len(searchable) else " "
            if not (before.isalnum() or before in "_@") and not (
                after.isalnum() or after == "_"
            ):
                return source[index + 2 :]
        index += 1
    return source


def _trim_sql_unit_tokens(tokens: Sequence[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    result = list(tokens)
    while result and result[-1] == ("symbol", ";"):
        result.pop()
    return tuple(result)


def _sql_traceability_units(sql_text: str) -> List[Dict[str, Any]]:
    """Extract executable units while treating only the procedure envelope as generated structure."""
    tokens = _sql_code_tokens(
        _extract_sp_body_or_sql_fragment(sql_text),
        ignore_statement_terminators=False,
    )
    units: List[Dict[str, Any]] = []
    index = 0
    while index < len(tokens):
        kind, value = tokens[index]
        if kind != "word" or value not in _SQL_TRACEABLE_STATEMENT_STARTS:
            index += 1
            continue

        start = index
        statement_kind = value
        paren_depth = 0
        case_depth = 0
        index += 1
        while index < len(tokens):
            token_kind, token_value = tokens[index]
            if token_kind == "symbol":
                if token_value == "(":
                    paren_depth += 1
                elif token_value == ")" and paren_depth > 0:
                    paren_depth -= 1
                elif token_value == ";" and paren_depth == 0 and case_depth == 0:
                    index += 1
                    break
            elif token_kind == "word":
                if token_value == "CASE":
                    case_depth += 1
                elif token_value == "END" and case_depth > 0:
                    case_depth -= 1
                elif paren_depth == 0 and case_depth == 0:
                    if statement_kind in {"IF", "WHILE"} and token_value == "BEGIN":
                        break
                    if token_value in {"END", "ELSE"}:
                        break
                    if token_value in _SQL_TRACEABLE_STATEMENT_STARTS:
                        insert_select = statement_kind == "INSERT" and token_value == "SELECT"
                        merge_action = statement_kind == "MERGE" and token_value in {
                            "DELETE",
                            "INSERT",
                            "UPDATE",
                        }
                        update_set = statement_kind == "UPDATE" and token_value == "SET"
                        if not (insert_select or merge_action or update_set):
                            break
            index += 1

        unit_tokens = _trim_sql_unit_tokens(tokens[start:index])
        if unit_tokens:
            units.append(
                {
                    "kind": statement_kind,
                    "tokens": unit_tokens,
                    "fingerprint": hashlib.sha256(
                        json.dumps(
                            unit_tokens,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest(),
                    "preview": " ".join(token_value for _, token_value in unit_tokens)[:240],
                    "start_index": start,
                    "end_index": index,
                }
            )
        if index == start:
            index += 1

    consumed_indexes = {
        token_index
        for unit in units
        for token_index in range(unit["start_index"], unit["end_index"])
    }
    residual_start = -1
    residual_tokens: List[tuple[str, str]] = []

    def append_residual(end_index: int) -> None:
        nonlocal residual_start, residual_tokens
        unit_tokens = _trim_sql_unit_tokens(residual_tokens)
        if unit_tokens:
            units.append(
                {
                    "kind": "RESIDUAL",
                    "tokens": unit_tokens,
                    "fingerprint": hashlib.sha256(
                        json.dumps(
                            unit_tokens,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest(),
                    "preview": " ".join(token_value for _, token_value in unit_tokens)[:240],
                    "start_index": residual_start,
                    "end_index": end_index,
                }
            )
        residual_start = -1
        residual_tokens = []

    for token_index, token in enumerate(tokens):
        if token_index in consumed_indexes:
            append_residual(token_index)
            continue
        token_kind, token_value = token
        structural = token == ("symbol", ";") or (
            token_kind == "word" and token_value in {"BEGIN", "END"}
        )
        next_token = tokens[token_index + 1] if token_index + 1 < len(tokens) else ("", "")
        structural_qualifier = (
            token_kind == "word"
            and token_value in {"BEGIN", "END"}
            and next_token[0] == "word"
            and next_token[1] in {"CATCH", "DISTRIBUTED", "TRAN", "TRANSACTION", "TRY"}
            and token_index + 1 not in consumed_indexes
        )
        if structural and not structural_qualifier:
            append_residual(token_index)
            continue
        if residual_start < 0:
            residual_start = token_index
        residual_tokens.append(token)
    append_residual(len(tokens))
    units.sort(key=lambda unit: unit["start_index"])
    return units


def _is_generated_wrapper_unit(unit: Dict[str, Any]) -> bool:
    tokens = list(unit.get("tokens") or [])
    values = [value for _, value in tokens]
    return values == ["SET", "NOCOUNT", "ON"]


def _sql_hierarchical_trace(sql_text: str) -> List[Dict[str, Any]]:
    """Bind executable and structural units to scope, arm, and deterministic order."""
    body = _extract_sp_body_or_sql_fragment(sql_text)
    has_procedure_envelope = bool(_extract_sp_procedure_name(sql_text))
    tokens = _sql_code_tokens(body, ignore_statement_terminators=False)
    units = _sql_traceability_units(sql_text)
    units_by_start = {unit["start_index"]: unit for unit in units}
    trace: List[Dict[str, Any]] = []
    event_order_by_path: Dict[tuple[tuple[str, int, str], ...], int] = {}
    generated_nocount_consumed = False
    nonwrapper_event_seen = False

    def skip_terminators(index: int) -> int:
        while index < len(tokens) and tokens[index] == ("symbol", ";"):
            index += 1
        return index

    def token_values(start: int, end: int) -> tuple[tuple[str, str], ...]:
        return _trim_sql_unit_tokens(tokens[start:end])

    def structural_unit(
        kind: str,
        start: int,
        end: int,
        preview: str,
    ) -> Dict[str, Any]:
        unit_tokens = token_values(start, end)
        fingerprint_payload: Any = unit_tokens or (("structure", kind),)
        return {
            "kind": kind,
            "tokens": unit_tokens,
            "fingerprint": hashlib.sha256(
                json.dumps(
                    fingerprint_payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            "preview": preview,
            "start_index": start,
            "end_index": end,
        }

    def is_word(index: int, value: str) -> bool:
        return index < len(tokens) and tokens[index] == ("word", value)

    def is_generic_begin(index: int) -> bool:
        if not is_word(index, "BEGIN"):
            return False
        next_value = tokens[index + 1][1] if index + 1 < len(tokens) else ""
        return next_value not in {
            "CATCH",
            "DISTRIBUTED",
            "TRAN",
            "TRANSACTION",
            "TRY",
        }

    def transaction_begin_end(index: int) -> int:
        unit = units_by_start.get(index)
        if unit and unit["end_index"] > index:
            return int(unit["end_index"])
        cursor = index + 1
        while cursor < len(tokens):
            if tokens[cursor] == ("symbol", ";"):
                return cursor + 1
            if (
                cursor > index + 1
                and tokens[cursor][0] == "word"
                and tokens[cursor][1]
                in _SQL_TRACEABLE_STATEMENT_STARTS
                | {"BEGIN", "COMMIT", "ROLLBACK", "SAVE"}
            ):
                break
            cursor += 1
        return cursor

    def add_unit(
        unit: Dict[str, Any],
        path: tuple[tuple[str, int, str], ...],
        *,
        generated_envelope: bool = False,
    ) -> Dict[str, Any]:
        nonlocal generated_nocount_consumed, nonwrapper_event_seen
        wrapper = bool(
            _is_generated_wrapper_unit(unit)
            and has_procedure_envelope
            and not path
            and not generated_nocount_consumed
            and not nonwrapper_event_seen
        )
        if generated_envelope:
            order = 0
            order_kind = "envelope"
        elif wrapper:
            generated_nocount_consumed = True
            order = 0
            order_kind = "wrapper"
        else:
            nonwrapper_event_seen = True
            order = event_order_by_path.get(path, 0) + 1
            event_order_by_path[path] = order
            if unit["kind"] == "IF":
                order_kind = "branch"
            elif unit["kind"] in {
                "BEGIN_SCOPE",
                "END_SCOPE",
                "TRY_BEGIN",
                "TRY_END",
                "CATCH_BEGIN",
                "CATCH_END",
                "ELSE",
                "ARM_BEGIN",
                "ARM_END",
                "UNMATCHED_END",
            }:
                order_kind = "scope"
            else:
                order_kind = "statement"
        path_payload = [
            {
                "condition_fingerprint": condition_fingerprint,
                "branch_order": branch_order,
                "arm": arm,
            }
            for condition_fingerprint, branch_order, arm in path
        ]
        trace_key_payload = {
            "path": list(path),
            "order": order,
            "order_kind": order_kind,
            "kind": unit["kind"],
            "fingerprint": unit["fingerprint"],
        }
        item = {
            "kind": unit["kind"],
            "fingerprint": unit["fingerprint"],
            "preview": unit["preview"],
            "path": path_payload,
            "order_in_path": order,
            "order_kind": order_kind,
            "generated_wrapper": wrapper,
            "generated_envelope": generated_envelope,
            "trace_key": hashlib.sha256(
                json.dumps(
                    trace_key_payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        }
        trace.append(item)
        return item

    def parse_arm(
        index: int,
        path: tuple[tuple[str, int, str], ...],
    ) -> int:
        index = skip_terminators(index)
        if is_generic_begin(index):
            add_unit(
                structural_unit("ARM_BEGIN", index, index + 1, "BEGIN"),
                path,
            )
            index = parse_sequence(index + 1, path, stop_kind="END")
            if is_word(index, "END"):
                add_unit(
                    structural_unit("ARM_END", index, index + 1, "END"),
                    path,
                )
                index += 1
            return skip_terminators(index)
        return parse_one(index, path)

    def parse_try_catch(
        index: int,
        path: tuple[tuple[str, int, str], ...],
    ) -> int:
        try_item = add_unit(
            structural_unit("TRY_BEGIN", index, index + 2, "BEGIN TRY"),
            path,
        )
        try_path = path + (
            (try_item["fingerprint"], try_item["order_in_path"], "try"),
        )
        cursor = parse_sequence(index + 2, try_path, stop_kind="END_TRY")
        if is_word(cursor, "END") and is_word(cursor + 1, "TRY"):
            add_unit(
                structural_unit("TRY_END", cursor, cursor + 2, "END TRY"),
                path,
            )
            cursor = skip_terminators(cursor + 2)
        if is_word(cursor, "BEGIN") and is_word(cursor + 1, "CATCH"):
            add_unit(
                structural_unit(
                    "CATCH_BEGIN",
                    cursor,
                    cursor + 2,
                    "BEGIN CATCH",
                ),
                path,
            )
            catch_path = path + (
                (try_item["fingerprint"], try_item["order_in_path"], "catch"),
            )
            cursor = parse_sequence(
                cursor + 2,
                catch_path,
                stop_kind="END_CATCH",
            )
            if is_word(cursor, "END") and is_word(cursor + 1, "CATCH"):
                add_unit(
                    structural_unit(
                        "CATCH_END",
                        cursor,
                        cursor + 2,
                        "END CATCH",
                    ),
                    path,
                )
                cursor = skip_terminators(cursor + 2)
        return cursor

    def parse_one(
        index: int,
        path: tuple[tuple[str, int, str], ...],
    ) -> int:
        index = skip_terminators(index)
        if is_word(index, "BEGIN") and is_word(index + 1, "TRY"):
            return parse_try_catch(index, path)
        if is_word(index, "BEGIN") and (
            is_word(index + 1, "TRAN")
            or is_word(index + 1, "TRANSACTION")
            or (
                is_word(index + 1, "DISTRIBUTED")
                and (
                    is_word(index + 2, "TRAN")
                    or is_word(index + 2, "TRANSACTION")
                )
            )
        ):
            end = transaction_begin_end(index)
            unit = units_by_start.get(index) or structural_unit(
                "BEGIN_TRANSACTION",
                index,
                end,
                " ".join(value for _, value in tokens[index:end]),
            )
            add_unit(unit, path)
            return skip_terminators(end)
        if is_generic_begin(index):
            scope_item = add_unit(
                structural_unit("BEGIN_SCOPE", index, index + 1, "BEGIN"),
                path,
            )
            scope_path = path + (
                (
                    scope_item["fingerprint"],
                    scope_item["order_in_path"],
                    "scope",
                ),
            )
            cursor = parse_sequence(index + 1, scope_path, stop_kind="END")
            if is_word(cursor, "END"):
                add_unit(
                    structural_unit("END_SCOPE", cursor, cursor + 1, "END"),
                    path,
                )
                cursor += 1
            return skip_terminators(cursor)
        unit = units_by_start.get(index)
        if not unit:
            return min(index + 1, len(tokens))
        if unit["kind"] not in {"IF", "WHILE"}:
            add_unit(unit, path)
            return skip_terminators(unit["end_index"])

        control_item = add_unit(unit, path)
        branch_order = control_item["order_in_path"]
        if unit["kind"] == "WHILE":
            return parse_arm(
                unit["end_index"],
                path + ((unit["fingerprint"], branch_order, "loop"),),
            )
        index = parse_arm(
            unit["end_index"],
            path + ((unit["fingerprint"], branch_order, "then"),),
        )
        index = skip_terminators(index)
        if is_word(index, "ELSE"):
            add_unit(
                structural_unit("ELSE", index, index + 1, "ELSE"),
                path,
            )
            index = parse_arm(
                index + 1,
                path + ((unit["fingerprint"], branch_order, "else"),),
            )
        return skip_terminators(index)

    def parse_sequence(
        index: int,
        path: tuple[tuple[str, int, str], ...],
        *,
        stop_kind: str | None,
    ) -> int:
        while index < len(tokens):
            index = skip_terminators(index)
            if index >= len(tokens):
                break
            if stop_kind == "END" and is_word(index, "END") and not (
                is_word(index + 1, "TRY") or is_word(index + 1, "CATCH")
            ):
                break
            if stop_kind == "END_TRY" and is_word(index, "END") and is_word(
                index + 1, "TRY"
            ):
                break
            if stop_kind == "END_CATCH" and is_word(index, "END") and is_word(
                index + 1, "CATCH"
            ):
                break
            if is_word(index, "ELSE"):
                break
            if is_word(index, "END"):
                end = index + 1
                if is_word(end, "TRY") or is_word(end, "CATCH"):
                    end += 1
                add_unit(
                    structural_unit(
                        "UNMATCHED_END",
                        index,
                        end,
                        " ".join(value for _, value in tokens[index:end]),
                    ),
                    path,
                )
                index = end
                continue
            next_index = parse_one(index, path)
            index = next_index if next_index > index else index + 1
        return index

    start = skip_terminators(0)
    if has_procedure_envelope and is_generic_begin(start):
        add_unit(
            structural_unit(
                "PROCEDURE_BEGIN_SCOPE",
                start,
                start + 1,
                "BEGIN",
            ),
            tuple(),
            generated_envelope=True,
        )
        end = parse_sequence(start + 1, tuple(), stop_kind="END")
        if is_word(end, "END"):
            add_unit(
                structural_unit(
                    "PROCEDURE_END_SCOPE",
                    end,
                    end + 1,
                    "END",
                ),
                tuple(),
                generated_envelope=True,
            )
            end += 1
        parse_sequence(end, tuple(), stop_kind=None)
    else:
        parse_sequence(0, tuple(), stop_kind=None)
    return trace


def _canonical_nonwrapper_trace_payload(sql_text: str) -> Dict[str, Any]:
    return {
        "schema_version": "kh.pb.nonwrapper-trace.v2",
        "trace_keys": [
            item["trace_key"]
            for item in _sql_hierarchical_trace(sql_text)
            if not item["generated_wrapper"]
        ],
    }


def _canonical_nonwrapper_trace_sha256(sql_text: str) -> str:
    canonical_json = json.dumps(
        _canonical_nonwrapper_trace_payload(sql_text),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _candidate_body_traceability(
    candidate_sql: str,
    source_authorities: Sequence[Dict[str, Any]],
    branch_contract_authorities: Sequence[Dict[str, Any]] | None = None,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    candidate_trace = _sql_hierarchical_trace(candidate_sql)

    def trace_key_counts(
        trace_items: Sequence[Dict[str, Any]],
        *,
        include_envelope: bool,
    ) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for trace_item in trace_items:
            if trace_item["generated_wrapper"]:
                continue
            if trace_item.get("generated_envelope") and not include_envelope:
                continue
            trace_key = trace_item["trace_key"]
            counts[trace_key] = counts.get(trace_key, 0) + 1
        return counts

    candidate_full_trace_key_counts = trace_key_counts(
        candidate_trace,
        include_envelope=True,
    )
    candidate_body_trace_key_counts = trace_key_counts(
        candidate_trace,
        include_envelope=False,
    )

    authorities: List[Dict[str, Any]] = []
    for authority in source_authorities:
        authority_text = str(authority.get("text") or "")
        authority_has_envelope = bool(_extract_sp_procedure_name(authority_text))
        authority_trace_key_counts = trace_key_counts(
            _sql_hierarchical_trace(authority_text),
            include_envelope=authority_has_envelope,
        )
        expected_trace_key_counts = (
            candidate_full_trace_key_counts
            if authority_has_envelope
            else candidate_body_trace_key_counts
        )
        if authority_trace_key_counts:
            authorities.append(
                {
                    "authority_id": str(authority.get("authority_id") or "source"),
                    "authority_kind": "source_artifact",
                    "coverage": "source_statement",
                    "trace_key_counts": authority_trace_key_counts,
                    "expected_trace_key_counts": expected_trace_key_counts,
                    "covers_envelope": authority_has_envelope,
                }
            )
    for authority in branch_contract_authorities or []:
        trace_key_counts = dict(authority.get("trace_key_counts") or {})
        authority_kind = str(
            authority.get("authority_kind") or "branch_contract"
        )
        if trace_key_counts:
            covers_envelope = authority_kind == "composite_contract"
            authorities.append(
                {
                    "authority_id": str(
                        authority.get("authority_id") or "branch_contract"
                    ),
                    "authority_kind": authority_kind,
                    "coverage": authority_kind,
                    "trace_key_counts": trace_key_counts,
                    "expected_trace_key_counts": (
                        candidate_full_trace_key_counts
                        if covers_envelope
                        else candidate_body_trace_key_counts
                    ),
                    "covers_envelope": covers_envelope,
                }
            )

    def authority_coverage_count(authority: Dict[str, Any]) -> int:
        counts = authority["trace_key_counts"]
        expected_counts = authority["expected_trace_key_counts"]
        return sum(
            min(required, int(counts.get(trace_key, 0)))
            for trace_key, required in expected_counts.items()
        )

    matching_authorities = [
        authority
        for authority in authorities
        if authority["trace_key_counts"]
        == authority["expected_trace_key_counts"]
    ]
    authority_priority = {
        "composite_contract": 0,
        "branch_contract": 1,
        "source_artifact": 2,
    }
    selected_authority = min(
        matching_authorities,
        key=lambda authority: authority_priority.get(
            str(authority.get("authority_kind") or ""),
            99,
        ),
        default=None,
    )
    authority_summaries = [
        {
            "authority_id": authority["authority_id"],
            "authority_kind": authority["authority_kind"],
            "covered_event_count": authority_coverage_count(authority),
            "required_event_count": sum(
                authority["expected_trace_key_counts"].values()
            ),
            "authority_event_count": sum(authority["trace_key_counts"].values()),
        }
        for authority in authorities
    ]
    trace: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []
    executable_ordinal = 0
    if candidate_body_trace_key_counts and selected_authority is None:
        issues.append(
            {
                "code": "candidate_body_not_covered_by_single_authority",
                "severity": "error",
                "message": (
                    "One independently SHA-256-bound body authority must cover the candidate's complete "
                    "non-wrapper executable event stream and branch topology. Independent source and branch "
                    "artifacts are not pooled to authorize disjoint pieces."
                ),
                "authority_coverage": authority_summaries,
            }
        )
    for unit in candidate_trace:
        wrapper = bool(unit["generated_wrapper"])
        envelope = bool(unit.get("generated_envelope"))
        generated_envelope = bool(
            envelope
            and (
                selected_authority is None
                or not bool(selected_authority.get("covers_envelope"))
            )
        )
        if wrapper or generated_envelope:
            ordinal = 0
        else:
            executable_ordinal += 1
            ordinal = executable_ordinal
        covered = wrapper or generated_envelope or selected_authority is not None
        coverage = (
            "generated_wrapper"
            if wrapper
            else "generated_envelope"
            if generated_envelope
            else str(selected_authority["coverage"])
            if selected_authority is not None
            else "missing"
        )
        trace.append(
            {
                "ordinal": ordinal,
                "kind": unit["kind"],
                "fingerprint": unit["fingerprint"],
                "trace_key": unit["trace_key"],
                "branch_path": unit["path"],
                "order_kind": unit["order_kind"],
                "order_in_path": unit["order_in_path"],
                "coverage": coverage,
                "authority_id": (
                    str(selected_authority["authority_id"])
                    if selected_authority is not None
                    and not wrapper
                    and not generated_envelope
                    else ""
                ),
                "authority_kind": (
                    str(selected_authority["authority_kind"])
                    if selected_authority is not None
                    and not wrapper
                    and not generated_envelope
                    else "generated_wrapper"
                    if wrapper
                    else "generated_envelope"
                    if generated_envelope
                    else ""
                ),
                "preview": unit["preview"],
            }
        )
        if covered:
            continue
        issues.append(
            {
                "code": "candidate_body_statement_not_covered_by_source",
                "severity": "error",
                "message": (
                    "Every non-wrapper executable candidate event must be covered by the same independently "
                    "bound source or complete branch authority. Smaller or disjoint fragments cannot collectively "
                    "authorize candidate behavior."
                ),
                "ordinal": ordinal,
                "statement_kind": unit["kind"],
                "statement_fingerprint": unit["fingerprint"],
                "statement_trace_key": unit["trace_key"],
                "branch_path": unit["path"],
                "order_in_path": unit["order_in_path"],
                "statement_preview": unit["preview"],
            }
        )
    return trace, issues


def _existing_sp_cleanup_preservation_issues(
    original_sql: str,
    candidate_sql: str,
) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    original_name = _extract_sp_procedure_name(original_sql)
    candidate_name = _extract_sp_procedure_name(candidate_sql)
    if not original_name or not candidate_name or original_name != candidate_name:
        issues.append(
            {
                "code": "existing_sp_identity_changed",
                "severity": "error",
                "message": "Existing-SP cleanup must preserve the exact procedure identity.",
                "original_procedure": original_name,
                "candidate_procedure": candidate_name,
            }
        )
    if _sql_comment_tokens(original_sql) != _sql_comment_tokens(candidate_sql):
        issues.append(
            {
                "code": "existing_sp_comments_changed",
                "severity": "error",
                "message": "Formatting-only cleanup must preserve every original SQL comment payload and order.",
            }
        )
    elif _sql_contract_tokens(
        original_sql,
        include_comments=True,
    ) != _sql_contract_tokens(candidate_sql, include_comments=True):
        issues.append(
            {
                "code": "existing_sp_comment_binding_changed",
                "severity": "error",
                "message": (
                    "Formatting-only cleanup must preserve each business comment at the same relative "
                    "executable-token position. The ordinary SSMS object preamble remains valid when its "
                    "comment and surrounding executable order are unchanged."
                ),
            }
        )
    if _sql_code_tokens(original_sql) != _sql_code_tokens(candidate_sql):
        issues.append(
            {
                "code": "existing_sp_body_or_statement_changed",
                "severity": "error",
                "message": (
                    "Formatting-only cleanup may change whitespace and keyword/identifier case only; "
                    "procedure statements, operators, literals, terminators, and body tokens must remain unchanged."
                ),
            }
        )
    return issues


def _source_definition_text(item: Dict[str, Any]) -> tuple[str, str]:
    text = str(item.get("definition_text") or "")
    path = str(
        item.get("resolved_path")
        or item.get("definition_path")
        or item.get("path")
        or ""
    ).strip()
    if not text and path:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError:
            return "", "existing_sp_definition_unreadable"
    if not text:
        return "", "existing_sp_definition_missing"
    expected_hash = str(item.get("sha256") or item.get("definition_hash") or "").strip().lower()
    if expected_hash and hashlib.sha256(text.encode("utf-8")).hexdigest() != expected_hash:
        return "", "existing_sp_definition_hash_mismatch"
    return text, ""


def _bound_source_artifact_text(item: Dict[str, Any]) -> tuple[str, str, str]:
    """Return source text only when host evidence binds it to a locator and SHA-256."""
    if not bool(item.get("verified")):
        return "", "source_artifact_unverified", ""

    artifact_uri = str(item.get("artifact_uri") or "").strip()
    definition_path = str(
        item.get("resolved_path")
        or item.get("definition_path")
        or item.get("path")
        or ""
    ).strip()
    locator = artifact_uri or definition_path
    if not locator:
        return "", "source_artifact_locator_missing", ""
    if not definition_path:
        return "", "source_artifact_uri_unresolved", locator

    declared_text = str(item.get("definition_text") or item.get("artifact_text") or "")
    text = declared_text
    try:
        path_text = Path(definition_path).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return "", "source_artifact_unreadable", locator
    if declared_text and declared_text != path_text:
        return "", "source_artifact_text_path_mismatch", locator
    text = path_text

    if not text:
        return "", "source_artifact_text_missing", locator
    expected_hash = str(item.get("sha256") or item.get("definition_hash") or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        return "", "source_artifact_hash_missing_or_invalid", locator
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != expected_hash:
        return "", "source_artifact_hash_mismatch", locator
    return text, "", locator


def _sql_evidence_fingerprint(sql_text: str) -> str:
    tokens = _sql_code_tokens(sql_text, ignore_statement_terminators=True)
    canonical = json.dumps(tokens, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest() if tokens else ""


def _normalized_sp_object_name(value: Any) -> str:
    parts = [part.strip().strip("[]") for part in str(value or "").split(".")]
    return parts[-1].upper() if parts and parts[-1] else ""


def _normalized_sp_identity(value: Any) -> str:
    raw = str(value or "").strip()
    identifier = r"(?:\[[^\]\r\n]+\]|[A-Za-z_][A-Za-z0-9_#$@]*)"
    match = re.fullmatch(
        rf"\s*(?:(?P<schema>{identifier})\s*\.\s*)?(?P<procedure>{identifier})\s*",
        raw,
    )
    if not match:
        return ""
    schema = str(match.group("schema") or "DBO").strip().strip("[]").upper()
    procedure = str(match.group("procedure") or "").strip().strip("[]").upper()
    if not schema or not procedure:
        return ""
    return f"{schema}.{procedure}"


def _extract_sp_procedure_identity(sql_text: str) -> str:
    match = re.search(
        r"\b(?:CREATE\s+(?:OR\s+ALTER\s+)?|ALTER\s+)PROCEDURE\s+"
        r"(?P<identity>(?:\[[^\]]+\]|[A-Z0-9_]+)(?:\s*\.\s*(?:\[[^\]]+\]|[A-Z0-9_]+))?)",
        _strip_sql_literals_and_comments_for_pb_contract(sql_text),
        flags=re.IGNORECASE,
    )
    return _normalized_sp_identity(match.group("identity")) if match else ""


def _bound_caller_artifact_text(item: Dict[str, Any]) -> tuple[str, str]:
    declared_text = str(item.get("definition_text") or item.get("artifact_text") or "")
    path = str(
        item.get("resolved_path")
        or item.get("definition_path")
        or item.get("path")
        or ""
    ).strip()
    artifact_uri = str(item.get("artifact_uri") or "").strip()
    if not path and not artifact_uri:
        return "", "caller_artifact_locator_missing"
    if not path:
        return "", "caller_artifact_uri_unresolved"
    text = declared_text
    if path:
        try:
            path_text = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return "", "caller_artifact_unreadable"
        if declared_text and declared_text != path_text:
            return "", "caller_artifact_text_path_mismatch"
        text = path_text
    if not text:
        return "", "caller_artifact_missing"
    expected_hash = str(item.get("sha256") or item.get("definition_hash") or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        return "", "caller_artifact_hash_missing_or_invalid"
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != expected_hash:
        return "", "caller_artifact_hash_mismatch"
    return text, ""


def _bound_branch_contract_trace_keys(
    item: Dict[str, Any],
    candidate_target_procedure: str,
    candidate_sql: str,
) -> tuple[Dict[str, int], str, Dict[str, Any]]:
    artifact_text, artifact_error = _bound_caller_artifact_text(item)
    if artifact_error:
        return {}, artifact_error, {}
    if not bool(item.get("verified")):
        return {}, "branch_contract_unverified", {}
    try:
        payload = json.loads(artifact_text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}, "branch_contract_artifact_invalid", {}
    if not isinstance(payload, dict):
        return {}, "branch_contract_artifact_invalid", {}

    declared_target_raw = str(item.get("target_procedure") or "").strip()
    artifact_target_raw = str(payload.get("target_procedure") or "").strip()
    declared_target = _normalized_sp_identity(declared_target_raw)
    artifact_target = _normalized_sp_identity(artifact_target_raw)
    if not declared_target or not artifact_target:
        return {}, "branch_contract_target_procedure_invalid", {}
    if (
        declared_target != candidate_target_procedure
        or artifact_target != candidate_target_procedure
    ):
        return {}, "branch_contract_target_procedure_mismatch", {}

    contract_kind = str(item.get("kind") or "branch_contract")
    is_composite = contract_kind == "composite_contract"
    sql_field = "trace_sql" if is_composite else "branch_sql"
    declared_branch_sql = str(item.get(sql_field) or "").strip()
    artifact_branch_sql = str(payload.get(sql_field) or "").strip()
    if (
        not declared_branch_sql
        or not artifact_branch_sql
        or declared_branch_sql != artifact_branch_sql
    ):
        return (
            {},
            "composite_contract_sql_mismatch"
            if is_composite
            else "branch_contract_sql_mismatch",
            {},
        )

    authority_metadata: Dict[str, Any] = {}
    if is_composite:
        declared_lineage = item.get("source_lineage")
        artifact_lineage = payload.get("source_lineage")
        if (
            not isinstance(declared_lineage, list)
            or not declared_lineage
            or declared_lineage != artifact_lineage
            or not all(str(value or "").strip() for value in declared_lineage)
        ):
            return {}, "composite_contract_source_lineage_invalid", {}
        declared_trace_sha256 = str(item.get("trace_sha256") or "").strip().lower()
        artifact_trace_sha256 = str(payload.get("trace_sha256") or "").strip().lower()
        if (
            not re.fullmatch(r"[0-9a-f]{64}", declared_trace_sha256)
            or declared_trace_sha256 != artifact_trace_sha256
        ):
            return {}, "composite_contract_trace_sha256_invalid", {}
        computed_trace_sha256 = _canonical_nonwrapper_trace_sha256(declared_branch_sql)
        if computed_trace_sha256 != declared_trace_sha256:
            return {}, "composite_contract_trace_sha256_mismatch", {}
        candidate_trace_sha256 = _canonical_nonwrapper_trace_sha256(candidate_sql)
        if declared_trace_sha256 != candidate_trace_sha256:
            return {}, "composite_contract_candidate_trace_mismatch", {}
        authority_metadata = {
            "source_lineage": [str(value).strip().lower() for value in declared_lineage],
            "trace_sha256": declared_trace_sha256,
            "trace_schema_version": "kh.pb.nonwrapper-trace.v2",
        }

    branch_trace = _sql_hierarchical_trace(declared_branch_sql)
    if not branch_trace or (
        not is_composite and not any(item["kind"] == "IF" for item in branch_trace)
    ):
        return {}, "branch_contract_topology_invalid", {}

    trace_key_counts: Dict[str, int] = {}
    lineage_trace_keys: List[str] = []
    for trace_item in branch_trace:
        if trace_item["generated_wrapper"]:
            continue
        trace_key = trace_item["trace_key"]
        trace_key_counts[trace_key] = trace_key_counts.get(trace_key, 0) + 1
        if not trace_item.get("generated_envelope"):
            lineage_trace_keys.append(trace_key)
    authority_metadata["lineage_trace_keys"] = lineage_trace_keys
    return trace_key_counts, "", authority_metadata


def _csharp_preprocessor_active_positions(
    source_text: str,
    lexical_code_positions: Sequence[bool],
) -> tuple[List[bool], List[bool], bool]:
    """Mark directives and branches that cannot be proven active without build symbols."""
    text = str(source_text or "")
    active_positions = [True] * len(text)
    ambiguous_positions = [False] * len(text)
    stack: List[Dict[str, Any]] = []
    active = True
    ambiguous = False
    preprocessor_valid = True
    offset = 0

    def condition_value(expression: str) -> bool | None:
        normalized = re.sub(r"\s+", "", expression).lower()
        if normalized in {"true", "1"}:
            return True
        if normalized in {"false", "0"}:
            return False
        if normalized in {"!false", "!0"}:
            return True
        if normalized in {"!true", "!1"}:
            return False
        return None

    for line in text.splitlines(keepends=True):
        line_end = offset + len(line)
        directive = re.match(r"\s*#\s*(?P<name>[A-Za-z]+)(?P<body>.*)", line)
        hash_index = line.find("#")
        if (
            directive
            and (
                hash_index < 0
                or offset + hash_index >= len(lexical_code_positions)
                or not lexical_code_positions[offset + hash_index]
            )
        ):
            directive = None
        if directive:
            for index in range(offset, line_end):
                active_positions[index] = False
            name = directive.group("name").lower()
            body = directive.group("body").strip()
            if name == "if":
                parent_active = active
                parent_ambiguous = ambiguous
                selected = condition_value(body)
                unknown = selected is None
                active = bool(parent_active and selected is True and not parent_ambiguous)
                ambiguous = bool(
                    parent_ambiguous or (parent_active and unknown)
                )
                stack.append(
                    {
                        "parent_active": parent_active,
                        "parent_ambiguous": parent_ambiguous,
                        "branch_taken": selected is True,
                        "unknown": unknown,
                    }
                )
            elif name == "elif" and stack:
                frame = stack[-1]
                selected_value = condition_value(body)
                if frame["unknown"] or selected_value is None:
                    frame["unknown"] = True
                    active = False
                    ambiguous = bool(
                        frame["parent_ambiguous"] or frame["parent_active"]
                    )
                else:
                    selected = not frame["branch_taken"] and selected_value
                    frame["branch_taken"] = frame["branch_taken"] or selected
                    active = bool(
                        frame["parent_active"]
                        and selected
                        and not frame["parent_ambiguous"]
                    )
                    ambiguous = bool(frame["parent_ambiguous"])
            elif name == "else" and stack:
                frame = stack[-1]
                if frame["unknown"]:
                    active = False
                    ambiguous = bool(
                        frame["parent_ambiguous"] or frame["parent_active"]
                    )
                else:
                    selected = not frame["branch_taken"]
                    frame["branch_taken"] = True
                    active = bool(
                        frame["parent_active"]
                        and selected
                        and not frame["parent_ambiguous"]
                    )
                    ambiguous = bool(frame["parent_ambiguous"])
            elif name == "endif" and stack:
                frame = stack.pop()
                active = frame["parent_active"]
                ambiguous = frame["parent_ambiguous"]
            elif name in {"elif", "else", "endif"}:
                preprocessor_valid = False
        elif not active or ambiguous:
            for index in range(offset, line_end):
                active_positions[index] = False
                if ambiguous and lexical_code_positions[index]:
                    ambiguous_positions[index] = True
        offset = line_end
    if offset < len(text) and not active:
        for index in range(offset, len(text)):
            active_positions[index] = False
    return active_positions, ambiguous_positions, preprocessor_valid and not stack


def _mask_csharp_comments_with_code_positions(
    source_text: str,
) -> tuple[str, List[bool], List[bool], bool]:
    """Preserve indexes and string payloads while marking positions that are executable C# code."""
    text = str(source_text or "")
    masked = list(text)
    code_positions = [False] * len(text)
    state = "code"
    raw_delimiter = 0
    index = 0
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            if char == "/" and next_char == "/":
                masked[index] = masked[index + 1] = " "
                state = "line_comment"
                index += 2
                continue
            if char == "/" and next_char == "*":
                masked[index] = masked[index + 1] = " "
                state = "block_comment"
                index += 2
                continue
            if char == '"':
                quote_count = 1
                while index + quote_count < len(text) and text[index + quote_count] == '"':
                    quote_count += 1
                if quote_count >= 3:
                    state = "raw_string"
                    raw_delimiter = quote_count
                    index += quote_count
                    continue
                verbatim = index > 0 and text[index - 1] == "@"
                state = "verbatim_string" if verbatim else "string"
                index += 1
                continue
            if char == "'":
                state = "char"
                index += 1
                continue
            code_positions[index] = True
            index += 1
            continue
        if state == "line_comment":
            if char in "\r\n":
                state = "code"
                code_positions[index] = True
            else:
                masked[index] = " "
            index += 1
            continue
        if state == "block_comment":
            if char == "*" and next_char == "/":
                masked[index] = masked[index + 1] = " "
                state = "code"
                index += 2
            else:
                if char not in "\r\n":
                    masked[index] = " "
                index += 1
            continue
        if state == "string":
            if char == "\\":
                index += 2
            elif char == '"':
                state = "code"
                index += 1
            else:
                index += 1
            continue
        if state == "verbatim_string":
            if char == '"' and next_char == '"':
                index += 2
            elif char == '"':
                state = "code"
                index += 1
            else:
                index += 1
            continue
        if state == "raw_string":
            if char == '"':
                quote_count = 1
                while index + quote_count < len(text) and text[index + quote_count] == '"':
                    quote_count += 1
                if quote_count >= raw_delimiter:
                    state = "code"
                    index += raw_delimiter
                    continue
            index += 1
            continue
        if state == "char":
            if char == "\\":
                index += 2
            elif char == "'":
                state = "code"
                index += 1
            else:
                index += 1
    lexical_valid = state == "code"
    active_positions, ambiguous_positions, preprocessor_valid = _csharp_preprocessor_active_positions(
        text,
        code_positions,
    )
    for position, is_active in enumerate(active_positions):
        if is_active:
            continue
        code_positions[position] = False
        if masked[position] not in "\r\n":
            masked[position] = " "
    return (
        "".join(masked),
        code_positions,
        ambiguous_positions,
        lexical_valid and preprocessor_valid,
    )


def _csharp_delimiters_balanced(source_text: str, code_positions: Sequence[bool]) -> bool:
    stack: List[str] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    for index, char in enumerate(source_text):
        if index >= len(code_positions) or not code_positions[index]:
            continue
        if char in "([{":
            stack.append(char)
        elif char in pairs:
            if not stack or stack.pop() != pairs[char]:
                return False
    return not stack


def _csharp_code_tokens_with_positions(
    source_text: str,
    code_positions: Sequence[bool],
) -> List[Dict[str, Any]]:
    tokens: List[Dict[str, Any]] = []
    index = 0
    while index < len(source_text):
        if index >= len(code_positions) or not code_positions[index]:
            index += 1
            continue
        char = source_text[index]
        if char.isspace():
            index += 1
            continue
        identifier = re.match(r"[A-Za-z_][A-Za-z0-9_]*", source_text[index:])
        if identifier:
            value = identifier.group(0)
            tokens.append(
                {
                    "kind": "identifier",
                    "value": value,
                    "start": index,
                    "end": index + len(value),
                }
            )
            index += len(value)
            continue
        tokens.append(
            {
                "kind": "symbol",
                "value": char,
                "start": index,
                "end": index + 1,
            }
        )
        index += 1
    return tokens


def _csharp_interpolated_string_payload_spans(
    source_text: str,
    code_positions: Sequence[bool],
) -> List[tuple[int, int]]:
    """Return executable expression spans for active interpolated strings."""
    spans: List[tuple[int, int]] = []
    text = str(source_text or "")
    prefix_pattern = re.compile(r"(?:@\$+|\$+@?)\"+")
    for match in prefix_pattern.finditer(text):
        dollar_index = text.find("$", match.start(), match.end())
        if (
            dollar_index < 0
            or dollar_index >= len(code_positions)
            or not code_positions[dollar_index]
        ):
            continue
        quote_start = text.find('"', dollar_index, match.end())
        if quote_start < 0:
            continue
        quote_count = 1
        while (
            quote_start + quote_count < len(text)
            and text[quote_start + quote_count] == '"'
        ):
            quote_count += 1
        raw = quote_count >= 3
        delimiter = quote_count if raw else 1
        verbatim = "@" in text[match.start():quote_start]
        payload_start = quote_start + delimiter
        cursor = payload_start
        brace_depth = 0
        close_start = -1
        expression_start = -1
        expression_spans: List[tuple[int, int]] = []
        dollar_count = text[match.start():quote_start].count("$")
        while cursor < len(text):
            if raw and brace_depth == 0 and text.startswith('"' * delimiter, cursor):
                close_start = cursor
                break
            char = text[cursor]
            next_char = text[cursor + 1] if cursor + 1 < len(text) else ""
            if brace_depth > 0:
                if char == "/" and next_char == "/":
                    newline = text.find("\n", cursor + 2)
                    cursor = len(text) if newline < 0 else newline + 1
                    continue
                if char == "/" and next_char == "*":
                    comment_end = text.find("*/", cursor + 2)
                    cursor = len(text) if comment_end < 0 else comment_end + 2
                    continue
                if char == "'":
                    cursor += 1
                    while cursor < len(text):
                        if text[cursor] == "\\":
                            cursor += 2
                            continue
                        if text[cursor] == "'":
                            cursor += 1
                            break
                        cursor += 1
                    continue
                if char == "@" and next_char == '"':
                    cursor += 2
                    while cursor < len(text):
                        if text[cursor] == '"':
                            if cursor + 1 < len(text) and text[cursor + 1] == '"':
                                cursor += 2
                                continue
                            cursor += 1
                            break
                        cursor += 1
                    continue
                if char == '"':
                    nested_delimiter = 1
                    while (
                        cursor + nested_delimiter < len(text)
                        and text[cursor + nested_delimiter] == '"'
                    ):
                        nested_delimiter += 1
                    if nested_delimiter >= 3:
                        nested_end = text.find('"' * nested_delimiter, cursor + nested_delimiter)
                        cursor = len(text) if nested_end < 0 else nested_end + nested_delimiter
                        continue
                    cursor += 1
                    while cursor < len(text):
                        if text[cursor] == "\\":
                            cursor += 2
                            continue
                        if text[cursor] == '"':
                            cursor += 1
                            break
                        cursor += 1
                    continue
            if not raw and brace_depth == 0 and char == '"':
                if verbatim and next_char == '"':
                    cursor += 2
                    continue
                if not verbatim:
                    backslashes = 0
                    scan = cursor - 1
                    while scan >= 0 and text[scan] == "\\":
                        backslashes += 1
                        scan -= 1
                    if backslashes % 2:
                        cursor += 1
                        continue
                close_start = cursor
                break
            if char == "{" and next_char == "{" and brace_depth == 0:
                if raw and dollar_count > 1:
                    expression_start = cursor + dollar_count
                    brace_depth = 1
                    cursor += dollar_count
                    continue
                cursor += 2
                continue
            if char == "}" and next_char == "}" and brace_depth == 0:
                cursor += 2
                continue
            if char == "{":
                if brace_depth == 0:
                    expression_start = cursor + 1
                brace_depth += 1
            elif char == "}" and brace_depth > 0:
                brace_depth -= 1
                if brace_depth == 0 and expression_start >= 0:
                    expression_spans.append((expression_start, cursor))
                    expression_start = -1
            cursor += 1
        if close_start < 0:
            close_start = len(text)
        if expression_start >= 0:
            expression_spans.append((expression_start, close_start))
        spans.extend(expression_spans)
    return spans


def _csharp_invocation_code_positions(
    source_text: str,
    code_positions: Sequence[bool],
) -> List[bool]:
    """Expose interpolated payloads to call counting; ambiguity fails closed."""
    invocation_positions = list(code_positions)
    for start, end in _csharp_interpolated_string_payload_spans(
        source_text,
        code_positions,
    ):
        fragment = source_text[start:end]
        _, fragment_positions, _, fragment_valid = (
            _mask_csharp_comments_with_code_positions(fragment)
        )
        if not fragment_valid:
            fragment_positions = [True] * len(fragment)
        for offset, is_code in enumerate(fragment_positions):
            index = start + offset
            if is_code and 0 <= index < len(invocation_positions):
                invocation_positions[index] = True
    return invocation_positions


def _csharp_dbclient_call_sites(
    source_text: str,
    code_positions: Sequence[bool],
) -> List[Dict[str, Any]]:
    invocation_positions = _csharp_invocation_code_positions(
        source_text,
        code_positions,
    )
    tokens = _csharp_code_tokens_with_positions(source_text, invocation_positions)
    sites: List[Dict[str, Any]] = []

    def receiver_start(end_index: int) -> int:
        while end_index >= 0 and tokens[end_index]["value"] == "!":
            end_index -= 1
        if end_index < 0:
            return -1
        if tokens[end_index]["value"] == ")":
            depth = 1
            cursor = end_index - 1
            while cursor >= 0:
                value = tokens[cursor]["value"]
                if value == ")":
                    depth += 1
                elif value == "(":
                    depth -= 1
                    if depth == 0:
                        inner_start = receiver_start(end_index - 1)
                        if inner_start != cursor + 1:
                            return -1
                        return cursor
                cursor -= 1
            return -1
        if (
            tokens[end_index]["kind"] == "identifier"
            and tokens[end_index]["value"] == "dbClient"
        ):
            return end_index
        return -1

    for method_index, method in enumerate(tokens):
        if method["kind"] != "identifier" or method_index < 2:
            continue
        verbatim_identifier = (
            method_index >= 3 and tokens[method_index - 1]["value"] == "@"
        )
        dot_index = method_index - 2 if verbatim_identifier else method_index - 1
        if tokens[dot_index]["value"] != ".":
            continue
        access_start = dot_index
        if dot_index > 0 and tokens[dot_index - 1]["value"] == "?":
            access_start = dot_index - 1
        receiver_index = receiver_start(access_start - 1)
        if receiver_index < 0:
            continue
        next_index = method_index + 1
        if next_index < len(tokens) and tokens[next_index]["value"] == "<":
            generic_depth = 0
            while next_index < len(tokens):
                value = tokens[next_index]["value"]
                if value == "<":
                    generic_depth += 1
                elif value == ">":
                    generic_depth -= 1
                    if generic_depth == 0:
                        next_index += 1
                        break
                next_index += 1
            if generic_depth != 0:
                continue
        if next_index >= len(tokens) or tokens[next_index]["value"] != "(":
            continue
        sites.append(
            {
                "start": tokens[receiver_index]["start"],
                "method": method["value"],
                "open_index": tokens[next_index]["start"],
            }
        )
    return sites


def _find_csharp_matching_parenthesis(
    source_text: str,
    code_positions: Sequence[bool],
    open_index: int,
) -> int:
    depth = 0
    for index in range(open_index, len(source_text)):
        if not code_positions[index]:
            continue
        if source_text[index] == "(":
            depth += 1
        elif source_text[index] == ")":
            depth -= 1
            if depth == 0:
                return index
            if depth < 0:
                return -1
    return -1


def _split_csharp_top_level_arguments(
    source_text: str,
    code_positions: Sequence[bool],
    open_index: int,
    close_index: int,
) -> List[tuple[int, int]]:
    result: List[tuple[int, int]] = []
    start = open_index + 1
    paren_depth = 0
    bracket_depth = 0
    brace_depth = 0
    for index in range(start, close_index):
        if not code_positions[index]:
            continue
        char = source_text[index]
        if char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth -= 1
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth -= 1
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth -= 1
        elif (
            char == ","
            and paren_depth == 0
            and bracket_depth == 0
            and brace_depth == 0
        ):
            result.append((start, index))
            start = index + 1
        if paren_depth < 0 or bracket_depth < 0 or brace_depth < 0:
            return []
    if paren_depth or bracket_depth or brace_depth:
        return []
    result.append((start, close_index))
    return result


def _csharp_value_expression_tokens(
    source_text: str,
    code_positions: Sequence[bool],
    start: int,
    end: int,
) -> List[tuple[str, str]]:
    tokens: List[tuple[str, str]] = []
    index = start
    two_character_operators = {
        "=>",
        "??",
        "?.",
        "?[",
        "==",
        "!=",
        "<=",
        ">=",
        "&&",
        "||",
        "++",
        "--",
        "+=",
        "-=",
        "*=",
        "/=",
        "%=",
        "&=",
        "|=",
        "^=",
        "<<",
        ">>",
    }
    while index < end:
        char = source_text[index]
        if char.isspace():
            index += 1
            continue
        if index >= len(code_positions):
            return []
        if not code_positions[index]:
            literal_end = index + 1
            while literal_end < end and not code_positions[literal_end]:
                literal_end += 1
            literal = source_text[index:literal_end]
            if literal.strip():
                tokens.append(("literal", literal))
            index = literal_end
            continue
        if char in "@$":
            prefix_end = index
            while (
                prefix_end < end
                and source_text[prefix_end] in "@$"
                and code_positions[prefix_end]
            ):
                prefix_end += 1
            if (
                prefix_end < end
                and not code_positions[prefix_end]
                and source_text[prefix_end] in {'"', "'"}
            ):
                literal_end = prefix_end + 1
                while literal_end < end and not code_positions[literal_end]:
                    literal_end += 1
                tokens.append(("literal", source_text[index:literal_end]))
                index = literal_end
                continue
        identifier = re.match(r"[A-Za-z_][A-Za-z0-9_]*", source_text[index:end])
        if identifier:
            value = identifier.group(0)
            tokens.append(("identifier", value))
            index += len(value)
            continue
        number = re.match(
            r"(?:0[xX][0-9A-Fa-f_]+|0[bB][01_]+|(?:\d[\d_]*)(?:\.\d[\d_]*)?(?:[eE][+-]?\d[\d_]*)?)(?:[uUlLfFdDmM]+)?",
            source_text[index:end],
        )
        if number:
            value = number.group(0)
            tokens.append(("number", value))
            index += len(value)
            continue
        operator = source_text[index : index + 2]
        if operator in two_character_operators:
            tokens.append(("symbol", operator))
            index += 2
            continue
        tokens.append(("symbol", char))
        index += 1
    return tokens


def _is_supported_csharp_parameter_value(
    source_text: str,
    code_positions: Sequence[bool],
    start: int,
    end: int,
) -> bool:
    """Accept only the target-style scalar value expressions used by direct DbParameter calls."""
    tokens = _csharp_value_expression_tokens(source_text, code_positions, start, end)
    if not tokens:
        return False
    banned_identifiers = {
        "async",
        "await",
        "delegate",
        "from",
        "new",
        "select",
        "stackalloc",
        "with",
        "yield",
    }
    banned_symbols = {
        "=>",
        "{",
        "}",
        ";",
        "=",
        "+=",
        "-=",
        "*=",
        "/=",
        "%=",
        "&=",
        "|=",
        "^=",
        "++",
        "--",
        "&&",
        "||",
        "==",
        "!=",
        "<=",
        ">=",
        "<<",
        ">>",
        "?",
        ":",
    }
    if any(
        (kind == "identifier" and value.lower() in banned_identifiers)
        or (kind == "symbol" and value in banned_symbols)
        for kind, value in tokens
    ):
        return False

    position = 0

    def current() -> tuple[str, str] | None:
        return tokens[position] if position < len(tokens) else None

    def consume(value: str | None = None) -> tuple[str, str] | None:
        nonlocal position
        token = current()
        if token is None or (value is not None and token[1] != value):
            return None
        position += 1
        return token

    def starts_value(token: tuple[str, str] | None) -> bool:
        return bool(
            token
            and (
                token[0] in {"identifier", "literal", "number"}
                or token[1] in {"(", "+", "-", "!", "~"}
            )
        )

    def cast_close_index(open_position: int) -> int:
        index = open_position + 1
        saw_identifier = False
        while index < len(tokens):
            kind, value = tokens[index]
            if value == ")":
                if not saw_identifier or index + 1 >= len(tokens):
                    return -1
                return index if starts_value(tokens[index + 1]) else -1
            if kind == "identifier":
                saw_identifier = True
            elif value not in {".", "?", "[", "]"}:
                return -1
            index += 1
        return -1

    def parse_expression() -> bool:
        if not parse_unary_and_postfix():
            return False
        while current() and current()[1] == "??":
            consume("??")
            if not parse_unary_and_postfix():
                return False
        return True

    def parse_argument_list(close_symbol: str) -> bool:
        if current() and current()[1] == close_symbol:
            consume(close_symbol)
            return True
        while True:
            if not parse_expression():
                return False
            token = current()
            if token and token[1] == ",":
                consume(",")
                continue
            if token and token[1] == close_symbol:
                consume(close_symbol)
                return True
            return False

    def parse_unary_and_postfix() -> bool:
        token = current()
        if token and token[1] in {"+", "-", "!", "~"}:
            consume(token[1])
            return parse_unary_and_postfix()
        if token and token[1] == "(":
            cast_close = cast_close_index(position)
            if cast_close >= 0:
                consume("(")
                while position < cast_close:
                    consume()
                consume(")")
                if not parse_unary_and_postfix():
                    return False
            else:
                consume("(")
                if not parse_expression() or not consume(")"):
                    return False
        elif token and token[0] in {"identifier", "literal", "number"}:
            consume()
        else:
            return False

        while current():
            token = current()
            if token[1] in {".", "?."}:
                consume(token[1])
                member = consume()
                if not member or member[0] != "identifier":
                    return False
                continue
            if token[1] in {"[", "?["}:
                consume(token[1])
                if not parse_argument_list("]"):
                    return False
                continue
            if token[1] == "(":
                consume("(")
                if not parse_argument_list(")"):
                    return False
                continue
            break
        return True

    return parse_expression() and position == len(tokens)


def _is_plausible_csharp_return_type(return_type_text: str) -> bool:
    text = str(return_type_text or "").strip()
    if not text:
        return False
    tokens = [
        token
        for token in re.findall(
            r"::|[A-Za-z_][A-Za-z0-9_]*|[<>,.?\[\]()]",
            text,
        )
        if token
    ]
    if not tokens or "".join(tokens) != re.sub(r"\s+", "", text):
        return False
    word_tokens = [
        token.lower()
        for token in tokens
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token)
    ]
    if "void" in word_tokens:
        return len(tokens) == 1 and tokens[0].lower() == "void"
    reserved_non_types = {
        "as",
        "break",
        "case",
        "catch",
        "checked",
        "continue",
        "default",
        "delegate",
        "do",
        "else",
        "finally",
        "fixed",
        "for",
        "foreach",
        "goto",
        "if",
        "in",
        "is",
        "lock",
        "namespace",
        "operator",
        "out",
        "params",
        "ref",
        "return",
        "sizeof",
        "stackalloc",
        "switch",
        "throw",
        "try",
        "typeof",
        "unchecked",
        "unsafe",
        "using",
        "var",
        "while",
        "yield",
    }
    if any(token.lower() in reserved_non_types for token in tokens if token[0].isalpha()):
        return False

    position = 0

    def current() -> str:
        return tokens[position] if position < len(tokens) else ""

    def consume(value: str | None = None) -> str:
        nonlocal position
        token = current()
        if not token or (value is not None and token != value):
            return ""
        position += 1
        return token

    def identifier() -> bool:
        token = current()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token or ""):
            return False
        consume()
        return True

    def parse_named_type() -> bool:
        if current() == "global":
            consume("global")
            if not consume("::"):
                return False
        if not identifier():
            return False
        if current() == "<":
            if not parse_generic_arguments():
                return False
        while current() in {".", "::"}:
            consume()
            if not identifier():
                return False
            if current() == "<" and not parse_generic_arguments():
                return False
        return True

    def parse_generic_arguments() -> bool:
        if not consume("<") or not parse_type():
            return False
        while current() == ",":
            consume(",")
            if not parse_type():
                return False
        return bool(consume(">"))

    def parse_tuple_type() -> bool:
        if not consume("(") or not parse_type():
            return False
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", current() or ""):
            consume()
        count = 1
        while current() == ",":
            consume(",")
            if not parse_type():
                return False
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", current() or ""):
                consume()
            count += 1
        return count >= 2 and bool(consume(")"))

    def parse_type() -> bool:
        if current() == "(":
            if not parse_tuple_type():
                return False
        elif not parse_named_type():
            return False
        if current() == "?":
            consume("?")
        while current() == "[":
            consume("[")
            while current() == ",":
                consume(",")
            if not consume("]"):
                return False
        return True

    return parse_type() and position == len(tokens)


def _csharp_call_context_is_direct(
    source_text: str,
    code_positions: Sequence[bool],
    call_start: int,
) -> bool:
    active_text = "".join(
        char if index < len(code_positions) and code_positions[index] else " "
        for index, char in enumerate(source_text)
    )
    stack: List[Dict[str, str]] = []
    segment_start = 0
    control_names = {
        "catch",
        "checked",
        "do",
        "else",
        "finally",
        "fixed",
        "for",
        "foreach",
        "if",
        "lock",
        "switch",
        "try",
        "unchecked",
        "unsafe",
        "using",
        "while",
    }

    method_modifiers = {
        "abstract",
        "async",
        "extern",
        "internal",
        "new",
        "override",
        "partial",
        "private",
        "protected",
        "public",
        "sealed",
        "static",
        "unsafe",
        "virtual",
    }

    def classify_brace(segment: str) -> Dict[str, str]:
        compact = segment.strip()
        if re.search(r"=>\s*$", compact):
            return {"kind": "lambda", "name": ""}
        if re.search(r"\bdelegate(?:\s*\([^{};]*\))?\s*$", compact):
            return {"kind": "delegate", "name": ""}
        type_match = re.search(
            r"\b(?:class|struct|record(?:\s+(?:class|struct))?)\s+"
            r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b[^;{}]*$",
            compact,
        )
        if type_match:
            return {"kind": "type", "name": type_match.group("name")}
        if re.search(r"\bnamespace\b[^;{}]*$", compact):
            return {"kind": "namespace", "name": ""}
        if re.search(r"\b(?:get|set|init|add|remove)\s*$", compact):
            return {"kind": "accessor", "name": ""}
        method_header = re.sub(r"\s+where\s+[^{};]+$", "", compact).rstrip()
        parameter_open = -1
        if method_header.endswith(")"):
            depth = 0
            for cursor in range(len(method_header) - 1, -1, -1):
                char = method_header[cursor]
                if char == ")":
                    depth += 1
                elif char == "(":
                    depth -= 1
                    if depth == 0:
                        parameter_open = cursor
                        break
        before_parameters = (
            method_header[:parameter_open].rstrip()
            if parameter_open >= 0
            else ""
        )
        if before_parameters.endswith(">"):
            generic_depth = 0
            for cursor in range(len(before_parameters) - 1, -1, -1):
                char = before_parameters[cursor]
                if char == ">":
                    generic_depth += 1
                elif char == "<":
                    generic_depth -= 1
                    if generic_depth == 0:
                        before_parameters = before_parameters[:cursor].rstrip()
                        break
        method_name_match = re.search(
            r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)$",
            before_parameters,
        )
        if method_name_match:
            name = method_name_match.group("name")
            if name.lower() in control_names:
                return {"kind": "block", "name": name}
            nearest_type_name = next(
                (
                    context["name"]
                    for context in reversed(stack)
                    if context["kind"] == "type"
                ),
                "",
            )
            prefix = before_parameters[: method_name_match.start("name")].strip()
            prefix_without_attributes = prefix
            while True:
                leading_attribute = re.match(
                    r"^\s*\[[^\]]*\]\s*",
                    prefix_without_attributes,
                )
                if not leading_attribute:
                    break
                prefix_without_attributes = prefix_without_attributes[
                    leading_attribute.end() :
                ]
            return_type_text = prefix_without_attributes.strip()
            modifier_pattern = re.compile(
                r"^(?:" + "|".join(sorted(method_modifiers)) + r")\b\s*",
                flags=re.IGNORECASE,
            )
            while True:
                stripped = modifier_pattern.sub("", return_type_text, count=1)
                if stripped == return_type_text:
                    break
                return_type_text = stripped.lstrip()
            nonordinary = bool(
                re.search(r"\boperator\b", compact)
                or re.search(rf"~\s*{re.escape(name)}\s*\(", compact)
                or (nearest_type_name and name == nearest_type_name)
                or not _is_plausible_csharp_return_type(return_type_text)
            )
            return {
                "kind": "nonordinary_method" if nonordinary else "ordinary_method",
                "name": name,
            }
        return {"kind": "block", "name": ""}

    for index, char in enumerate(active_text[:call_start]):
        if char == "{":
            stack.append(classify_brace(active_text[segment_start:index]))
            segment_start = index + 1
        elif char == "}":
            if not stack:
                return False
            stack.pop()
            segment_start = index + 1
        elif char == ";":
            segment_start = index + 1

    statement_prefix = active_text[segment_start:call_start]
    if not re.fullmatch(r"\s*(?:return\s+)?", statement_prefix):
        return False
    if any(
        context["kind"]
        in {"lambda", "delegate", "accessor", "nonordinary_method"}
        for context in stack
    ):
        return False
    type_count = sum(context["kind"] == "type" for context in stack)
    method_count = sum(context["kind"] == "ordinary_method" for context in stack)
    if type_count < 1 or method_count != 1:
        return False
    return True


def _direct_csharp_dbparameter_name(
    source_text: str,
    code_positions: Sequence[bool],
    start: int,
    end: int,
) -> str:
    argument = source_text[start:end]
    match = re.fullmatch(
        r"\s*new\s+DbParameter\s*\((?P<body>.*)\)\s*",
        argument,
        flags=re.DOTALL,
    )
    if not match:
        return ""
    open_index = source_text.find("(", start, end)
    if open_index < 0 or not code_positions[open_index]:
        return ""
    close_index = _find_csharp_matching_parenthesis(
        source_text,
        code_positions,
        open_index,
    )
    if close_index < 0 or close_index >= end:
        return ""
    if source_text[close_index + 1 : end].strip():
        return ""
    constructor_arguments = _split_csharp_top_level_arguments(
        source_text,
        code_positions,
        open_index,
        close_index,
    )
    if len(constructor_arguments) != 2:
        return ""
    name_start, name_end = constructor_arguments[0]
    name_match = re.fullmatch(
        r'\s*"@(?P<parameter>[A-Za-z][A-Za-z0-9_]*)"\s*',
        source_text[name_start:name_end],
    )
    value_start, value_end = constructor_arguments[1]
    if (
        not name_match
        or not _is_supported_csharp_parameter_value(
            source_text,
            code_positions,
            value_start,
            value_end,
        )
    ):
        return ""
    return f"@{name_match.group('parameter').upper()}"


def _extract_csharp_sp_calls(artifact_text: str) -> List[Dict[str, Any]]:
    (
        without_comments,
        code_positions,
        ambiguous_positions,
        lexical_valid,
    ) = _mask_csharp_comments_with_code_positions(artifact_text)
    calls: List[Dict[str, Any]] = []
    if not lexical_valid or not _csharp_delimiters_balanced(
        without_comments,
        code_positions,
    ):
        return []
    if _csharp_dbclient_call_sites(str(artifact_text or ""), ambiguous_positions):
        return []
    active_sites = _csharp_dbclient_call_sites(without_comments, code_positions)
    if len(active_sites) != 1:
        return []
    supported_methods = {"GetDataSetFromSP", "ExecSPTrn", "ExecSP"}
    for site in active_sites:
        if site["method"] not in supported_methods:
            return []
        if not _csharp_call_context_is_direct(
            without_comments,
            code_positions,
            site["start"],
        ):
            return []
        open_index = int(site["open_index"])
        if open_index < 0 or not code_positions[open_index]:
            continue
        close_paren_index = _find_csharp_matching_parenthesis(
            without_comments,
            code_positions,
            open_index,
        )
        close_index = close_paren_index + 1 if close_paren_index >= 0 else -1
        if close_index < 0:
            continue
        terminator_index = close_index
        while terminator_index < len(without_comments) and (
            without_comments[terminator_index].isspace()
            or not code_positions[terminator_index]
        ):
            terminator_index += 1
        if terminator_index >= len(without_comments) or without_comments[terminator_index] != ";":
            continue

        arguments = _split_csharp_top_level_arguments(
            without_comments,
            code_positions,
            open_index,
            close_paren_index,
        )
        if not arguments:
            continue
        procedure_start, procedure_end = arguments[0]
        procedure_match = re.fullmatch(
            r'\s*"(?P<procedure>[^"\\\r\n]+)"\s*',
            without_comments[procedure_start:procedure_end],
        )
        if not procedure_match:
            continue
        parameters: List[str] = []
        direct_arguments_valid = True
        for parameter_start, parameter_end in arguments[1:]:
            parameter_name = _direct_csharp_dbparameter_name(
                without_comments,
                code_positions,
                parameter_start,
                parameter_end,
            )
            if not parameter_name:
                direct_arguments_valid = False
                break
            parameters.append(parameter_name)
        if not direct_arguments_valid:
            continue
        calls.append(
            {
                "target_procedure": _normalized_sp_identity(
                    procedure_match.group("procedure")
                ),
                "parameters": parameters,
            }
        )
    return calls


def _caller_contract_is_present_in_artifact(
    artifact_text: str,
    contract: List[Dict[str, Any]],
    *,
    kind: str,
    caller_id: str = "",
    target_procedure: str = "",
) -> bool:
    if not contract:
        return False
    if kind == "csharp_call":
        expected_target = _normalized_sp_identity(target_procedure)
        expected_parameters = [item["name"] for item in contract]
        return any(
            call["target_procedure"] == expected_target
            and call["parameters"] == expected_parameters
            for call in _extract_csharp_sp_calls(artifact_text)
        )
    try:
        payload = json.loads(artifact_text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    if caller_id and str(payload.get("caller_id") or "").strip() != caller_id:
        return False
    if _normalized_sp_identity(payload.get("target_procedure")) != _normalized_sp_identity(
        target_procedure
    ):
        return False
    artifact_contract = _normalize_caller_parameter_contract(
        payload.get("parameter_contract") or payload.get("parameters")
    )
    fields = ["name", "type_spec", "default_present", "default", "output", "readonly"]
    return len(artifact_contract) == len(contract) and all(
        all(artifact_contract[index].get(field) == contract[index].get(field) for field in fields)
        for index in range(len(contract))
    )


def _csharp_contract_unproven_metadata(contract: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    unproven: List[Dict[str, Any]] = []
    for parameter in contract:
        fields = []
        if parameter.get("type_specified"):
            fields.append("type_spec")
        if parameter.get("default_specified"):
            fields.append("default")
        if parameter.get("output_specified"):
            fields.append("output")
        if parameter.get("readonly_specified"):
            fields.append("readonly")
        if fields:
            unproven.append({"parameter": parameter.get("name"), "fields": fields})
    return unproven


def _external_caller_artifact_caller_id(artifact_text: str) -> str:
    try:
        payload = json.loads(artifact_text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return ""
    return str(payload.get("caller_id") or "").strip() if isinstance(payload, dict) else ""


def _external_caller_artifact_target_procedure(artifact_text: str) -> str:
    return _normalized_sp_identity(
        _external_caller_artifact_target_procedure_raw(artifact_text)
    )


def _external_caller_artifact_target_procedure_raw(artifact_text: str) -> str:
    try:
        payload = json.loads(artifact_text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("target_procedure") or "").strip()


def _source_metadata_values(items: List[Dict[str, Any]]) -> tuple[set[str], set[str]]:
    authors: set[str] = set()
    dates: set[str] = set()
    for item in items:
        kind = str(item.get("kind") or "")
        if kind not in {"existing_sp", "pasted_sql", "pb_srd_sql"}:
            continue
        definition, error = _source_definition_text(item)
        if error or not definition:
            continue
        match = SP_METADATA_HEADER_PATTERN.search(definition)
        if not match:
            continue
        author = str(match.group("author") or "").strip()
        create_date = str(match.group("create_date") or "").strip()
        if author:
            authors.add(author)
        if create_date:
            dates.add(create_date)
    return authors, dates


def verify_pb_migration_sp_generation_contract(
    sql_text: str,
    *,
    source_evidence: Any = None,
    allow_inferred_draft: bool = False,
    profile_evidence: Any = None,
    operation: str = "new_generation",
    original_sp_text: str | None = None,
    caller_parameter_contract: Any = None,
    external_caller_contract: Any = None,
) -> HarnessResult:
    """Check that generated SELECT/SAVE SP work is evidence-gated before it is presented as migration output."""
    sql = str(sql_text or "")
    issues: List[Dict[str, Any]] = []
    allowed_operations = {
        "new_generation",
        "pb_srd_generation",
        "existing_sp_cleanup",
        "approved_inferred_draft",
    }
    effective_operation = "approved_inferred_draft" if allow_inferred_draft else str(operation or "new_generation")
    profile_context, profile_issues = _consume_profile_evidence(profile_evidence, "sql")
    issues.extend(profile_issues)
    if not profile_issues:
        applied_issues, profile_context = _apply_consumed_profile_rules(
            _strip_sql_literals_and_comments_for_pb_contract(sql),
            profile_context,
            domain="sql",
            procedure_name=_extract_sp_procedure_name(sql),
            preserve_existing=effective_operation == "existing_sp_cleanup",
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
    candidate_target_procedure = _extract_sp_procedure_identity(sql)
    if effective_operation not in allowed_operations:
        issues.append(
            {
                "code": "unsupported_sp_generation_operation",
                "severity": "error",
                "message": "SP verification requires an explicit supported operation mode.",
                "operation": effective_operation,
            }
        )
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
    allowed_evidence_kinds = {
        "pb_srd_sql",
        "existing_sp",
        "pasted_sql",
        "db_schema",
        "approved_inferred_draft",
        "csharp_call",
        "external_caller",
        "branch_contract",
        "composite_contract",
    }
    accepted_source_evidence = []
    accepted_body_source_evidence: List[Dict[str, Any]] = []
    bound_source_text_by_locator: Dict[str, str] = {}
    bound_source_authority_lineage: List[str] = []
    bound_source_trace_by_hash: Dict[str, List[str]] = {}
    branch_contract_authorities: List[Dict[str, Any]] = []
    candidate_fingerprint = _sql_evidence_fingerprint(sql)
    for item in normalized_source_evidence:
        kind = str(item.get("kind") or "")
        if kind not in allowed_evidence_kinds:
            if any(
                key in item
                for key in [
                    "caller_parameters",
                    "db_parameters",
                    "csharp_db_parameters",
                    "external_caller_parameters",
                    "parameter_contract",
                ]
            ):
                issues.append(
                    {
                        "code": "untrusted_caller_evidence_kind",
                        "severity": "error",
                        "message": "Only csharp_call or verified external_caller evidence may authorize SP parameters.",
                        "kind": kind,
                    }
                )
            continue
        if kind == "approved_inferred_draft" and effective_operation != "approved_inferred_draft":
            issues.append(
                {
                    "code": "inferred_evidence_operation_mismatch",
                    "severity": "error",
                    "message": "Approved inferred evidence is valid only under operation='approved_inferred_draft'.",
                    "operation": effective_operation,
                }
            )
            continue
        path_or_summary = bool(str(item.get("path") or item.get("summary") or "").strip())
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
        if kind in {"existing_sp", "pasted_sql", "pb_srd_sql"}:
            source_text, source_error, source_locator = _bound_source_artifact_text(item)
            has_detail = not source_error
            if source_error:
                issues.append(
                    {
                        "code": source_error,
                        "severity": "error",
                        "message": (
                            "PB/SQL/SP source evidence must be verified and bound to a readable path or "
                            "host-resolved artifact URI by a matching SHA-256 digest."
                        ),
                        "kind": kind,
                        "locator": source_locator,
                    }
                )
            if has_detail and kind == "existing_sp":
                source_object = _extract_sp_procedure_name(source_text)
                declared_object = _normalized_sp_object_name(item.get("object"))
                has_detail = bool(object_name and source_object and declared_object == source_object)
                if not has_detail:
                    issues.append(
                        {
                            "code": "existing_sp_object_definition_mismatch",
                            "severity": "error",
                            "message": "Existing-SP evidence object name must match the bound procedure definition.",
                            "declared_object": declared_object,
                            "definition_object": source_object,
                        }
                    )
            if has_detail and kind == "pasted_sql":
                evidence_role = str(item.get("evidence_role") or "")
                has_detail = evidence_role in {"existing_procedure", "pb_query", "body_fragment"}
                if not has_detail:
                    issues.append(
                        {
                            "code": "pasted_sql_evidence_role_missing_or_invalid",
                            "severity": "error",
                            "message": "Pasted SQL must declare existing_procedure, pb_query, or body_fragment role.",
                        }
                    )
                elif evidence_role == "existing_procedure" and not _extract_sp_procedure_name(source_text):
                    has_detail = False
                    issues.append(
                        {
                            "code": "pasted_existing_procedure_definition_missing",
                            "severity": "error",
                            "message": "Pasted SQL marked existing_procedure must contain a procedure definition.",
                        }
                    )
            if has_detail and kind in {"pb_srd_sql", "pasted_sql"} and not re.search(
                r"\b(?:SELECT|FROM|WHERE|JOIN|INSERT|UPDATE|DELETE|EXEC(?:UTE)?|CREATE|ALTER)\b",
                _strip_sql_literals_and_comments_for_pb_contract(source_text),
                flags=re.IGNORECASE,
            ):
                has_detail = False
                issues.append(
                    {
                        "code": "source_artifact_contains_no_sql_statement",
                        "severity": "error",
                        "message": "PB/pasted SQL evidence must contain an actual SQL statement or body fragment.",
                        "kind": kind,
                    }
                )
            if (
                has_detail
                and effective_operation != "existing_sp_cleanup"
                and candidate_fingerprint
                and _sql_evidence_fingerprint(source_text) == candidate_fingerprint
            ):
                has_detail = False
                issues.append(
                    {
                        "code": "candidate_reused_as_source_evidence",
                        "severity": "error",
                        "message": (
                            "The generated candidate cannot authenticate itself as PB/SQL/SP source evidence. "
                            "Use an independently captured source artifact or existing_sp_cleanup."
                        ),
                        "kind": kind,
                        "locator": source_locator,
                    }
                )
            if has_detail and effective_operation != "existing_sp_cleanup":
                correlated, correlation_reason = _source_correlates_to_candidate(
                    item,
                    source_text,
                    sql,
                )
                if not correlated:
                    has_detail = False
                    issues.append(
                        {
                            "code": (
                                "body_fragment_not_present_in_candidate"
                                if kind == "pasted_sql" and str(item.get("evidence_role") or "") == "body_fragment"
                                else "source_evidence_not_correlated_to_candidate"
                            ),
                            "severity": "error",
                            "message": (
                                "Source evidence must identify the candidate procedure and prove at least one "
                                "meaningful SQL fragment preserved in both the bound source artifact and candidate."
                            ),
                            "kind": kind,
                            "correlation_reason": correlation_reason,
                            "locator": source_locator,
                        }
                    )
                else:
                    item["candidate_correlation"] = correlation_reason
            if has_detail:
                bound_source_text_by_locator[source_locator] = source_text
                source_hash = str(item.get("sha256") or item.get("definition_hash") or "").strip().lower()
                if source_hash and source_hash not in bound_source_authority_lineage:
                    bound_source_authority_lineage.append(source_hash)
                    bound_source_trace_by_hash[source_hash] = [
                        trace_item["trace_key"]
                        for trace_item in _sql_hierarchical_trace(source_text)
                        if not trace_item["generated_wrapper"]
                        and not trace_item.get("generated_envelope")
                    ]
        elif kind == "approved_inferred_draft":
            has_detail = bool(
                item.get("approved")
                and str(item.get("approval_artifact") or item.get("approval_id") or "").strip()
                and item.get("approved_parameters")
            )
        elif kind == "csharp_call":
            caller_values = item.get("parameter_contract")
            if caller_values is None:
                caller_values = item.get("db_parameters")
            if caller_values is None:
                caller_values = item.get("csharp_db_parameters")
            caller_contract = _normalize_caller_parameter_contract(caller_values)
            artifact_text, artifact_error = _bound_caller_artifact_text(item)
            if not verified and not artifact_error:
                artifact_error = "caller_artifact_unverified"
            unproven_metadata = _csharp_contract_unproven_metadata(caller_contract)
            declared_target_raw = str(item.get("target_procedure") or "").strip()
            declared_target = _normalized_sp_identity(declared_target_raw)
            declared_target_invalid = bool(declared_target_raw and not declared_target)
            target_matches = bool(
                declared_target
                and candidate_target_procedure
                and declared_target == candidate_target_procedure
            )
            has_detail = bool(
                verified
                and not artifact_error
                and not unproven_metadata
                and target_matches
                and _caller_contract_is_present_in_artifact(
                    artifact_text,
                    caller_contract,
                    kind="csharp_call",
                    target_procedure=candidate_target_procedure,
                )
            )
            if not has_detail:
                if declared_target_invalid:
                    issue_code = "csharp_caller_target_procedure_invalid"
                elif not declared_target:
                    issue_code = "csharp_caller_target_procedure_missing"
                elif not target_matches or (
                    not artifact_error
                    and not _caller_contract_is_present_in_artifact(
                        artifact_text,
                        caller_contract,
                        kind="csharp_call",
                        target_procedure=candidate_target_procedure,
                    )
                ):
                    issue_code = "csharp_caller_target_procedure_mismatch"
                else:
                    issue_code = (
                        artifact_error
                        or (
                            "csharp_caller_parameter_metadata_not_proven_by_artifact"
                            if unproven_metadata
                            else "caller_contract_not_bound_to_artifact"
                        )
                    )
                issues.append(
                    {
                        "code": issue_code,
                        "severity": "error",
                        "message": (
                            "C# caller evidence must contain one bound dbClient call to the exact candidate procedure "
                            "and the ordered DbParameter list. It cannot claim SQL type, default, OUTPUT, or READONLY "
                            "metadata absent from the C# artifact."
                        ),
                        "candidate_target_procedure": candidate_target_procedure,
                        "declared_target_procedure": declared_target,
                        "unproven_metadata": unproven_metadata,
                    }
                )
        elif kind == "external_caller":
            external_parameter_contract = _normalize_caller_parameter_contract(
                item.get("parameter_contract")
            )
            artifact_text, artifact_error = _bound_caller_artifact_text(item)
            declared_caller_id = str(item.get("caller_id") or "").strip()
            artifact_caller_id = _external_caller_artifact_caller_id(artifact_text)
            declared_target_raw = str(item.get("target_procedure") or "").strip()
            declared_target = _normalized_sp_identity(declared_target_raw)
            declared_target_invalid = bool(declared_target_raw and not declared_target)
            artifact_target_raw = _external_caller_artifact_target_procedure_raw(artifact_text)
            artifact_target = _external_caller_artifact_target_procedure(artifact_text)
            artifact_target_invalid = bool(artifact_target_raw and not artifact_target)
            caller_id_matches = bool(
                declared_caller_id
                and artifact_caller_id
                and declared_caller_id == artifact_caller_id
            )
            target_matches = bool(
                candidate_target_procedure
                and declared_target == candidate_target_procedure
                and artifact_target == candidate_target_procedure
            )
            has_detail = bool(
                verified
                and caller_id_matches
                and target_matches
                and str(item.get("artifact_uri") or item.get("path") or "").strip()
                and re.fullmatch(r"[0-9a-fA-F]{64}", str(item.get("sha256") or "").strip())
                and external_parameter_contract
                and not artifact_error
                and _caller_contract_is_present_in_artifact(
                    artifact_text,
                    external_parameter_contract,
                    kind="external_caller",
                    caller_id=declared_caller_id,
                    target_procedure=candidate_target_procedure,
                )
            )
            if not has_detail and artifact_error:
                issues.append(
                    {
                        "code": artifact_error,
                        "severity": "error",
                        "message": "External caller evidence requires a readable SHA-256-bound artifact.",
                    }
                )
            elif not has_detail and (declared_target_invalid or artifact_target_invalid):
                issues.append(
                    {
                        "code": "external_caller_target_procedure_invalid",
                        "severity": "error",
                        "message": (
                            "External caller target_procedure must use a strict one-part or two-part SQL "
                            "identifier with no empty or extra qualifiers."
                        ),
                        "declared_target_procedure": declared_target_raw,
                        "artifact_target_procedure": artifact_target_raw,
                    }
                )
            elif not has_detail and declared_caller_id != artifact_caller_id:
                issues.append(
                    {
                        "code": "external_caller_id_mismatch",
                        "severity": "error",
                        "message": "External caller evidence caller_id must match the SHA-256-bound artifact caller_id.",
                        "declared_caller_id": declared_caller_id,
                        "artifact_caller_id": artifact_caller_id,
                    }
                )
            elif not has_detail and (not declared_target or not artifact_target):
                issues.append(
                    {
                        "code": "external_caller_target_procedure_missing",
                        "severity": "error",
                        "message": (
                            "External caller evidence and its SHA-256-bound JSON artifact must both declare "
                            "target_procedure."
                        ),
                        "declared_target_procedure": declared_target,
                        "artifact_target_procedure": artifact_target,
                    }
                )
            elif not has_detail and not target_matches:
                issues.append(
                    {
                        "code": "external_caller_target_procedure_mismatch",
                        "severity": "error",
                        "message": "External caller target_procedure must match the exact candidate procedure.",
                        "candidate_target_procedure": candidate_target_procedure,
                        "declared_target_procedure": declared_target,
                        "artifact_target_procedure": artifact_target,
                    }
                )
        elif kind in {"branch_contract", "composite_contract"}:
            (
                branch_trace_keys,
                branch_error,
                contract_metadata,
            ) = _bound_branch_contract_trace_keys(
                item,
                candidate_target_procedure,
                sql,
            )
            has_detail = bool(branch_trace_keys and not branch_error)
            if branch_error:
                issues.append(
                    {
                        "code": branch_error,
                        "severity": "error",
                        "message": (
                            "Generated branch conditions require a verified SHA-256-bound JSON authority whose "
                            "target_procedure and complete trace topology match the candidate. Composite authorities "
                            "must also bind an explicit source_lineage list."
                        ),
                    }
                )
            if has_detail:
                branch_contract_authorities.append(
                    {
                        "authority_id": str(
                            item.get("artifact_uri")
                            or item.get("path")
                            or item.get("sha256")
                            or "branch_contract"
                        ),
                        "trace_key_counts": dict(branch_trace_keys),
                        "authority_kind": kind,
                        "source_lineage": list(
                            contract_metadata.get("source_lineage") or []
                        ),
                        "trace_sha256": str(
                            contract_metadata.get("trace_sha256") or ""
                        ),
                        "lineage_trace_keys": list(
                            contract_metadata.get("lineage_trace_keys") or []
                        ),
                    }
                )
        elif kind == "db_schema":
            has_detail = path_or_summary or hash_or_definition or (object_name and verified)
        if has_detail:
            accepted_source_evidence.append(item)
            if kind in {"existing_sp", "pasted_sql", "pb_srd_sql"}:
                accepted_body_source_evidence.append(item)
        elif kind in {"external_caller", "approved_inferred_draft"}:
            issues.append(
                {
                    "code": f"incomplete_{kind}_evidence",
                    "severity": "error",
                    "message": f"{kind} evidence is missing its required role, artifact, hash, approval, or parameter contract.",
                }
            )

    validated_contract_authorities: List[Dict[str, Any]] = []
    for authority in branch_contract_authorities:
        if authority.get("authority_kind") == "composite_contract":
            lineage = [
                str(value or "").strip().lower()
                for value in authority.get("source_lineage") or []
                if str(value or "").strip()
            ]
            if len(lineage) != len(set(lineage)):
                issues.append(
                    {
                        "code": "composite_contract_source_lineage_duplicate",
                        "severity": "error",
                        "message": (
                            "Composite source_lineage cannot contain duplicate source authority hashes."
                        ),
                        "source_lineage": lineage,
                    }
                )
                continue
            if lineage != bound_source_authority_lineage:
                issues.append(
                    {
                        "code": "composite_contract_source_lineage_mismatch",
                        "severity": "error",
                        "message": (
                            "Composite source_lineage must exactly equal every independently bound and "
                            "candidate-correlated source authority SHA-256 in verification order. Subsets, "
                            "unknown hashes, and reordering fail closed."
                        ),
                        "source_lineage": lineage,
                        "expected_source_lineage": bound_source_authority_lineage,
                    }
                )
                continue
            expected_lineage_trace = [
                trace_key
                for source_hash in lineage
                for trace_key in bound_source_trace_by_hash.get(source_hash, [])
            ]
            if list(authority.get("lineage_trace_keys") or []) != expected_lineage_trace:
                issues.append(
                    {
                        "code": "composite_contract_source_trace_mismatch",
                        "severity": "error",
                        "message": (
                            "Composite trace_sql must equal the exhaustive ordered non-envelope trace "
                            "of every bound source authority in source_lineage order."
                        ),
                        "source_lineage": lineage,
                        "expected_trace_event_count": len(expected_lineage_trace),
                        "actual_trace_event_count": len(
                            list(authority.get("lineage_trace_keys") or [])
                        ),
                    }
                )
                continue
        validated_contract_authorities.append(authority)
    branch_contract_authorities = validated_contract_authorities

    migration_source_evidence = [
        item
        for item in accepted_source_evidence
        if str(item.get("kind") or "")
        not in {
            "csharp_call",
            "external_caller",
            "branch_contract",
            "composite_contract",
        }
    ]

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
                    "immediately above CREATE/ALTER PROCEDURE. DESCRIPTION is required; AUTHOR and "
                    "CREATE DATE are included only when supplied by authoritative source evidence."
                ),
            }
        )
    elif header_match:
        header_author = str(header_match.group("author") or "").strip()
        header_create_date = str(header_match.group("create_date") or "").strip()
        header_description = str(header_match.group("description") or "").strip()
        procedure_name = _extract_sp_procedure_name(sql)
        if header_author and re.search(
            r"<[^>]+>|TODO|SAMPLE|MAINTAINER|UNKNOWN|TBD",
            header_author,
            flags=re.IGNORECASE,
        ):
            issues.append(
                {
                    "code": "sp_metadata_author_placeholder",
                    "severity": "error",
                    "message": (
                        "Do not invent or placeholder-fill AUTHOR. Preserve a source/caller-provided "
                        "author or omit the AUTHOR line."
                    ),
                    "actual_author": header_author,
                }
            )
        metadata_sources = list(accepted_source_evidence)
        if effective_operation == "existing_sp_cleanup" and str(original_sp_text or "").strip():
            metadata_sources.append(
                {
                    "kind": "existing_sp",
                    "definition_text": str(original_sp_text),
                }
            )
        authoritative_authors, authoritative_dates = _source_metadata_values(metadata_sources)
        if header_author and not authoritative_authors:
            issues.append(
                {
                    "code": "sp_metadata_author_not_source_backed",
                    "severity": "error",
                    "message": "Omit AUTHOR unless authoritative source evidence supplies the exact value.",
                    "actual_author": header_author,
                }
            )
        elif header_author and header_author not in authoritative_authors:
            issues.append(
                {
                    "code": "sp_metadata_author_mismatch",
                    "severity": "error",
                    "message": "AUTHOR does not match authoritative source evidence.",
                    "actual_author": header_author,
                    "expected_authors": sorted(authoritative_authors),
                }
            )
        if header_create_date and not authoritative_dates:
            issues.append(
                {
                    "code": "sp_metadata_create_date_not_source_backed",
                    "severity": "error",
                    "message": "Omit CREATE DATE unless authoritative source evidence supplies the exact value.",
                    "actual_create_date": header_create_date,
                }
            )
        elif header_create_date and header_create_date not in authoritative_dates:
            issues.append(
                {
                    "code": "sp_metadata_create_date_mismatch",
                    "severity": "error",
                    "message": "CREATE DATE does not match authoritative source evidence.",
                    "actual_create_date": header_create_date,
                    "expected_create_dates": sorted(authoritative_dates),
                }
            )
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
    body_traceability: List[Dict[str, Any]] = []
    if (
        sql.strip()
        and effective_operation != "approved_inferred_draft"
        and not accepted_body_source_evidence
    ):
        issues.append(
            {
                "code": "inferred_draft_not_complete" if allow_inferred_draft else "missing_pb_or_db_source_evidence_for_sp_generation",
                "severity": "error",
                "message": (
                    "Do not present a full migration SELECT/SAVE procedure as completed unless independently "
                    "hash-bound PB/DataWindow SQL, existing-SP, or pasted-SQL body evidence is recorded. "
                    "Schema evidence alone does not authorize a procedure body."
                ),
            }
        )
    if effective_operation in {"new_generation", "pb_srd_generation"} and bound_source_text_by_locator:
        source_authorities = [
            {"authority_id": locator, "text": source_text}
            for locator, source_text in bound_source_text_by_locator.items()
        ]
        body_traceability, body_traceability_issues = _candidate_body_traceability(
            sql,
            source_authorities,
            branch_contract_authorities,
        )
        issues.extend(body_traceability_issues)
    if effective_operation != "existing_sp_cleanup" and "@WORKTYPE" not in upper_unprotected:
        issues.append(
            {
                "code": "missing_worktype_contract",
                "severity": "error",
                "message": "Migration SELECT/SAVE procedures must expose the @WORKTYPE branch contract.",
            }
        )
    if effective_operation != "existing_sp_cleanup" and re.search(r"@WORKTYPE\s+VARCHAR\s*\(\s*20\s*\)\s*=\s*''", upper_comments_stripped):
        issues.append(
            {
                "code": "worktype_empty_string_default_detected",
                "severity": "error",
                "message": "Target-style procedures do not default @WORKTYPE to an empty string; use NULL or the verified required parameter contract.",
            }
        )
    if effective_operation != "existing_sp_cleanup" and re.search(r"@[A-Z][A-Z0-9_]*\s+(?:N?VARCHAR|N?CHAR)\s*\([^)]*\)\s*=\s*'%'", upper_comments_stripped):
        issues.append(
            {
                "code": "wildcard_filter_parameter_default_detected",
                "severity": "error",
                "message": "Do not default text filter parameters to '%' unless verified target procedure evidence uses that exact contract.",
            }
        )
    if effective_operation != "existing_sp_cleanup" and re.search(r"@[A-Z][A-Z0-9_]*\s+(?:N?VARCHAR|N?CHAR)\s*\([^)]*\)\s*=\s*'(?:T|1)'", upper_comments_stripped):
        issues.append(
            {
                "code": "business_flag_parameter_default_detected",
                "severity": "error",
                "message": "Do not default business selector parameters to generated literals unless verified target procedure evidence uses them.",
            }
        )
    procedure_parameter_contract = _extract_sp_parameter_contract(sql)
    procedure_parameters = [item["name"] for item in procedure_parameter_contract]
    caller_contract = _normalize_caller_parameter_contract(caller_parameter_contract)
    declared_external_contract = _normalize_caller_parameter_contract(
        external_caller_contract
    )
    external_contract: List[Dict[str, Any]] = []
    for item in accepted_source_evidence:
        kind = str(item.get("kind") or "")
        if kind == "csharp_call":
            values = item.get("parameter_contract")
            if values is None:
                for key in ["db_parameters", "csharp_db_parameters"]:
                    if item.get(key) is not None:
                        values = item.get(key)
                        break
            caller_contract.extend(_normalize_caller_parameter_contract(values))
        elif kind == "external_caller":
            contract = _normalize_caller_parameter_contract(item.get("parameter_contract"))
            if any(not parameter.get("type_spec") for parameter in contract):
                issues.append(
                    {
                        "code": "external_caller_parameter_type_missing",
                        "severity": "error",
                        "message": "Verified external caller contracts must include ordered SQL type specifications.",
                    }
                )
            external_contract.extend(contract)

    if declared_external_contract:
        if not external_contract:
            issues.append(
                {
                    "code": "external_caller_contract_without_provenance",
                    "severity": "error",
                    "message": "The external_caller_contract argument cannot authorize parameters without matching verified external_caller artifact evidence.",
                }
            )
        elif not _sp_signatures_equal(declared_external_contract, external_contract):
            issues.append(
                {
                    "code": "external_caller_contract_evidence_mismatch",
                    "severity": "error",
                    "message": "The direct external caller contract does not match the artifact-backed external caller evidence.",
                }
            )

    signature_authority = "none"
    original_parameter_contract: List[Dict[str, Any]] = []
    if effective_operation == "existing_sp_cleanup":
        original_definition = ""
        for item in accepted_body_source_evidence:
            if str(item.get("kind") or "") == "existing_sp" or (
                str(item.get("kind") or "") == "pasted_sql"
                and str(item.get("evidence_role") or "") == "existing_procedure"
            ):
                locator = str(
                    item.get("artifact_uri")
                    or item.get("definition_path")
                    or item.get("path")
                    or ""
                ).strip()
                original_definition = bound_source_text_by_locator.get(locator, "")
                if original_definition:
                    break
        if not original_definition:
            issues.append(
                {
                    "code": "existing_sp_definition_missing",
                    "severity": "error",
                    "message": (
                        "Existing-SP cleanup cannot prove signature preservation without an authenticated "
                        "existing_sp or pasted_sql(existing_procedure) artifact."
                    ),
                }
            )
        else:
            if str(original_sp_text or "") and str(original_sp_text) != original_definition:
                issues.append(
                    {
                        "code": "original_sp_text_evidence_mismatch",
                        "severity": "error",
                        "message": "The direct original_sp_text argument does not match the authenticated source artifact.",
                    }
                )
            original_parameter_contract = _extract_sp_parameter_contract(original_definition)
            signature_authority = "existing_sp_definition"
            if not _sp_signatures_equal(procedure_parameter_contract, original_parameter_contract):
                issues.append(
                    {
                        "code": "existing_sp_signature_changed",
                        "severity": "error",
                        "message": "Formatting/cleanup must preserve parameter name, order, type, size, default, OUTPUT, and READONLY exactly.",
                        "original_signature": original_parameter_contract,
                        "candidate_signature": procedure_parameter_contract,
                    }
                )
            issues.extend(_existing_sp_cleanup_preservation_issues(original_definition, sql))
    elif effective_operation in {"new_generation", "pb_srd_generation"}:
        expected_contract = caller_contract + external_contract
        expected_names = [item["name"] for item in expected_contract]
        if not expected_contract and procedure_parameters:
            issues.append(
                {
                    "code": "missing_caller_parameter_contract",
                    "severity": "error",
                    "message": (
                        "New PB migration procedure generation requires an ordered C# caller contract or "
                        "a verified external-caller artifact. PB/DataWindow SQL does not authorize parameters."
                    ),
                    "parameters": procedure_parameters,
                }
            )
        elif expected_contract:
            signature_authority = "csharp_or_verified_external_caller"
            extra = [name for name in procedure_parameters if name not in expected_names]
            missing = [name for name in expected_names if name not in procedure_parameters]
            if extra:
                issues.append(
                    {
                        "code": "non_caller_procedure_parameter_detected",
                        "severity": "error",
                        "message": "SP helper/calculation values must be local DECLARE variables, not procedure parameters.",
                        "parameters": extra,
                        "caller_parameters": expected_names,
                    }
                )
            if missing:
                issues.append(
                    {
                        "code": "caller_parameter_missing_from_procedure",
                        "severity": "error",
                        "message": "Every approved caller parameter must appear in the generated procedure signature.",
                        "parameters": missing,
                    }
                )
            if not extra and not missing and procedure_parameters != expected_names:
                issues.append(
                    {
                        "code": "caller_parameter_order_mismatch",
                        "severity": "error",
                        "message": "Generated procedure parameters must preserve caller order.",
                        "expected": expected_names,
                        "actual": procedure_parameters,
                    }
                )
            for index, expected in enumerate(expected_contract):
                if index >= len(procedure_parameter_contract):
                    break
                expected_type = str(expected.get("type_spec") or "")
                if expected_type and expected_type != procedure_parameter_contract[index].get("type_spec"):
                    issues.append(
                        {
                            "code": "caller_parameter_type_mismatch",
                            "severity": "error",
                            "message": "Generated procedure parameter type differs from the verified caller contract.",
                            "parameter": expected["name"],
                            "expected": expected_type,
                            "actual": procedure_parameter_contract[index].get("type_spec"),
                        }
                    )
                for field, issue_code, label in [
                    ("output", "caller_parameter_output_mismatch", "OUTPUT"),
                    ("readonly", "caller_parameter_readonly_mismatch", "READONLY"),
                    ("default_present", "caller_parameter_default_presence_mismatch", "default presence"),
                    ("default", "caller_parameter_default_mismatch", "default value"),
                ]:
                    specified_key = (
                        "default_specified"
                        if field in {"default_present", "default"}
                        else f"{field}_specified"
                    )
                    if not expected.get(specified_key):
                        continue
                    if expected.get(field) == procedure_parameter_contract[index].get(field):
                        continue
                    issues.append(
                        {
                            "code": issue_code,
                            "severity": "error",
                            "message": f"Generated procedure parameter {label} differs from the verified caller contract.",
                            "parameter": expected["name"],
                            "expected": expected.get(field),
                            "actual": procedure_parameter_contract[index].get(field),
                        }
                    )
        if effective_operation == "pb_srd_generation" and not any(
            str(item.get("kind") or "") == "pb_srd_sql" for item in migration_source_evidence
        ):
            issues.append(
                {
                    "code": "pb_srd_evidence_missing_for_operation",
                    "severity": "error",
                    "message": "pb_srd_generation requires explicit PB/DataWindow SQL evidence.",
                }
            )
    elif effective_operation == "approved_inferred_draft":
        approval_items = [
            item
            for item in accepted_source_evidence
            if str(item.get("kind") or "") == "approved_inferred_draft"
        ]
        approved_contract = _normalize_caller_parameter_contract(
            approval_items[0].get("approved_parameters") if approval_items else None
        )
        if not approval_items or [item["name"] for item in approved_contract] != procedure_parameters:
            issues.append(
                {
                    "code": "approved_inferred_parameter_contract_mismatch",
                    "severity": "error",
                    "message": "Approved inferred drafts require an artifact-backed ordered parameter list matching the draft.",
                }
            )
        issues.append(
            {
                "code": "approved_inferred_draft_release_pending",
                "severity": "pending",
                "message": "An inferred draft remains non-release-ready until caller and DB evidence are verified.",
            }
        )

    if procedure_parameter_contract:
        helper_date_params = sorted(
            item["name"]
            for item in procedure_parameter_contract
            if item["name"] in {"@DERIVED_YEAR", "@DERIVED_MONTH", "@BASE_YEAR", "@BOUNDARY_DATE"}
        )
        if helper_date_params and effective_operation != "existing_sp_cleanup":
            issues.append(
                {
                    "code": "derived_date_helper_parameter_detected",
                    "severity": "error",
                    "message": (
                        "Do not expose derived helper date values such as @DERIVED_YEAR, @DERIVED_MONTH, @BASE_YEAR, or @BOUNDARY_DATE "
                        "as generated procedure parameters. Accept the raw target-style date input, then use local DECLARE and SET "
                        "inside the procedure when derived values are needed."
                    ),
                    "parameters": helper_date_params,
                }
            )
    if effective_operation != "existing_sp_cleanup" and re.search(
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
    if effective_operation != "existing_sp_cleanup" and re.search(
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
    if effective_operation != "existing_sp_cleanup" and re.search(
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
    if effective_operation != "existing_sp_cleanup" and re.search(r"SET\s+@WORKTYPE\s*=\s*ISNULL\s*\(", upper_comments_stripped):
        issues.append(
            {
                "code": "worktype_isnull_normalization_detected",
                "severity": "error",
                "message": "Do not add SET @WORKTYPE = ISNULL(...) normalization in generated KH-style SP output.",
            }
        )
    if effective_operation != "existing_sp_cleanup" and re.search(r"SET\s+@[A-Z0-9_]+\s*=\s*\(\s*CASE\s+WHEN\s+ISNULL\s*\(", upper_comments_stripped):
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
        if effective_operation != "existing_sp_cleanup" and re.search(pattern, upper_comments_stripped):
            issues.append(
                {
                    "code": code,
                    "severity": "error",
                    "message": "Do not add generated parameter normalization blocks unless verified target SP evidence already uses that exact pattern.",
                }
            )
    if effective_operation != "existing_sp_cleanup" and re.search(r"(^|[;\s])WITH\s+(?:\[[^\]]+\]|[A-Z0-9_]+)\s+AS\s*\(", upper_unprotected):
        issues.append(
            {
                "code": "cte_in_generated_sp",
                "severity": "error",
                "message": "Do not introduce CTEs in migration SP generation by default.",
            }
        )
    if effective_operation != "existing_sp_cleanup" and re.search(r"SELECT\s+TOP\s*\(?\s*0\s*\)?[\s\S]{0,800}(?:CAST|CONVERT|TRY_CONVERT)\s*\(", upper_unprotected):
        issues.append(
            {
                "code": "schema_only_select_top_0_fallback_in_generated_sp",
                "severity": "error",
                "message": "Do not add source-unbacked SELECT TOP 0/SELECT TOP (0) CAST/CONVERT/TRY_CONVERT(...) schema-only fallback blocks to migration SP output.",
            }
        )
    if effective_operation != "existing_sp_cleanup" and re.search(r"#[A-Z0-9_]+", upper_unprotected):
        issues.append(
            {
                "code": "temp_table_in_generated_sp",
                "severity": "error",
                "message": "Do not introduce # temporary tables in migration SP generation by default.",
            }
        )
    if effective_operation != "existing_sp_cleanup" and "MERGE " in upper_unprotected:
        issues.append(
            {
                "code": "merge_in_generated_sp",
                "severity": "error",
                "message": "Do not introduce MERGE in migration SP generation by default.",
            }
        )
    if effective_operation != "existing_sp_cleanup" and "NOT EXISTS" in upper_unprotected:
        issues.append(
            {
                "code": "not_exists_in_generated_sp",
                "severity": "error",
                "message": "Do not introduce NOT EXISTS in migration SP generation by default.",
            }
        )
    if effective_operation != "existing_sp_cleanup" and _pb_contract_contains_if_exists_where_subquery(upper_unprotected):
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

    has_errors = any(issue["severity"] == "error" for issue in issues)
    has_pending = any(issue["severity"] == "pending" for issue in issues)
    passed = not has_errors and not has_pending
    status = "blocked" if has_errors else "pending" if has_pending else "passed"
    metadata = {
        "harness": "pb-to-csharp-migration-harness",
        "status": status,
        "operation": effective_operation,
        "source_evidence": accepted_source_evidence,
        "source_evidence_count": len(accepted_source_evidence),
        "allow_inferred_draft": bool(allow_inferred_draft),
        "profile_consumption": profile_consumption,
        "signature_authority": signature_authority,
        "candidate_parameter_contract": procedure_parameter_contract,
        "original_parameter_contract": original_parameter_contract,
        "caller_parameter_contract": caller_contract,
        "external_caller_contract": external_contract,
        "declared_external_caller_contract": declared_external_contract,
        "body_traceability": body_traceability,
        "release_readiness": {
            "status": "ready" if passed else "pending" if has_pending and not has_errors else "blocked"
        },
        "issues": issues,
        "sp_generation_contract": (
            "Release-ready migration SP output requires independently captured, readable, SHA-256-matched "
            "PB/DataWindow SQL, existing-SP, or pasted-SQL body evidence plus caller authority. Schema evidence "
            "does not authorize a body, and approved inferred drafts remain pending. SQL style verification remains separate."
        ),
        "token_optimizer_status": "passthrough",
        "token_optimizer_status_reason": "SQL/stored procedure text is contract-sensitive and was not compressed.",
    }
    return HarnessResult(
        success=passed,
        stdout=json.dumps({"status": metadata["status"], "issue_count": len(issues)}, ensure_ascii=False, sort_keys=True),
        stderr="" if passed else "SP generation contract verification blocked by missing evidence or style issues.",
        exit_code=0 if passed else 2 if status == "pending" else 1,
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

def _execute_pb_sql_final_response_binding(
    original_sql_text: str,
    formatted_sql_text: str,
    draft_final_response: str,
    *,
    sql_provider_path: str | Path,
    selected_active_sql_provider_path: str | Path | None = None,
    sql_provider_selection: Mapping[str, Any] | None = None,
    cte_temp_table_reason: str = "",
    alias_role_plan: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    sql_formatting_verifier_kwargs: Mapping[str, Any] | None = None,
) -> tuple[bool, Dict[str, Any]]:
    from src.skills.sql_formatting_provider import (
        SqlFinalResponseBindingError,
        SqlFormattingProviderPathError,
        guard_and_bind_verified_sql_final_response,
    )

    if not str(draft_final_response or ""):
        return False, {
            "status": "blocked",
            "code": "sql_final_response_missing",
            "message": "SQL-emitting PB validation requires the exact draft final response for binding.",
        }
    if not str(sql_provider_path or ""):
        return False, {
            "status": "blocked",
            "code": "sql_provider_path_missing",
            "message": "SQL-emitting PB validation requires the authoritative SQL provider path.",
        }
    if not str(selected_active_sql_provider_path or ""):
        return False, {
            "status": "blocked",
            "code": "selected_active_sql_provider_path_missing",
            "message": "SQL-emitting PB validation requires the exact active provider path selected by the front door.",
        }
    if not isinstance(sql_provider_selection, Mapping):
        return False, {
            "status": "blocked",
            "code": "sql_provider_selection_missing",
            "message": "SQL-emitting PB validation requires correlated front-door provider-selection evidence.",
        }
    verifier_kwargs = dict(sql_formatting_verifier_kwargs or {})
    operation = verifier_kwargs.pop("operation", "formatting")
    style_contract_path = verifier_kwargs.pop("style_contract_path", None)
    if operation != "formatting" or verifier_kwargs:
        return False, {
            "status": "blocked",
            "code": "unsupported_sql_binding_verifier_options",
            "message": "The PB final-response binder accepts only operation='formatting' and style_contract_path.",
            "unsupported_options": sorted(verifier_kwargs),
        }
    try:
        release = guard_and_bind_verified_sql_final_response(
            original_sql_text,
            formatted_sql_text,
            draft_final_response,
            provider_path=sql_provider_path,
            selected_active_provider_path=selected_active_sql_provider_path,
            provider_selection=sql_provider_selection,
            style_contract_path=style_contract_path,
            cte_temp_table_reason=cte_temp_table_reason,
            alias_role_plan=alias_role_plan,
        )
    except (SqlFinalResponseBindingError, SqlFormattingProviderPathError, OSError, ValueError) as exc:
        return False, {
            "status": "blocked",
            "code": str(getattr(exc, "code", "sql_final_response_binding_failed")),
            "message": str(exc),
        }
    return True, release.to_receipt_dict()


def _pb_sql_release_evidence_views(
    release_success: bool,
    release_receipt: Mapping[str, Any],
) -> tuple[bool, Dict[str, Any], Dict[str, Any]]:
    full_release = dict(release_receipt)
    if not release_success:
        blocked = dict(full_release)
        return False, blocked, full_release
    binding = full_release.get("binding")
    if (
        type(full_release.get("status")) is not str
        or full_release.get("status") != "passed"
        or not isinstance(binding, Mapping)
        or type(binding.get("status")) is not str
        or binding.get("status") != "bound"
    ):
        blocked = {
            "status": "blocked",
            "code": "sql_final_response_release_contract_invalid",
            "message": (
                "Successful PB SQL release evidence requires release.status=passed "
                "and release.binding.status=bound."
            ),
        }
        return False, blocked, full_release
    return True, dict(binding), full_release


def verify_pb_migration_sp_with_sql_formatting(
    original_sql_text: str,
    formatted_sql_text: str,
    *,
    source_evidence: Any = None,
    allow_inferred_draft: bool = False,
    cte_temp_table_reason: str = "",
    profile_evidence: Any = None,
    alias_role_plan: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    sql_formatting_verifier_kwargs: Mapping[str, Any] | None = None,
    sp_operation: str = "new_generation",
    original_sp_text: str | None = None,
    caller_parameter_contract: Any = None,
    external_caller_contract: Any = None,
    draft_final_response: str = "",
    sql_provider_path: str | Path = "",
    selected_active_sql_provider_path: str | Path | None = None,
    sql_provider_selection: Mapping[str, Any] | None = None,
) -> HarnessResult:
    """Verify the SP contract and bind the exact SQL-bearing final response as one gate."""

    contract_result = verify_pb_migration_sp_generation_contract(
        formatted_sql_text,
        source_evidence=source_evidence,
        allow_inferred_draft=allow_inferred_draft,
        profile_evidence=profile_evidence,
        operation=sp_operation,
        original_sp_text=original_sp_text,
        caller_parameter_contract=caller_parameter_contract,
        external_caller_contract=external_caller_contract,
    )
    binding_success = False
    binding_receipt: Dict[str, Any] = {
        "status": "blocked",
        "code": "sp_generation_contract_failed",
        "message": "Final SQL binding did not run because the PB SP contract failed.",
    }
    release_receipt: Dict[str, Any] = dict(binding_receipt)
    if contract_result.success:
        binding_success, release_receipt = _execute_pb_sql_final_response_binding(
            original_sql_text,
            formatted_sql_text,
            draft_final_response,
            sql_provider_path=sql_provider_path,
            selected_active_sql_provider_path=selected_active_sql_provider_path,
            sql_provider_selection=sql_provider_selection,
            cte_temp_table_reason=cte_temp_table_reason,
            alias_role_plan=alias_role_plan,
            sql_formatting_verifier_kwargs=sql_formatting_verifier_kwargs,
        )
        binding_success, binding_receipt, release_receipt = (
            _pb_sql_release_evidence_views(binding_success, release_receipt)
        )
    success = bool(contract_result.success and binding_success)
    metadata = {
        "harness": "pb-to-csharp-migration-harness",
        "status": "passed" if success else "blocked",
        "sp_generation_contract": contract_result.metadata,
        "sql_final_response_binding": binding_receipt,
        "sql_final_response_release": release_receipt,
        "sql_formatting_style": {
            "status": "passed" if binding_success else "blocked",
            "evidence_source": "sql_final_response_binding",
        },
        "token_optimizer_status": "passthrough",
        "token_optimizer_status_reason": "SQL/stored procedure text is contract-sensitive and was not compressed.",
    }
    return HarnessResult(
        success=success,
        stdout=json.dumps(
            {
                "status": metadata["status"],
                "sp_contract_status": contract_result.metadata.get("status"),
                "sql_formatting_status": metadata["sql_formatting_style"]["status"],
                "sql_final_response_binding_status": binding_receipt.get("status"),
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
    expected_control_contracts: Iterable[Mapping[str, Any]] | None = None,
    no_control_contract_evidence: Any = None,
    evidence_registry: Any = None,
    target_source_path: str | Path = "",
    target_source_sha256: str = "",
    target_designer_path: str | Path = "",
    target_designer_sha256: str = "",
    baseline_designer_path: str | Path = "",
    baseline_designer_sha256: str = "",
    expected_grid_role: str = "",
    expected_grid_suffix: str = "",
    expected_grid_prefix: str = "",
    expected_grid_columns: Iterable[Any] | None = None,
    expected_grid_contracts: Iterable[Mapping[str, Any]] | None = None,
    layout_load_artifact_path: str = "",
    layout_load_artifact_text: str = "",
    layout_load_evidence: Any = None,
    source_evidence: Any = None,
    allow_inferred_draft: bool = False,
    cte_temp_table_reason: str = "",
    alias_role_plan: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    sql_formatting_verifier_kwargs: Mapping[str, Any] | None = None,
    sp_operation: str = "new_generation",
    caller_parameter_contract: Any = None,
    external_caller_contract: Any = None,
    draft_final_response: str = "",
    sql_provider_path: str | Path = "",
    selected_active_sql_provider_path: str | Path | None = None,
    sql_provider_selection: Mapping[str, Any] | None = None,
) -> HarnessResult:
    """Run the fail-closed offline profile, C#, SP, and formatting validation contract."""
    required_order = [
        "load-profile",
        "validate-csharp",
        "validate-sp",
        "final-sql-binding",
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
        expected_control_contracts=expected_control_contracts,
        no_control_contract_evidence=no_control_contract_evidence,
        evidence_registry=evidence_registry,
        target_source_path=target_source_path,
        target_source_sha256=target_source_sha256,
        target_designer_path=target_designer_path,
        target_designer_sha256=target_designer_sha256,
        baseline_designer_path=baseline_designer_path,
        baseline_designer_sha256=baseline_designer_sha256,
        expected_grid_role=expected_grid_role,
        expected_grid_suffix=expected_grid_suffix,
        expected_grid_prefix=expected_grid_prefix,
        expected_grid_columns=expected_grid_columns,
        expected_grid_contracts=expected_grid_contracts,
        layout_load_artifact_path=layout_load_artifact_path,
        layout_load_artifact_text=layout_load_artifact_text,
        layout_load_evidence=layout_load_evidence,
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

    normalized_sp_evidence: List[Dict[str, Any]] = []
    if isinstance(source_evidence, dict):
        normalized_sp_evidence.append(dict(source_evidence))
    elif isinstance(source_evidence, (list, tuple)):
        normalized_sp_evidence.extend(dict(item) for item in source_evidence if isinstance(item, dict))
    sp_result = verify_pb_migration_sp_generation_contract(
        formatted_sql_text,
        source_evidence=normalized_sp_evidence,
        allow_inferred_draft=allow_inferred_draft,
        profile_evidence=loaded_profile,
        operation=sp_operation,
        original_sp_text=original_sql_text if sp_operation == "existing_sp_cleanup" else None,
        caller_parameter_contract=caller_parameter_contract,
        external_caller_contract=external_caller_contract,
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

    binding_success, release_receipt = _execute_pb_sql_final_response_binding(
        original_sql_text,
        formatted_sql_text,
        draft_final_response,
        sql_provider_path=sql_provider_path,
        selected_active_sql_provider_path=selected_active_sql_provider_path,
        sql_provider_selection=sql_provider_selection,
        cte_temp_table_reason=cte_temp_table_reason,
        alias_role_plan=alias_role_plan,
        sql_formatting_verifier_kwargs=sql_formatting_verifier_kwargs,
    )
    binding_success, binding_receipt, release_receipt = _pb_sql_release_evidence_views(
        binding_success,
        release_receipt,
    )
    stages.append(
        {
            "name": "final-sql-binding",
            "status": "passed" if binding_success else "blocked",
        }
    )
    evidence["sql_final_response_binding"] = binding_receipt
    evidence["sql_final_response_release"] = release_receipt
    evidence["formatting"] = {
        "status": "passed" if binding_success else "blocked",
        "evidence_source": "sql_final_response_binding",
    }
    return finish(binding_success)


def build_datawindow_grid_layout(
    source_text: str,
    *,
    prefix: str = "",
    input_format: str = "list",
    table_name: str = "",
    purpose_name: str = "",
    grid_view_name: str = "",
    serialized_view_name: str = "",
) -> HarnessResult:
    """Build grid XML from SRD text and return contract-shaped evidence."""
    resolved_prefix = prefix or resolve_csharp_grid_column_prefix(
        input_format, table_name=table_name, purpose_name=purpose_name
    )
    grid_names = resolve_csharp_grid_control_names(input_format, table_name=table_name, purpose_name=purpose_name)
    resolved_serialized_view_name = serialized_view_name or grid_view_name or "gridView1"
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
    xml = generate_devexpress_grid_xml(
        column_specs,
        prefix=resolved_prefix,
        serialized_view_name=resolved_serialized_view_name,
    )
    metadata = {
        "harness": "pb-to-csharp-migration-harness",
        "status": "passed",
        "columns": [spec.field_name for spec in column_specs],
        "column_specs": [spec.to_dict() for spec in column_specs],
        "column_count": len(column_specs),
        "csharp_column_prefix": resolved_prefix,
        "csharp_column_prefix_rule": "{input_format}_{column}: colList_, colDetail_, col<TABLE>_, or col<PURPOSE>_",
        "csharp_grid_names": grid_names,
        "serialized_grid_view_name": resolved_serialized_view_name,
        "legacy_grid_view_name_alias_used": bool(grid_view_name and not serialized_view_name),
        "csharp_grid_name_rule": "grdList/gvwList, grdDetail/gvwDetail, grd<TABLE>/gvw<TABLE>, or grd<PURPOSE>/gvw<PURPOSE>",
        "converter_contract": (
            "DataWindowToXml-compatible PB column occurrence order with exact XML names, separate C# member mappings, "
            "and matched DataWindow captions when available"
        ),
        "gridview_defaults": DATAWINDOW_TO_XML_OPTIONS_VIEW_DEFAULTS,
        "verification_scope": "static_layout_load_ready_xml_generation",
        "actual_live_layout_load_observed": False,
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
                field_name = _normalize_datawindow_field_name(item.field_name)
                specs.append(
                    DataWindowColumnSpec(
                        field_name=field_name,
                        caption=str(item.caption or item.field_name),
                        csharp_name=str(item.csharp_name or build_csharp_grid_column_name(field_name, prefix=prefix)),
                        xml_column_name=str(item.xml_column_name or f"{prefix}{field_name}"),
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
                csharp_name = str(item.get("csharp_name") or "").strip()
                xml_column_name = str(item.get("xml_column_name") or "").strip()
                specs.append(
                    DataWindowColumnSpec(
                        field_name=field_name,
                        caption=str(item.get("caption") or field_name),
                        csharp_name=csharp_name or build_csharp_grid_column_name(field_name, prefix=prefix),
                        xml_column_name=xml_column_name or f"{prefix}{field_name}",
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
                    xml_column_name=f"{prefix}{field_name}",
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
    return columns


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
