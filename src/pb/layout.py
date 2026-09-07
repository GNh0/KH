"""Retained pb syntax and domain mechanics from KH; no host orchestration."""

from __future__ import annotations

import json

import re

from dataclasses import dataclass, field

from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence

from src.common.results import HarnessResult

from .models import (
    CSharpDesignerControlSpec,
    DetailFormFieldSpec,
)

from .datawindow import (
    _normalize_datawindow_field_name,
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
            stdout=json.dumps({"fields": [], "status": "failed"}, ensure_ascii=False),
            stderr="No detail form fields were provided.",
            exit_code=1,
            metadata={
                "harness": "pb-to-csharp-migration-harness",
                "status": "failed",
                "reason": "missing_detail_form_fields",
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
        canonical_editor_name = _build_editor_control_name(editor_type, logical_name, field_name)
        requested_editor_name = str(field.get("csharp_editor_name") or "").strip()
        editor_name = requested_editor_name or canonical_editor_name
        canonical_label_name = str(field.get("csharp_label_name") or f"lbl{_normalize_datawindow_field_name(field_name)}").strip()
        for member in (editor_name, canonical_label_name):
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", member):
                issues.append({"code": "detail_member_invalid", "severity": "error", "message": "Supply a valid C# member name.", "member": member})
        binding_evidence = supplied_binding_map.get(field_name, supplied_binding_map.get(editor_name, {}))
        if isinstance(binding_evidence, str):
            binding_evidence = {"result_field": binding_evidence}
        binding_evidence = dict(binding_evidence) if isinstance(binding_evidence, Mapping) else {}
        result_field = _normalize_datawindow_field_name(
            binding_evidence.get("result_field") or field_name
        )
        explicit_binding_field = bool(
            str(binding_evidence.get("binding_property") or "").lower() == "bindingfield"
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
                csharp_label_name=canonical_label_name,
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
        "status": "passed" if not issues else "failed",
        "section_caption": str(section_caption or "detail"),
        "not_checked": ["actual UserControl dimensions", "runtime bindings", "Designer rendering"],
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
            "DataBindings map. Explicit target names override the naming defaults."
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

def extract_csharp_designer_control_specs(source_text: str) -> HarnessResult:
    """Share C# literal boundaries, members, properties and real containment."""
    from src.csharp.designer_model import parse_designer_source
    from src.csharp.lexer import _scan_csharp, balanced_close
    model = parse_designer_source(source_text)
    code, _ = _scan_csharp(source_text)
    collections = {}
    for match in re.finditer(r'\bthis\.(\w+)\.([\w.]*AddRange)\s*\(', code):
        opening = code.find('(', match.start())
        closing = balanced_close(code, opening, '(', ')')
        if closing >= 0:
            collections.setdefault(match[1], {}).setdefault(match[2], []).append(source_text[match.start():closing+1]+';')
    specs = []
    for name, control in model.controls.items():
        values = {key: _parse_csharp_designer_value(value) for key,value in control.properties.items()}
        specs.append(CSharpDesignerControlSpec(
            name=name, type_name=control.type_name, parent_name=control.parent,
            children=[n for n,c in model.controls.items() if c.parent==name],
            properties=values, raw_properties=control.properties, collection_calls=collections.get(name,{}),
            field_name=str(values.get('FieldName','')), caption=str(values.get('Caption',values.get('Text',''))),
            binding_field=str(values.get('BindingField','')), tab_index=control.tab_index,
            location={'x':control.location[0],'y':control.location[1]} if control.location else None,
            size={'width':control.size[0],'height':control.size[1]} if control.size else None))
    columns = [s.to_dict() for s in specs if s.type_name.split('.')[-1]=='GridColumn']
    metadata = {'status':'passed' if specs else 'incomplete', 'controls':[s.to_dict() for s in specs],
                'control_count':len(specs), 'grid_columns':columns, 'grid_columns_present':bool(columns),
                'grid_column_count':len(columns), 'not_checked':['dynamic properties', 'control API version', 'Designer rendering']}
    return HarnessResult(success=bool(specs), stdout=json.dumps(metadata,ensure_ascii=False,indent=2),
                         exit_code=0 if specs else 2, metadata=metadata)

def _parse_csharp_designer_value(raw_value: str) -> Any:
    value = str(raw_value or "").strip()
    from src.csharp.designer_model import _csharp_string_value
    decoded = _csharp_string_value(value)
    if decoded is not None:
        return decoded
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

def _to_control_suffix(value: str) -> str:
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", str(value or "")) if part]
    if not parts:
        return "Field"
    suffix = "".join(part[:1].upper() + part[1:] for part in parts)
    return suffix or "Field"
