import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List
from xml.sax.saxutils import escape

from src.contracts import HarnessResult


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
    r"(?:\[[^\]]+\]|\w+)?\s*\.?\s*(?:\[(?P<bracketed>SP_[A-Z0-9_]+)\]|(?P<plain>SP_[A-Z0-9_]+))",
    re.IGNORECASE,
)

AUTHOR_TAGGED_CSHARP_STYLE_BASELINE: Dict[str, Any] = {
    "snapshot_date": "2026-07-03",
    "db_source": "C_KONE110 SYS.OBJECTS + SYS.SQL_MODULES",
    "sp_selector": "procedure definition contains KH, Geunho, or Jang Geunho author text",
    "sp_count": 62,
    "normalized_program_key_count": 41,
    "primary_csharp_baseline_files_analyzed": 37,
    "designer_files_analyzed": 37,
    "source_root": r"C:\Users\KONEIT\Desktop\Source\TY\C_KONE110_1\Programs",
    "baseline_exclusions": {
        "SA900100": "current generated/repair target, not accepted as a seed style sample",
        "SA116T": "author-tagged SP only; no same-name C# screen file found",
        "PopDwgnoFrm": "platform popup mapping, no same-name screen file under Programs",
        "popSendMail": "platform popup mapping, no same-name screen file under Programs",
    },
    "primary_csharp_pattern_counts": {
        "dbClient.GetDataSetFromSP": {"files": 35, "hits": 38},
        "CallSelectProcedure": {"files": 31, "hits": 135},
        "CallViewQuery": {"files": 5, "hits": 43},
        "SelectType": {"files": 33, "hits": 339},
        "SearchCommand": {"files": 34, "hits": 136},
        "SaveCommand": {"files": 31, "hits": 124},
        "DataUtil.DataTableToXml": {"files": 27, "hits": 71},
        "dbClient.ExecSPTrn": {"files": 24, "hits": 32},
        "dbClient.ExecSP": {"files": 5, "hits": 5},
        "GetFocusedDataRow": {"files": 27, "hits": 74},
        "dr_index_ToString": {"files": 20, "hits": 91},
        "devFnc.InitControl": {"files": 29, "hits": 154},
    },
    "designer_pattern_counts": {
        "u_GridControl": {"files": 35, "hits": 221},
        "u_GridView": {"files": 21, "hits": 235},
        "u_TextEdit": {"files": 25, "hits": 1990},
        "u_ButtonEdit": {"files": 11, "hits": 176},
        "u_DateEdit": {"files": 28, "hits": 206},
        "u_SpinEdit": {"files": 18, "hits": 922},
        "u_RadioButton": {"files": 16, "hits": 265},
        "u_CheckEdit": {"files": 12, "hits": 246},
        "BindingField": {"files": 31, "hits": 754},
        "explicit_GridColumn_fields": {"files": 34, "hits": 2336},
        "Columns.AddRange": {"files": 35, "hits": 93},
        "AppearanceHeader.Options.UseFont": {"files": 34, "hits": 2493},
        "AppearanceHeader.HAlignment.Center": {"files": 34, "hits": 2578},
        "AppearanceHeader.VAlignment.Center": {"files": 33, "hits": 2072},
        "AppearanceCell.Options.UseFont": {"files": 35, "hits": 2432},
        "ColumnEdit_repository": {"files": 26, "hits": 387},
        "RepositoryItemSpinEdit": {"files": 27, "hits": 791},
        "TabIndex": {"files": 37, "hits": 1911},
    },
    "zero_hit_generated_patterns": {
        "private_sealed_class": 0,
        "context_class_or_GetContext": 0,
        "GetEditValue_helper": 0,
        "GetColumnText_helper": 0,
        "DBNull_ternary_row_value": 0,
        "SelectType_DETAIL_ternary": 0,
        "percent_null_coalesce": 0,
        "ButtonEdit_null_string_empty_ternary": 0,
        "radio_Convert_ToString_local": 0,
        "CallSelectProcedure_inline_wildcard_argument": 0,
        "CSharp_like_wildcard_shaping": 0,
        "DateEdit_null_SetToDay_default": 0,
        "DateEdit_year_or_now_parameter_shaping": 0,
        "generated_date_boundary_DateTime_block": 0,
        "direct_grid_datasource_null_reset": 0,
        "CallDetailQuery_generated_method": 0,
    },
    "positive_generation_recipe": {
        "source_priority": [
            "author-tagged SP definition",
            "normalized program key from procedure name",
            "same-program primary C# file",
            "same-program Designer file",
            "same-module neighbor only when the active program is excluded or unmapped",
        ],
        "screen_base": {
            "normal_screen": "FrmDevBase",
            "popup_screen": "FrmPopBase",
            "evidence": "34 normal screens and 3 popup screens in the matched baseline",
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
            "use devFnc.InitControl(grd*) or matched local reset helpers for KoneLib grid resets",
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
    "AS100100": [r"Programs\50.품질(QC)\Konesystem.QC02\AS100100.cs", r"Programs\50.품질(QC)\Konesystem.QC02\AS100100.Designer.cs"],
    "AS100110": [r"Programs\50.품질(QC)\Konesystem.QC02\AS100110.cs", r"Programs\50.품질(QC)\Konesystem.QC02\AS100110.Designer.cs"],
    "AS200100": [r"Programs\50.품질(QC)\Konesystem.QC02\AS200100.cs", r"Programs\50.품질(QC)\Konesystem.QC02\AS200100.Designer.cs"],
    "AS200110": [r"Programs\50.품질(QC)\Konesystem.QC02\AS200110.cs", r"Programs\50.품질(QC)\Konesystem.QC02\AS200110.Designer.cs"],
    "BA000100": [r"Programs\10.기준(BA)\Konesystem.BA01\BA000100.cs", r"Programs\10.기준(BA)\Konesystem.BA01\BA000100.Designer.cs"],
    "BA000200": [r"Programs\10.기준(BA)\Konesystem.BA01\BA000200.cs", r"Programs\10.기준(BA)\Konesystem.BA01\BA000200.Designer.cs"],
    "BA000500": [r"Programs\10.기준(BA)\Konesystem.BA01\BA000500.cs", r"Programs\10.기준(BA)\Konesystem.BA01\BA000500.Designer.cs"],
    "BA000600": [r"Programs\10.기준(BA)\Konesystem.BA01\BA000600.cs", r"Programs\10.기준(BA)\Konesystem.BA01\BA000600.Designer.cs"],
    "BA000700": [r"Programs\10.기준(BA)\Konesystem.BA01\BA000700.cs", r"Programs\10.기준(BA)\Konesystem.BA01\BA000700.Designer.cs"],
    "DE000500": [r"Programs\60.설계(DE)\Konesystem.DE01\DE000500.cs", r"Programs\60.설계(DE)\Konesystem.DE01\DE000500.Designer.cs"],
    "DE000600": [r"Programs\60.설계(DE)\Konesystem.DE01\DE000600.cs", r"Programs\60.설계(DE)\Konesystem.DE01\DE000600.Designer.cs"],
    "DE000700": [r"Programs\60.설계(DE)\Konesystem.DE01\DE000700.cs", r"Programs\60.설계(DE)\Konesystem.DE01\DE000700.Designer.cs"],
    "DE100100": [r"Programs\60.설계(DE)\Konesystem.DE01\DE100100.cs", r"Programs\60.설계(DE)\Konesystem.DE01\DE100100.Designer.cs"],
    "DE600100": [r"Programs\60.설계(DE)\Konesystem.DE01\DE600100.cs", r"Programs\60.설계(DE)\Konesystem.DE01\DE600100.Designer.cs"],
    "MA100100": [r"Programs\30.자재물류(MA)\Konesystem.MA01\MA100100.cs", r"Programs\30.자재물류(MA)\Konesystem.MA01\MA100100.Designer.cs"],
    "MA100100_POP": [r"Programs\30.자재물류(MA)\Konesystem.MA01\POP\MA100100_POP.cs", r"Programs\30.자재물류(MA)\Konesystem.MA01\POP\MA100100_POP.Designer.cs"],
    "MA100200": [r"Programs\30.자재물류(MA)\Konesystem.MA01\MA100200.cs", r"Programs\30.자재물류(MA)\Konesystem.MA01\MA100200.Designer.cs"],
    "MA200100": [r"Programs\30.자재물류(MA)\Konesystem.MA01\MA200100.cs", r"Programs\30.자재물류(MA)\Konesystem.MA01\MA200100.Designer.cs"],
    "MA400100": [r"Programs\30.자재물류(MA)\Konesystem.MA01\MA400100.cs", r"Programs\30.자재물류(MA)\Konesystem.MA01\MA400100.Designer.cs"],
    "PR100350": [r"Programs\40.생산(PR)\Konesystem.PR01\PR100350.cs", r"Programs\40.생산(PR)\Konesystem.PR01\PR100350.Designer.cs"],
    "PR100350_USERPOP": [r"Programs\40.생산(PR)\Konesystem.PR01\POP\PR100350_USERPOP.cs", r"Programs\40.생산(PR)\Konesystem.PR01\POP\PR100350_USERPOP.Designer.cs"],
    "PR300100": [r"Programs\40.생산(PR)\Konesystem.PR01\PR300100.cs", r"Programs\40.생산(PR)\Konesystem.PR01\PR300100.Designer.cs"],
    "PR300110": [r"Programs\40.생산(PR)\Konesystem.PR01\PR300110.cs", r"Programs\40.생산(PR)\Konesystem.PR01\PR300110.Designer.cs"],
    "PR300120": [r"Programs\40.생산(PR)\Konesystem.PR01\PR300120.cs", r"Programs\40.생산(PR)\Konesystem.PR01\PR300120.Designer.cs"],
    "PR300500": [r"Programs\40.생산(PR)\Konesystem.PR01\PR300500.cs", r"Programs\40.생산(PR)\Konesystem.PR01\PR300500.Designer.cs"],
    "PR600100": [r"Programs\40.생산(PR)\Konesystem.PR01\PR600100.cs", r"Programs\40.생산(PR)\Konesystem.PR01\PR600100.Designer.cs"],
    "PR600200": [r"Programs\40.생산(PR)\Konesystem.PR01\PR600200.cs", r"Programs\40.생산(PR)\Konesystem.PR01\PR600200.Designer.cs"],
    "QC000100": [r"Programs\50.품질(QC)\Konesystem.QC01\QC000100.cs", r"Programs\50.품질(QC)\Konesystem.QC01\QC000100.Designer.cs"],
    "QC100100": [r"Programs\50.품질(QC)\Konesystem.QC01\QC100100.cs", r"Programs\50.품질(QC)\Konesystem.QC01\QC100100.Designer.cs"],
    "SA100100": [r"Programs\20.영업(SA)\Konesystem.SA01\SA100100.cs", r"Programs\20.영업(SA)\Konesystem.SA01\SA100100.Designer.cs"],
    "SA100100_COPYPOP": [r"Programs\20.영업(SA)\Konesystem.SA01\POP\SA100100_COPYPOP.cs", r"Programs\20.영업(SA)\Konesystem.SA01\POP\SA100100_COPYPOP.Designer.cs"],
    "SA100110": [r"Programs\20.영업(SA)\Konesystem.SA01\SA100110.cs", r"Programs\20.영업(SA)\Konesystem.SA01\SA100110.Designer.cs"],
    "SA200100": [r"Programs\20.영업(SA)\Konesystem.SA01\SA200100.cs", r"Programs\20.영업(SA)\Konesystem.SA01\SA200100.Designer.cs"],
    "SA200150": [r"Programs\20.영업(SA)\Konesystem.SA01\SA200150.cs", r"Programs\20.영업(SA)\Konesystem.SA01\SA200150.Designer.cs"],
    "SA400100": [r"Programs\20.영업(SA)\Konesystem.SA01\SA400100.cs", r"Programs\20.영업(SA)\Konesystem.SA01\SA400100.Designer.cs"],
    "SA800100": [r"Programs\20.영업(SA)\Konesystem.SA02\SA800100.cs", r"Programs\20.영업(SA)\Konesystem.SA02\SA800100.Designer.cs"],
    "TEST": [r"Programs\10.기준(BA)\Konesystem.BA01\TEST.cs", r"Programs\10.기준(BA)\Konesystem.BA01\TEST.Designer.cs"],
}


def get_author_tagged_csharp_style_baseline() -> Dict[str, Any]:
    """Return the bundled author-tagged SP-to-C# style evidence snapshot."""
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


def _load_author_tagged_program_style_profile(program_key: str) -> Dict[str, Any]:
    """Load the bundled per-program profile without requiring the user's source tree."""
    key = str(program_key or "").upper()
    if not key:
        return {}
    profile_path = (
        Path(__file__).resolve().parents[2]
        / "skills"
        / "pb_to_csharp_migration_harness"
        / "references"
        / "author-tagged-program-style-profiles.json"
    )
    try:
        with profile_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    profile = payload.get("profiles", {}).get(key, {})
    return dict(profile) if isinstance(profile, dict) else {}


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


def resolve_author_tagged_style_evidence(
    procedure_name: str,
    *,
    csharp_root: str = "",
) -> HarnessResult:
    """Resolve author-tagged SP style evidence through the program-key C# mapping."""
    program_key = normalize_author_tagged_program_key(procedure_name)
    exclusions = {key.upper(): value for key, value in AUTHOR_TAGGED_CSHARP_STYLE_BASELINE["baseline_exclusions"].items()}
    relative_paths = AUTHOR_TAGGED_PROGRAM_CSHARP_MAPPINGS.get(program_key, [])
    discovered_paths = _discover_author_tagged_csharp_paths(program_key, csharp_root)
    evidence_paths = discovered_paths or [
        os.path.normpath(os.path.join(csharp_root, rel_path)) if csharp_root else rel_path
        for rel_path in relative_paths
    ]
    exists = [os.path.exists(path) for path in evidence_paths] if csharp_root else []
    status = "matched"
    if program_key in exclusions:
        status = "excluded"
    elif not relative_paths:
        status = "unmapped"
    elif csharp_root and len(discovered_paths) < 2:
        status = "stale_or_missing"
    elif csharp_root and exists and not all(exists):
        status = "stale_or_missing"
    style_profile: Dict[str, Any] = {}
    if status == "matched" and csharp_root and len(evidence_paths) >= 2 and all(os.path.exists(path) for path in evidence_paths[:2]):
        try:
            with open(evidence_paths[0], "r", encoding="utf-8-sig", errors="ignore") as source_file:
                source_text = source_file.read()
            with open(evidence_paths[1], "r", encoding="utf-8-sig", errors="ignore") as designer_file:
                designer_text = designer_file.read()
            style_profile = _build_author_tagged_screen_style_profile(program_key, source_text, designer_text)
        except OSError:
            style_profile = {}
    if status == "matched" and not style_profile:
        style_profile = _load_author_tagged_program_style_profile(program_key)
    metadata = {
        "harness": "pb-to-csharp-migration-harness",
        "procedure_name": procedure_name,
        "program_key": program_key,
        "status": status,
        "primary_style_evidence_paths": evidence_paths,
        "path_exists": exists,
        "missing_style_evidence_paths": [
            path for path, path_exists in zip(evidence_paths, exists) if not path_exists
        ],
        "exclusion_reason": exclusions.get(program_key, ""),
        "style_profile": style_profile,
        "baseline_counts": {
            "sp_count": AUTHOR_TAGGED_CSHARP_STYLE_BASELINE["sp_count"],
            "normalized_program_key_count": AUTHOR_TAGGED_CSHARP_STYLE_BASELINE["normalized_program_key_count"],
            "primary_csharp_baseline_files_analyzed": AUTHOR_TAGGED_CSHARP_STYLE_BASELINE["primary_csharp_baseline_files_analyzed"],
            "designer_files_analyzed": AUTHOR_TAGGED_CSHARP_STYLE_BASELINE["designer_files_analyzed"],
        },
        "author_tagged_generation_recipe": AUTHOR_TAGGED_CSHARP_STYLE_BASELINE["positive_generation_recipe"],
    }
    success = status == "matched" and bool(relative_paths) and (not csharp_root or all(exists))
    return HarnessResult(
        success=success,
        stdout=json.dumps({"status": status, "program_key": program_key, "evidence_count": len(evidence_paths)}, ensure_ascii=False, sort_keys=True),
        stderr="" if success else "Author-tagged SP did not resolve to fresh primary same-program C# style evidence.",
        exit_code=0 if success else 1,
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


def _extract_sp_procedure_name(sql_text: str) -> str:
    match = SP_PROCEDURE_NAME_PATTERN.search(sql_text or "")
    if not match:
        return ""
    return str(match.group("bracketed") or match.group("plain") or "").upper()


def _display_format_string_looks_numeric(format_string: str) -> bool:
    stripped = format_string.strip()
    if not stripped:
        return False
    return bool(re.fullmatch(r"[#,0.]+", stripped))

KONELIB_CONTROL_TYPES = {
    "grid": "KoneLib.Controls.u_GridControl",
    "text": "KoneLib.Controls.u_TextEdit",
    "label": "KoneLib.Controls.u_Label",
    "group": "KoneLib.Controls.u_GroupControl",
    "panel": "KoneLib.Controls.u_Panel",
    "tab": "KoneLib.Controls.u_TabControl",
    "date": "KoneLib.Controls.u_DateEdit",
    "spin": "KoneLib.Controls.u_SpinEdit",
    "button": "KoneLib.Controls.u_ButtonEdit",
    "combo": "KoneLib.Controls.u_ComboBox",
    "memo": "KoneLib.Controls.u_MemoEdit",
    "check": "KoneLib.Controls.u_CheckEdit",
    "tree": "KoneLib.Controls.u_TreeList",
}
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
) -> HarnessResult:
    """Build a clean SA100100-style detail form layout plan for label/editor pairs."""
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
    pitch = label_width + label_editor_gap + editor_width + column_gap
    specs: List[DetailFormFieldSpec] = []
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
        binding_property = "BindingField"
        specs.append(
            DetailFormFieldSpec(
                logical_name=logical_name,
                field_name=field_name,
                caption=caption,
                editor_type=editor_type,
                csharp_label_name=field.get("csharp_label_name") or f"lbl{_normalize_datawindow_field_name(field_name)}",
                csharp_editor_name=editor_name,
                binding_property=binding_property,
                binding_code=f'this.{editor_name}.BindingField = "{field_name}";',
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
        "status": "passed",
        "section_caption": str(section_caption or "detail"),
        "data_source_name": data_source,
        "field_count": len(specs),
        "columns": safe_columns,
        "layout_rule": (
            "SA100100-style aligned detail form: place label/editor pairs in fixed rows and columns; "
            "use PB/source order and captions, but do not copy PB pixel coordinates blindly."
        ),
        "control_pair_rule": (
            "LabelControl + TextEdit/SpinEdit/DateEdit/LookUpEdit/ButtonEdit/CheckEdit/MemoEdit by field type; "
            "fallback names use observed prefixes txt/btn/cbo/Spin/ymd/Chk/memo plus pn/grp/grd/gvw/treeList/tab for containers."
        ),
        "binding_rule": (
            "Each editor carries the source field name and a target-project BindingField assignment. "
            "Existing target control names override generated fallback names."
        ),
        "tab_order_rule": "Input editor TabIndex follows the generated left-to-right, top-to-bottom row/column order.",
        "fields": [spec.to_dict() for spec in specs],
    }
    return HarnessResult(
        success=True,
        stdout=json.dumps(metadata, ensure_ascii=False, indent=2),
        stderr="",
        exit_code=0,
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
    target_style_text = " ".join(
        [
            input_state.target_style,
            input_state.target_project_name,
            input_state.procedure_name,
            input_state.program_key,
        ]
    ).upper()
    author_tagged_required = bool(
        input_state.author_tagged_required
        or "C_KONE110" in target_style_text
        or "KH" in target_style_text
        or input_state.procedure_name
        or input_state.program_key
    )
    resolved_program_key = (
        input_state.program_key.upper()
        if input_state.program_key
        else normalize_author_tagged_program_key(input_state.procedure_name)
    )
    author_tagged_style_resolution: Dict[str, Any] = {
        "required": author_tagged_required,
        "status": "not_requested",
        "program_key": resolved_program_key,
        "fallback_program_key": input_state.fallback_program_key.upper(),
        "primary_style_evidence_paths": list(input_state.primary_style_evidence_paths),
        "generation_recipe": AUTHOR_TAGGED_CSHARP_STYLE_BASELINE["positive_generation_recipe"] if author_tagged_required else {},
    }
    if author_tagged_required:
        if input_state.primary_style_evidence_paths:
            expected_key = input_state.fallback_program_key.upper() or resolved_program_key
            author_tagged_style_resolution.update(
                {
                    "status": "provided",
                    "expected_style_program_key": expected_key,
                    "path_match": _author_tagged_evidence_paths_match(
                        expected_key,
                        input_state.primary_style_evidence_paths,
                    ),
                }
            )
        elif input_state.procedure_name:
            resolved = resolve_author_tagged_style_evidence(input_state.procedure_name)
            author_tagged_style_resolution.update(resolved.metadata)
        elif resolved_program_key:
            expected_paths = _expected_author_tagged_style_paths(resolved_program_key)
            author_tagged_style_resolution.update(
                {
                    "status": "matched" if expected_paths else "unmapped",
                    "expected_style_program_key": resolved_program_key,
                    "primary_style_evidence_paths": expected_paths,
                    "path_match": bool(expected_paths),
                }
            )
        else:
            author_tagged_style_resolution.update(
                {
                    "status": "blocked",
                    "blocked_reason": "author_tagged_style_requested_without_procedure_or_program_key",
                }
            )
    steps = [
        "Frame the PB screen/program objective, operator workflow, and target C# surface.",
        "Select the PBL export provider: PblScripter wrapper, direct ORCA, pre-exported source, pasted source, described behavior, or bundled fallback.",
        "Match the PB/ORCA runtime version to the PBL lineage before opening or exporting libraries.",
        "Collect PB evidence from exported .sru/.srw/.srd files, pasted source, user-described behavior, or bundled fallback references.",
        "Separate confirmed behavior from inferred behavior when PB source is absent.",
        "Trace SRU/SRW event flow before DataWindow SQL so popup/save behavior is not missed.",
        "Map DataWindow columns to target-project controls; fall back to DevExpress and then WinForms basics when needed.",
        "For detail forms, lay out label/editor pairs in clean aligned rows and columns instead of blindly copying PB coordinates.",
        "Resolve the target-project control stack before generating C# so project-specific controls are not replaced by a fixed TY/KoneLib assumption.",
        "For C_KONE110/KH style, resolve author-tagged SP -> program key -> same-program C#/Designer evidence before generating code.",
        "Draft C# flow by preserving existing target-project method paths such as CallViewQuery, CallProc, SelectType, DataTableToXml, and SetModified when present.",
        "Draft SELECT/SAVE stored procedures from the packaged KH SP style reference and host-local sql-formatting contract.",
        "Separate formatting-only cleanup from semantic/performance rewrites; require DB-backed evidence for semantic changes.",
        "Produce a migration checklist, traceability table, and verification plan before implementation claims.",
    ]
    deliverables = [
        "PBL export provider and PB version strategy",
        "PB source analysis notes",
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
        "author_tagged_style_resolution": author_tagged_style_resolution,
        "token_optimizer_status": "passthrough",
        "token_optimizer_status_reason": (
            "PB source, SQL, C# style rules, and business literals are source-of-truth content; do not compress them."
        ),
    }
    return HarnessResult(
        success=bool(objective.strip()),
        stdout=json.dumps(payload, ensure_ascii=False, sort_keys=True),
        stderr="" if objective.strip() else "Migration objective is required.",
        exit_code=0 if objective.strip() else 1,
        metadata=payload,
    )


def extract_datawindow_columns(source_text: str) -> List[str]:
    """Extract SRD column names using the same narrow column=(... name=...) rule as the local HTML helper."""
    return [spec.field_name for spec in extract_datawindow_column_specs(source_text)]


def extract_datawindow_column_specs(source_text: str, *, prefix: str = "colList_") -> List[DataWindowColumnSpec]:
    """Extract DataWindow grid columns, C# column names, and best-effort captions from SRD text."""
    source = str(source_text or "")
    starts = [match.start() for match in DATAWINDOW_COLUMN_PATTERN.finditer(source)]
    table_columns: List[str] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(source)
        name_match = DATAWINDOW_NAME_PATTERN.search(source[start:end])
        if name_match:
            table_columns.append(_normalize_datawindow_field_name(name_match.group("name")))

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
                source="visual-column",
                x=column.get("x"),
                y=column.get("y"),
                width=column.get("width"),
                height=column.get("height"),
            )
        )
        seen.add(field_name)

    for field_name in table_columns:
        if field_name in seen:
            continue
        specs.append(
            DataWindowColumnSpec(
                field_name=field_name,
                caption=field_name,
                csharp_name=build_csharp_grid_column_name(field_name, prefix=prefix),
            )
        )
        seen.add(field_name)
    return specs


def build_csharp_grid_column_name(field_name: str, *, prefix: str = "colList_") -> str:
    """Build a target C# GridColumn member/control name such as colList_ITEMCD."""
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

    numeric_repository_by_column: Dict[str, str] = {}
    for column in normalized:
        field_upper = str(column.field_name or "").upper()
        if _is_numeric_grid_field_name(field_upper):
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
        "status": "passed",
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
        "designer_contract": (
            "Use explicit GridColumn members and Columns.AddRange with colList_/colDetail_/col<TABLE>_/col<PURPOSE>_ "
            "names. Do not generate runtime AddGridColumn, Columns.AddField, or view.Name + \"_\" + fieldName helpers by default."
        ),
        "token_optimizer_status": "passthrough",
        "token_optimizer_status_reason": "Generated Designer code is contract-sensitive and was not compressed.",
    }
    return HarnessResult(
        success=True,
        stdout="\n".join(designer_lines),
        stderr="",
        exit_code=0,
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


def verify_migration_generated_csharp_style(
    source_text: str,
    *,
    program_key: str = "",
    fallback_program_key: str = "",
    primary_style_evidence_paths: Any = None,
    excluded_paths: Any = None,
    require_author_tagged_evidence: bool = False,
) -> HarnessResult:
    """Block generated C# patterns that do not match the target Designer/grid style."""
    source = str(source_text or "")
    issues: List[Dict[str, Any]] = []
    normalized_program_key = str(program_key or "").upper()
    primary_paths = [str(path) for path in (primary_style_evidence_paths or []) if str(path)]
    excluded = [str(path) for path in (excluded_paths or []) if str(path)]

    if require_author_tagged_evidence and not primary_paths:
        issues.append(
            {
                "code": "author_tagged_style_evidence_required",
                "severity": "error",
                "message": (
                    "C_KONE110/KH-style generated C# must name primary style evidence resolved from "
                    "author-tagged SP -> program key -> matching C# screen source."
                ),
            }
        )
    excluded_keys = {key.upper() for key in AUTHOR_TAGGED_CSHARP_STYLE_BASELINE["baseline_exclusions"]}
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
                        "resolved from established author-tagged same-module evidence."
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
                        "Primary style evidence must match the author-tagged SP -> program key -> same-program "
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
                    "message": "No bundled author-tagged C# mapping exists for the requested style program key.",
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
                    "Matched C_KONE110/KH screen retrieve code keeps explicit DbParameter entries near "
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
                    "GridColumn generation did not expose target-style column names such as colList_ITEMCD."
                ),
            }
        )

    if re.search(r"\bprivate\s+sealed\s+class\s+[A-Za-z_][A-Za-z0-9_]*\s*", source):
        issues.append(
            {
                "code": "generated_internal_dto_class_detected",
                "severity": "error",
                "message": (
                    "C_KONE110/KH-style screen retrieval code should not invent private sealed DTO/context "
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
                "message": "Do not generate private SearchParams/Request/Criteria helper classes for C_KONE110/KH-style screen code.",
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
                "message": "Do not generate a generic GetEditValue helper for ordinary C_KONE110/KH-style screen code.",
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
                "message": "Do not generate a generic GetColumnText helper for ordinary C_KONE110/KH-style screen code.",
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
            "Do not invent CallDetailQuery for C_KONE110/KH focused-row detail handling; use the target event shape or proven fnFocusedRowChanged/CallViewQuery pattern.",
        ),
        "generated_default_search_values_helper_detected": (
            r"\b(?:private|protected|public|internal)?\s*(?:static\s+)?void\s+SetDefaultSearchValues\s*\(",
            "Do not invent SetDefaultSearchValues for ordinary C_KONE110/KH screens; set default control values directly in Load/Clear unless a target file proves that helper.",
        ),
        "generated_list_column_layout_helper_detected": (
            r"\b(?:private|protected|public|internal)?\s*(?:static\s+)?void\s+ApplyListColumnLayout\s*\(",
            "Do not invent ApplyListColumnLayout/runtime column-layout helpers; preserve Designer columns and use narrow direct assignments only when required.",
        ),
        "generated_basis_year_helper_detected": (
            r"\b(?:private|protected|public|internal)?\s*(?:static\s+)?string\s+GetBasisYear\s*\(",
            "Do not invent GetBasisYear for u_DateEdit year inputs; read the date control near the procedure call in the same style as existing screens.",
        ),
        "generated_customer_like_helper_detected": (
            r"\b(?:private|protected|public|internal)?\s*(?:static\s+)?string\s+GetCustomerLike\s*\(",
            "Do not invent GetCustomerLike wrappers; keep simple LIKE parameter composition near the SP call unless target code already has the helper.",
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
    if "PopCustFrm" in source and re.search(r"DialogResult\.Yes\s*\|\|\s*di\s*==\s*DialogResult\.OK|DialogResult\.OK\s*\|\|\s*di\s*==\s*DialogResult\.Yes", source):
        issues.append(
            {
                "code": "popcust_dialogresult_yes_or_ok_detected",
                "severity": "error",
                "message": "PopCustFrm selection should follow the target popup contract; do not broaden it to DialogResult.Yes || DialogResult.OK without source evidence.",
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
                "message": "Do not generate DBNull ternary wrappers around focused-row values for ordinary C_KONE110/KH detail lookups; follow target direct row-value access unless source proves otherwise.",
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
                "message": "Do not generate CallSelectProcedure call-site arguments that inline LIKE wildcards such as btnCUSTCD.Text + \"%\" or rowValue + \"%\"; pass raw values and let the stored procedure own LIKE shaping.",
            }
        )
    if re.search(r"\b(?:custcd|itemcd|[A-Za-z0-9_]*(?:cd|CD))\s*=\s*[^;\n]+\+\s*\"%\"\s*;", source) or re.search(
        r"\b(?:custcd|itemcd|[A-Za-z0-9_]*(?:cd|CD))\s*=\s*\"%\"\s*;",
        source,
    ):
        issues.append(
            {
                "code": "generated_csharp_like_wildcard_shaping_detected",
                "severity": "error",
                "message": "Do not generate C# wildcard shaping such as custcd = custcd + \"%\" or itemcd = \"%\" for migration SELECT parameters; pass raw values and handle LIKE defaults in the stored procedure.",
            }
        )
    if re.search(
        r"if\s*\(\s*(ymd[A-Z0-9_]*)\.EditValue\s*==\s*null\s*\)\s*(?:\{\s*)?\1\.SetToDay\s*\(\s*0\s*\)",
        source,
    ):
        issues.append(
            {
                "code": "generated_dateedit_settoday_null_default_detected",
                "severity": "error",
                "message": "Do not generate DateEdit null guards that silently call SetToDay(0) inside search/procedure paths; initialize in Load/Clear or validate before execution.",
            }
        )
    if re.search(r'new\s+DbParameter\s*\(\s*"@(?:YYYY|BASYYYY)"\s*,\s*ymd[A-Z0-9_]*\.DateTime\.Year\.ToString\s*\(\s*\)\s*\)', source) or re.search(
        r'new\s+DbParameter\s*\(\s*"@(?:MM|BASYYYY)"\s*,\s*DateTime\.Now\.[A-Za-z]+\.ToString\s*\(',
        source,
    ):
        issues.append(
            {
                "code": "generated_dateedit_year_or_now_parameter_shaping_detected",
                "severity": "error",
                "message": "Do not generate C# parameters that split u_DateEdit values into @YYYY/@MM/@BASYYYY with DateTime.Year.ToString() or DateTime.Now; pass the target-style raw YYYYMMDD() value and let the stored procedure derive related date parameters.",
            }
        )
    if re.search(r"\bgrd[A-Za-z0-9_]*\.DataSource\s*=\s*null\s*;", source):
        issues.append(
            {
                "code": "generated_direct_grid_datasource_null_reset_detected",
                "severity": "error",
                "message": "Do not generate direct grd*.DataSource = null resets for KoneLib-style screens; use devFnc.InitControl(grd*) unless the active target source proves otherwise.",
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
    if re.search(r"new\s+DateTime\s*\(\s*ymd[A-Z0-9_]*\.DateTime\.Year\s*-\s*1\s*,\s*12\s*,\s*31\s*\)", source):
        issues.append(
            {
                "code": "generated_year_end_datetime_block_detected",
                "severity": "error",
                "message": "Do not generate ad hoc year-end DateTime construction blocks from DateEdit values unless matched target evidence proves that exact pattern.",
            }
        )
    if re.search(r"\(\s*ymd[A-Z0-9_]*\.DateTime\.Year\s*-\s*1\s*\)\s*\.ToString\s*\(\s*\"0000\"\s*\)\s*\+\s*\"1231\"", source):
        issues.append(
            {
                "code": "generated_year_end_string_boundary_detected",
                "severity": "error",
                "message": "Do not generate year-end boundary strings such as (ymdGIJUN.DateTime.Year - 1).ToString(\"0000\") + \"1231\" in C#; let the stored procedure own derived date boundaries.",
            }
        )
    if re.search(r"\?\?\s*\"%\"", source):
        issues.append(
            {
                "code": "generated_percent_null_coalesce_detected",
                "severity": "error",
                "message": "Do not generate null-coalescing wildcard defaults such as _itemcd ?? \"%\" for migration C# unless the target code proves that pattern.",
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
    if re.search(r"KoneLib\.Controls\.u_DateEdit\s+txt[A-Z0-9_]*NM\b", source):
        issues.append(
            {
                "code": "text_name_field_generated_as_dateedit",
                "severity": "error",
                "message": "Name/display fields such as txtCUSTNM should use a text edit, not u_DateEdit.",
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
        "primary_style_evidence_paths": primary_paths,
        "excluded_paths": excluded,
        "author_tagged_baseline_counts": {
            "sp_count": AUTHOR_TAGGED_CSHARP_STYLE_BASELINE["sp_count"],
            "normalized_program_key_count": AUTHOR_TAGGED_CSHARP_STYLE_BASELINE["normalized_program_key_count"],
            "primary_csharp_baseline_files_analyzed": AUTHOR_TAGGED_CSHARP_STYLE_BASELINE["primary_csharp_baseline_files_analyzed"],
            "designer_files_analyzed": AUTHOR_TAGGED_CSHARP_STYLE_BASELINE["designer_files_analyzed"],
        },
        "author_tagged_generation_recipe": AUTHOR_TAGGED_CSHARP_STYLE_BASELINE["positive_generation_recipe"],
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
) -> HarnessResult:
    """Check that generated SELECT/SAVE SP work is evidence-gated before it is presented as migration output."""
    sql = str(sql_text or "")
    issues: List[Dict[str, Any]] = []
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
                    "C_KONE110/KH-style procedure output must include the standard metadata comment block "
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
        if expected_descriptions and not any(
            expected in header_description or header_description in expected
            for expected in expected_descriptions
        ):
            issues.append(
                {
                    "code": "sp_metadata_description_mismatch",
                    "severity": "error",
                    "message": "DESCRIPTION must match the target program/screen name recorded in source evidence.",
                    "expected_descriptions": expected_descriptions,
                    "actual_description": header_description,
                }
            )
        if (
            header_description == "총괄조회 조회"
            and procedure_name
            and not procedure_name.startswith("SP_SA900100_")
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
                "message": "C_KONE110/KH-style procedures do not default @WORKTYPE to an empty string; use NULL or the verified required parameter contract.",
            }
        )
    if re.search(r"@(CUSTCD|ITEMCD)\s+(?:N?VARCHAR|N?CHAR)\s*\([^)]*\)\s*=\s*'%'", upper_comments_stripped):
        issues.append(
            {
                "code": "wildcard_filter_parameter_default_detected",
                "severity": "error",
                "message": "Do not default filter parameters such as @CUSTCD or @ITEMCD to '%' unless verified target SP evidence uses that exact contract.",
            }
        )
    if re.search(r"@(GUBUN|GB)\s+(?:N?VARCHAR|N?CHAR)\s*\([^)]*\)\s*=\s*'(?:T|1)'", upper_comments_stripped):
        issues.append(
            {
                "code": "business_flag_parameter_default_detected",
                "severity": "error",
                "message": "Do not default business selector parameters such as @GUBUN or @GB to generated literals unless verified target SP evidence uses them.",
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
                    r"@(YYYY|MM|BASYYYY|LASTDT)\s+(?:\[[^\]]+\]|[A-Z][A-Z0-9_]*)(?:\s*\.\s*(?:\[[^\]]+\]|[A-Z][A-Z0-9_]*))?(?:\s*\([^)]*\))?",
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
                        "Do not expose derived helper date values such as @YYYY, @MM, @BASYYYY, or @LASTDT "
                        "as generated procedure parameters. Accept the raw target-style date input, then use local DECLARE and SET "
                        "inside the procedure when derived values are needed."
                    ),
                    "parameters": [f"@{name}" for name in helper_date_params],
                }
            )
    if re.search(
        r"IF\s*\(?\s*ISNULL\s*\(\s*@(GIJUNDT|YYYY|MM|BASYYYY|LASTDT)\s*,\s*''\s*\)",
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
        r"SET\s+@(YYYY|MM|BASYYYY|LASTDT)\s*=\s*(?:LEFT\s*\(\s*@GIJUNDT|SUBSTRING\s*\(\s*@GIJUNDT|RIGHT\s*\(\s*'0'\s*\+|CONVERT\s*\(\s*VARCHAR\s*\(\s*[48]\s*\)\s*,\s*(?:YEAR|DATEADD|CONVERT))",
        upper_comments_stripped,
    ) and re.search(
        r"IF\s*\(?\s*(?:ISNULL\s*\(\s*@(GIJUNDT|YYYY|MM|BASYYYY|LASTDT)|@(GIJUNDT|YYYY|MM|BASYYYY|LASTDT)\s*(?:<>|=|>|<|>=|<=))",
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
        r"IF\s*\(?\s*@(GIJUNDT|YYYY|MM|BASYYYY|LASTDT)\s*(?:<>|=|>|<|>=|<=)[\s\S]{0,240}\bSET\s+@(YYYY|MM|BASYYYY|LASTDT)\s*=",
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

    passed = not any(issue["severity"] == "error" for issue in issues)
    metadata = {
        "harness": "pb-to-csharp-migration-harness",
        "status": "passed" if passed else "blocked",
        "source_evidence": accepted_source_evidence,
        "source_evidence_count": len(accepted_source_evidence),
        "allow_inferred_draft": bool(allow_inferred_draft),
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

def verify_pb_migration_sp_with_sql_formatting(
    original_sql_text: str,
    formatted_sql_text: str,
    *,
    source_evidence: Any = None,
    allow_inferred_draft: bool = False,
    cte_temp_table_reason: str = "",
) -> HarnessResult:
    """Verify migration SP evidence and host-local SQL formatting style as one composed gate."""
    from src.skills.sql_formatting_style import verify_sql_formatting_style

    contract_result = verify_pb_migration_sp_generation_contract(
        formatted_sql_text,
        source_evidence=source_evidence,
        allow_inferred_draft=allow_inferred_draft,
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
                        source=str(item.get("source") or "provided"),
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
        if available_controls.get("has_konelib") or available_controls.get("konelib"):
            inventory["types"].update(KONELIB_CONTROL_TYPES.values())
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
