"""PB Designer mappings share the C# scanner and explicit Designer model."""
from src.csharp.designer import check_designer
from src.csharp.designer_model import parse_designer_source, _csharp_string_value
from src.common.results import CheckResult, Issue


def check_field_lineage(source_fields, result_fields, designer_source):
    model = parse_designer_source(designer_source)
    bindings = {_csharp_string_value(c.properties['FieldName']) for c in model.controls.values() if 'FieldName' in c.properties}
    result = CheckResult(checked=['provided source/result fields against explicit Designer FieldName values'],
                         not_checked=['retrieve execution', 'runtime lookup and display values'])
    if None in bindings:
        bindings.remove(None)
        result.incomplete = True
        result.issues.append(Issue('dynamic_field_binding', 'warning', 'A FieldName expression needs the actual runtime value.'))
    for field in sorted(set(source_fields) - set(result_fields)):
        result.issues.append(Issue('source_field_not_returned', 'error', 'A required source field is missing from the declared result.', details={'field': field}))
    for field in sorted(bindings - set(result_fields)):
        result.issues.append(Issue('designer_field_not_returned', 'error', 'A Designer binding is absent from the declared result.', details={'field': field}))
    return result
