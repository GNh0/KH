"""Join call-local C# and Designer observations to supplied, named SQL definitions."""
from collections import Counter
import re

from src.common.results import CheckResult, Issue
from src.sql.screen_contract import Procedure, Projection, read_procedure
from .designer_model import parse_designer_source
from .lexer import mask_code, mask_comments, string_literal_value
from .screen_serializer import serializer_key, serializer_shapes
from .screen_calls import (Call, IDENT, TRANSPORT, actual_parameters, assignments, calls_in,
                           enum_members, methods, mode_evidence, xml_names)


def _grid_columns(source: str) -> dict[str, dict[str, tuple[str, int] | None]]:
    model = parse_designer_source(source)
    code = mask_code(source)
    views = {}
    # The GridView's actual column membership, not a naming convention, owns FieldName.
    for m in re.finditer(r'\b(?:this\.)?(\w+)\.Columns\.(?:AddRange|Add)\s*\(([^;]*)\)\s*;', code):
        members = re.findall(r'(?:this\.)?(\w+)\s*(?=[,})]|$)', m[2])
        views.setdefault(m[1], []).extend(members)
    result = {name: {} for name, ctrl in model.controls.items() if ctrl.type_name.split('.')[-1] == 'GridControl'}
    for assign in model.assignments:
        if assign['property'] == 'GridControl':
            grid = assign['value'].strip().removeprefix('this.')
            result.setdefault(grid, {})
        if assign['property'] != 'MainView':
            continue
        grid = assign['name']
        view = assign['value'].strip().removeprefix('this.')
        fields = result.setdefault(grid, {})
        for member in views.get(view, []):
            fields[member] = None
            ctrl = model.controls.get(member)
            if not ctrl:
                continue
            if ctrl.properties.get('UnboundExpression') or (
                    'UnboundType' in ctrl.properties and not ctrl.properties['UnboundType'].endswith('.Bound')):
                fields.pop(member)
                continue
            field = string_literal_value(ctrl.properties.get('FieldName', ''))
            if field:
                line = next(a['line'] for a in model.assignments if a['name'] == member and a['property'] == 'FieldName')
                fields[member] = (field, line)
    return result


def _compare_params(result: CheckResult, passed: list[tuple[str, str]], unknown: list[str],
                    proc: Procedure, evidence: dict) -> None:
    names = Counter(name for name, _ in passed)
    for name, count in names.items():
        details = dict(evidence, parameter=name)
        if name not in proc.parameters:
            result.issues.append(Issue('unexpected_sp_parameter', 'error', 'This call passes a name absent from its SP signature.', details=details))
        if count > 1:
            result.issues.append(Issue('duplicate_sp_parameter', 'error', 'This call supplies the same named parameter more than once.', details=details))
    for name, defaulted in proc.parameters.items():
        if not defaulted and name not in names and not unknown:
            result.issues.append(Issue('required_sp_parameter_missing', 'error', 'This call omits a required SP parameter.', details=dict(evidence, parameter=name)))


def _bound_results(proc: Procedure, by_parameter: dict[str, list[str]]) -> list[Projection] | None:
    if not proc.branches:
        return proc.unguarded_results
    if proc.outside_results:
        return None
    matched = [b for b in proc.branches if any(v in b.values for v in by_parameter.get(b.parameter, []))]
    return matched[0].results if len(matched) == 1 else None


def check_screen_contract(caller: str, designer: str | None, procedures: dict[str, str], *,
                          caller_path: str = 'caller', designer_path: str = 'designer',
                          serializer: str | None = None, serializer_path: str = 'serializer') -> CheckResult:
    result = CheckResult(checked=['call-local literal parameter names and required signatures',
        'observed caller modes against literal SQL guards', 'serialized DataTable names against parameter-specific OPENXML row elements',
        'direct DataSource and result index against owning grid columns and ordered SELECT projections'],
        not_checked=['procedure execution, parameter types/directions, XML attributes and runtime row contents',
                     'indirect/external DB APIs beyond ' + TRANSPORT.replace('|', ', ')])
    records: list[dict] = []
    grids: list[dict] = []
    result.metadata.update(calls=records, grid_bindings=grids)

    def gap(code: str, message: str, details: dict, path: str = caller_path, line: int | None = None):
        result.incomplete = True
        result.issues.append(Issue(code, 'warning', message, path, line, details))

    definitions = []
    for path, sql in procedures.items():
        try:
            definitions.append(read_procedure(sql, path))
        except ValueError as error:
            gap('procedure_contract_unresolved', str(error), {}, path)
    source = mask_comments(caller)
    code = mask_code(source)
    functions = methods(source, code)
    enum = enum_members(code)
    shapes = serializer_shapes(serializer) if serializer else {}
    columns = _grid_columns(designer) if designer is not None else {}
    if designer is None:
        gap('designer_contract_unresolved', 'Supply the matching Designer to compare grid FieldNames.', {})
    site_results: dict[int, tuple[Procedure, dict[str, list[str]]] | None] = {}
    source_sites: list[Call] = []
    seen: set[int] = set()
    for method in functions:
        for call in calls_in(method, TRANSPORT):
            offset = method.offset + call.start
            seen.add(offset)
            line = source.count('\n', 0, offset) + 1
            name = string_literal_value(call.args[0]) if call.args else None
            passed, unknown = actual_parameters(call)
            evidence = dict(procedure=name, method=method.name, call_line=line)
            mode_report: dict[str, dict] = {}
            xml_report: dict[str, dict] = {}
            record: dict[str, object] = dict(evidence, transport=call.name, parameters=[p for p, _ in passed],
                          unresolved_arguments=unknown, modes=mode_report, xml=xml_report)
            records.append(record)
            if unknown:
                gap('call_arguments_unresolved', 'Inspect the unresolved argument expressions for this call.',
                    dict(evidence, arguments=unknown), line=line)
            identity = (name or '').replace('[', '').replace(']', '').upper().split('.')
            matches = [p for p in definitions if p.name.split('.')[-len(identity):] == identity]
            if not name or len(matches) != 1:
                record['target_expression'] = call.args[0] if call.args else ''
                gap('procedure_target_unresolved', 'This call needs a unique matching procedure definition.',
                    dict(evidence, expression=call.args[0] if call.args else '', matches=[p.path for p in matches]), line=line)
                continue
            proc = matches[0]
            record['definition'] = proc.path
            _compare_params(result, passed, unknown, proc, evidence)
            # Only direct local wrapper invocations can supply this transport's formal mode.
            sites = [s for f in functions for s in calls_in(f, re.escape(method.name))
                     if not f.code[:s.start].rstrip().endswith('.') or
                     re.search(r'\bthis\s*\.\s*$', f.code[:s.start])]
            if sum(f.name == method.name for f in functions) > 1:
                sites = []
                gap('wrapper_overload_unresolved', 'Resolve the overloaded wrapper at each caller.', evidence, line=line)
            by_site: dict[int, dict[str, list[str]]] = {}
            for param, expr in passed:
                branch = [b for b in proc.branches if b.parameter == param]
                # A declared enum used by the callers still needs SQL evidence if every
                # recognized arm was removed or rewritten as an unsupported predicate.
                formal = re.fullmatch(r'(\w+)\s*\.\s*ToString\s*\(\s*\)', expr)
                enum_caller = False
                if formal and formal[1] in method.parameters:
                    ix = method.parameters.index(formal[1])
                    enum_caller = any(len(s.args) > ix and s.args[ix].split('.', 1)[0].strip() in enum for s in sites)
                if branch or param in proc.uncertain_guards or enum_caller:
                    observed, vals, dynamic = mode_evidence(call, expr, sites, enum)
                    supported = {v for b in branch for v in b.values}
                    mode_report[param] = dict(observed=sorted(vals), sql_values=sorted(supported),
                        branches=[dict(line=b.line, values=b.values) for b in branch], unresolved=dynamic)
                    for pos, vals_for_site in observed.items():
                        by_site.setdefault(pos, {})[param] = vals_for_site
                    by_site.setdefault(offset, {})[param] = sorted(vals)
                    if dynamic:
                        gap('mode_value_unresolved', 'Some possible mode values depend on a runtime expression or caller.',
                            dict(evidence, parameter=param, expression=expr), line=line)
                    for val in sorted(vals - supported):
                        details = dict(evidence, parameter=param, mode=val, definition=proc.path)
                        if param in proc.uncertain_guards or not branch or any(v.casefold() == val.casefold() for v in supported):
                            gap('mode_guard_unresolved', 'The value has no observed literal guard; other predicates or fallback need inspection.', details, line=line)
                        else:
                            result.issues.append(Issue('sp_mode_missing', 'error', 'This caller value has no matching observed SQL dispatch arm.', caller_path, line, details))
                names, expressions, unresolved = xml_names(call, expr)
                if param not in proc.xml and not expressions:
                    continue
                rows = proc.xml.get(param, [])
                xml_report[param] = dict(table_names=sorted(names), openxml=[dict(path=x, line=n) for x, n in rows])
                resolved = {shapes.get(key) if (key := serializer_key(x)) else None for x in expressions}
                shape = next(iter(resolved)) if len(resolved) == 1 else None
                if shape:
                    xml_report[param]['serializer'] = dict(path=serializer_path, root=shape.root, root_line=shape.root_line,
                        fixed_row=shape.fixed_row, row_line=shape.row_line)
                    if rows and any(x.split('/')[1] != shape.root for x, _line in rows):
                        result.issues.append(Issue('xml_root_mismatch', 'error', 'The serializer root differs from the OPENXML root.',
                            caller_path, line, dict(evidence, parameter=param, root=shape.root, paths=[x for x, _ in rows])))
                if unresolved or not rows:
                    gap('xml_binding_unresolved', 'Trace the serializer input and the prepared OPENXML handle for this parameter.',
                        dict(evidence, parameter=param, expression=expr), line=line)
                if rows and names:
                    expected = {x.rsplit('/', 1)[-1] for x, _ in rows}
                    actual = {shape.fixed_row} if shape and shape.fixed_row is not None else names
                    if len(actual) == len(expected) == 1 and actual != expected:
                        result.issues.append(Issue('xml_row_name_mismatch', 'error', 'The supplied row name differs from its parameter-specific OPENXML row element.',
                            caller_path, line, dict(evidence, parameter=param, table_names=sorted(names), paths=[x for x, _ in rows])))
                    elif len(names) != 1 or len(expected) != 1:
                        gap('xml_branch_mapping_unresolved', 'Resolve mode-specific XML assignments and OPENXML paths.', dict(evidence, parameter=param), line=line)
            if proc.unknown_xml:
                gap('openxml_path_unresolved', 'Trace the OPENXML path and its document handle.', evidence, proc.path, proc.unknown_xml[0])
            if any('serializer' not in xml for xml in xml_report.values()):
                gap('serializer_root_unverified', 'Verify the XML root and emitted elements in the actual serialization helper; this comparison uses the input TableName.',
                    evidence, line=line)
            if call.name == 'GetDataSetFromSP':
                # A wrapper only propagates this result when returning the DB call directly.
                prefix = method.code[:call.start]
                returns = bool(re.search(r'\breturn\s+(?:[\w.]+\s*\.\s*)?$', prefix))
                for site in [call, *(sites if returns else [])]:
                    pos = site.method.offset + site.start
                    if pos in site_results:
                        site_results[pos] = None
                        gap('wrapper_result_unresolved', 'Multiple transports may produce this wrapper result.', evidence, line=line)
                    else:
                        site_results[pos] = proc, by_site.get(pos, {})
                        source_sites.append(site)
            record['wrapper_calls'] = [dict(method=s.method.name, line=source.count('\n', 0, s.method.offset+s.start)+1,
                modes=by_site.get(s.method.offset+s.start, {})) for s in sites]
    for m in re.finditer(r'\b(?:' + TRANSPORT + r')\s*\(', code):
        if m.start() not in seen:
            gap('transport_scope_unresolved', 'Transport call outside a recognized method body.', {}, line=source.count('\n', 0, m.start()) + 1)
    if not seen:
        gap('screen_calls_unresolved', 'No supported transport call was resolved from the supplied caller.', {})

    for method in functions:
        for assignment in re.finditer(r'\b(\w+)\s*\.\s*DataSource\s*=(?!=)\s*([^;]*);', method.code):
            grid = assignment[1]
            if grid not in columns or assignment[2].strip() == 'null':
                continue
            line = source.count('\n', 0, method.offset + assignment.start()) + 1
            rhs = assignment[2]
            table = re.search(r'\.\s*Tables\s*\[\s*(\d+)\s*\]\s*$', rhs)
            record = dict(grid=grid, binding_line=line)
            grids.append(record)
            if not table:
                gap('grid_source_unresolved', 'Trace this grid assignment to its query and result index.', record, line=line)
                continue
            idx = int(table[1])
            ref = rhs[:table.start()].strip()
            sites = [s for s in source_sites if s.method is method and assignment.start(2) <= s.start < assignment.end(2)
                     and re.fullmatch(r'(?:[\w.]+\.)?', method.code[assignment.start(2):s.start].strip()) and
                     not method.code[s.end:assignment.start(2) + table.start()].strip()]
            if re.fullmatch(IDENT, ref):
                earlier = assignments(method, ref, assignment.start())
                if len(earlier) == 1:
                    start = earlier[0][0]
                    end = method.code.find(';', start)
                    sites = [s for s in source_sites if s.method is method and start <= s.start < end and
                             re.fullmatch(r'(?:[\w.]+\.)?', method.code[method.code.find('=', start)+1:s.start].strip()) and
                             not method.code[s.end:end].strip()]
            if len(sites) != 1 or (entry := site_results.get(method.offset + sites[0].start)) is None:
                gap('grid_source_unresolved', 'Resolve the DataSet producer in this method.', record, line=line)
                continue
            proc, modes = entry
            output = _bound_results(proc, modes)
            record.update(procedure=proc.name, definition=proc.path, modes=modes, result_index=idx)
            if output is None:
                gap('grid_result_unresolved', 'Multiple/conditional or indirect result shapes prevent resolving the ordered result.', record, line=line)
                continue
            if idx >= len(output):
                result.issues.append(Issue('grid_result_index_missing', 'error', 'This SELECT branch returns fewer results than the bound index.',
                    caller_path, line, dict(record, result_count=len(output))))
                continue
            projection = output[idx]
            binding_fields: dict[str, str] = {}
            record.update(select_line=projection.line, projection=projection.fields, fields=binding_fields)
            if not columns[grid]:
                gap('grid_columns_unresolved', 'Resolve the main view and actual bound columns.', record, line=line)
            for member, field_info in columns[grid].items():
                if field_info is None:
                    gap('grid_field_unresolved', 'Resolve the actual bound FieldName.', dict(grid=grid, member=member), designer_path)
                    continue
                field, field_line = field_info
                binding_fields[member] = field
                if field.upper() in projection.fields:
                    continue
                if projection.complete:
                    result.issues.append(Issue('grid_result_field_missing', 'error', 'The bound grid FieldName is absent from this specific SELECT result.',
                        designer_path, field_line, dict(grid=grid, member=member, field=field, result_index=idx,
                        modes=modes, definition=proc.path, select_line=projection.line)))
                else:
                    gap('grid_projection_unresolved', 'A wildcard or unresolved SELECT expression prevents confirming this field.',
                        dict(grid=grid, member=member, field=field, select_line=projection.line), designer_path, field_line)
    for grid in columns.keys() - {item['grid'] for item in grids}:
        gap('grid_binding_unresolved', 'No supported grid-to-result assignment was found.', dict(grid=grid), designer_path)
    return result
