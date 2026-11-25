"""Retained pb syntax and domain mechanics from KH; no host orchestration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence


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
    base_type_family: str = ""
    sequence_type_family: str = ""
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
            base_type_family=str(data.get("base_type_family") or ""),
            sequence_type_family=str(data.get("sequence_type_family") or ""),
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
