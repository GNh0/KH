"""Retained pb syntax and domain mechanics from KH; no host orchestration."""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence
from src.common.results import HarnessResult
from .models import (
    CompositeBusinessKeyDisplayObservation,
    CompositeBusinessKeyDisplaySpec,
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
            "Declare the actual base-key type as character for this concatenation helper.",
        )
    sequence_family = str(contract.sequence_type_family).strip().lower()
    if sequence_family not in {"integer", "numeric"}:
        add_issue(
            "composite_display_key_sequence_type_unsupported",
            "Declare actual sequence types: integer uses CONVERT; numeric retains an explicit FORMAT pattern.",
        )
    if sequence_family == "numeric" and not str(contract.sequence_format):
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
        expression = (f"CONVERT(VARCHAR(30), {sequence_ref})" if sequence_family == "integer"
                      else f"FORMAT({sequence_ref}, '{format_literal}')")
        concatenation += f" + '-' + {expression}"
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
        "type_behavior": "declared integer CONVERT or numeric FORMAT; raw component types remain unchanged",
        "sequence_format": contract.sequence_format,
        "evidence_kind": contract.evidence_kind,
        "evidence_refs": list(contract.evidence_refs),
    }
    passed = not issues
    metadata = {
        "harness": "pb-to-csharp-migration-harness",
        "status": "passed" if passed else "failed",
        "not_checked": ["actual database column types", "result execution", "grid rendering"],
        "contract": "composite-business-key-display-v1",
        "plan": plan,
        "issues": issues,
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
        "status": "passed" if passed else "failed",
        "not_checked": ["actual database column types", "result execution", "grid rendering"],
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
    }
    return HarnessResult(
        success=passed,
        stdout=json.dumps({"status": metadata["status"], "issue_count": len(issues)}, sort_keys=True),
        stderr="" if passed else "Composite business-key display verification failed.",
        exit_code=0 if passed else 1,
        metadata=metadata,
    )
