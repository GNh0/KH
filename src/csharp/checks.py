"""Useful local C# comparisons without authentication/exception ledgers."""
from collections import Counter
from dataclasses import replace
import re
from typing import Mapping, Sequence
from src.common.results import CheckResult, HarnessResult, Issue, from_legacy_issues
from .lexer import _scan_csharp
from .source import _call_count, _target_local_method_inventory, _designer_wired_event_handlers, _row_rewrite_loops, _transaction_invocation_drift_issues
from .designer import check_designer
from .designer_model import parse_designer_source
from .grid_style import check_grid_style
from .syntax import _property_assignments, linq_candidates


def check_csharp(candidate: str, *, original: str | None = None, designer: str | None = None,
                 allowed_changes: Mapping[str, Sequence[str]] | None = None,
                 original_designer: str | None = None, column_edit_modes: Mapping[str, str] | None = None,
                 allowed_property_changes: Sequence[str] = ()) -> CheckResult:
    allowed = allowed_changes or {}
    result = CheckResult(checked=["C# lexical source patterns"],
                         not_checked=["C# compilation", "runtime UI and database behavior", "full C# semantic analysis"])
    code, _ = _scan_csharp(candidate)
    before, _ = _scan_csharp(original or "")
    candidate_model = parse_designer_source(candidate)
    baseline_model = parse_designer_source(original) if original is not None else None
    if designer is not None:
        types = parse_designer_source(designer).controls
        candidate_model = replace(candidate_model, controls={name: replace(control, type_name=types[name].type_name)
            if not control.type_name and name in types else control for name, control in candidate_model.controls.items()})
        if baseline_model is not None:
            original_types = parse_designer_source(original_designer).controls if original_designer is not None else types
            baseline_model = replace(baseline_model, controls={name: replace(control, type_name=original_types[name].type_name)
                if not control.type_name and name in original_types else control for name, control in baseline_model.controls.items()})
    result.issues.extend(check_grid_style(candidate_model, original=baseline_model,
                         column_edit_modes=column_edit_modes if designer is None else None,
                         allowed_property_changes=allowed_property_changes, check_required_defaults=False))
    if not code.strip():
        result.incomplete = True
        result.issues.append(Issue('csharp_code_missing', 'warning', 'No executable/declarative C# text is available for the requested source checks.'))
    if original is not None:
        result.checked += ["target method signatures", "transaction-named call changes", "new whole-table row rewrites"]
        result.not_checked.append("transaction participation and wrapper equivalence; inspect actual call bodies/API contracts")
        wired = _designer_wired_event_handlers(designer)
        old_methods = Counter(x["signature"] for x in _target_local_method_inventory(before, wired_event_handlers=wired))
        new_methods = Counter(x["signature"] for x in _target_local_method_inventory(code, wired_event_handlers=wired))
        for signature, count in (old_methods - new_methods).items():
            if signature not in allowed.get("removed_methods", []):
                result.issues.append(Issue("target_method_removed", "warning", "Review removal of an established target-local method against the requested change.", details={"signature": signature, "count": count}))
        for call in ("PostEditor", "UpdateCurrentRow"):
            if _call_count(code, call) > _call_count(before, call) and call not in allowed.get("new_calls", []):
                result.issues.append(Issue("new_edit_commit_call", "warning", "Confirm why this new edit-commit call is needed in the actual framework path.", details={"call": call}))
        for finding in _transaction_invocation_drift_issues(before, code):
            if finding["code"] not in allowed.get("issue_codes", []):
                result.issues += from_legacy_issues([finding])
        old_loops = Counter(x["fingerprint"] for x in _row_rewrite_loops(original))
        for loop in _row_rewrite_loops(candidate):
            if old_loops[loop["fingerprint"]]:
                old_loops[loop["fingerprint"]] -= 1
            elif not set(loop["columns"]) <= set(allowed.get("whole_table_columns", [])):
                result.issues.append(Issue("whole_table_row_rewrite", "warning", "Check XML/SP field ownership before propagating values across every row.", details=loop))
        previous_properties = _property_assignments(original)
        for member, properties in _property_assignments(candidate).items():
            for prop, (value, line) in properties.items():
                old = previous_properties.get(member, {}).get(prop)
                if (prop in {'Location', 'Size', 'Font', 'Caption', 'FieldName', 'ColumnEdit'} or prop.startswith('Appearance')) and (old is None or old[0] != value):
                    result.issues.append(Issue('static_ui_in_code_behind_review', 'warning', 'Place static UI setup in Designer; retain a code-behind assignment when the actual event requires dynamic behavior.', line=line, details={'member': member, 'property': prop}))
    patterns = {
        "intermediate_table_preference": r"\b(?:Clone|ImportRow)\s*\(",
        "expression_body_preference": r"\b(?:public|protected|private|internal)\b[^;{}\n]*=>",
    }
    if len(linq_candidates(candidate)) > len(linq_candidates(original or '')):
        result.issues.append(Issue('linq_preference', 'warning',
            'Review a likely LINQ invocation against the existing project form. The lexer cannot resolve extension methods; verify the actual API. An exception needs difficult implementation without it or an extreme performance disadvantage.'))
    for name, pattern in patterns.items():
        if len(re.findall(pattern, code)) > len(re.findall(pattern, before)):
            result.issues.append(Issue(name, "warning", "Prefer the established project form. A difficult implementation without this construct or an extreme performance disadvantage can justify an exception; convenience alone cannot."))
    if designer is not None:
        ui = check_designer(designer, code_behind=candidate, original=original_designer,
                            column_edit_modes=column_edit_modes, allowed_property_changes=allowed_property_changes)
        result.issues.extend(ui.issues)
        result.checked.extend(ui.checked)
        result.not_checked.extend(ui.not_checked)
        result.incomplete |= ui.incomplete
    return result


def verify_csharp_edit_contract(original_source: str, candidate_source: str, *, evidence=None, designer_source=None) -> HarnessResult:
    evidence = evidence or {}
    allowed = {"removed_methods": evidence.get("allowed_removed_helpers", []),
               "new_calls": evidence.get("allowed_new_calls", []),
               "whole_table_columns": evidence.get("allowed_whole_table_row_rewrite_columns", [])}
    result = check_csharp(candidate_source, original=original_source, designer=designer_source, allowed_changes=allowed)
    return HarnessResult(success=result.success, stdout=result.to_json(), exit_code=result.exit_code, metadata=result.to_dict())
