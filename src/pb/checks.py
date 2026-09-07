from src.common.results import CheckResult, Issue
from .source import parse_pb_export


def check_pb_export(text: str, *, path: str | None = None) -> CheckResult:
    parsed = parse_pb_export(text, path=path)
    result = CheckResult(checked=['supplied PB export objects/events/dataobjects/columns/SQL candidates'],
                         not_checked=['unprovided PBL objects and parent implementations', 'complete PowerScript function/subroutine and dynamic-call analysis', 'PB execution', 'C# and report rendering', 'database behavior'])
    if not text.strip():
        result.issues.append(Issue('empty_pb_export', 'error', 'The PB input is empty.', path=path))
    elif not any([parsed.objects, parsed.events, parsed.columns, parsed.sql_fragments]):
        result.incomplete = True
        result.issues.append(Issue('pb_structure_not_identified', 'warning', 'No supported textual PB structure was identified; inspect the export format and encoding.', path=path))
    if parsed.dataobjects:
        result.not_checked.append('linked DataWindow sources: '+', '.join(parsed.dataobjects))
    result.metadata['source'] = parsed.to_dict()
    return result
