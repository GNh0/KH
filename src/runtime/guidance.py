"""Read exact Markdown guidance units without loading unrelated sections."""
from pathlib import Path
import re


def document(root: Path, relative: str) -> tuple[Path, str, int, int]:
    filename, _, anchor = relative.partition('#')
    path = root / 'skills' / filename
    text = path.read_text(encoding='utf-8-sig')
    lines = text.splitlines(keepends=True)
    if not anchor:
        return path, text, 1, len(lines)
    headings = []
    fence = ''
    for index, line in enumerate(lines):
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            if not fence:
                fence = marker[1]
            elif marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not line[marker.end():].strip():
                fence = ''
        if not fence:
            match = re.match(r'^#{1,6}\s+(.+?)\s*#*\s*$', line)
            if match:
                slug = re.sub(r'[^\w\s-]', '', match[1]).strip().casefold()
                headings.append((index, re.sub(r'\s+', '-', slug)))
    starts = [index for index, slug in headings if slug == anchor]
    if len(starts) != 1:
        raise ValueError('Required guidance section is absent or ambiguous: ' + relative)
    start = starts[0]
    end = next((index for index, _ in headings if index > start), len(lines))
    return path, ''.join(lines[start:end]), start + 1, end


def location(root: Path, relative: str) -> str:
    path, _body, start, end = document(root, relative)
    return str(path) + (' (lines ' + str(start) + '-' + str(end) + '; #' + relative.partition('#')[2] + ')'
                        if '#' in relative else '')
