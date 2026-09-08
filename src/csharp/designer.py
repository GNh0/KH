"""Check explicit Designer structure; live Designer compatibility stays separate."""
import re
from collections import defaultdict
from typing import Iterable, Mapping
from src.common.results import CheckResult, Issue
from .lexer import _scan_csharp
from .syntax import _method_declarations
from .designer_model import parse_designer_source, _normalized_csharp_value
from .grid_style import check_grid_style


def check_designer(designer: str, *, code_behind: str = "", original: str | None = None,
                   preserved_properties: Iterable[str] = (), expected_tab_order: Iterable[str] = (),
                   inherited_handlers: Iterable[str] = (), column_edit_modes: Mapping[str, str] | None = None,
                   allowed_property_changes: Iterable[str] = ()) -> CheckResult:
    result = CheckResult(checked=["explicit Designer members and assignments", "event handler references"],
                         not_checked=["Visual Studio Designer load", "rendered layout", "control-library version compatibility"])
    model = parse_designer_source(designer)
    baseline = parse_designer_source(original) if original is not None else None
    result.issues.extend(check_grid_style(model, original=baseline, column_edit_modes=column_edit_modes,
                                         allowed_property_changes=allowed_property_changes))
    result.checked.append('KH HTML grid defaults and explicit column edit modes; property deltas when baseline supplied')
    masked, _ = _scan_csharp(designer)
    preserved_properties = tuple(preserved_properties)
    inherited_handlers = set(inherited_handlers)
    if preserved_properties and original is None:
        result.incomplete = True
        result.issues.append(Issue('preservation_baseline_missing', 'warning', 'Supply the original Designer to verify requested property preservation.'))
    for match in re.finditer(r"\bthis\.(\w+)\s*=\s*(?:this\.)?(Create\w*|Build\w*)\s*\(", masked):
        result.issues.append(Issue("designer_factory_assignment", "warning",
                                  "Check Designer support for this factory assignment; static controls normally use explicit initialization.",
                                  line=masked.count("\n", 0, match.start()) + 1, details={"member": match[1]}))
    for handler in re.findall(r"\+=\s*(?:new\s+[\w.<>]+\s*\(\s*)?(?:this\.)?(\w+)\s*(?:\)|;)", masked):
        if handler not in inherited_handlers and not _method_declarations(code_behind + "\n" + designer, handler):
            result.issues.append(Issue("handler_definition_not_found", "warning", "The subscribed handler was not found in the supplied partial files; check inherited/other partial declarations.", details={"handler": handler}))
    declarations = {name for name, control in model.controls.items() if control.type_name}
    registered = set()
    for match in re.finditer(r'\.RepositoryItems\.Add(?:Range)?\s*\((.*?)\)\s*;', masked, re.S):
        registered.update(re.findall(r'\bthis\.(\w+)', match[1]))
    for name, control in model.controls.items():
        repository = control.properties.get("ColumnEdit", "").removeprefix("this.").strip()
        if repository and repository not in declarations:
            result.issues.append(Issue("repository_not_declared", "warning", "ColumnEdit references a repository not present in this supplied Designer.", details={"column": name, "repository": repository}))
        elif repository and repository not in registered:
            result.issues.append(Issue('repository_registration_unconfirmed', 'warning', 'ColumnEdit repository registration was not found; inspect inherited/dynamic registration if applicable.', details={'column': name, 'repository': repository}))
    if baseline is not None:
        requested = set(preserved_properties)
        for key in requested:
            member, separator, prop = key.partition(".")
            if not separator:
                raise ValueError("preserved properties must be member.property paths")
            before = baseline.controls.get(member)
            after = model.controls.get(member)
            old = before.properties.get(prop) if before else None
            new = after.properties.get(prop) if after else None
            if old is None:
                result.incomplete = True
                result.issues.append(Issue("baseline_property_missing", "warning", "The requested original property was not found; preservation cannot be established.", details={"property": key}))
            elif new is None or _normalized_csharp_value(old) != _normalized_csharp_value(new):
                result.issues.append(Issue("user_property_changed", "error", "An explicitly preserved Designer property changed.", details={"property": key, "before": old, "after": new}))
    order = list(expected_tab_order)
    if order:
        result.checked.append("specified input tab order")
        grouped = defaultdict(list)
        for name in order:
            control = model.controls.get(name)
            if control is None or control.tab_index is None:
                result.issues.append(Issue("tab_order_unknown", "warning", "A requested input has no explicit TabIndex in the supplied Designer.", details={"control": name}))
                result.incomplete = True
            else:
                grouped[control.parent].append(control)
        for parent, controls in grouped.items():
            indexes = [c.tab_index for c in controls]
            if indexes != sorted(indexes) or len(indexes) != len(set(indexes)):
                result.issues.append(Issue("tab_order_mismatch", "error", "TabIndex does not follow the specified input order within its container.", details={"parent": parent, "controls": [c.name for c in controls]}))
        if len(grouped) > 1:
            result.not_checked.append("tab traversal order between separate containers")
    result.metadata["controls"] = sorted(model.controls)
    return result
