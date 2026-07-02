import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List
from xml.sax.saxutils import escape

from src.contracts import HarnessResult


DATAWINDOW_COLUMN_PATTERN = re.compile(r"column\s*=\s*\(", re.IGNORECASE)
DATAWINDOW_NAME_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])name\s*=\s*\"?(?P<name>[a-zA-Z0-9_#$]+)\"?",
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
    source = str(source_text or "")
    starts = [match.start() for match in DATAWINDOW_COLUMN_PATTERN.finditer(source)]
    columns: List[str] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(source)
        name_match = DATAWINDOW_NAME_PATTERN.search(source[start:end])
        if name_match:
            columns.append(name_match.group("name").upper())
    return columns


def generate_devexpress_grid_xml(
    columns: Iterable[str],
    *,
    prefix: str = "colList_",
    grid_view_name: str = "gridView1",
) -> str:
    """Generate the portable DevExpress GridView XML core produced by the DataWindowToXml helper."""
    normalized = [str(column).strip().upper() for column in columns if str(column).strip()]
    lines = [
        '<XtraSerializer version="1.0" application="View">',
        '  <property name="#LayoutVersion" />',
        "  <property name=\"BestFitMaxRowCount\">-1</property>",
        "  <property name=\"PreviewLineCount\">-1</property>",
        "  <property name=\"HorzScrollStep\">3</property>",
        "  <property name=\"FocusRectStyle\">CellFocus</property>",
        "  <property name=\"ScrollStyle\">LiveVertScroll, LiveHorzScroll</property>",
        "  <property name=\"PreviewIndent\">-1</property>",
        "  <property name=\"GroupPanelText\" />",
        "  <property name=\"GroupFooterShowMode\">VisibleIfExpanded</property>",
        "  <property name=\"SynchronizeClones\">true</property>",
        "  <property name=\"BorderStyle\">Default</property>",
        "  <property name=\"DetailHeight\">350</property>",
        f"  <property name=\"Name\">{escape(grid_view_name)}</property>",
        "  <property name=\"ActiveFilterEnabled\">true</property>",
        f"  <property name=\"Columns\" iskey=\"true\" value=\"{len(normalized)}\">",
    ]
    for index, column in enumerate(normalized, start=1):
        escaped_column = escape(column)
        escaped_name = escape(f"{prefix}{column}")
        lines.extend(
            [
                f"    <property name=\"Item{index}\" isnull=\"true\" iskey=\"true\">",
                "      <property name=\"AppearanceHeader\" isnull=\"true\" iskey=\"true\">",
                "        <property name=\"Options\" isnull=\"true\" iskey=\"true\">",
                "          <property name=\"UseTextOptions\">true</property>",
                "          <property name=\"UseFont\">true</property>",
                "        </property>",
                "        <property name=\"TextOptions\" isnull=\"true\" iskey=\"true\">",
                "          <property name=\"HAlignment\">Center</property>",
                "          <property name=\"VAlignment\">Center</property>",
                "        </property>",
                "        <property name=\"Font\">Tahoma, 9pt</property>",
                "      </property>",
                "      <property name=\"AppearanceCell\" isnull=\"true\" iskey=\"true\">",
                "        <property name=\"Options\" isnull=\"true\" iskey=\"true\">",
                "          <property name=\"UseFont\">true</property>",
                "        </property>",
                "        <property name=\"Font\">Tahoma, 9pt</property>",
                "      </property>",
                "      <property name=\"Visible\">true</property>",
                f"      <property name=\"VisibleIndex\">{index}</property>",
                f"      <property name=\"FieldName\">{escaped_column}</property>",
                f"      <property name=\"Name\">{escaped_name}</property>",
                f"      <property name=\"Caption\">{escaped_column}</property>",
                "      <property name=\"ColumnEditName\" />",
                "    </property>",
            ]
        )
    lines.extend(
        [
            "  </property>",
            "  <property name=\"OptionsView\" isnull=\"true\" iskey=\"true\">",
            "    <property name=\"ShowViewCaption\">false</property>",
            "    <property name=\"EnableAppearanceEvenRow\">true</property>",
            "    <property name=\"ShowGroupPanel\">false</property>",
            "    <property name=\"ColumnAutoWidth\">false</property>",
            "    <property name=\"ShowFooter\">true</property>",
            "    <property name=\"ShowAutoFilterRow\">true</property>",
            "  </property>",
            "</XtraSerializer>",
        ]
    )
    return "\n".join(lines)


def build_datawindow_grid_layout(source_text: str, *, prefix: str = "colList_") -> HarnessResult:
    """Build grid XML from SRD text and return contract-shaped evidence."""
    columns = extract_datawindow_columns(source_text)
    if not columns:
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
    xml = generate_devexpress_grid_xml(columns, prefix=prefix)
    metadata = {
        "harness": "pb-to-csharp-migration-harness",
        "status": "passed",
        "columns": columns,
        "column_count": len(columns),
        "converter_contract": "DataWindowToXml-compatible narrow SRD column-name to DevExpress GridView XML mapping",
    }
    return HarnessResult(
        success=True,
        stdout=xml,
        stderr="",
        exit_code=0,
        metadata=metadata,
    )


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
