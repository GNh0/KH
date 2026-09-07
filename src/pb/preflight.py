"""Exact project/source availability; builds are not a default prerequisite."""
from pathlib import Path
import fnmatch
import xml.etree.ElementTree as ET
from src.common.files import read_file
from src.common.results import CheckResult, Issue


def inspect_project(project: str | Path, sources=()) -> CheckResult:
    snapshot = read_file(project)
    root = ET.fromstring(snapshot.text())
    result = CheckResult(checked=['actual project declarations and source availability'],
                         not_checked=['MSBuild evaluation', 'compilation', 'Designer runtime'])
    includes = [node.get('Include') for node in root.iter() if node.tag.split('}')[-1] in {'Compile', 'EmbeddedResource'} and node.get('Include')]
    references = [node.get('Include') for node in root.iter() if node.tag.split('}')[-1] == 'Reference' and node.get('Include')]
    sdk = bool(root.get('Sdk'))
    default_compile = next((n.text for n in root.iter() if n.tag.split('}')[-1] == 'EnableDefaultCompileItems'), None)
    removed = [part.replace('\\', '/').casefold() for n in root.iter()
               if n.tag.split('}')[-1] == 'Compile' for part in (n.get('Remove', '') + ';' + n.get('Exclude', '')).split(';') if part]
    uncertain_items = any(n.get('Condition') or '$(' in str(n.attrib) or '*'+ '*' in n.get('Include', '')
                          for n in root.iter() if n.tag.split('}')[-1] in {'Compile', 'ItemGroup', 'EnableDefaultCompileItems'})
    def matches(value, pattern):
        return fnmatch.fnmatchcase(value, pattern) or (pattern.startswith('**/') and fnmatch.fnmatchcase(value, pattern[3:]))
    for source in sources:
        path = Path(source)
        if not path.is_absolute():
            raise ValueError('source paths must be absolute')
        if not path.is_file():
            result.issues.append(Issue('project_source_missing', 'error', 'Requested source file is absent.', path=str(path)))
            continue
        try:
            relative = path.resolve().relative_to(snapshot.path.parent).as_posix().casefold()
        except ValueError:
            relative = None
        listed = relative is not None and relative in {value.replace('\\', '/').casefold() for value in includes}
        implicit = sdk and str(default_compile).lower() != 'false' and relative is not None and path.suffix.lower() == '.cs'
        excluded = relative is not None and (any(matches(relative, pattern) for pattern in removed) or
                    (implicit and any(part in {'bin', 'obj'} for part in relative.split('/')[:-1])))
        if excluded:
            listed = implicit = False
        if uncertain_items:
            result.incomplete = True
            result.issues.append(Issue('conditional_project_items', 'warning', 'Conditional or expanded project items require evaluation or a targeted source check.', path=str(path)))
        if not listed and not implicit:
            result.issues.append(Issue('source_registration_unconfirmed', 'warning', 'No explicit or ordinary SDK inclusion was found; inspect imported projects and conditional items.', path=str(path)))
            result.incomplete = True
    result.metadata.update(project=str(snapshot.path), source_sha256=snapshot.sha256, sdk_style=sdk,
                           includes=includes, references=references,
                           devexpress_references=[x for x in references if 'DevExpress' in x])
    return result
