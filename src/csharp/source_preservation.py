"""Compare retained Designer assignments with the actual supplied source."""
from collections.abc import Mapping, Sequence
import json
import re

from src.common.results import CheckResult, Issue
from .designer_model import DesignerModel, _normalized_csharp_value
from .lexer import _scan_csharp, string_literal_value


def remap_members(source: str, renames: Mapping[str, str]) -> str:
    """Normalize explicit member renames in memory, without changing source files."""
    if not renames:
        return source
    if any(not re.fullmatch(r'[A-Za-z_]\w*', name) for pair in renames.items() for name in pair):
        raise ValueError('member renames must contain simple C# identifiers')
    if len(set(renames.values())) != len(renames):
        raise ValueError('member rename destinations must be unique')
    code, tokens = _scan_csharp(source)
    edits: list[tuple[int, int, str]] = []
    for kind, value, start, end in tokens:
        if kind == 'identifier' and value in renames:
            edits.append((start, end, renames[value]))
        elif kind == 'string':
            name_assignment = re.search(r'\bthis\.(\w+)\.Name\s*=\s*$', code[:start])
            literal = string_literal_value(source[start:end])
            if name_assignment and literal is not None and literal == name_assignment[1] and literal in renames:
                edits.append((start, end, json.dumps(renames[literal])))
            elif literal is not None and re.search(r'\bresources\.Get(?:Object|String)\s*\(\s*$', code[:start]):
                prefix, separator, suffix = literal.partition('.')
                if separator and prefix in renames:
                    edits.append((start, end, json.dumps(renames[prefix] + '.' + suffix)))
    for start, end, value in reversed(edits):
        source = source[:start] + value + source[end:]
    return source


def validate_designer_renames(model: DesignerModel, renames: Mapping[str, str]) -> None:
    unknown = set(renames) - set(model.controls)
    if unknown:
        raise ValueError('original Designer members not found: ' + ', '.join(sorted(unknown)))
    targets = [renames.get(name, name) for name in model.controls]
    if len(targets) != len(set(targets)):
        raise ValueError('member rename collides with another original Designer member')


def compare_existing_properties(model: DesignerModel, baseline: DesignerModel,
                                allowed_changes: Sequence[str] = ()) -> CheckResult:
    result = CheckResult(checked=['retained Designer type and explicit property assignments'],
                         not_checked=['removed/new controls, resource contents, collection calls, initialization order and indirect/runtime property values'])
    matched = set(model.controls) & set(baseline.controls)
    changed = 0
    exclusions = set(allowed_changes)
    groups = [(name, baseline.controls[name].properties, model.controls[name].properties) for name in sorted(matched)]
    groups.append(('form', baseline.form_properties, model.form_properties))
    for name, before, after in groups:
        differences = []
        for prop in sorted(set(before) | set(after)):
            if name + '.' + prop in exclusions:
                continue
            old, new = before.get(prop), after.get(prop)
            if old is None or new is None or _normalized_csharp_value(old) != _normalized_csharp_value(new):
                differences.append(prop)
        if name != 'form':
            old_type, new_type = baseline.controls[name].type_name, model.controls[name].type_name
            if old_type != new_type and name + '.type' not in exclusions:
                differences.append('type')
        if differences:
            changed += len(differences)
            result.issues.append(Issue('designer_existing_properties_changed', 'warning',
                'Retained source properties were changed, added or removed. Reconcile each delta with the requested migration; do not rebuild defaults.',
                details={'member': name, 'properties': differences}))
    if baseline.controls and model.controls and not matched:
        result.incomplete = True
        result.issues.append(Issue('designer_baseline_unmatched', 'warning',
            'No original Designer members matched. Supply explicit member renames; this is not evidence of preserved properties.'))
    result.metadata['designer_preservation'] = {
        'matched_members': len(matched), 'property_deltas': changed,
        'unmatched_original_members': sorted(set(baseline.controls) - set(model.controls)),
        'new_members': sorted(set(model.controls) - set(baseline.controls)),
        'excluded_properties': sorted(exclusions),
    }
    return result
