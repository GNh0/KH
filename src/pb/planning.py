"""Source-linked plan data for the requested PB migration scope."""
from .source import parse_pb_export


def build_migration_plan(source: str, *, scope: str = 'analysis', source_path: str | None = None, target: str | None = None) -> dict:
    if scope not in {'analysis', 'sql', 'screen', 'report'}:
        raise ValueError('scope must be analysis, sql, screen or report')
    observed = parse_pb_export(source, path=source_path)
    needs = ['Confirm exact object, parent and linked DataWindow sources.']
    if scope in {'screen', 'analysis'}:
        needs += ['Map fields, controls, defaults, lookup/repository bindings, protection and permissions.',
                  'Map events, focus/checked selection, NEW/MOD/DEL, XML/SP ownership and save/requery/restore.']
    if scope in {'sql', 'screen', 'analysis'}:
        needs += ['Map retrieve parameters and actual SELECT/SAVE procedure contracts in the requested scope.']
    if scope == 'report':
        needs += ['Preserve H/D/F, group, page and band order; inspect rendered output.']
    return {'scope': scope, 'target': target, 'source': observed.to_dict(), 'work': needs,
            'unresolved': ['unprovided linked/parent source', 'target framework/API and user comparator' if target is None else 'runtime behavior'],
            'implementation_performed': False}
