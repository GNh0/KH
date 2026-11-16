"""Task-local source baselines and bounded, literal C# dependency evidence."""
import hashlib
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from src.common.files import read_file
from src.csharp.control_defaults import read_control_defaults
from src.csharp.designer_model import parse_designer_source


SOURCE_LIMIT = 1024 * 1024
BASELINE_LIMIT = 64


def digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def source_text(path: Path) -> str:
    return read_file(path, max_bytes=SOURCE_LIMIT).text()


def safe_directory(path: Path) -> None:
    for item in (path, *path.parents):
        if item.is_symlink() or (item.exists() and getattr(item.lstat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('Check snapshots cannot traverse a reparse point or symbolic link.')


def companion(path: Path) -> Path | None:
    if path.suffix.casefold() != '.cs':
        return None
    name = path.name[:-12] + '.cs' if path.name.casefold().endswith('.designer.cs') else path.stem + '.Designer.cs'
    candidate = path.with_name(name)
    if not candidate.exists() and candidate.parent.is_dir():
        matches = [item for item in candidate.parent.iterdir() if item.name.casefold() == name.casefold() and item.is_file()]
        if len(matches) > 1:
            raise ValueError('Ambiguous case variants for the companion source; select the actual pair.')
        if matches:
            candidate = matches[0]
    return candidate.resolve()


def source_identity(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def nearby_projects(path: Path) -> list[Path]:
    for parent in list(path.parents)[:8]:
        found = sorted(parent.glob('*.csproj'))
        if found:
            return found
    return []


class SourceBaselines:
    def __init__(self, directory: Path, state: dict):
        self.directory = directory
        self.records = state.setdefault('check_baselines', {})

    def record_key(self, path: Path) -> str:
        identity = source_identity(path)
        matches = [key for key in self.records if source_identity(Path(key)) == identity]
        if len(matches) > 1 and any(self.records[key] != self.records[matches[0]] for key in matches[1:]):
            raise ValueError('Conflicting original snapshots for the same source file; inspect before comparing.')
        return matches[0] if matches else identity

    def capture(self, path: Path) -> None:
        key = self.record_key(path)
        if key in self.records:
            return
        if len(self.records) >= BASELINE_LIMIT:
            raise ValueError('More than 64 source baselines; remaining comparisons are unverified.')
        if not path.exists():
            self.records[key] = {'exists': False}
            return
        text = source_text(path)
        raw = text.encode('utf-8')
        if len(raw) > SOURCE_LIMIT:
            raise ValueError('UTF-8 source baseline exceeds the 1 MiB bound.')
        fingerprint = digest(text)
        safe_directory(self.directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = self.directory / (fingerprint + '.source')
        safe_directory(target)
        if target.exists():
            if digest(source_text(target)) != fingerprint:
                raise ValueError('Existing check snapshot does not match its content hash.')
        else:
            with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as file:
                file.write(raw)
        self.records[key] = {'exists': True, 'content_hash': fingerprint}

    def original(self, path: Path) -> str | None:
        item = self.records.get(self.record_key(path))
        if item is None:
            return None
        if not item.get('exists'):
            return ''
        fingerprint = item.get('content_hash', '')
        if not isinstance(fingerprint, str) or not re.fullmatch('[0-9a-f]{64}', fingerprint):
            raise ValueError('Invalid source baseline identity.')
        safe_directory(self.directory)
        target = self.directory / (fingerprint + '.source')
        safe_directory(target)
        text = source_text(target)
        if digest(text) != fingerprint:
            raise ValueError('Check snapshot changed; original comparison is unverified.')
        return text

    def cleanup(self) -> None:
        safe_directory(self.directory)
        targets = set()
        for item in self.records.values():
            fingerprint = item.get('content_hash', '')
            if not isinstance(fingerprint, str) or not re.fullmatch('[0-9a-f]{64}', fingerprint):
                continue
            target = self.directory / (fingerprint + '.source')
            if target.exists():
                safe_directory(target)
                if digest(source_text(target)) != fingerprint:
                    raise ValueError('Owned check snapshot changed; cleanup needs inspection.')
                targets.add(target)
        if self.directory.exists():
            if set(self.directory.iterdir()) - targets:
                raise ValueError('Unexpected files in the check snapshot directory; nothing else was removed.')
            for target in targets:
                target.unlink()
            self.directory.rmdir()
        self.records.clear()


def literal_project_sources(path: Path, texts: list[str]) -> tuple[list[str], dict]:
    """Resolve used control definitions from explicit unconditional local project items.

    This is source evidence, not evaluated MSBuild membership or runtime compatibility.
    Dynamic imports, ambiguous projects/types and unmatched file names remain unverified.
    """
    types = {control.type_name.removeprefix('global::')
             for text in texts for control in parse_designer_source(text).controls.values()
             if control.type_name}
    wanted = {name.rsplit('.', 1)[-1] for name in types}
    metadata: dict = {'project': None, 'sources': [], 'dependencies': [], 'unverified': []}
    projects = nearby_projects(path)
    if len(projects) > 1:
        metadata['unverified'].append('Multiple sibling C# projects; no project was selected automatically.')
        return [], metadata
    if not projects:
        metadata['unverified'].append('No unambiguous nearby C# project; control sources were not inferred.')
        return [], metadata
    metadata['project'] = str(projects[0])
    queue, visited, candidates = projects[:], set(), {}
    item_count = 0
    while queue:
        project = queue.pop(0).resolve()
        if project in visited:
            continue
        if len(visited) >= 16:
            metadata['unverified'].append('Project-reference scan reached its 16-project bound.')
            break
        visited.add(project)
        body = source_text(project)
        metadata['dependencies'].append({'path': str(project), 'sha256': digest(body)})
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            metadata['unverified'].append('Project XML is invalid; its control sources were not selected.')
            continue
        transformed_compile = any(
            element.tag.rsplit('}', 1)[-1] == 'Compile' and
            any(element.get(key) for key in ('Remove', 'Update', 'Exclude')) for element in root.iter())

        def visit(element, conditional=False):
            nonlocal item_count
            tag = element.tag.rsplit('}', 1)[-1]
            conditional = conditional or bool(element.get('Condition')) or tag in {'Choose', 'When', 'Otherwise'}
            if tag in {'Import', 'Sdk'} or element.get('Sdk') or (tag == 'Compile' and any(element.get(key) for key in ('Remove', 'Update', 'Exclude'))):
                metadata['unverified'].append('MSBuild imports/SDK/transforms and effective runtime membership were not evaluated.')
            value = element.get('Include', '')
            if tag in {'Compile', 'ProjectReference'} and value:
                item_count += 1
                if item_count > 4096:
                    raise ValueError('Project-source scan exceeded 4096 declared items.')
                if conditional or any(mark in value for mark in ('$','@','%','*','?',';')):
                    metadata['unverified'].append('Conditional/dynamic project items were not evaluated.')
                elif tag == 'Compile' and transformed_compile:
                    metadata['unverified'].append('Compile transforms prevent automatic control-source selection in this project.')
                else:
                    selected = (project.parent / value.replace('\\', '/')).resolve()
                    relevant = tag == 'ProjectReference' or selected.stem in wanted
                    if relevant and not selected.is_file():
                        metadata['dependencies'].append({'path': str(selected), 'sha256': 'deleted'})
                        metadata['unverified'].append('A declared project/control source is missing; its defaults remain unverified.')
                    if selected.is_file():
                        if tag == 'ProjectReference':
                            queue.append(selected)
                        elif selected.stem in wanted:
                            candidates[selected] = None
            for child in element:
                visit(child, conditional)
        visit(root)
    matched = {}
    for selected in sorted(candidates):
        body = source_text(selected)
        metadata['dependencies'].append({'path': str(selected), 'sha256': digest(body)})
        declarations = read_control_defaults([body])
        names = {item.type_name for item in declarations}
        for name in types:
            if name in names or ('.' not in name and any(n.rsplit('.', 1)[-1] == name for n in names)):
                matched.setdefault(name, []).append((selected, body))
    sources = {}
    for matches in matched.values():
        if len(matches) == 1:
            selected, body = matches[0]
            sources[selected] = body
        else:
            metadata['unverified'].append('Ambiguous control type; no constructor default was inferred.')
    for selected, body in sources.items():
        metadata['sources'].append({'path': str(selected), 'sha256': digest(body)})
    metadata['unverified'] = sorted(set(metadata['unverified']))
    return list(sources.values()), metadata
