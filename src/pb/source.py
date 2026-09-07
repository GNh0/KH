"""Read supplied PowerScript/DataWindow exports without claiming full PBL coverage."""
from dataclasses import asdict, dataclass, field
import re
from .datawindow import extract_datawindow_column_specs
from src.sql.pb_extract import extract_powerbuilder_sql_fragments


def mask_pb_comments(text: str) -> str:
    result = list(text)
    index = 0
    while index < len(text):
        if text[index] in {'"', "'"}:
            quote = text[index]
            index += 1
            while index < len(text):
                if text[index] == '~':
                    index += 2
                elif text[index] == quote:
                    index += 1
                    break
                else:
                    index += 1
            continue
        if text.startswith('//', index):
            end = text.find('\n', index)
            end = len(text) if end == -1 else end
        elif text.startswith('/*', index):
            close = text.find('*/', index + 2)
            end = len(text) if close == -1 else close + 2
        else:
            index += 1
            continue
        for cursor in range(index, end):
            if result[cursor] not in '\r\n':
                result[cursor] = ' '
        index = end
    return ''.join(result)


@dataclass
class PBExport:
    path: str | None
    objects: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    dataobjects: list[str] = field(default_factory=list)
    columns: list[dict] = field(default_factory=list)
    sql_fragments: list = field(default_factory=list)
    coverage: str = 'supplied textual export only; inheritance and linked objects require their own sources'

    def to_dict(self):
        return asdict(self)


def parse_pb_export(text: str, *, path: str | None = None) -> PBExport:
    code = mask_pb_comments(text)
    objects = [{'name': m[1], 'parent': m[2], 'line': code.count('\n', 0, m.start()) + 1}
               for m in re.finditer(r'(?im)^[ \t]*(?:global\s+)?type\s+(\w+)\s+from\s+([\w.]+)', code)]
    events = []
    for match in re.finditer(r'(?im)^[ \t]*event\s+(?:(?:type\s+)?(?:integer|long|boolean|string|decimal|double)\s+)?(?:(\w+)::)?(\w+)[^\r\n;]*;?', code):
        end = re.search(r'(?im)^[ \t]*end\s+event\b', code[match.end():])
        # Prototype declarations have no body and are not counted as executable events.
        if end is None:
            continue
        body_end = match.end() + end.start()
        next_event = re.search(r'(?im)^[ \t]*event\s+', code[match.end():body_end])
        if next_event:
            continue
        events.append({'object': match[1], 'name': match[2], 'kind': 'event', 'line': code.count('\n', 0, match.start()) + 1,
                       'body': text[match.end():body_end].strip()})
    for match in re.finditer(r'(?im)^[ \t]*on\s+(\w+)\.(\w+)\s*;?[^\S\r\n]*$', code):
        end = re.search(r'(?im)^[ \t]*end\s+on\b', code[match.end():])
        if end:
            body_end = match.end() + end.start()
            events.append({'object': match[1], 'name': match[2], 'kind': 'lifecycle',
                           'line': code.count('\n', 0, match.start()) + 1,
                           'body': text[match.end():body_end].strip()})
    events.sort(key=lambda event: event['line'])
    dataobjects = list(dict.fromkeys(m[1] for m in re.finditer(r'(?im)^[ \t]*dataobject\s*=\s*"([^"]+)"', code)))
    columns = [item.to_dict() for item in extract_datawindow_column_specs(code)]
    return PBExport(path, objects, events, dataobjects, columns, extract_powerbuilder_sql_fragments(code))
