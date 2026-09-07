"""Retained pb syntax and domain mechanics from KH; no host orchestration."""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from src.common.results import HarnessResult
from .models import (
    DataWindowColumnSpec,
)


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


NUMERIC_GRID_FIELD_TOKENS = ("AMT", "QTY", "UNP", "WGT", "PRICE", "RATE", "COST", "TOTAL")


NUMERIC_GRID_FIELD_SUFFIXES = ("TOT", "BAL")


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


def _grid_column_mapping_issues(column_inputs, normalized, *, prefix):
    issues = []
    seen_csharp, seen_xml = set(), set()
    for column in normalized:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", column.csharp_name):
            issues.append({"code": "grid_column_csharp_name_invalid", "severity": "error", "field_name": column.field_name,
                           "message": "Supply a valid C# member for this field; field names and member names may differ."})
        if column.csharp_name in seen_csharp or column.xml_column_name in seen_xml:
            issues.append({"code": "grid_column_name_duplicate", "severity": "error", "field_name": column.field_name,
                           "message": "Columns need distinct C# members and XML names."})
        seen_csharp.add(column.csharp_name)
        seen_xml.add(column.xml_column_name)
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
        "status": "passed" if passed else "failed",
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
    column_properties: Mapping[str, Mapping[str, str]] | None = None,
    view_properties: Mapping[str, str] | None = None,
) -> HarnessResult:
    """Build an explicit Designer grid equivalent to the authoritative XML Layout Load result."""
    column_inputs = list(columns)
    resolved_prefix = prefix or resolve_csharp_grid_column_prefix(
        input_format, table_name=table_name, purpose_name=purpose_name
    )
    grid_names = resolve_csharp_grid_control_names(input_format, table_name=table_name, purpose_name=purpose_name)
    requested_view_name = str(grid_view_name or "").strip()
    view_name = requested_view_name or grid_names["grid_view_name"]
    normalized = _normalize_grid_column_specs(column_inputs, prefix=resolved_prefix)
    if not normalized:
        return HarnessResult(
            success=False,
            stdout=json.dumps({"columns": [], "status": "failed"}, ensure_ascii=False),
            stderr="No grid columns were provided.",
            exit_code=1,
            metadata={
                "harness": "pb-to-csharp-migration-harness",
                "status": "failed",
                "reason": "missing_grid_columns",
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
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", view_name):
        issues.append({"code": "grid_view_name_invalid", "severity": "error", "message": "Supply a valid GridView member name."})
    numeric_repository_by_column: Dict[str, str] = {}
    for column in normalized:
        if _is_numeric_grid_column(column):
            csharp_field_name = (
                column.csharp_name[len(resolved_prefix) :]
                if column.csharp_name.startswith(resolved_prefix)
                else column.csharp_name
            )
            numeric_repository_by_column[column.csharp_name] = (
                f"rpsSpin{csharp_field_name}"
            )
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
        "status": "passed" if not issues else "failed",
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
        "not_checked": ["actual target control defaults and API version", "Designer rendering", "runtime binding"],
        "designer_contract": (
            "Use explicit grd<Role>/gvw<Role>/col<Role>_<FIELD> members, GridControl/GridView wiring, Columns.AddRange, "
            "and the authoritative DataWindow XML Layout Load defaults. Register repositories before ColumnEdit and "
            "do not copy the serialized gridView1 name into C# Designer output."
        ),
    }
    # These helpers create a draft. Exact target properties supplied by the caller
    # replace template values rather than being rejected as style violations.
    names = {column.field_name: column.csharp_name for column in normalized}
    names.update({column.csharp_name: column.csharp_name for column in normalized})
    overrides = [(view_name, dict(view_properties or {}))]
    for key, properties in (column_properties or {}).items():
        if key not in names:
            issues.append({"code": "column_override_target_missing", "severity": "error", "message": "A property override needs an existing field/member.", "target": key})
        else:
            overrides.append((names[key], dict(properties)))
    for member, properties in overrides:
        for property_name, value in properties.items():
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", property_name) or not isinstance(value, str) or not value.strip():
                issues.append({"code": "designer_override_invalid", "severity": "error", "message": "Use an explicit property path and C# value expression from the target."})
                continue
            assignment_prefix = f"this.{member}.{property_name} = "
            designer_lines = [line for line in designer_lines if not line.startswith(assignment_prefix)]
            designer_lines.append(assignment_prefix + value.rstrip(';') + ';')
    metadata["property_overrides"] = {"columns": column_properties or {}, "view": view_properties or {}}
    metadata["status"] = "passed" if not issues else "failed"
    return HarnessResult(
        success=not issues,
        stdout="\n".join(designer_lines),
        stderr="" if not issues else "Grid FieldName/result-field validation failed.",
        exit_code=0 if not issues else 1,
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
            stdout=json.dumps({"columns": [], "status": "failed"}, ensure_ascii=False),
            stderr="No DataWindow column=(...) name=... entries were found.",
            exit_code=1,
            metadata={
                "harness": "pb-to-csharp-migration-harness",
                "status": "failed",
                "reason": "missing_datawindow_columns",
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


def _escape_csharp_string(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace('"', '\\"')


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
