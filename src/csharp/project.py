"""Inspect explicit project membership/references without evaluating MSBuild."""
from pathlib import Path
import xml.etree.ElementTree as ET

from src.common.results import CheckResult, Issue


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit('}', 1)[-1]


def _literal(value: str) -> bool:
    return not any(token in value for token in ('$', '@', '%', '*', '?', ';'))


def _path(root: Path, value: str) -> Path:
    return (root / value.replace('\\', '/')).resolve()


def check_project(project_file: str | Path, files: list[str | Path],
                  required_references: list[str] | None = None) -> CheckResult:
    """Check only supplied files and required direct assembly references.

    Conditional/generated/SDK inputs need MSBuild evidence; they are never
    reported as verified or as a definite missing item from XML alone.
    """
    project = Path(project_file).resolve()
    try:
        tree = ET.parse(project)
    except ET.ParseError as error:
        raise ValueError(f'Invalid project XML: {project}: {error}') from error
    root = tree.getroot()
    if _tag(root) != 'Project':
        raise ValueError(f'Expected an MSBuild Project element: {project}')
    entries: list[tuple[ET.Element, bool]] = []

    def visit(element: ET.Element, conditional: bool = False) -> None:
        conditional = conditional or bool(element.get('Condition')) or _tag(element) in {'Choose', 'When', 'Otherwise'}
        entries.append((element, conditional))
        for child in element:
            visit(child, conditional)

    visit(root)
    sdk = bool(root.get('Sdk')) or any(_tag(item) == 'Sdk' for item, _ in entries)
    imported = any(_tag(item) == 'Import' for item, _ in entries)
    packaged = any(_tag(item) in {'PackageReference', 'ProjectReference'} for item, _ in entries)
    result = CheckResult(not_checked=[
        'MSBuild evaluation, assembly loading, compilation and live Visual Studio Designer behavior'])
    evidence: list[dict[str, str]] = []

    def unknown(message: str) -> None:
        result.incomplete = True
        result.not_checked.append(message)

    for selected in dict.fromkeys(Path(value).resolve() for value in files):
        kind = {'.cs': 'Compile', '.resx': 'EmbeddedResource'}.get(selected.suffix.lower())
        if kind is None:
            raise ValueError(f'Project item must be a selected .cs or .resx file: {selected}')
        if not selected.is_file():
            result.issues.append(Issue('project_item_file_missing', 'error',
                'The selected project file does not exist.', path=str(selected)))
            continue
        matching = False
        uncertain = sdk or imported
        for item, conditional in entries:
            if _tag(item) != kind or not item.get('Include'):
                continue
            include = item.get('Include', '')
            if not _literal(include):
                uncertain = True
            elif _path(project.parent, include) == selected:
                if conditional or item.get('Exclude'):
                    uncertain = True
                else:
                    matching = True
        # A local transform prevents certifying the selected explicit entry.
        transforms = any(_tag(item) == kind and (item.get('Remove') or item.get('Update'))
                         for item, _ in entries)
        if matching and not transforms:
            evidence.append({'path': str(selected), 'item_type': kind, 'status': 'verified'})
        elif uncertain or transforms:
            evidence.append({'path': str(selected), 'item_type': kind, 'status': 'unverified'})
            unknown(f'Effective {kind} membership requires MSBuild evaluation: {selected}')
        else:
            evidence.append({'path': str(selected), 'item_type': kind, 'status': 'missing'})
            result.issues.append(Issue('project_item_not_registered', 'error',
                f'The selected file has no explicit {kind} registration in the supplied project.',
                path=str(selected), details={'project_file': str(project)}))

    references: list[dict[str, str]] = []
    for requested in dict.fromkeys(required_references or []):
        name = requested.split(',', 1)[0].strip()
        if not name or not _literal(name):
            raise ValueError('--required-reference requires a literal assembly name')
        matching_refs = [(item, conditional) for item, conditional in entries
                         if _tag(item) == 'Reference' and
                         item.get('Include', '').split(',', 1)[0].strip().casefold() == name.casefold()]
        verified = False
        uncertain = sdk or imported or packaged or any(
            _tag(item) == 'Reference' and
            (not _literal(item.get('Include', '')) or item.get('Remove') or item.get('Update'))
            for item, _ in entries)
        for item, conditional in matching_refs:
            hints = [child for child in item if _tag(child) == 'HintPath']
            if conditional or any(child.get('Condition') for child in hints):
                uncertain = True
                continue
            if not hints:
                verified = True  # Direct declaration only, not resolver/assembly proof.
            elif len(hints) != 1 or not _literal((hints[0].text or '').strip()):
                uncertain = True
            else:
                hint = _path(project.parent, (hints[0].text or '').strip())
                if hint.is_file():
                    verified = True
                else:
                    result.issues.append(Issue('project_reference_hint_missing', 'warning',
                        'The required reference declares a literal HintPath that does not exist.',
                        path=str(hint), details={'assembly': name, 'project_file': str(project)}))
                    uncertain = True  # Another resolver/GAC path may still satisfy it.
        transformed = any(_tag(item) == 'Reference' and (item.get('Remove') or item.get('Update'))
                          for item, _ in entries)
        if verified and not transformed:
            state = 'verified'
        elif uncertain:
            state = 'unverified'
            unknown(f'Effective assembly reference requires MSBuild/resolver evidence: {name}')
        elif matching_refs:
            state = 'missing'
        else:
            state = 'missing'
            result.issues.append(Issue('project_required_reference_missing', 'error',
                'The explicitly required direct assembly reference is absent from the supplied project.',
                path=str(project), details={'assembly': name}))
        references.append({'assembly': name, 'status': state})

    result.checked.append('Explicit registrations for selected files and supplied direct assembly references in the actual project XML')
    result.metadata['project_integration'] = {
        'status': 'failed' if result.status == 'failed' else 'unverified' if result.incomplete else 'verified_static',
        'project_file': str(project), 'files': evidence, 'required_references': references,
    }
    return result
