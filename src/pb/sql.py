"""Compare a selected C# call with one real SELECT/SAVE procedure."""
from src.common.results import CheckResult, Issue
from src.csharp.syntax import parameter_constructor_sites
from src.sql.lexer import _scan_sql_tokens
from src.sql.delta import _full_replace_records


def procedure_parameters(sql: str) -> dict[str, bool]:
    """Return parameter names and whether an explicit default is present."""
    tokens, errors = _scan_sql_tokens(sql)
    if errors:
        raise ValueError('SQL lexical errors prevent parameter comparison')
    start = next((i for i, t in enumerate(tokens) if t.normalized in {'PROC', 'PROCEDURE'}), None)
    if start is None:
        raise ValueError('A procedure definition is required')
    finish = next((i for i in range(start + 1, len(tokens)) if tokens[i].normalized == 'AS' and tokens[i].depth == 0), None)
    if finish is None:
        raise ValueError('Procedure AS body boundary was not found')
    result = {}
    current = None
    for token in tokens[start+1:finish]:
        if token.text.startswith('@') and token.depth == 0:
            current = token.text.upper()
            result[current] = False
        elif token.text == '=' and current:
            result[current] = True
    return result


def check_sp_call(csharp_call: str, procedure_sql: str) -> CheckResult:
    """The C# input must be the selected call, not an unrelated whole form."""
    result = CheckResult(checked=['selected call parameter names vs procedure definition'],
                         not_checked=['parameter values and data types', 'parameter direction (OUTPUT/INPUTOUTPUT) and return values', 'XML schema', 'stored procedure runtime behavior'])
    try:
        defined = procedure_parameters(procedure_sql)
    except ValueError as error:
        result.incomplete = True
        result.issues.append(Issue('procedure_input_incomplete', 'warning', str(error)))
        return result
    sites = parameter_constructor_sites(csharp_call)
    passed = {'@' + name.lstrip('@').upper() for _, name, _ in sites if name is not None}
    unresolved = not sites or any(name is None for _, name, _ in sites)
    if unresolved and defined:
        result.incomplete = True
        result.issues.append(Issue('call_parameters_unresolved', 'warning', 'Some parameter names need expression evaluation or no typed literal parameter constructors were found.'))
    for name in sorted(passed - defined.keys()):
        result.issues.append(Issue('unexpected_sp_parameter', 'error', 'The selected C# call passes a parameter absent from this SP.', details={'parameter': name}))
    for name in sorted(defined.keys() - passed):
        if not defined[name]:
            result.issues.append(Issue('required_sp_parameter_unconfirmed' if unresolved else 'required_sp_parameter_missing',
                'warning' if unresolved else 'error',
                'A required SP parameter is not resolved from the supplied constructors.' if unresolved else 'The selected call omits a required SP parameter.',
                details={'parameter': name}))
    result.metadata.update(passed_parameters=sorted(passed), defined_parameters=defined)
    result.not_checked.append('caller procedure identity; supply only the selected call for this procedure')
    return result


def review_save_delta(sql: str) -> CheckResult:
    findings = [Issue('full_replace_requires_review', 'warning', 'Confirm that whole-row replacement is requested; preserve actual NEW/MOD/DEL behavior otherwise.', details=r) for r in _full_replace_records(sql)]
    return CheckResult(issues=findings, checked=['DELETE followed by INSERT shape'], not_checked=['actual XML row states', 'DB post-write values'])
