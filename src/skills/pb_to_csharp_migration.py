import json
import re
from dataclasses import dataclass, field
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

KONELIB_CONTROL_TYPES = {
    "grid": "KoneLib.Controls.u_GridControl",
    "text": "KoneLib.Controls.u_TextEdit",
    "label": "KoneLib.Controls.u_Label",
    "group": "KoneLib.Controls.u_GroupControl",
    "panel": "KoneLib.Controls.u_Panel",
    "tab": "KoneLib.Controls.u_TabControl",
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
    has_exported_pb_sources: bool = False
    has_datawindow_converter: bool = False
    has_target_csharp_samples: bool = False
    has_ty_csharp_samples: bool = False
    has_sp_style_reference: bool = False
    has_live_db_access: bool = False
    has_pasted_source: bool = False
    has_behavior_description: bool = False
    target_project_name: str = ""
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_pblscripter": self.has_pblscripter,
            "has_exported_pb_sources": self.has_exported_pb_sources,
            "has_datawindow_converter": self.has_datawindow_converter,
            "has_target_csharp_samples": self.has_target_csharp_samples or self.has_ty_csharp_samples,
            "has_ty_csharp_samples": self.has_ty_csharp_samples,
            "has_sp_style_reference": self.has_sp_style_reference,
            "has_live_db_access": self.has_live_db_access,
            "has_pasted_source": self.has_pasted_source,
            "has_behavior_description": self.has_behavior_description,
            "target_project_name": self.target_project_name,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MigrationInputState":
        return cls(
            has_pblscripter=bool(data.get("has_pblscripter", False)),
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


def classify_migration_mode(state: MigrationInputState | Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Classify whether the migration run is standalone, described-behavior, partial-reference, full-reference, or pasted-source."""
    input_state = _coerce_state(state)
    has_csharp_reference = input_state.has_target_csharp_samples or input_state.has_ty_csharp_samples
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
        "runtime_lookup_required": False,
        "fallback_policy": (
            "Use bundled references first. Use user-provided behavior descriptions as inferred requirements, not "
            "source parity. Use live PBL, source, converter, C# samples, or DB access only when the user provides "
            "them or explicitly asks for refresh/verification."
        ),
    }


def resolve_csharp_control_stack(
    available_controls: Dict[str, Any] | Iterable[str] | None = None,
    required_controls: Iterable[str] = ("grid", "text", "label", "group", "panel", "tab"),
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


def build_pb_to_csharp_migration_plan(
    objective: str,
    state: MigrationInputState | Dict[str, Any] | None = None,
) -> HarnessResult:
    """Build a deterministic migration plan that works without host-local PB/C#/DB assets."""
    mode = classify_migration_mode(state)
    input_state = _coerce_state(state)
    control_stack = resolve_csharp_control_stack(dict(state or {}).get("available_controls") if isinstance(state, dict) else None)
    steps = [
        "Frame the PB screen/program objective, operator workflow, and target C# surface.",
        "Collect PB evidence from exported .sru/.srw/.srd files, pasted source, user-described behavior, or bundled fallback references.",
        "Separate confirmed behavior from inferred behavior when PB source is absent.",
        "Trace SRU/SRW event flow before DataWindow SQL so popup/save behavior is not missed.",
        "Map DataWindow columns to target-project controls; fall back to DevExpress and then WinForms basics when needed.",
        "Resolve the target-project control stack before generating C# so project-specific controls are not replaced by a fixed TY/KoneLib assumption.",
        "Draft C# flow by preserving existing target-project method paths such as CallViewQuery, CallProc, SelectType, DataTableToXml, and SetModified when present.",
        "Draft SELECT/SAVE stored procedures from the packaged KH SP style reference and host-local sql-formatting contract.",
        "Separate formatting-only cleanup from semantic/performance rewrites; require DB-backed evidence for semantic changes.",
        "Produce a migration checklist, traceability table, and verification plan before implementation claims.",
    ]
    deliverables = [
        "PB source analysis notes",
        "confirmed vs inferred behavior map",
        "DataWindow column/layout mapping",
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
        "control_stack": control_stack,
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


def _normalize_datawindow_field_name(value: str) -> str:
    return str(value or "").strip().strip('"').upper()


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
    data = dict(state or {})
    return MigrationInputState(
        has_pblscripter=bool(data.get("has_pblscripter", False)),
        has_exported_pb_sources=bool(data.get("has_exported_pb_sources", False)),
        has_datawindow_converter=bool(data.get("has_datawindow_converter", False)),
        has_target_csharp_samples=bool(data.get("has_target_csharp_samples", data.get("has_ty_csharp_samples", False))),
        has_ty_csharp_samples=bool(data.get("has_ty_csharp_samples", False)),
        has_sp_style_reference=bool(data.get("has_sp_style_reference", False)),
        has_live_db_access=bool(data.get("has_live_db_access", False)),
        has_pasted_source=bool(data.get("has_pasted_source", False)),
        has_behavior_description=bool(data.get("has_behavior_description", False)),
        target_project_name=str(data.get("target_project_name", "")),
        notes=[str(item) for item in data.get("notes", [])],
    )


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
                    "DevExpress.XtraEditors.TextEdit",
                    "DevExpress.XtraEditors.LabelControl",
                    "DevExpress.XtraEditors.GroupControl",
                    "DevExpress.XtraEditors.PanelControl",
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
