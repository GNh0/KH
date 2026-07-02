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


@dataclass(frozen=True)
class MigrationInputState:
    """Portable evidence state for PB -> C# migration planning."""

    has_pblscripter: bool = False
    has_exported_pb_sources: bool = False
    has_datawindow_converter: bool = False
    has_ty_csharp_samples: bool = False
    has_sp_style_reference: bool = False
    has_live_db_access: bool = False
    has_pasted_source: bool = False
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_pblscripter": self.has_pblscripter,
            "has_exported_pb_sources": self.has_exported_pb_sources,
            "has_datawindow_converter": self.has_datawindow_converter,
            "has_ty_csharp_samples": self.has_ty_csharp_samples,
            "has_sp_style_reference": self.has_sp_style_reference,
            "has_live_db_access": self.has_live_db_access,
            "has_pasted_source": self.has_pasted_source,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MigrationInputState":
        return cls(
            has_pblscripter=bool(data.get("has_pblscripter", False)),
            has_exported_pb_sources=bool(data.get("has_exported_pb_sources", False)),
            has_datawindow_converter=bool(data.get("has_datawindow_converter", False)),
            has_ty_csharp_samples=bool(data.get("has_ty_csharp_samples", False)),
            has_sp_style_reference=bool(data.get("has_sp_style_reference", False)),
            has_live_db_access=bool(data.get("has_live_db_access", False)),
            has_pasted_source=bool(data.get("has_pasted_source", False)),
            notes=[str(item) for item in data.get("notes", [])],
        )


def classify_migration_mode(state: MigrationInputState | Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Classify whether the migration run is standalone, partial-reference, full-reference, or pasted-source."""
    input_state = _coerce_state(state)
    if input_state.has_exported_pb_sources and input_state.has_ty_csharp_samples and input_state.has_sp_style_reference:
        mode = "full-reference"
        confidence = 0.9 if input_state.has_live_db_access else 0.82
    elif input_state.has_pasted_source:
        mode = "pasted-source"
        confidence = 0.74
    elif any(
        [
            input_state.has_pblscripter,
            input_state.has_exported_pb_sources,
            input_state.has_datawindow_converter,
            input_state.has_ty_csharp_samples,
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
    if input_state.has_ty_csharp_samples:
        strong_evidence.append("representative TY/C_KONE110 C# samples")
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

    return {
        "mode": mode,
        "confidence": confidence,
        "state": input_state.to_dict(),
        "strong_evidence": strong_evidence,
        "weak_evidence": weak_evidence,
        "runtime_lookup_required": False,
        "fallback_policy": (
            "Use bundled references first. Use live PBL, source, converter, C# samples, or DB access only when "
            "the user provides them or explicitly asks for refresh/verification."
        ),
    }


def build_pb_to_csharp_migration_plan(
    objective: str,
    state: MigrationInputState | Dict[str, Any] | None = None,
) -> HarnessResult:
    """Build a deterministic migration plan that works without host-local PB/TY/DB assets."""
    mode = classify_migration_mode(state)
    steps = [
        "Frame the PB screen/program objective, operator workflow, and TY target surface.",
        "Collect PB evidence from exported .sru/.srw/.srd files, pasted source, or bundled fallback references.",
        "Trace SRU/SRW event flow before DataWindow SQL so popup/save behavior is not missed.",
        "Map DataWindow columns to DevExpress GridView columns or a TY form layout using the packaged rules.",
        "Draft TY C# flow by preserving existing CallViewQuery, CallProc, SelectType, DataTableToXml, and SetModified patterns.",
        "Draft SELECT/SAVE stored procedures from the packaged KH SP style reference and host-local sql-formatting contract.",
        "Separate formatting-only cleanup from semantic/performance rewrites; require DB-backed evidence for semantic changes.",
        "Produce a migration checklist, traceability table, and verification plan before implementation claims.",
    ]
    deliverables = [
        "PB source analysis notes",
        "DataWindow column/layout mapping",
        "TY C# implementation plan",
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
        has_ty_csharp_samples=bool(data.get("has_ty_csharp_samples", False)),
        has_sp_style_reference=bool(data.get("has_sp_style_reference", False)),
        has_live_db_access=bool(data.get("has_live_db_access", False)),
        has_pasted_source=bool(data.get("has_pasted_source", False)),
        notes=[str(item) for item in data.get("notes", [])],
    )
