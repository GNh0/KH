"""Read-only file structure checks. Never equate container validity with rendering."""
import csv
import io
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import zipfile
from src.common.files import read_file
from src.common.results import CheckResult, Issue


def check_artifact(path: str | Path) -> CheckResult:
    snapshot = read_file(path, max_bytes=128 * 1024 * 1024)
    data, suffix = snapshot.data, snapshot.path.suffix.lower()
    result = CheckResult(checked=['actual file bytes and selected format structure'],
                         not_checked=['content against user requirements', 'rendered appearance and readability'],
                         metadata={'path': str(snapshot.path), 'sha256': snapshot.sha256, 'bytes': len(data)})
    if not data:
        result.issues.append(Issue('empty_artifact', 'error', 'The output file is empty.'))
        return result
    try:
        if suffix in {'.docx', '.xlsx', '.pptx'}:
            required = {'.docx': 'word/document.xml', '.xlsx': 'xl/workbook.xml', '.pptx': 'ppt/presentation.xml'}[suffix]
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                members = archive.infolist()
                if sum(x.file_size for x in members) > 256 * 1024 * 1024:
                    raise ValueError('expanded document exceeds this checker limit')
                names = [x.filename for x in members]
                if len(names) != len(set(names)):
                    raise ValueError('duplicate ZIP member names')
                for name in ('[Content_Types].xml', '_rels/.rels', required):
                    if name not in names:
                        raise ValueError('missing document part: ' + name)
                root_names = {'[Content_Types].xml': 'Types', '_rels/.rels': 'Relationships',
                              required: {'.docx': 'document', '.xlsx': 'workbook', '.pptx': 'presentation'}[suffix]}
                for name, expected_root in root_names.items():
                    if ET.fromstring(archive.read(name)).tag.split('}')[-1] != expected_root:
                        raise ValueError('unexpected root element in document part: ' + name)
                for member in members:
                    if member.filename.endswith(('.xml', '.rels')):
                        ET.fromstring(archive.read(member))
                broken = archive.testzip()
                if broken:
                    raise ValueError('CRC mismatch: ' + broken)
                result.metadata['container_parts'] = len(names)
                result.not_checked.extend(['OOXML schema and relationship resolution', 'formulas/data freshness', 'external relationships and linked resources'])
        elif suffix in {'.xml', '.svg'}:
            root = ET.fromstring(data)
            result.metadata['root_element'] = root.tag
            if suffix == '.svg' and root.tag.split('}')[-1] != 'svg':
                raise ValueError('SVG root element is absent')
        elif suffix == '.json':
            value = json.loads(snapshot.text())
            result.metadata['json_type'] = type(value).__name__
        elif suffix in {'.csv', '.tsv'}:
            rows = list(csv.reader(io.StringIO(snapshot.text()), delimiter='\t' if suffix == '.tsv' else ','))
            widths = sorted({len(row) for row in rows if row})
            result.metadata.update(rows=len(rows), column_counts=widths)
            if len(widths) > 1:
                result.issues.append(Issue('uneven_delimited_rows', 'warning', 'Rows have different column counts; confirm intentional free-form content.'))
        elif suffix == '.png':
            if not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data) < 33 or data[12:16] != b'IHDR':
                raise ValueError('invalid PNG signature or IHDR')
            width, height = struct.unpack('>II', data[16:24])
            if not width or not height or b'IEND' not in data[-32:]:
                raise ValueError('invalid PNG dimensions or missing IEND')
            result.metadata.update(width=width, height=height)
            result.not_checked.append('full image decoding')
        elif suffix == '.pdf':
            if not data.startswith(b'%PDF-') or b'%%EOF' not in data[-2048:]:
                raise ValueError('invalid PDF header or missing EOF marker')
            result.not_checked.append('PDF object graph, pages and fonts; use the PDF skill')
        elif suffix in {'.html', '.htm', '.md', '.txt', '.sql', '.cs'}:
            snapshot.text()
            result.not_checked.append('format semantics; only nonempty UTF-8 text checked')
        else:
            result.incomplete = True
            result.issues.append(Issue('unsupported_artifact_format', 'warning', 'Use the format-specific tool for this file type.'))
    except (ValueError, UnicodeError, ET.ParseError, zipfile.BadZipFile, RuntimeError) as error:
        result.issues.append(Issue('artifact_structure_invalid', 'error', str(error)))
    return result
